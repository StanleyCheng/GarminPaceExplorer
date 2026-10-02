from garminconnect import GarminConnectConnectionError

from get_data import fetch_activities, get_client


class _Client:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.calls = []

    def get_activities(self, start, limit):
        self.calls.append((start, limit))
        result = next(self.batches)
        if isinstance(result, Exception):
            raise result
        return result


def test_get_client_uses_persistent_tokenstore(monkeypatch, tmp_path):
    calls = {}

    class _Garmin:
        def __init__(self, username, password, *, prompt_mfa):
            calls["credentials"] = (username, password)
            calls["prompt_mfa"] = prompt_mfa

        def login(self, tokenstore):
            calls["tokenstore"] = tokenstore

    monkeypatch.setattr("get_data.Garmin", _Garmin)

    client = get_client("runner@example.com", "secret", tokenstore=str(tmp_path))

    assert isinstance(client, _Garmin)
    assert calls["credentials"] == ("runner@example.com", "secret")
    assert callable(calls["prompt_mfa"])
    assert calls["tokenstore"] == str(tmp_path)


def test_fetch_activities_paginates_to_requested_limit():
    client = _Client([[1, 2], [3, 4], [5]])

    assert fetch_activities(client, max_activities=5, batch_size=2) == [1, 2, 3, 4, 5]
    assert client.calls == [(0, 2), (2, 2), (4, 1)]


def test_fetch_activities_retries_connection_error(monkeypatch):
    client = _Client([GarminConnectConnectionError("temporary"), [1]])
    delays = []
    monkeypatch.setattr("get_data.time.sleep", delays.append)

    assert fetch_activities(client, max_activities=1, retries=2) == [1]
    assert delays == [1]


def test_fetch_all_activities_has_no_default_history_cap():
    client = _Client([[1, 2], [3, 4], []])
    assert fetch_activities(client, max_activities=None, batch_size=2) == [1, 2, 3, 4]
    assert client.calls == [(0, 2), (2, 2), (4, 2)]


def test_fetch_all_continues_after_short_pages_until_empty():
    client = _Client([[1], [2, 3], [4], []])
    assert fetch_activities(client, max_activities=None, batch_size=2) == [1, 2, 3, 4]
    assert client.calls == [(0, 2), (1, 2), (3, 2), (4, 2)]


def test_fetch_all_exceeds_ten_thousand_records():
    client = _Client([[1] * 100 for _ in range(100)] + [[2, 3, 4], []])
    result = fetch_activities(client, max_activities=None)
    assert len(result) == 10003
    assert client.calls[-1] == (10003, 100)
