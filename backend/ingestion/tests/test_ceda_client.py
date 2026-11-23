"""Tests for the CEDA client's truncation guard and window helpers (no network)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.ingestion.ceda_client import (
    PRICE_COLUMNS,
    CedaClient,
    quarter_windows,
)


class FakeServer(CedaClient):
    """Emulates an API that silently cuts every response at ``cap`` rows (newest first)."""

    def __init__(self, cap: int, inclusive_end: bool = True) -> None:
        super().__init__(api_key="test", base_url="http://localhost", auth_scheme="x-api-key", delay_sec=0)
        self.cap = cap
        self.inclusive_end = inclusive_end
        self.calls = 0

    def _series(self, path, columns, commodity_id, state_id, markets, start, end):
        self.calls += 1
        last = end if self.inclusive_end else end - timedelta(days=1)
        rows = []
        d = last
        while d >= start:  # newest first, like the CEDA CSV
            for m, _dist in markets:
                rows.append({c: None for c in columns} | {
                    "date": d.isoformat(), "market_id": m, "modal_price": 1000.0 + m,
                })
            d -= timedelta(days=1)
        df = pd.DataFrame(rows, columns=columns)
        return df.head(self.cap)  # the silent truncation


def _markets(n: int) -> list[tuple[int, int]]:
    return [(100 + i, 1) for i in range(n)]


def test_truncated_responses_are_split_until_complete():
    server = FakeServer(cap=50)
    start, end = date(2025, 1, 1), date(2025, 2, 9)  # 40 days inclusive

    df = server.fetch_series("price", 1, 1, _markets(5), start, end, max_rows=50)

    assert len(df) == 5 * 40
    assert df.drop_duplicates(["date", "market_id"]).shape[0] == 5 * 40
    assert server.calls > 1  # it really had to bisect


def test_small_responses_are_not_split():
    server = FakeServer(cap=1000)
    df = server.fetch_series("price", 1, 1, _markets(2), date(2025, 1, 1), date(2025, 1, 10), max_rows=1000)
    assert server.calls == 1
    assert len(df) == 2 * 10


def test_large_uncut_responses_are_not_split():
    """Real log: the API returned 1,300-1,565 rows uncut. That must cost ONE call, not several."""
    server = FakeServer(cap=10_000)
    start, end = date(2025, 1, 1), date(2025, 4, 11)  # 101 days inclusive

    df = server.fetch_series("price", 1, 1, _markets(13), start, end, max_rows=100_000)

    assert len(df) == 13 * 101 == 1313
    assert server.calls == 1


def test_a_power_of_two_cap_is_detected_and_worked_around():
    server = FakeServer(cap=2048)                  # silent cap that is not a multiple of 100
    start, end = date(2025, 1, 1), date(2025, 4, 11)  # 101 days inclusive

    df = server.fetch_series("price", 1, 1, _markets(30), start, end, max_rows=100_000)

    assert len(df) == 30 * 101 == 3030             # nothing lost
    assert server.calls > 1


def test_unknown_small_cap_is_caught_by_the_round_number_heuristic():
    """The server cuts at 100 rows; the client was only told 1000. A response of exactly
    100 rows must still be treated as truncated and split until nothing is lost."""
    server = FakeServer(cap=100)
    start, end = date(2025, 1, 1), date(2025, 3, 1)  # 60 days inclusive

    df = server.fetch_series("price", 1, 1, _markets(3), start, end, max_rows=1000)

    assert len(df) == 3 * 60
    assert server.calls > 1


def test_quarter_windows_cover_the_range_and_share_boundaries():
    wins = quarter_windows(date(2015, 1, 1), date(2025, 12, 31))
    assert wins[0][0] == date(2015, 1, 1)
    assert wins[-1][1] == date(2025, 12, 31)
    for (_, prev_end), (next_start, _) in zip(wins, wins[1:]):
        assert prev_end == next_start  # overlap by one day on purpose


def test_leap_years_do_not_leave_a_wasteful_tiny_final_window():
    wins = quarter_windows(date(2019, 1, 1), date(2025, 12, 31), days=365)
    assert len(wins) == 7                      # not 8: a 1-day leftover would cost extra calls
    assert wins[-1][1] == date(2025, 12, 31)
    assert all((b - a).days >= 300 for a, b in wins)


def test_windows_lose_no_day_even_if_to_date_is_exclusive():
    """If the API treats to_date as exclusive, the shared boundary day still gets fetched."""
    server = FakeServer(cap=10_000, inclusive_end=False)
    start, end = date(2025, 1, 1), date(2025, 6, 30)

    frames = [
        server.fetch_series("price", 1, 1, _markets(1), a, b, max_rows=10_000)
        for a, b in quarter_windows(start, end)
    ]
    got = set(pd.concat(frames)["date"])
    want = {(start + timedelta(days=i)).isoformat() for i in range((end - start).days)}
    assert want <= got


def test_price_columns_are_always_present_even_when_empty():
    server = FakeServer(cap=10)
    df = server.fetch_series("price", 1, 1, [], date(2025, 1, 1), date(2025, 1, 2), max_rows=10)
    assert list(df.columns) == PRICE_COLUMNS


class CannedResponses(CedaClient):
    """Returns whatever JSON it was given, to test response-shape handling."""

    def __init__(self, payload) -> None:
        super().__init__(api_key="test", base_url="http://localhost", auth_scheme="bearer", delay_sec=0)
        self.payload = payload

    def _request(self, method, path, json_body=None):
        return self.payload


def test_commodities_accept_the_real_field_names_and_wrapper_variants():
    real_rows = [{"commodity_id": 2, "commodity_name": "Paddy(Dhan)(Common)"},
                 {"commodity_id": 7, "commodity_name": "Tomato"}]
    for payload in (
        {"data": real_rows},                                   # wrapped, real field names
        real_rows,                                             # bare list
        {"commodities": [{"id": 2, "name": "Paddy(Dhan)(Common)"},   # Swagger-example shape
                         {"id": 7, "name": "Tomato"}]},
    ):
        df = CannedResponses(payload).commodities()
        assert df["name"].tolist() == ["Paddy(Dhan)(Common)", "Tomato"]
        assert df["id"].tolist() == [2, 7]


def test_unrecognised_commodities_shape_fails_loudly_with_the_shape():
    import pytest

    from backend.ingestion.ceda_client import CedaError

    with pytest.raises(CedaError, match="unexpected response shape"):
        CannedResponses({"data": [{"foo": 1, "bar": "x"}]}).commodities()


def test_geographies_flatten_states_and_districts():
    payload = {"geographies": [
        {"state_id": 3, "state_name": "Karnataka",
         "districts": [{"district_id": 41, "district_name": "Kolar"},
                       {"district_id": 42, "district_name": "Bangalore"}]},
    ]}
    df = CannedResponses(payload).geographies()
    assert df["district_name"].tolist() == ["Kolar", "Bangalore"]
    assert set(df["state_name"]) == {"Karnataka"}


def test_series_with_unexpected_columns_is_rejected_not_loaded_as_nulls():
    import pytest

    from backend.ingestion.ceda_client import CedaError

    payload = {"data": [{"date": "2025-01-01", "market_id": 1, "price": 100}]}
    with pytest.raises(CedaError, match="unexpected columns"):
        CannedResponses(payload).fetch_series(
            "price", 1, 1, [(1, 1)], date(2025, 1, 1), date(2025, 1, 2), max_rows=1000
        )


def test_responses_wrapped_in_an_output_object_are_unwrapped():
    """The live API returns {"output": {...}} where the Swagger example shows no wrapper."""
    rows = [{"commodity_id": 7, "commodity_name": "Tomato"}]
    for payload in ({"output": {"data": rows}}, {"output": {"commodities": rows}}, {"output": rows}):
        df = CannedResponses(payload).commodities()
        assert df["name"].tolist() == ["Tomato"]


def test_geographies_unwrap_output_and_support_flat_layout():
    nested = {"output": {"geographies": [
        {"state_id": 3, "state_name": "Karnataka",
         "districts": [{"district_id": 41, "district_name": "Kolar"}]}]}}
    flat = {"output": {"data": [
        {"state_id": 3, "state_name": "Karnataka", "district_id": 41, "district_name": "Kolar"},
        {"state_id": 3, "state_name": "Karnataka", "district_id": 42, "district_name": "Bangalore"}]}}
    assert CannedResponses(nested).geographies()["district_name"].tolist() == ["Kolar"]
    assert CannedResponses(flat).geographies()["district_name"].tolist() == ["Kolar", "Bangalore"]


def test_series_unwrap_output_data_and_empty_is_fine():
    row = {"date": "2025-01-01", "market_id": 1, "modal_price": 900, "min_price": 800, "max_price": 1000}
    got = CannedResponses({"output": {"data": [row]}}).fetch_series(
        "price", 1, 1, [(1, 1)], date(2025, 1, 1), date(2025, 1, 2), max_rows=1000)
    assert got["modal_price"].tolist() == [900.0]
    empty = CannedResponses({"output": {"data": []}}).fetch_series(
        "price", 1, 1, [(1, 1)], date(2025, 1, 1), date(2025, 1, 2), max_rows=1000)
    assert empty.empty


def test_shape_describes_nesting_without_values():
    from backend.ingestion.ceda_client import _shape

    s = _shape({"output": {"data": [{"commodity_id": 1, "commodity_name": "Tomato"}]}})
    assert "output" in s and "commodity_name" in s and "Tomato" not in s


def test_real_geographies_layout_from_the_live_api():
    payload = {"output": {"type": "success", "message": "Data exists", "data": [
        {"census_state_id": 1, "census_state_name": "Jammu & Kashmir",
         "census_district_id": 1, "census_district_name": "Kupwara"},
        {"census_state_id": 1, "census_state_name": "Jammu & Kashmir",
         "census_district_id": 2, "census_district_name": "Badgam"},
    ]}}
    df = CannedResponses(payload).geographies()
    assert df["state_id"].tolist() == [1, 1]
    assert df["district_id"].tolist() == [1, 2]
    assert df["district_name"].tolist() == ["Kupwara", "Badgam"]
    assert set(df["state_name"]) == {"Jammu & Kashmir"}


def test_real_price_and_quantity_records_from_the_live_api():
    price = {"output": {"type": "success", "message": "Data exists", "data": [
        {"date": "2025-03-03T00:00:00.000Z", "commodity_id": 1, "census_state_id": 8,
         "census_district_id": 104, "market_id": 3149,
         "min_price": 2864, "max_price": 2887, "modal_price": 2880}]}}
    got = CannedResponses(price).fetch_series(
        "price", 1, 8, [(3149, 104)], date(2025, 3, 1), date(2025, 3, 5), max_rows=1000)
    assert got["date"].tolist() == ["2025-03-03"]          # ISO timestamp trimmed to the day
    assert got["modal_price"].tolist() == [2880.0]

    qty = {"output": {"type": "success", "message": "Data exists", "data": [
        {"date": "2014-11-14T00:00:00.000Z", "commodity_id": 3, "census_state_id": 3,
         "census_district_id": 43, "market_id": 232, "quantity": 200}]}}
    got = CannedResponses(qty).fetch_series(
        "quantity", 3, 3, [(232, 43)], date(2014, 11, 1), date(2014, 11, 30), max_rows=1000)
    assert got["quantity"].tolist() == [200.0]
    assert got["date"].tolist() == ["2014-11-14"]


class _Resp:
    def __init__(self, status, headers=None, text="", payload=None):
        self.status_code, self.headers, self.text, self._payload = status, headers or {}, text, payload

    def json(self):
        return self._payload


class _Session:
    def __init__(self, resp):
        self.resp, self.calls = resp, 0

    def request(self, *a, **k):
        self.calls += 1
        return self.resp


class _Waiting:
    """Stands in for a client method on a client created with wait_on_limit=True."""

    wait_on_limit = True

    def __init__(self, fn):
        self.fn = fn

    def call(self):
        return self.fn()


class _Stopping(_Waiting):
    wait_on_limit = False


def test_429_is_raised_with_headers_and_never_retried_in_place():
    import pytest

    from backend.ingestion.ceda_client import CedaRateLimited

    sess = _Session(_Resp(429, {"Retry-After": "30", "X-RateLimit-Remaining": "0"}, "Too many requests"))
    c = CedaClient(api_key="k", base_url="http://x", auth_scheme="bearer", delay_sec=0, session=sess)
    with pytest.raises(CedaRateLimited) as ei:
        c.commodities()
    assert ei.value.retry_after == 30.0
    assert ei.value.info["x-ratelimit-remaining"] == "0"  # header names are lower-cased
    assert sess.calls == 1  # no hidden retry loop hammering a limited API


def test_with_backoff_waits_then_succeeds(monkeypatch):
    from backend.ingestion import ceda_fetch
    from backend.ingestion.ceda_client import CedaRateLimited

    sleeps: list[float] = []
    monkeypatch.setattr(ceda_fetch.time, "sleep", sleeps.append)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise CedaRateLimited(None, {}, "")
        return "ok"

    assert ceda_fetch.with_backoff(_Waiting(flaky).call) == "ok"
    assert sleeps == [60, 180]


def test_with_backoff_stops_instead_of_sleeping_for_hours(monkeypatch):
    import pytest

    from backend.ingestion import ceda_fetch
    from backend.ingestion.ceda_client import CedaRateLimited

    sleeps: list[float] = []
    monkeypatch.setattr(ceda_fetch.time, "sleep", sleeps.append)

    def blocked():
        raise CedaRateLimited(7200.0, {"retry-after": "7200"}, "quota")

    with pytest.raises(CedaRateLimited):
        ceda_fetch.with_backoff(_Waiting(blocked).call)
    assert sleeps == []


def test_with_backoff_waits_exactly_the_servers_retry_after(monkeypatch):
    from backend.ingestion import ceda_fetch
    from backend.ingestion.ceda_client import CedaRateLimited

    sleeps: list[float] = []
    monkeypatch.setattr(ceda_fetch.time, "sleep", sleeps.append)
    attempts = {"n": 0}

    def once_blocked():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise CedaRateLimited(2574.0, {"retry-after": "2574"}, "")  # value from the real 429
        return "ok"

    assert ceda_fetch.with_backoff(_Waiting(once_blocked).call) == "ok"
    assert sleeps == [2579.0]  # retry-after + 5s margin


def _spent_budget_client(**kwargs):
    headers = {"ratelimit-limit": "40", "ratelimit-remaining": "0", "ratelimit-reset": "100"}
    payload = {"output": {"data": [{"commodity_id": 1, "commodity_name": "Wheat"}]}}
    sess = _Session(_Resp(200, headers, payload=payload))
    client = CedaClient(api_key="k", base_url="http://x", auth_scheme="bearer", delay_sec=0,
                        session=sess, **kwargs)
    return client, sess


def test_client_stops_instead_of_sleeping_when_the_hourly_budget_is_spent(monkeypatch):
    import pytest

    from backend.ingestion import ceda_client
    from backend.ingestion.ceda_client import CedaRateLimited

    sleeps: list[float] = []
    monkeypatch.setattr(ceda_client.time, "sleep", sleeps.append)
    c, sess = _spent_budget_client()          # default: stop at the limit

    c.commodities()                           # uses the last call of the window
    with pytest.raises(CedaRateLimited) as ei:
        c.commodities()
    assert 100 <= ei.value.retry_after <= 106  # tells the caller how long until the reset
    assert sess.calls == 1                    # the second request was never even sent
    assert sleeps == []                       # and nothing slept


def test_with_backoff_does_not_wait_in_stop_mode(monkeypatch):
    import pytest

    from backend.ingestion import ceda_fetch
    from backend.ingestion.ceda_client import CedaRateLimited

    sleeps: list[float] = []
    monkeypatch.setattr(ceda_fetch.time, "sleep", sleeps.append)

    def blocked():
        raise CedaRateLimited(2574.0, {}, "")

    with pytest.raises(CedaRateLimited):
        ceda_fetch.with_backoff(_Stopping(blocked).call)
    assert sleeps == []


def test_client_can_sleep_through_the_limit_when_asked(monkeypatch):
    from backend.ingestion import ceda_client

    sleeps: list[float] = []
    monkeypatch.setattr(ceda_client.time, "sleep", sleeps.append)
    c, _ = _spent_budget_client(wait_on_limit=True)

    c.commodities()
    assert sleeps == []
    c.commodities()          # waits for the reset BEFORE calling, instead of burning a 429
    assert len(sleeps) == 1 and 100 <= sleeps[0] <= 106
