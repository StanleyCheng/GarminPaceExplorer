import os
import time
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)


DEFAULT_MAX_ACTIVITIES = 10_000
DEFAULT_BATCH_SIZE = 100
MAX_BATCH_SIZE = 100
DEFAULT_RETRIES = 3
DEFAULT_TOKENSTORE = "~/.garminconnect"


def get_client(username, password, *, tokenstore=None, prompt_mfa=None):
    """Authenticate with Garmin, restoring and refreshing saved tokens first."""
    tokenstore = tokenstore or os.getenv("GARMINTOKENS", DEFAULT_TOKENSTORE)
    client = Garmin(
        username,
        password,
        prompt_mfa=prompt_mfa or (lambda: input("Garmin MFA code: ").strip()),
    )
    try:
        client.login(tokenstore)
    except GarminConnectConnectionError as exc:
        if "all login strategies exhausted" in str(exc).lower():
            raise GarminConnectConnectionError(
                "Garmin blocked the fresh sign-in (rate limit, CAPTCHA, or HTTP 403). "
                "Stop retrying, sign in at https://connect.garmin.com in a browser, "
                "then wait for the login cooldown before trying this command once. "
                f"After a successful login, this script will reuse tokens from {tokenstore}."
            ) from exc
        raise

    if tokenstore.lstrip().startswith("{"):
        return client
    token_path = Path(tokenstore).expanduser()
    if token_path.is_dir() or not token_path.name.endswith(".json"):
        token_path = token_path / "garmin_tokens.json"
    if token_path.exists():
        token_path.chmod(0o600)
    return client


def fetch_activities(client, *, max_activities=DEFAULT_MAX_ACTIVITIES,
                    batch_size=DEFAULT_BATCH_SIZE, retries=DEFAULT_RETRIES):
    """Fetch up to max_activities from Garmin Connect, paginated.

    Pass max_activities=None to fetch the complete history without a cap.
    Retries on transient errors. Raises TooManyRequestsError after final retry.
    """
    if (max_activities is not None and max_activities < 0) or batch_size <= 0 or retries <= 0:
        raise ValueError("max_activities must be >= 0; batch_size and retries must be > 0")
    if batch_size > MAX_BATCH_SIZE:
        batch_size = MAX_BATCH_SIZE
    activities, start = [], 0
    while max_activities is None or start < max_activities:
        limit = batch_size if max_activities is None else min(batch_size, max_activities - start)
        for attempt in range(1, retries + 1):
            try:
                batch = client.get_activities(start, limit)
                break
            except (GarminConnectTooManyRequestsError,
                    GarminConnectConnectionError) as exc:
                if attempt == retries:
                    raise
                delay = 2 ** (attempt - 1)
                print(f"Garmin fetch retry {attempt}/{retries} after {delay}s: {exc}")
                time.sleep(delay)
        if not isinstance(batch, list):
            raise TypeError("Garmin returned an invalid activities response")
        if not batch:
            break
        activities.extend(batch)
        fetched = len(batch)
        start += fetched
        if max_activities is not None and fetched < limit:
            break
    return activities
