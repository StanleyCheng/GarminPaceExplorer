"""Authentication and encrypted storage never accept a browser's ownership scope."""

import base64
import copy
import io
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

import supabase_store
from supabase_store import (
    DashboardError,
    Supabase,
    SupabaseError,
    UserStore,
    decrypt_private,
    encrypt_private,
    login_email,
    normalize_username,
    require_configuration,
    validate_garmin_credentials,
)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable-test-only")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-test-only")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"t" * 32).decode())


class RecordingSupabase:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.requests = []
        self.calls = []

    def request(self, path, **kwargs):
        self.requests.append((path, copy.deepcopy(kwargs)))
        table = urlsplit(path).path.rsplit("/", 1)[-1]
        query = parse_qs(urlsplit(path).query)
        owner = query["user_id"][0].removeprefix("eq.")
        rows = copy.deepcopy(self.rows.get((table, owner), []))
        offset = int(query.get("offset", [0])[0])
        limit = int(query.get("limit", [len(rows)])[0])
        return rows[offset:offset + limit]

    def rpc(self, name, params):
        self.calls.append((name, copy.deepcopy(params)))
        return None


@pytest.mark.parametrize("value,expected", [(" Runner_01 ", "runner_01"), ("ABC", "abc"),
                                             ("a" * 32, "a" * 32), ("run.2026-hk", "run.2026-hk")])
def test_username_normalizes_to_stable_login_alias(value, expected):
    assert normalize_username(value) == expected
    assert login_email(expected) == f"{expected}@accounts.pace-explorer.invalid"


@pytest.mark.parametrize("value", [None, 42, "", "ab", "a" * 33, "runner@example.com", "_runner", "../runner", "中文名", "runner name"])
def test_invalid_username_is_rejected(value):
    with pytest.raises(DashboardError) as error:
        normalize_username(value)
    assert error.value.status == 400


def test_credentials_reject_invalid_values_and_preserve_password_characters():
    assert validate_garmin_credentials(" runner@example.com ", " secret ") == {
        "username": "runner@example.com", "password": " secret "}
    for username, password in [("not-email", "password"), (None, "password"),
                               ("runner@example.com", ""), ("runner@example.com", None),
                               ("runner@example.com", "x" * 1025)]:
        with pytest.raises(DashboardError) as error:
            validate_garmin_credentials(username, password)
        assert error.value.status == 400


def test_configuration_errors_reveal_no_environment_values(monkeypatch):
    monkeypatch.delenv("SUPABASE_SECRET_KEY")
    with pytest.raises(DashboardError) as error:
        require_configuration()
    assert error.value.status == 503
    assert "publishable-test-only" not in str(error.value)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-test-only")
    monkeypatch.setenv("SUPABASE_URL", "http://test.supabase.co")
    with pytest.raises(DashboardError, match="HTTPS"):
        require_configuration()


@pytest.mark.parametrize("key", ["", "invalid", base64.urlsafe_b64encode(b"short").decode()])
def test_configuration_rejects_invalid_encryption_key(monkeypatch, key):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", key)
    with pytest.raises(DashboardError):
        require_configuration()


def test_encryption_randomizes_ciphertext_and_binds_it_to_owner():
    owner = str(uuid4())
    other = str(uuid4())
    private = {"username": "runner@example.com", "password": "private-password", "tokens": ["private-token"]}
    first = encrypt_private(private, owner)
    second = encrypt_private(private, owner)
    assert first != second
    assert "private-password" not in first and "private-token" not in first
    assert decrypt_private(first, owner) == private
    for ciphertext, scope in [(first, other), (first[:-4] + "abcd", owner), ("invalid", owner)]:
        with pytest.raises(DashboardError) as error:
            decrypt_private(ciphertext, scope)
        assert "private-password" not in str(error.value)


