"""Per-user Garmin syncs that paginate to the end across Vercel requests."""

import json
import tempfile
from uuid import UUID, uuid4

from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from aggregate import build_payload, now_iso
from get_data import get_client
from supabase_store import DashboardError, encrypt_private
from transform import clean, format_public_username, normalize_activity


def read_dashboard(store, identity):
    connection = store.connection()
    return {"user": {"username": identity["username"],
                     "garmin_username": connection["credentials"]["username"]},
            "payload": store.snapshot()}


def _mfa_required():
    raise DashboardError(
        "Garmin needs verification. In Account settings, import the session JSON "
        "from a successful local Garmin login, then refresh again.", 422
    )


def start_refresh(store):
    """Start or resume this user's complete-history import, without a record cap."""
    connection = store.connection()
    job = store.call("pace_begin_sync", p_revision=connection["revision"])
    return {"job_id": job["id"], "records_loaded": job["next_offset"], "complete": False}


def refresh_step(store, job_id):
    """Fetch one page, save it durably, and finalize only after an empty page."""
    try:
        job_id = str(UUID(job_id))
    except (ValueError, TypeError, AttributeError):
        raise DashboardError("Invalid sync request.", 400)
    worker = str(uuid4())
    job = store.call("pace_claim_sync", p_job=job_id, p_worker=worker)
    if not job:
        raise DashboardError("This sync is already loading a page. Try again shortly.", 409)
    if job["status"] == "complete":
        return {"complete": True, "records_loaded": job["next_offset"], "payload": store.snapshot()}
    try:
        connection = store.connection()
        if connection["revision"] != job["credentials_revision"]:
            raise DashboardError("Your Garmin connection changed. Start a new refresh.", 409)
        if job["status"] == "finalizing":
            return _finish_refresh(store, job, worker, connection)

        with tempfile.TemporaryDirectory(prefix="garmin-") as token_dir:
            client = get_client(
                connection["credentials"]["username"], connection["credentials"]["password"],
                tokenstore=connection["session"] or token_dir, prompt_mfa=_mfa_required,
            )
            # One request per page; short non-empty pages never imply completion.
            records = client.get_activities(job["next_offset"], 100)
            if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
                raise DashboardError("Garmin returned an invalid activity page. Try refreshing again.", 502)
            job = store.call("pace_append_sync", p_job=job_id, p_worker=worker,
                             p_offset=job["next_offset"], p_records=records,
                             p_session=encrypt_private(client.client.dumps(), store.user_id))
        return {"job_id": job_id, "records_loaded": job["next_offset"], "complete": False,
                "finalizing": job["status"] == "finalizing"}
    except GarminConnectTooManyRequestsError as exc:
        raise DashboardError("Garmin is rate limiting requests. Wait a few minutes, then tap refresh to resume.", 429) from exc
    except GarminConnectAuthenticationError as exc:
        raise DashboardError("Garmin sign-in failed. Check your Garmin credentials in Account settings, or import a verified Garmin session.", 422) from exc
    except GarminConnectConnectionError as exc:
        raise DashboardError("Garmin could not be reached or blocked this sign-in. Try later, or import a verified session in Account settings.", 502) from exc
    finally:
        try:
            store.call("pace_release_sync", p_job=job_id, p_worker=worker)
        except Exception:
            # A lost connection leaves a bounded lease; the next attempt can resume.
            pass


def _finish_refresh(store, job, worker, connection):
    raw = list(store.import_batches(job["id"]))
    if len(raw) != job["next_offset"]:
        raise DashboardError("The saved pages are incomplete. Tap refresh to retry; your previous dashboard is unchanged.", 409)
    normalized = [normalize_activity(record) for record in raw]
    kept, drops = clean(normalized)
    payload = build_payload(kept, drops, generated_at=now_iso(),
                            garmin_username_masked=format_public_username(connection["credentials"]["username"]))
    payload["meta"]["activity_count_fetched"] = len(raw)
    store.call("pace_finish_sync", p_job=job["id"], p_worker=worker, p_payload=payload)
    return {"complete": True, "records_loaded": len(raw), "payload": payload}


def import_garmin_session(store, value):
    try:
        session = json.loads(value)
        if not all(isinstance(session.get(key), str) and session[key]
                   for key in ("di_token", "di_refresh_token", "di_client_id")):
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise DashboardError("Paste the complete token JSON from your local Garmin login.", 400)
    store.call("pace_save_session", p_session=encrypt_private(json.dumps(session), store.user_id))
