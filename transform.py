from datetime import datetime


def _safe_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    v = _safe_float(value)
    if v is None:
        return None
    return int(round(v))


def _parse_datetime(value):
    """Parse Garmin's startTimeLocal. Returns datetime or None.

    Handles ISO with optional .SSSZ suffix and ±HH:MM offsets.
    """
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    # Garmin sometimes returns "Z" suffix; replace with +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _activity_type_key(activity):
    type_ = activity.get("activityType")
    if isinstance(type_, dict):
        return type_.get("typeKey")
    return type_


def normalize_activity(activity):
    """Normalize a raw Garmin activity into the cleaned-record schema.

    Returns a dict with: date, year, month, distance_km, pace_s_per_km,
    duration_s, avg_hr, max_hr (None if absent), elevation_m, vo2max,
    calories, activity_type.
    """
    out = {}
    dt = _parse_datetime(activity.get("startTimeLocal"))
    out["date"] = dt.date().isoformat() if dt else None
    out["year"] = dt.year if dt else None
    out["month"] = dt.month if dt else None

    distance_m = _safe_float(activity.get("distance"))
    # Keep full precision so cleaning can enforce the raw-metre boundaries.
    out["distance_km"] = distance_m / 1000 if distance_m is not None else None

    speed = _safe_float(activity.get("averageSpeed"))
    out["pace_s_per_km"] = round(1000 / speed, 2) if speed and speed > 0 else None

    out["duration_s"] = _safe_int(activity.get("duration"))
    out["avg_hr"] = _safe_int(activity.get("averageHR"))
    out["max_hr"] = _safe_int(activity.get("maxHR", activity.get("maxHeartRate")))
    out["calories"] = _safe_int(activity.get("calories"))
    out["elevation_m"] = _safe_float(activity.get("elevationGain"))
    out["vo2max"] = _safe_float(activity.get("vO2MaxValue"))
    out["activity_type"] = _activity_type_key(activity)
    return out


BUCKET_NAMES = ("<3", "3-5", "5-10", "10-15", "15-25", "25-40", "40+")
_BUCKET_UPPER_BOUNDS = (3, 5, 10, 15, 25, 40, float("inf"))


def to_bucket(distance_km):
    if distance_km is None:
        return "all"
    for upper, name in zip(_BUCKET_UPPER_BOUNDS, BUCKET_NAMES):
        if distance_km < upper:
            return name
    return "40+"


# Allow-rule keywords (matched as case-insensitive substring or equality)
_RUN_KEYWORDS = ("run",)
_WALK_KEYWORDS = ("walking", "walk")
_HIKE_KEYWORDS = ("hiking", "hike")

# Accepted whole-activity pace: 3:00–20:00 per km for every included type.
_PACE_MIN_S_PER_KM = 180
_PACE_MAX_S_PER_KM = 1200
_DISTANCE_MIN_M = 500
_DISTANCE_MAX_M = 200_000
_DURATION_MIN_S = 60
_DURATION_MAX_S = 12 * 3600
_HR_MIN = 30
_HR_MAX = 230


def _activity_class(activity_type):
    """Classify activity_type into 'run', 'walk', 'hike', or None (drop)."""
    if not activity_type:
        return None
    t = activity_type.lower()
    if any(k in t for k in _RUN_KEYWORDS):
        return "run"
    if any(k in t for k in _HIKE_KEYWORDS):
        return "hike"
    if any(k in t for k in _WALK_KEYWORDS):
        return "walk"
    return None


def clean(activities):
    """Apply drop rules in order. Returns (kept, dropped_by_reason)."""
    kept, dropped_by_reason = [], {}

    def _drop(reason):
        dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1

    for a in activities:
        if a.get("date") is None:
            _drop("date"); continue
        cls = _activity_class(a.get("activity_type"))
        if cls is None:
            _drop("type"); continue
        km = a.get("distance_km")
        if km is None or km * 1000 < _DISTANCE_MIN_M or km * 1000 > _DISTANCE_MAX_M:
            _drop("distance"); continue
        dur = a.get("duration_s")
        if dur is None or dur < _DURATION_MIN_S or dur > _DURATION_MAX_S:
            _drop("duration"); continue
        pace = a.get("pace_s_per_km")
        if pace is None:
            _drop("no_pace"); continue
        if pace < _PACE_MIN_S_PER_KM or pace > _PACE_MAX_S_PER_KM:
            _drop("pace"); continue
        hr = a.get("avg_hr")
        if hr is None or hr < _HR_MIN or hr > _HR_MAX:
            # Invalid HR must not erase otherwise valid training volume.
            a = {**a, "avg_hr": None}
        kept.append(a)

    return kept, dropped_by_reason


def format_public_username(username):
    """Return a privacy-safe representation of the Garmin username.

    Per spec §6: drop domain entirely — show only first letter + `***`.
    Cosmetic only; the underlying JSON contains enough data to identify
    the runner, so masking is not anonymity, just appearance.
    """
    if not username:
        return ""
    return username[0] + "***"