def test_each_user_reads_only_own_snapshot_credentials_and_encrypted_session():
    alice, bob = str(uuid4()), str(uuid4())
    rows = {}
    for owner, name in [(alice, "alice"), (bob, "bob")]:
        rows[("pace_snapshots", owner)] = [{"payload": {"activities": [{"owner": name}]}}]
        rows[("pace_garmin_connections", owner)] = [{
            "credentials_ciphertext": encrypt_private({"username": f"{name}@example.com", "password": f"{name}-private"}, owner),
            "session_ciphertext": encrypt_private(f"{name}-tokens", owner), "revision": str(uuid4()),
        }]
    backend = RecordingSupabase(rows)
    for owner, name in [(alice, "alice"), (bob, "bob")]:
        store = UserStore(backend, owner)
        assert store.snapshot()["activities"] == [{"owner": name}]
        connection = store.connection()
        assert connection["credentials"]["username"] == f"{name}@example.com"
        assert connection["session"] == f"{name}-tokens"
        assert "credentials_ciphertext" not in connection and "session_ciphertext" not in connection
        assert all(parse_qs(urlsplit(path).query)["user_id"] == ["eq." + owner]
                   for path, _ in backend.requests[-2:])


def test_rpc_and_queries_cannot_override_verified_owner():
    owner, spoofed = str(uuid4()), str(uuid4())
    backend = RecordingSupabase()
    store = UserStore(backend, owner)
    store.call("pace_update_garmin", p_user=spoofed, p_credentials="ciphertext")
    assert backend.calls[-1][1]["p_user"] == owner
    store._rows("pace_snapshots", user_id="eq." + spoofed, select="payload")
    assert parse_qs(urlsplit(backend.requests[-1][0]).query)["user_id"] == ["eq." + owner]


def test_credentials_updates_encrypt_before_rpc_and_bind_owner():
    owner = str(uuid4())
    backend = RecordingSupabase()
    credentials = {"username": "runner@example.com", "password": "private-password"}
    UserStore(backend, owner).update_credentials(credentials)
    name, params = backend.calls[0]
    assert name == "pace_update_garmin" and params["p_user"] == owner
    assert "private-password" not in params["p_credentials"]
    assert decrypt_private(params["p_credentials"], owner) == credentials


def test_batch_reads_paginate_past_postgrest_page_size_and_scope_job_owner():
    owner, job_id = str(uuid4()), str(uuid4())
    rows = [{"records": [{"batch": index}]} for index in range(501)]
    backend = RecordingSupabase({("pace_import_batches", owner): rows})
    assert list(UserStore(backend, owner).import_batches(job_id)) == [{"batch": index} for index in range(501)]
    queries = [parse_qs(urlsplit(path).query) for path, _ in backend.requests]
    assert [query["offset"][0] for query in queries] == ["0", "500", "501"]
    assert all(query["job_id"] == ["eq." + job_id] and query["user_id"] == ["eq." + owner]
               for query in queries)


def test_missing_connection_and_snapshot_have_safe_initial_behavior():
    store = UserStore(RecordingSupabase(), str(uuid4()))
    assert store.snapshot() is None
    with pytest.raises(DashboardError) as error:
        store.connection()
    assert error.value.status == 422


def test_request_uses_server_key_for_storage_and_public_key_plus_user_token_for_auth(monkeypatch):
    captured = []

    def open_request(request, timeout):
        captured.append((request, timeout))
        return io.BytesIO(b'{"ok":true}')

    monkeypatch.setattr(supabase_store, "urlopen", open_request)
    backend = Supabase()
    assert backend.request("/rest/v1/pace_snapshots") == {"ok": True}
    backend.request("/auth/v1/user", privileged=False, token="user-access-token")
    storage_request, storage_timeout = captured[0]
    auth_request, _ = captured[1]
    assert storage_request.get_header("Apikey") == "secret-test-only"
    assert auth_request.get_header("Apikey") == "publishable-test-only"
    assert auth_request.get_header("Authorization") == "Bearer user-access-token"
    assert storage_timeout == 25


