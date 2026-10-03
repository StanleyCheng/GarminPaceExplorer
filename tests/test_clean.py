import pytest
from transform import clean


def _act(**overrides):
    base = {
        "date": "2024-03-15", "year": 2024, "month": 3,
        "distance_km": 10.0, "pace_s_per_km": 300,
        "duration_s": 3000, "avg_hr": 150,
        "activity_type": "running",
    }
    base.update(overrides)
    return base


def test_clean_keeps_valid_running():
    kept, drops = clean([_act()])
    assert len(kept) == 1
    assert drops == {}


def test_clean_drops_unparseable_date():
    kept, drops = clean([_act(date=None)])
    assert kept == [] and drops == {"date": 1}


def test_clean_drops_no_pace():
    kept, drops = clean([_act(pace_s_per_km=None)])
    assert kept == [] and drops == {"no_pace": 1}


def test_clean_drops_too_fast_pace():
    kept, drops = clean([_act(pace_s_per_km=179)])
    assert kept == [] and drops == {"pace": 1}


@pytest.mark.parametrize("activity_type", ["running", "walking", "hiking"])
@pytest.mark.parametrize("pace", [180, 1200])
def test_clean_keeps_new_pace_boundaries(activity_type, pace):
    kept, drops = clean([_act(activity_type=activity_type, pace_s_per_km=pace)])
    assert len(kept) == 1 and drops == {}


def test_clean_keeps_walk_at_20min_per_km():
    kept, drops = clean([_act(activity_type="walking", pace_s_per_km=1200)])
    assert len(kept) == 1


def test_clean_drops_walk_too_slow():
    kept, drops = clean([_act(activity_type="walking", pace_s_per_km=1201)])
    assert kept == [] and drops == {"pace": 1}


def test_clean_drops_hike_over_20min_per_km():
    kept, drops = clean([_act(activity_type="hiking", pace_s_per_km=1500)])
    assert kept == [] and drops == {"pace": 1}


def test_clean_drops_distance_below_500m():
    kept, drops = clean([_act(distance_km=0.49)])
    assert kept == [] and drops == {"distance": 1}


def test_clean_keeps_distance_at_500m():
    kept, drops = clean([_act(distance_km=0.5)])
    assert len(kept) == 1


def test_clean_keeps_distance_at_200km():
    kept, drops = clean([_act(distance_km=200.0)])
    assert len(kept) == 1


def test_clean_drops_distance_above_200km():
    kept, drops = clean([_act(distance_km=200.01)])
    assert kept == [] and drops == {"distance": 1}


def test_clean_drops_cycling():
    kept, drops = clean([_act(activity_type="cycling")])
    assert kept == [] and drops == {"type": 1}


def test_clean_keeps_track_running_subtype():
    kept, drops = clean([_act(activity_type="track_running")])
    assert len(kept) == 1


def test_clean_keeps_ultra_run():
    kept, drops = clean([_act(activity_type="ultra_run")])
    assert len(kept) == 1


def test_clean_drops_duration_too_short():
    kept, drops = clean([_act(duration_s=30)])
    assert kept == [] and drops == {"duration": 1}


def test_clean_drops_duration_too_long():
    kept, drops = clean([_act(duration_s=13 * 3600)])
    assert kept == [] and drops == {"duration": 1}


def test_clean_keeps_activity_with_invalid_hr_for_volume():
    kept, drops = clean([_act(avg_hr=20)])
    assert len(kept) == 1 and kept[0]["avg_hr"] is None and drops == {}


@pytest.mark.parametrize("hr", [None, 240])
def test_clean_keeps_activity_with_missing_or_high_hr(hr):
    kept, drops = clean([_act(avg_hr=hr)])
    assert len(kept) == 1 and kept[0]["avg_hr"] is None and drops == {}


def test_clean_aggregates_drop_reasons():
    acts = [
        _act(date=None),
        _act(pace_s_per_km=None),
        _act(activity_type="cycling"),
        _act(avg_hr=20),
    ]
    kept, drops = clean(acts)
    assert drops == {"date": 1, "no_pace": 1, "type": 1}
    assert len(kept) == 1 and kept[0]["avg_hr"] is None
