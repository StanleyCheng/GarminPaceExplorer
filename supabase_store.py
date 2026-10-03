"""Server-only Supabase Auth, encrypted Garmin credentials, and scoped storage."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "CREDENTIALS_ENCRYPTION_KEY")
USERNAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.-]{2,31}\Z")


class DashboardError(Exception):
    """A safe message that can be returned to the browser."""

    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class SupabaseError(Exception):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__(f"Supabase request failed ({status}, {code})")


def require_configuration():
    missing = [key for key in REQUIRED_ENV if not os.environ.get(key)]
    if missing:
        raise DashboardError("Server setup is incomplete. Add the Supabase environment variables in Vercel and redeploy.")
    url = os.environ["SUPABASE_URL"]
    if not url.startswith("https://"):
        raise DashboardError("SUPABASE_URL must use HTTPS.")
    encryption_key()


def encryption_key():
    try:
        key = base64.urlsafe_b64decode(os.environ["CREDENTIALS_ENCRYPTION_KEY"] + "===")
        if len(key) != 32:
            raise ValueError
        return key
    except (KeyError, ValueError):
        raise DashboardError("CREDENTIALS_ENCRYPTION_KEY must be a base64-encoded 32-byte key.")


def encrypt_private(value, user_id):
    """Bind ciphertext to its owner so rows cannot be swapped between users."""
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(encryption_key()).encrypt(
        nonce, json.dumps(value).encode(), str(UUID(user_id)).encode()
    )
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_private(value, user_id):
    try:
        data = base64.urlsafe_b64decode(value)
        return json.loads(AESGCM(encryption_key()).decrypt(
            data[:12], data[12:], str(UUID(user_id)).encode()
        ))
    except Exception as exc:
        raise DashboardError("Your saved Garmin connection could not be opened. Contact the app owner; the encryption key may have changed.") from exc


def normalize_username(value):
    username = value.strip().lower() if isinstance(value, str) else ""
    if not USERNAME_PATTERN.fullmatch(username):
        raise DashboardError("Use 3–32 characters for your username: letters, numbers, dots, dashes, or underscores.", 400)
    return username


def login_email(username):
    # Supabase Auth manages passwords; this stable alias enables username-only login.
    return f"{username}@accounts.pace-explorer.invalid"


def validate_garmin_credentials(username, password):
    username = username.strip() if isinstance(username, str) else ""
    if not username or len(username) > 254 or "@" not in username:
        raise DashboardError("Enter the email address you use for Garmin Connect.", 400)
    if not isinstance(password, str) or not 1 <= len(password) <= 1024:
        raise DashboardError("Enter your Garmin Connect password.", 400)
    return {"username": username, "password": password}


class Supabase:
    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].rstrip("/")

    def request(self, path, *, method="GET", body=None, privileged=True, token=None):
        key = os.environ["SUPABASE_SECRET_KEY" if privileged else "SUPABASE_PUBLISHABLE_KEY"]
        headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        request = Request(self.url + path, headers=headers, method=method,
                          data=json.dumps(body).encode() if body is not None else None)
        try:
            with urlopen(request, timeout=25) as response:
                data = response.read()
            return json.loads(data) if data else None
        except HTTPError as exc:
            try:
                error = json.loads(exc.read())
                code = error.get("error_code") or error.get("code") or "upstream"
            except (ValueError, AttributeError):
                code = "upstream"
            raise SupabaseError(exc.code, code) from exc
        except (URLError, TimeoutError) as exc:
            raise DashboardError("The account service could not be reached. Please try again.", 502) from exc

    def rpc(self, name, body):
        try:
            return self.request(f"/rest/v1/rpc/{name}", method="POST", body=body)
        except SupabaseError as exc:
            if exc.code in ("PGRST202", "PGRST205", "42P01"):
                raise DashboardError("Database setup is incomplete. Run the Supabase schema from the setup guide.") from exc
            if exc.code == "P0001":
                raise DashboardError("This sync is busy or the Garmin connection changed. Try refreshing again.", 409) from exc
            raise

    def limit_auth(self, fingerprint, kind):
        digest = hmac.new(encryption_key(), fingerprint.encode(), hashlib.sha256).hexdigest()
        if not self.rpc("pace_auth_attempt", {"p_fingerprint": digest, "p_kind": kind}):
            raise DashboardError("Too many attempts. Please wait a few minutes and try again.", 429)

    def sign_in(self, username, password):
        try:
            return self.request("/auth/v1/token?grant_type=password", method="POST",
                                body={"email": login_email(username), "password": password}, privileged=False)
        except SupabaseError as exc:
            if exc.status == 429:
                raise DashboardError("Too many sign-in attempts. Please wait and try again.", 429) from exc
            raise DashboardError("The username or password is incorrect.", 401) from exc

    def create_account(self, username, password, credentials):
        if not isinstance(password, str) or not 10 <= len(password) <= 128:
            raise DashboardError("Choose an app password with 10–128 characters.", 400)
        user_id = None
        try:
            result = self.request("/auth/v1/admin/users", method="POST", body={
                "email": login_email(username), "password": password, "email_confirm": True,
                "app_metadata": {"pace_username": username},
            })
            user_id = (result.get("user") or result)["id"]
            encrypted = encrypt_private(credentials, user_id)
            self.rpc("pace_create_profile", {"p_user": user_id, "p_username": username,
                                             "p_credentials": encrypted})
        except SupabaseError as exc:
            if user_id:
                self._remove_incomplete_account(user_id)
            if exc.code in ("email_exists", "user_already_exists", "23505"):
                raise DashboardError("That username is already taken. Choose another one.", 409) from exc
            if exc.code == "weak_password":
                raise DashboardError("Choose a stronger app password with a mix of letters, numbers, and symbols.", 400) from exc
            raise
        except Exception:
            if user_id:
                self._remove_incomplete_account(user_id)
            raise
        return self.sign_in(username, password)

    def _remove_incomplete_account(self, user_id):
        try:
            self.request(f"/auth/v1/admin/users/{user_id}", method="DELETE")
        except Exception:
            print("Incomplete account rollback could not be completed.")

    def identity(self, access_token, refresh_token):
        session = None
        if access_token:
            try:
                user = self.request("/auth/v1/user", privileged=False, token=access_token)
                return self._identity(user), session
            except SupabaseError as exc:
                if exc.status not in (401, 403):
                    raise
        if refresh_token:
            try:
                session = self.request("/auth/v1/token?grant_type=refresh_token", method="POST",
                                       body={"refresh_token": refresh_token}, privileged=False)
                user = self.request("/auth/v1/user", privileged=False, token=session["access_token"])
                return self._identity(user), session
            except SupabaseError as exc:
                raise DashboardError("Your session has expired. Sign in again.", 401) from exc
        raise DashboardError("Sign in to see your activities.", 401)

    @staticmethod
    def _identity(user):
        user_id = str(UUID(user["id"]))
        username = (user.get("app_metadata") or {}).get("pace_username")
        if not username:
            raise DashboardError("This account is not registered for Garmin Pace Lens.", 403)
        return {"id": user_id, "username": username}


class UserStore:
    """All data calls bind the server-verified identity, never a browser user ID."""

    def __init__(self, supabase, user_id):
        self.supabase = supabase
        self.user_id = str(UUID(user_id))

    def _rows(self, table, **query):
        query["user_id"] = "eq." + self.user_id
        return self.supabase.request("/rest/v1/" + table + "?" + urlencode(query))

    def connection(self):
        rows = self._rows("pace_garmin_connections", select="credentials_ciphertext,session_ciphertext,revision")
        if not rows:
            raise DashboardError("Add your Garmin connection in Account settings.", 422)
        row = rows[0]
        row["credentials"] = decrypt_private(row.pop("credentials_ciphertext"), self.user_id)
        row["session"] = decrypt_private(row.pop("session_ciphertext"), self.user_id) if row.get("session_ciphertext") else None
        row.pop("session_ciphertext", None)
        return row

    def snapshot(self):
        rows = self._rows("pace_snapshots", select="payload")
        return rows[0]["payload"] if rows else None

    def call(self, name, **params):
        return self.supabase.rpc(name, {**params, "p_user": self.user_id})

    def update_credentials(self, credentials):
        return self.call("pace_update_garmin", p_credentials=encrypt_private(credentials, self.user_id))

    def import_batches(self, job_id):
        offset = 0
        while True:
            rows = self._rows("pace_import_batches", select="records", job_id="eq." + str(UUID(job_id)),
                              order="start_offset.asc", offset=offset, limit=500)
            if not rows:
                return
            for row in rows:
                yield from row["records"]
            offset += len(rows)