def test_request_redacts_upstream_body_and_network_failure(monkeypatch):
    def http_failure(*args, **kwargs):
        raise HTTPError("https://test.supabase.co", 400, "bad", {},
                        io.BytesIO(b'{"error_code":"bad_request","message":"private-password private-token"}'))

    monkeypatch.setattr(supabase_store, "urlopen", http_failure)
    with pytest.raises(SupabaseError) as error:
        Supabase().request("/auth/v1/token")
    assert error.value.code == "bad_request" and error.value.status == 400
    assert "private-password" not in str(error.value)

    def unreachable(*args, **kwargs):
        raise URLError("private-password private-token")

    monkeypatch.setattr(supabase_store, "urlopen", unreachable)
    with pytest.raises(DashboardError) as error:
        Supabase().request("/auth/v1/token")
    assert error.value.status == 502 and "private-password" not in str(error.value)


def test_sign_in_only_uses_supabase_auth_and_returns_safe_failure(monkeypatch):
    backend = Supabase()
    captured = []
    session = {"access_token": "access", "refresh_token": "refresh"}

    def request(path, **kwargs):
        captured.append((path, kwargs))
        return session

    monkeypatch.setattr(backend, "request", request)
    assert backend.sign_in("runner", "app-private-password") == session
    assert captured == [("/auth/v1/token?grant_type=password", {
        "method": "POST", "body": {"email": login_email("runner"), "password": "app-private-password"},
        "privileged": False})]
    monkeypatch.setattr(backend, "request", lambda *a, **k: (_ for _ in ()).throw(SupabaseError(400, "invalid_credentials")))
    with pytest.raises(DashboardError) as error:
        backend.sign_in("runner", "app-private-password")
    assert error.value.status == 401 and "app-private-password" not in str(error.value)


def test_signup_creates_auth_user_then_encrypted_profile_and_signs_in(monkeypatch):
    owner = str(uuid4())
    backend = Supabase()
    calls = []
    credentials = {"username": "garmin@example.com", "password": "garmin-private"}
    session = {"access_token": "access", "refresh_token": "refresh"}

    def request(path, **kwargs):
        calls.append((path, kwargs))
        if path == "/auth/v1/admin/users":
            return {"id": owner}
        if path == "/auth/v1/token?grant_type=password":
            return session
        raise AssertionError(path)

    monkeypatch.setattr(backend, "request", request)
    monkeypatch.setattr(backend, "rpc", lambda name, params: calls.append((name, params)))
    assert backend.create_account("runner", "app-private-password", credentials) == session
    assert calls[0][1]["body"]["app_metadata"] == {"pace_username": "runner"}
    assert calls[0][1]["body"]["email_confirm"] is True
    assert calls[1][0] == "pace_create_profile"
    params = calls[1][1]
    assert params["p_user"] == owner and params["p_username"] == "runner"
    assert "garmin-private" not in params["p_credentials"]
    assert decrypt_private(params["p_credentials"], owner) == credentials


@pytest.mark.parametrize("failure", [SupabaseError(409, "23505"), DashboardError("Database unavailable.", 502), RuntimeError("private-token")])
def test_failed_profile_creation_rolls_back_new_auth_user(monkeypatch, failure):
    owner = str(uuid4())
    backend = Supabase()
    paths = []

    def request(path, **kwargs):
        paths.append((path, kwargs))
        return {"id": owner} if kwargs.get("method") == "POST" else None

    def rpc(*args):
        raise failure

    monkeypatch.setattr(backend, "request", request)
    monkeypatch.setattr(backend, "rpc", rpc)
    with pytest.raises((DashboardError, RuntimeError)):
        backend.create_account("runner", "app-private-password", {"username": "g@example.com", "password": "garmin-private"})
    assert paths[-1] == (f"/auth/v1/admin/users/{owner}", {"method": "DELETE"})


@pytest.mark.parametrize("password", [None, "short", "x" * 129])
def test_signup_rejects_bad_app_password_before_network(monkeypatch, password):
    backend = Supabase()
    monkeypatch.setattr(backend, "request", lambda *a, **k: pytest.fail("must not create user"))
    with pytest.raises(DashboardError) as error:
        backend.create_account("runner", password, {"username": "g@example.com", "password": "garmin-private"})
    assert error.value.status == 400


