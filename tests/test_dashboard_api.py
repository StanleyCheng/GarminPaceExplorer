"""Complete-history imports keep each user's previous snapshot until committed."""

import base64
import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

import dashboard_api
from dashboard_api import import_garmin_session, read_dashboard, refresh_step, start_refresh
from supabase_store import DashboardError, decrypt_private


class MemoryStore:
    """Model the durable RPC boundary; no real Garmin or Supabase requests."""

    def __init__(self, saved=None):
        self.user_id = str(uuid4())
        self.revision = str(uuid4())
        self.credentials = {"username": "runner@example.com", "password": "private-garmin-password"}
        self.saved = copy.deepcopy(saved)
        self.session = None
        self.job = None
        self.batches = []
        self.calls = []
        self.busy = False
        self.fail_append = False
        self.fail_finish = False

    def connection(self):
        return {"credentials": copy.deepcopy(self.credentials), "session": self.session,
                "revision": self.revision}

    def snapshot(self):
        return copy.deepcopy(self.saved)

    def import_batches(self, job_id):
        assert job_id == self.job["id"]
        yield from copy.deepcopy(self.batches)

    def call(self, name, **params):
        self.calls.append((name, copy.deepcopy(params)))
        if name == "pace_begin_sync":
            assert params["p_revision"] == self.revision
            if self.job is None:
                self.job = {"id": str(uuid4()), "next_offset": 0, "status": "running",
                            "credentials_revision": self.revision}
            return copy.deepcopy(self.job)
        if name == "pace_claim_sync":
            assert params["p_job"] == self.job["id"]
            if self.busy:
                return None
            self.worker = params["p_worker"]
            return copy.deepcopy(self.job)
        if name == "pace_append_sync":
            assert params["p_worker"] == self.worker
            assert params["p_offset"] == self.job["next_offset"]
            if self.fail_append:
                raise DashboardError("Could not save this page.", 502)
            self.batches.extend(copy.deepcopy(params["p_records"]))
            self.job["next_offset"] += len(params["p_records"])
            if not params["p_records"]:
                self.job["status"] = "finalizing"
            self.session = decrypt_private(params["p_session"], self.user_id)
            return copy.deepcopy(self.job)
        if name == "pace_finish_sync":
            assert self.job["status"] == "finalizing"
            assert params["p_worker"] == self.worker
            assert len(self.batches) == params["p_payload"]["meta"]["activity_count_fetched"]
            if self.fail_finish:
                raise DashboardError("Could not save the dashboard.", 502)
            self.saved = copy.deepcopy(params["p_payload"])
            self.job["status"] = "complete"
            return None
        if name == "pace_release_sync":
            return None
        if name == "pace_save_session":
            self.session = decrypt_private(params["p_session"], self.user_id)
            return None
        raise AssertionError(f"Unexpected RPC: {name}")


@pytest.fixture(autouse=True)
def encryption_configuration(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"t" * 32).decode())


def install_client(monkeypatch, pages):
    calls = []
    logins = []

    class GarminClient:
        client = SimpleNamespace(dumps=lambda: '{"di_token":"private-session-token"}')

        def get_activities(self, start, limit):
            calls.append((start, limit))
            records = pages(start, limit)
            if isinstance(records, Exception):
                raise records
            return records

    def get_client(username, password, **kwargs):
        logins.append((username, password, kwargs))
        return GarminClient()

    monkeypatch.setattr(dashboard_api, "get_client", get_client)
    return calls, logins


def complete_import(store):
    started = start_refresh(store)
    while True:
        result = refresh_step(store, started["job_id"])
        if result["complete"]:
            return result


def test_short_pages_continue_until_empty_and_only_then_replace_snapshot(monkeypatch, synthetic_activity):
    old = {"meta": {"generated_at": "previous"}, "activities": [{"old": True}]}
    store = MemoryStore(old)
    calls, logins = install_client(monkeypatch, lambda start, limit: {
        0: [synthetic_activity], 1: [synthetic_activity] * 2, 3: [],
    }[start])
    started = start_refresh(store)
    assert started["records_loaded"] == 0 and not started["complete"]
    for expected_count in (1, 3):
        result = refresh_step(store, started["job_id"])
        assert result["records_loaded"] == expected_count and not result["complete"]
        assert not result["finalizing"]
        assert store.saved == old
    result = refresh_step(store, started["job_id"])
    assert result["finalizing"] and not result["complete"]
    assert store.saved == old
    result = refresh_step(store, started["job_id"])
    assert result["complete"] and result["records_loaded"] == 3
    assert calls == [(0, 100), (1, 100), (3, 100)]
    assert result["payload"] == store.saved
    assert len(result["payload"]["activities"]) == 3
    assert logins[1][2]["tokenstore"] == store.session
    public_json = json.dumps(result)
    assert "private-garmin-password" not in public_json
    assert "private-session-token" not in public_json
    assert "credentials" not in public_json
    append = [params for name, params in store.calls if name == "pace_append_sync"]
    assert all("private-session-token" not in params["p_session"] for params in append)


