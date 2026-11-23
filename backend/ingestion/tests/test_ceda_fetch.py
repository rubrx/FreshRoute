"""Tests for limiting the CEDA download to the mandis in our live feed (no network)."""

from __future__ import annotations

from datetime import date

import pandas as pd

import backend.ingestion.ceda_fetch as f
from backend.ingestion.ceda_client import CedaClient, CedaRateLimited


def _geo() -> pd.DataFrame:
    return pd.DataFrame({
        "state_id": [29] * 4,
        "state_name": ["Karnataka"] * 4,
        "district_id": [1, 2, 3, 4],
        "district_name": ["Kolar", "Bangalore", "Belgaum", "Mysore"],
    })


_COMMODITIES = pd.DataFrame({"id": [78], "name": ["Tomato"]})

# CEDA's view of the world: market_id -> (district_id, name)
_CEDA_MARKETS = {
    1: [(101, "Kolar"), (102, "Srinivaspur"), (103, "Closed Mandi XYZ")],
    2: [(201, "Bangalore"), (202, "Yeshwanthpur APMC")],
    3: [(301, "Belgaum"), (302, "Gokak")],
    4: [(401, "Mysore")],
}


class FakeCeda(CedaClient):
    def __init__(self) -> None:
        super().__init__(api_key="k", base_url="http://x", auth_scheme="bearer", delay_sec=0)
        self.listing_calls: list[int] = []
        self.series_calls = 0

    def markets(self, commodity_id, state_id, district_id, indicator):
        self.listing_calls.append(int(district_id))
        rows = _CEDA_MARKETS[int(district_id)]
        return pd.DataFrame({
            "census_state_id": state_id,
            "census_district_id": district_id,
            "market_id": [m for m, _ in rows],
            "market_name": [n for _, n in rows],
        })

    def _series(self, path, columns, commodity_id, state_id, markets, start, end):
        self.series_calls += 1
        rows = [
            {c: None for c in columns} | {"date": start.isoformat(), "market_id": m, "modal_price": 1.0}
            for m, _ in markets
        ]
        return pd.DataFrame(rows, columns=columns)


def _live(*rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["state", "district", "market", "commodity"])


def test_district_scope_is_forgiving_about_case_and_small_spelling_changes():
    assert f._district_in_scope("Kolar", {"kolar"})
    assert f._district_in_scope("KOLAR ", {"kolar"})
    assert not f._district_in_scope("Mysore", {"kolar", "bangalore"})


def test_only_mandis_that_can_map_to_a_live_mandi_are_kept():
    mk = pd.DataFrame({
        "market_id": [101, 102, 103],
        "market_name": ["Kolar", "Srinivaspur", "Closed Mandi XYZ"],
        "state_name": "Karnataka",
        "district_name": "Kolar",
    })
    live = _live(("Karnataka", "Kolar", "Kolar APMC", "Tomato"),
                 ("Karnataka", "Kolar", "Srinivaspur", "Tomato"))
    kept = f.keep_mappable_markets(mk, live)
    assert sorted(kept["market_id"]) == [101, 102]  # the closed mandi is not downloaded


def test_scoped_fetch_lists_only_live_districts_and_downloads_only_mappable_markets(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "RAW_DIR", tmp_path)
    live = _live(("Karnataka", "Kolar", "Kolar", "Tomato"),
                 ("Karnataka", "Bangalore", "Bangalore APMC", "Tomato"),
                 ("Karnataka", "Kolar", "Kolar", "Onion"))  # other commodity: must be ignored
    client = FakeCeda()

    summary = f.fetch_state_commodity(
        client, "Tomato", "Karnataka", date(2024, 1, 1), date(2025, 12, 31),
        kinds=("price",), commodities=_COMMODITIES, geographies=_geo(),
        window_days=365, scope=live,
    )

    assert sorted(client.listing_calls) == [1, 2]       # Belgaum and Mysore never listed
    # 2 live mandis -> 1 batch; 2 yearly windows; price only
    assert client.series_calls == 1 * 2
    assert summary["chunks_fetched"] == 2