def test_identity_comes_from_auth_user_app_metadata_and_refreshes_expired_access(monkeypatch):
    owner = str(uuid4())
    backend = Supabase()
    captured = []
    renewed = {"access_token": "new-access", "refresh_token": "new-refresh"}

    def request(path, **kwargs):
        captured.append((path, kwargs))
        if kwargs.get("token") == "expired-access":
            raise SupabaseError(401, "bad_jwt")
        if path.startswith("/auth/v1/token"):
            return renewed
        return {"id": owner, "app_metadata": {"pace_username": "runner"},
                "user_metadata": {"pace_username": "attacker"}}

    monkeypatch.setattr(backend, "request", request)
    identity, session = backend.identity("expired-access", "saved-refresh")
    assert identity == {"id": owner, "username": "runner"} and session == renewed
    assert captured[1][1]["body"] == {"refresh_token": "saved-refresh"}
    assert captured[2][1]["token"] == "new-access"


def test_valid_access_identity_does_not_rotate_session(monkeypatch):
    owner = str(uuid4())
    backend = Supabase()
    monkeypatch.setattr(backend, "request", lambda *a, **k: {"id": owner, "app_metadata": {"pace_username": "runner"}})
    assert backend.identity("valid-access", "refresh") == ({"id": owner, "username": "runner"}, None)


def test_unknown_or_unregistered_identity_is_rejected(monkeypatch):
    backend = Supabase()
    with pytest.raises(DashboardError) as error:
        backend.identity(None, None)
    assert error.value.status == 401
    monkeypatch.setattr(backend, "request", lambda *a, **k: {"id": str(uuid4()), "user_metadata": {"pace_username": "spoofed"}})
    with pytest.raises(DashboardError) as error:
        backend.identity("access", None)
    assert error.value.status == 403


def test_auth_limits_store_only_keyed_fingerprint_and_return_429(monkeypatch):
    backend = Supabase()
    calls = []
    monkeypatch.setattr(backend, "rpc", lambda name, body: calls.append((name, body)) or False)
    with pytest.raises(DashboardError) as error:
        backend.limit_auth("203.0.113.42", "signup")
    assert error.value.status == 429
    assert calls[0][0] == "pace_auth_attempt"
    assert re.fullmatch(r"[0-9a-f]{64}", calls[0][1]["p_fingerprint"])
    assert "203.0.113.42" not in json.dumps(calls)


@pytest.mark.parametrize("code,status", [("PGRST202", 503), ("PGRST205", 503), ("42P01", 503), ("P0001", 409)])
def test_database_setup_and_sync_errors_have_safe_messages(monkeypatch, code, status):
    backend = Supabase()
    monkeypatch.setattr(backend, "request", lambda *a, **k: (_ for _ in ()).throw(SupabaseError(400, code)))
    with pytest.raises(DashboardError) as error:
        backend.rpc("pace_begin_sync", {})
    assert error.value.status == status


def test_schema_denies_browser_tables_and_rpc_and_joins_jobs_to_owner():
    """Inspect deployment DDL; real SQL execution is checked during provisioning."""
    schema = Path(__file__).resolve().parents[1].joinpath("supabase/schema.sql").read_text().lower()
    tables = ["pace_profiles", "pace_garmin_connections", "pace_sync_jobs", "pace_import_batches", "pace_snapshots", "pace_auth_attempts"]
    for table in tables:
        assert f"alter table public.{table} enable row level security" in schema
    assert "from anon, authenticated;" in schema
    assert "from public, anon, authenticated;" in schema
    assert "to service_role;" in schema
    assert "foreign key (job_id, user_id) references public.pace_sync_jobs(id, user_id)" in schema
    assert "where id = p_job and user_id = p_user for update" in schema
    assert "on public.pace_sync_jobs(user_id) where status in ('running','finalizing')" in schema
    assert "job.lease_owner is distinct from p_worker" in schema
    assert "job.lease_expires_at <= now()" in schema
    assert "revision = job.credentials_revision" in schema
    assert "jsonb_array_length(p_records) = 0 then 'finalizing'" in schema
    assert "record_count <> job.next_offset" in schema
    assert "insert into public.pace_snapshots" in schema