def test_complete_history_has_no_ten_thousand_record_cap(monkeypatch, synthetic_activity):
    total = 10_103
    calls, _ = install_client(monkeypatch, lambda start, limit: [synthetic_activity] * min(limit, max(0, total - start)))
    result = complete_import(MemoryStore())
    assert result["records_loaded"] == total
    assert result["payload"]["meta"]["activity_count_fetched"] == total
    assert len(result["payload"]["activities"]) == total
    assert calls[-2:] == [(10_100, 100), (10_103, 100)]


def test_interrupted_import_resumes_saved_offset_and_session(monkeypatch, synthetic_activity):
    store = MemoryStore()
    calls, _ = install_client(monkeypatch, lambda start, limit: [synthetic_activity] if start == 0 else [])
    first = start_refresh(store)
    refresh_step(store, first["job_id"])
    resumed = start_refresh(store)
    assert resumed["job_id"] == first["job_id"] and resumed["records_loaded"] == 1
    assert refresh_step(store, resumed["job_id"])["finalizing"]
    assert refresh_step(store, resumed["job_id"])["complete"]
    assert calls == [(0, 100), (1, 100)]


@pytest.mark.parametrize("upstream,status", [
    (GarminConnectTooManyRequestsError("private diagnostic"), 429),
    (GarminConnectAuthenticationError("private diagnostic"), 422),
    (GarminConnectConnectionError("private diagnostic"), 502),
])
def test_failed_page_preserves_dashboard_and_can_resume(monkeypatch, synthetic_activity, upstream, status):
    old = {"meta": {"generated_at": "previous"}}
    store = MemoryStore(old)
    install_client(monkeypatch, lambda start, limit: [synthetic_activity] if start == 0 else upstream)
    started = start_refresh(store)
    refresh_step(store, started["job_id"])
    with pytest.raises(DashboardError) as error:
        refresh_step(store, started["job_id"])
    assert error.value.status == status and "private diagnostic" not in str(error.value)
    assert store.saved == old and store.job["next_offset"] == 1
    assert store.calls[-1][0] == "pace_release_sync"
    assert start_refresh(store)["job_id"] == started["job_id"]
    install_client(monkeypatch, lambda start, limit: [])
    assert refresh_step(store, started["job_id"])["finalizing"]
    assert refresh_step(store, started["job_id"])["complete"]


@pytest.mark.parametrize("records", [None, {}, [None], ["activity"]])
def test_malformed_page_does_not_advance_or_replace_snapshot(monkeypatch, records):
    old = {"activities": [{"old": True}]}
    store = MemoryStore(old)
    install_client(monkeypatch, lambda *args: records)
    job = start_refresh(store)
    with pytest.raises(DashboardError) as error:
        refresh_step(store, job["job_id"])
    assert error.value.status == 502
    assert store.job["next_offset"] == 0 and store.batches == []
    assert store.saved == old and store.calls[-1][0] == "pace_release_sync"


def test_durable_page_failure_retries_same_offset(monkeypatch, synthetic_activity):
    store = MemoryStore({"activities": []})
    calls, _ = install_client(monkeypatch, lambda *args: [synthetic_activity])
    job = start_refresh(store)
    store.fail_append = True
    with pytest.raises(DashboardError):
        refresh_step(store, job["job_id"])
    assert store.job["next_offset"] == 0 and store.batches == []
    store.fail_append = False
    assert refresh_step(store, job["job_id"])["records_loaded"] == 1
    assert calls == [(0, 100), (0, 100)]


def test_finalization_failure_preserves_prior_snapshot_and_retries_without_fetch(monkeypatch, synthetic_activity):
    old = {"meta": {"generated_at": "previous"}}
    store = MemoryStore(old)
    calls, _ = install_client(monkeypatch, lambda start, limit: [synthetic_activity] if start == 0 else [])
    job = start_refresh(store)
    refresh_step(store, job["job_id"])
    refresh_step(store, job["job_id"])
    store.fail_finish = True
    with pytest.raises(DashboardError):
        refresh_step(store, job["job_id"])
    assert store.saved == old and store.job["status"] == "finalizing"
    store.fail_finish = False
    assert refresh_step(store, job["job_id"])["complete"]
    assert calls == [(0, 100), (1, 100)]