def test_pair_without_live_markets_costs_no_api_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "RAW_DIR", tmp_path)
    live = _live(("Karnataka", "Kolar", "Kolar", "Onion"))  # nothing for Tomato
    client = FakeCeda()

    summary = f.fetch_state_commodity(
        client, "Tomato", "Karnataka", date(2024, 1, 1), date(2025, 12, 31),
        commodities=_COMMODITIES, geographies=_geo(), scope=live,
    )

    assert client.listing_calls == [] and client.series_calls == 0
    assert summary["chunks_fetched"] == 0


def test_unscoped_fetch_still_lists_every_district(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "RAW_DIR", tmp_path)
    client = FakeCeda()
    f.fetch_state_commodity(
        client, "Tomato", "Karnataka", date(2025, 1, 1), date(2025, 12, 31),
        kinds=("price",), commodities=_COMMODITIES, geographies=_geo(), window_days=365,
    )
    assert sorted(client.listing_calls) == [1, 2, 3, 4]


def test_scoped_and_full_market_lists_are_cached_separately(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "RAW_DIR", tmp_path)
    assert f.markets_cache_path("price", "Tomato", "Karnataka", scoped=True) != \
        f.markets_cache_path("price", "Tomato", "Karnataka", scoped=False)


class LimitedCeda(FakeCeda):
    """Allows ``allow`` data requests, then behaves like CEDA's spent hourly budget."""

    def __init__(self, allow: int) -> None:
        super().__init__()
        self.allow = allow

    def _series(self, *args, **kwargs):
        if self.series_calls >= self.allow:
            raise CedaRateLimited(1800.0, {"ratelimit-remaining": "0"}, "budget used up")
        return super()._series(*args, **kwargs)


def test_a_run_stopped_by_the_limit_resumes_without_repeating_finished_work(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(f, "RAW_DIR", tmp_path)
    args = ("Tomato", "Karnataka", date(2018, 1, 1), date(2025, 12, 31))
    kwargs = dict(kinds=("price",), commodities=_COMMODITIES, geographies=_geo(), window_days=365)

    first = LimitedCeda(allow=3)
    with pytest.raises(CedaRateLimited):
        f.fetch_state_commodity(first, *args, **kwargs)
    assert first.series_calls == 3
    assert len(list((tmp_path / "price").rglob("*.parquet"))) == 3   # finished chunks are on disk

    second = FakeCeda()                      # "next hour": a fresh client, budget available
    summary = f.fetch_state_commodity(second, *args, **kwargs)
    assert second.listing_calls == []        # market list was cached, not re-listed
    assert summary["chunks_skipped"] == 3    # the 3 finished chunks are not fetched again
    assert summary["chunks_fetched"] == 5    # 8 yearly windows in total, 5 left
    assert second.series_calls == 5


class HistoryStartsIn2024(FakeCeda):
    """Like Tamil Nadu's Uzhavar Sandhais: nothing in CEDA before 2024."""

    def _series(self, path, columns, commodity_id, state_id, markets, start, end):
        if end < date(2024, 1, 1):
            self.series_calls += 1
            return pd.DataFrame(columns=columns)
        return super()._series(path, columns, commodity_id, state_id, markets, start, end)


class NeverAnyData(FakeCeda):
    def _series(self, path, columns, commodity_id, state_id, markets, start, end):
        self.series_calls += 1
        return pd.DataFrame(columns=columns)


def test_fetch_stops_going_back_once_the_history_clearly_ends(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "RAW_DIR", tmp_path)
    client = HistoryStartsIn2024()

    summary = f.fetch_state_commodity(
        client, "Tomato", "Karnataka", date(2018, 1, 1), date(2025, 12, 31),
        kinds=("price",), commodities=_COMMODITIES, geographies=_geo(), window_days=365,
    )

    # two windows with data + one empty window that proves the history has ended: 3 calls, not 8
    assert client.series_calls == 3
    assert summary["chunks_fetched"] == 3


def test_a_pair_with_no_data_at_all_costs_only_two_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "RAW_DIR", tmp_path)
    client = NeverAnyData()

    f.fetch_state_commodity(
        client, "Tomato", "Karnataka", date(2018, 1, 1), date(2025, 12, 31),
        kinds=("price",), commodities=_COMMODITIES, geographies=_geo(), window_days=365,
    )

    assert client.series_calls == 2
