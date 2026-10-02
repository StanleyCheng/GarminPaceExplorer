"""Vercel HTTP API: Supabase sessions, separate accounts, and Garmin syncs."""

import gzip
import json
import os
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from dashboard_api import import_garmin_session, read_dashboard, refresh_step, start_refresh
from supabase_store import (DashboardError, Supabase, SupabaseError, UserStore,
                            normalize_username, require_configuration,
                            validate_garmin_credentials)


class handler(BaseHTTPRequestHandler):
    def _reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        compressed = "gzip" in self.headers.get("Accept-Encoding", "") and len(body) > 1024
        if compressed:
            body = gzip.compress(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Vary", "Cookie, Accept-Encoding")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        if compressed:
            self.send_header("Content-Encoding", "gzip")
        for cookie in self.response_cookies:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _cookie(self, name, value, seconds):
        secure = "; Secure" if os.environ.get("VERCEL") else ""
        self.response_cookies.append(f"{name}={value}; Path=/api; HttpOnly; SameSite=Strict; Max-Age={seconds}{secure}")

    def _set_session(self, session):
        self._cookie("pace_access", session["access_token"], session.get("expires_in", 3600))
        self._cookie("pace_refresh", session["refresh_token"], 30 * 24 * 60 * 60)

    def _identity(self):
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        access = cookies.get("pace_access")
        refresh = cookies.get("pace_refresh")
        identity, session = self.supabase.identity(access.value if access else None, refresh.value if refresh else None)
        if session:
            self._set_session(session)
        return identity

    def _run(self, callback):
        self.response_cookies = []
        try:
            require_configuration()
            self.supabase = Supabase()
            callback()
        except DashboardError as exc:
            if exc.status == 401:
                self._cookie("pace_access", "", 0)
                self._cookie("pace_refresh", "", 0)
            self._reply(exc.status, {"error": str(exc)})
        except SupabaseError as exc:
            print(f"Dashboard account service failure: {exc.status} {exc.code}")
            self._reply(502, {"error": "The account service could not complete this request. Please try again."})
        except Exception as exc:
            # Never log raw exceptions or bodies: they can contain credentials/tokens.
            print(f"Dashboard request failed: {type(exc).__name__}")
            self._reply(502, {"error": "Could not complete this request. Please try again."})

    def do_GET(self):
        def get():
            identity = self._identity()
            self._reply(200, read_dashboard(UserStore(self.supabase, identity["id"]), identity))
        self._run(get)

    def do_POST(self):
        def post():
            origin = self.headers.get("Origin")
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
            if origin and urlsplit(origin).netloc != host:
                raise DashboardError("This request must come from the dashboard.", 403)
            if self.headers.get_content_type() != "application/json":
                raise DashboardError("Send a JSON request.", 415)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 32768:
                    raise ValueError
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                raise DashboardError("Invalid request.", 400)
            action = parse_qs(urlsplit(self.path).query).get("action", [""])[0]
            if action in ("login", "signup"):
                username = normalize_username(body.get("username"))
                password = body.get("password")
                if not isinstance(password, str) or len(password) > 128:
                    raise DashboardError("Enter your app password.", 400)
                fingerprint = self.headers.get("X-Forwarded-For", "local").split(",")[0].strip()
                self.supabase.limit_auth(fingerprint, action)
                if action == "signup":
                    credentials = validate_garmin_credentials(body.get("garmin_username"), body.get("garmin_password"))
                    session = self.supabase.create_account(username, password, credentials)
                else:
                    session = self.supabase.sign_in(username, password)
                self._set_session(session)
                self._reply(200, {"ok": True})
                return
            if action == "logout":
                self._cookie("pace_access", "", 0)
                self._cookie("pace_refresh", "", 0)
                cookies = SimpleCookie()
                cookies.load(self.headers.get("Cookie", ""))
                access = cookies.get("pace_access")
                if access:
                    try:
                        self.supabase.request("/auth/v1/logout?scope=local", method="POST",
                                              privileged=False, token=access.value)
                    except (SupabaseError, DashboardError):
                        pass
                self._reply(200, {"ok": True})
                return
            identity = self._identity()
            store = UserStore(self.supabase, identity["id"])
            if action == "refresh":
                self._reply(202, start_refresh(store))
            elif action == "sync-step":
                result = refresh_step(store, body.get("job_id"))
                self._reply(200 if result["complete"] else 202, result)
            elif action == "garmin":
                credentials = validate_garmin_credentials(body.get("garmin_username"), body.get("garmin_password"))
                store.update_credentials(credentials)
                self._reply(200, {"ok": True, "garmin_username": credentials["username"]})
            elif action == "garmin-session":
                import_garmin_session(store, body.get("session_json"))
                self._reply(200, {"ok": True})
            else:
                raise DashboardError("Unknown request.", 400)
        self._run(post)