def test_finalization_rejects_missing_saved_records(monkeypatch, synthetic_activity):
    old = {"activities": [{"old": True}]}
    store = MemoryStore(old)
    install_client(monkeypatch, lambda start, limit: [synthetic_activity] if start == 0 else [])
    job = start_refresh(store)
    refresh_step(store, job["job_id"])
    refresh_step(store, job["job_id"])
    store.batches.clear()
    with pytest.raises(DashboardError) as error:
        refresh_step(store, job["job_id"])
    assert error.value.status == 409
    assert store.saved == old
    assert not any(name == "pace_finish_sync" for name, _ in store.calls)


def test_empty_account_produces_complete_valid_empty_dashboard(monkeypatch):
    install_client(monkeypatch, lambda *args: [])
    result = complete_import(MemoryStore({"activities": [{"old": True}]}))
    assert result["complete"] and result["records_loaded"] == 0
    assert result["payload"]["activities"] == []
    assert result["payload"]["meta"]["year_range"] == []
    assert result["payload"]["meta"]["activity_count_fetched"] == 0


def test_completed_job_returns_committed_snapshot_without_garmin_login(monkeypatch):
    store = MemoryStore({"activities": []})
    job = start_refresh(store)
    store.job["status"] = "complete"
    monkeypatch.setattr(dashboard_api, "get_client", lambda *a, **k: pytest.fail("must not fetch"))
    assert refresh_step(store, job["job_id"]) == {"complete": True, "records_loaded": 0, "payload": store.saved}


@pytest.mark.parametrize("job_id", [None, "invalid", {}, "../other-user"])
def test_invalid_job_rejected_before_storage(job_id):
    store = MemoryStore()
    with pytest.raises(DashboardError) as error:
        refresh_step(store, job_id)
    assert error.value.status == 400 and store.calls == []


def test_busy_import_does_not_login_or_write(monkeypatch):
    store = MemoryStore()
    job = start_refresh(store)
    store.busy = True
    monkeypatch.setattr(dashboard_api, "get_client", lambda *a, **k: pytest.fail("must not fetch"))
    with pytest.raises(DashboardError) as error:
        refresh_step(store, job["job_id"])
    assert error.value.status == 409
    assert [name for name, _ in store.calls] == ["pace_begin_sync", "pace_claim_sync"]


def test_changed_credentials_abort_existing_job_before_login(monkeypatch):
    store = MemoryStore({"activities": []})
    job = start_refresh(store)
    store.revision = str(uuid4())
    monkeypatch.setattr(dashboard_api, "get_client", lambda *a, **k: pytest.fail("must not fetch"))
    with pytest.raises(DashboardError) as error:
        refresh_step(store, job["job_id"])
    assert error.value.status == 409 and store.saved == {"activities": []}


def test_public_dashboard_returns_username_and_snapshot_without_password_or_session():
    store = MemoryStore({"activities": []})
    store.session = "private-session-token"
    result = read_dashboard(store, {"id": store.user_id, "username": "runner"})
    assert result == {"user": {"username": "runner", "garmin_username": "runner@example.com"},
                      "payload": {"activities": []}}
    assert "private-garmin-password" not in json.dumps(result)
    assert "private-session-token" not in json.dumps(result)


def test_imported_garmin_session_is_encrypted_and_bound_to_owner():
    store = MemoryStore()
    tokens = {"di_token": "secret-access", "di_refresh_token": "secret-refresh", "di_client_id": "secret-client"}
    import_garmin_session(store, json.dumps(tokens))
    ciphertext = store.calls[-1][1]["p_session"]
    assert not any(value in ciphertext for value in tokens.values())
    assert json.loads(decrypt_private(ciphertext, store.user_id)) == tokens
    with pytest.raises(DashboardError):
        decrypt_private(ciphertext, str(uuid4()))


@pytest.mark.parametrize("value", [None, "invalid", "[]", "{}", '{"di_token":"token"}',
                                  '{"di_token":1,"di_refresh_token":"x","di_client_id":"y"}'])
def test_invalid_session_import_does_not_write(value):
    store = MemoryStore()
    with pytest.raises(DashboardError) as error:
        import_garmin_session(store, value)
    assert error.value.status == 400 and store.calls == []
