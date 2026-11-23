"""Orchestrate CEDA downloads into a resumable raw cache under ``data/raw/ceda/``.

Why a raw cache: CEDA keys are short-lived (the current one expires within a
week), so every API response is saved to parquet first. Mapping to our market
names and loading into TimescaleDB happen later, offline, and can be re-run
as often as needed without touching the API again.

Layout::

    data/raw/ceda/markets/{kind}__{commodity}__{state}.parquet   market lists
    data/raw/ceda/{kind}/{commodity}__{state}/{from}_{to}_m{lo}-{hi}-n{N}.parquet

A chunk file existing means "this (window, market batch) is done" — even if
empty — so interrupted runs resume where they stopped. Windows are fetched
newest first, so if the key dies early we still have the most recent years.
"""

from __future__ import annotations

import difflib
import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import structlog

from backend.config import get_settings
from backend.ingestion.ceda_client import (
    AUTH_SCHEMES,
    PRICE_COLUMNS,
    CedaClient,
    CedaError,
    CedaRateLimited,
    _first_list,
    _shape,
    quarter_windows,
)
from backend.ingestion.market_crosswalk import (
    build_crosswalk,
    is_matched,
    norm_district,
    norm_state,
    read_aliases,
)

log = structlog.get_logger(__name__)

RAW_DIR = Path("data/raw/ceda")
SCOPE_PATH = Path("data/reference/ceda_scope.csv")
ALIASES_PATH = Path("data/reference/market_aliases.csv")
KINDS = ("price", "quantity")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.casefold()).strip("-")


# After a 429 we wait and retry the same call a few times. If the server asks for
# more than MAX_AUTO_WAIT_SEC (e.g. a daily quota) we stop instead of sleeping for
# hours; every step is resumable, so just re-run the command later.
RATE_LIMIT_BACKOFF_SEC = (60, 180, 600)  # used when the server sends no Retry-After
MAX_AUTO_WAIT_SEC = 3900  # CEDA's window is one hour: wait for the reset, never for a day


def with_backoff(fn, *args, **kwargs):
    """Call ``fn``; on a 429 either wait and retry, or let it propagate.

    Waiting happens only if ``fn`` is a method of a client created with
    ``wait_on_limit=True``. By default a 429 propagates so the run stops cleanly.
    """
    if not getattr(getattr(fn, "__self__", None), "wait_on_limit", False):
        return fn(*args, **kwargs)
    waits = list(RATE_LIMIT_BACKOFF_SEC)
    while True:
        try:
            return fn(*args, **kwargs)
        except CedaRateLimited as exc:
            if not waits or (exc.retry_after or 0) > MAX_AUTO_WAIT_SEC:
                raise
            base = waits.pop(0)
            wait = exc.retry_after + 5 if exc.retry_after else base
            log.warning(
                "ceda_rate_limited_waiting", seconds=wait,
                retry_after=exc.retry_after, headers=exc.info,
            )
            time.sleep(wait)


# ----------------------------------------------------------------- resolving
def resolve_commodity(commodities: pd.DataFrame, name: str) -> tuple[int, str]:
    """CEDA id for one of OUR commodity names (exact, case-insensitive)."""
    hit = commodities[commodities["name"].str.strip().str.casefold() == name.strip().casefold()]
    if len(hit) == 1:
        return int(hit.iloc[0]["id"]), str(hit.iloc[0]["name"])
    close = commodities[commodities["name"].str.casefold().str.contains(name.strip().casefold(), regex=False)]
    raise CedaError(
        f"commodity {name!r}: expected exactly one exact match in CEDA, found {len(hit)}. "
        f"Similar names: {close['name'].tolist()[:10]}"
    )


def resolve_state(geographies: pd.DataFrame, name: str) -> tuple[int, str]:
    states = geographies[["state_id", "state_name"]].drop_duplicates()
    hit = states[states["state_name"].map(norm_state) == norm_state(name)]
    if len(hit) != 1:
        raise CedaError(
            f"state {name!r}: expected one match in CEDA, found {len(hit)}. "
            f"Available: {sorted(states['state_name'])[:40]}"
        )
    return int(hit.iloc[0]["state_id"]), str(hit.iloc[0]["state_name"])


# ------------------------------------------------------------------- scope
# CEDA has history for mandis that no longer report (and Tamil Nadu alone lists
# hundreds). With 40 API calls an hour we only download what can be used: districts
# and mandis that already appear in OUR live feed, since only those can be mapped
# onto our markets table and forecast. The scope file is written by `ceda-scope`
# from the database and is a small CSV (state, district, market, commodity) that
# can be handed to anyone running a slice of the download.
def load_scope(path: Path = SCOPE_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    missing = {"state", "district", "market", "commodity"} - set(df.columns)
    if missing:
        raise CedaError(f"{path}: missing columns {sorted(missing)}")
    return df


def _district_in_scope(name: str, scope: set[str]) -> bool:
    n = norm_district(name)
    return any(n == s or difflib.SequenceMatcher(None, n, s).ratio() >= 0.85 for s in scope)


def keep_mappable_markets(mk: pd.DataFrame, live: pd.DataFrame) -> pd.DataFrame:
    """Keep CEDA markets that match, or plausibly match, one of our live markets.

    Plausible = has at least one candidate above the review threshold, so a market
    that only needs a manual alias is still downloaded.
    """
    if mk.empty:
        return mk
    ours = (
        live[["state", "district", "market"]].drop_duplicates()
        .rename(columns={"market": "name"}).reset_index(drop=True)
    )
    ours.insert(0, "market_id", range(1, len(ours) + 1))
    ceda = mk.rename(columns={
        "market_id": "ceda_market_id", "market_name": "ceda_market_name",
        "state_name": "ceda_state", "district_name": "ceda_district",
    })[["ceda_market_id", "ceda_market_name", "ceda_state", "ceda_district"]]
    cw = build_crosswalk(ceda, ours, read_aliases(ALIASES_PATH))
    keep = cw[cw["method"].map(is_matched) | cw["candidates"].astype(str).ne("")]["ceda_market_id"]
    return mk[mk["market_id"].isin(set(keep))]


# ------------------------------------------------------------------- markets
def markets_cache_path(kind: str, commodity: str, state: str, scoped: bool = False) -> Path:
    suffix = "__scoped" if scoped else ""
    return RAW_DIR / "markets" / f"{kind}__{slug(commodity)}__{slug(state)}{suffix}.parquet"


def list_markets(
    client: CedaClient,
    commodity: tuple[int, str],
    state: tuple[int, str],
    geographies: pd.DataFrame,
    kind: str,
    only_districts: set[str] | None = None,
) -> pd.DataFrame:
    """Markets reporting ``kind`` for this commodity in this state (cached).

    With ``only_districts`` (normalised district names) just those districts are
    listed, which saves one API call per skipped district; the result is cached
    under a ``__scoped`` name so it never masquerades as the full list.

    Columns: market_id, market_name, district_id, district_name, state_id,
    state_name, commodity_id, commodity_name.
    """
    path = markets_cache_path(kind, commodity[1], state[1], scoped=only_districts is not None)
    if path.exists():
        return pd.read_parquet(path)

    cid, cname = commodity
    sid, sname = state
    districts = geographies[geographies["state_id"] == sid]
    if only_districts is not None:
        kept = districts[districts["district_name"].map(lambda n: _district_in_scope(n, only_districts))]
        log.info("ceda_districts_in_scope", state=sname, commodity=cname,
                 kept=len(kept), of=len(districts), wanted=len(only_districts))
        districts = kept
    frames: list[pd.DataFrame] = []
    for d in districts.itertuples(index=False):
        m = with_backoff(client.markets, cid, sid, d.district_id, indicator=kind)
        if m.empty:
            continue
        m = m.assign(
            district_id=int(d.district_id), district_name=d.district_name,
            state_id=sid, state_name=sname, commodity_id=cid, commodity_name=cname,
        )
        frames.append(m)
    out = (
        pd.concat(frames, ignore_index=True).drop_duplicates("market_id")
        if frames
        else pd.DataFrame(
            columns=["census_state_id", "census_district_id", "market_id", "market_name",
                     "district_id", "district_name", "state_id", "state_name",
                     "commodity_id", "commodity_name"]
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    log.info("ceda_markets_listed", kind=kind, commodity=cname, state=sname, markets=len(out))
    return out


# --------------------------------------------------------------------- fetch
def chunk_path(kind: str, commodity: str, state: str, start: date, end: date,
               batch: list[tuple[int, int]]) -> Path:
    ids = [m for m, _ in batch]
    name = f"{start.isoformat()}_{end.isoformat()}_m{min(ids)}-{max(ids)}-n{len(ids)}.parquet"
    return RAW_DIR / kind / f"{slug(commodity)}__{slug(state)}" / name


def fetch_state_commodity(
    client: CedaClient,
    commodity_name: str,
    state_name: str,
    start: date,
    end: date,
    kinds: tuple[str, ...] = KINDS,
    batch_size: int | None = None,
    commodities: pd.DataFrame | None = None,
    geographies: pd.DataFrame | None = None,
    window_days: int = 92,
    scope: pd.DataFrame | None = None,
) -> dict[str, int]:
    """Download one (commodity, state) into the raw cache. Resumable.

    With ``scope`` (see `load_scope`) only districts and mandis that exist in our live
    feed are listed and fetched; a pair with no live markets is skipped entirely.
    """
    batch_size = batch_size or get_settings().ceda_market_batch
    commodities = commodities if commodities is not None else client.commodities()
    geographies = geographies if geographies is not None else client.geographies()
    commodity = resolve_commodity(commodities, commodity_name)
    state = resolve_state(geographies, state_name)

    summary = {"chunks_fetched": 0, "chunks_skipped": 0, "rows": 0}

    live = None
    only_districts = None
    if scope is not None:
        live = scope[
            (scope["state"].map(norm_state) == norm_state(state[1]))
            & (scope["commodity"].str.strip().str.casefold() == commodity[1].casefold())
        ]
        if live.empty:
            log.warning("ceda_pair_has_no_live_markets_skipping", commodity=commodity[1], state=state[1])
            return summary
        only_districts = {norm_district(d) for d in live["district"] if norm_district(d)}

    # One market list serves both kinds. Listing costs one call per district, which is
    # the expensive part of a 40-calls-per-hour budget; markets that report arrivals but
    # never prices are rare and could not be recommended anyway.
    mk = list_markets(client, commodity, state, geographies, "price", only_districts=only_districts)
    if live is not None:
        before = len(mk)
        mk = keep_mappable_markets(mk, live)
        log.info("ceda_markets_in_scope", commodity=commodity[1], state=state[1],
                 kept=len(mk), of=before, live_markets=live["market"].nunique())
    for kind in kinds:
        if mk.empty:
            log.warning("ceda_no_markets", kind=kind, commodity=commodity[1], state=state[1])
            continue

        pairs = [
            (int(m), int(d))
            for m, d in mk.sort_values(["district_id", "market_id"])[["market_id", "district_id"]]
            .itertuples(index=False, name=None)
        ]
        batches = [pairs[i:i + batch_size] for i in range(0, len(pairs), batch_size)]
        windows = list(reversed(quarter_windows(start, end, window_days)))  # newest first

        log.info(
            "ceda_fetch_plan", kind=kind, commodity=commodity[1], state=state[1],
            markets=len(pairs), batches=len(batches), windows=len(windows),
        )
        # Windows run newest -> oldest. Mandis whose history starts late (e.g. Tamil Nadu's
        # Uzhavar Sandhais have nothing before 2024) would otherwise burn calls on empty
        # years, so stop once a whole window comes back empty after data was seen
        # (or after two empty windows in a row if none was ever seen).
        seen_data = False
        empty_run = 0
        for w0, w1 in windows:
            window_rows = 0
            for batch in batches:
                path = chunk_path(kind, commodity[1], state[1], w0, w1, batch)
                if path.exists():
                    summary["chunks_skipped"] += 1
                    window_rows += len(pd.read_parquet(path))
                    continue
                df = with_backoff(client.fetch_series, kind, commodity[0], state[0], batch, w0, w1)
                path.parent.mkdir(parents=True, exist_ok=True)
                df.to_parquet(path, index=False)
                summary["chunks_fetched"] += 1
                summary["rows"] += len(df)
                window_rows += len(df)
            log.info(
                "ceda_window_done", kind=kind, commodity=commodity[1], state=state[1],
                window=f"{w0}..{w1}", rows_so_far=summary["rows"],
                calls_left_this_hour=client.rate_info.get("ratelimit-remaining"),
            )
            if window_rows > 0:
                seen_data, empty_run = True, 0
            else:
                empty_run += 1
                if seen_data or empty_run >= 2:
                    log.info(
                        "ceda_no_older_history_stopping", kind=kind, commodity=commodity[1],
                        state=state[1], first_empty_window=f"{w0}..{w1}",
                    )
                    break
    return summary


# --------------------------------------------------------------------- probe
def _describe_rows(df: pd.DataFrame, msg: str) -> list[str]:
    out = [f"    rows: {len(df)} | API says: {msg}"]
    if df.empty:
        return out
    out.append(f"    columns: {list(df.columns)}")
    if "market_id" in df.columns:
        out.append(
            f"    market_id: {df['market_id'].nunique()} distinct, {int(df['market_id'].isna().sum())} null"
        )
    if "date" in df.columns:
        out.append(f"    dates: {df['date'].min()} .. {df['date'].max()}")
    out.append(f"    first row: {df.iloc[0].to_dict()}")
    if len(df) >= 100 and len(df) % 100 == 0:
        out.append("    NOTE: an exact multiple of 100 rows usually means a response cap")
    return out


def explore(commodity_id: int = 78, state_id: int = 29, year: int = 2022) -> list[str]:
    """Spend 3 API calls to learn whether a WHOLE STATE can be fetched at once.

    The budget is 40 calls/hour per key, so the download is only feasible if one
    request can return every market of a state. No lookup calls are made: ids are
    passed in (defaults: Tomato=78, Karnataka=29, both confirmed by `ceda-probe`).
    """
    lines = [f"commodity_id={commodity_id} state_id={state_id} year={year}"]
    client = CedaClient()
    try:
        _explore_inner(client, lines, commodity_id, state_id, year)
    except CedaRateLimited as exc:
        lines.append(f"\nSTOPPED: out of calls for this hour. {exc}")
    lines.append("")
    lines.append(f"calls used: {client.requests_made} | rate-limit headers: {client.rate_info}")
    return lines


def _explore_inner(client: CedaClient, lines: list[str], cid: int, sid: int, year: int) -> None:
    def attempt(title: str, fn) -> None:
        lines.append("")
        lines.append(title)
        try:
            lines.extend(fn())
        except CedaRateLimited:
            raise
        except CedaError as exc:
            lines.append(f"    ERROR: {str(exc)[:300]}")

    def markets_whole_state() -> list[str]:
        resp = client._request(
            "POST", "/agmarknet/markets",
            {"commodity_id": cid, "state_id": sid, "indicator": "price"},
        )
        out = resp.get("output", {}) if isinstance(resp, dict) else {}
        df = pd.DataFrame(_first_list(resp, ("data", "markets")))
        res = [f"    rows: {len(df)} | API says: {out.get('type')}: {out.get('message')}"]
        if len(df):
            res.append(f"    columns: {list(df.columns)}")
            res.append(f"    examples: {df.head(3).to_dict('records')}")
        return res

    def series_whole_state(path: str):
        def run() -> list[str]:
            resp = client._request(
                "POST", path,
                {"commodity_id": cid, "state_id": sid,
                 "from_date": f"{year}-01-01", "to_date": f"{year}-12-31"},
            )
            out = resp.get("output", {}) if isinstance(resp, dict) else {}
            df = pd.DataFrame(_first_list(resp, ("data",)))
            return _describe_rows(df, f"{out.get('type')}: {out.get('message')}")
        return run

    attempt("1) markets for the whole state (no district_id)", markets_whole_state)
    attempt(f"2) prices, whole state, {year}, no district/market filter", series_whole_state("/agmarknet/prices"))
    attempt(f"3) quantities, whole state, {year}, no district/market filter", series_whole_state("/agmarknet/quantities"))


def _cap_test(client: CedaClient, commodity, state, geographies, lines: list[str]) -> None:
    """One whole year for every market of a state in a single request: reveals any row cap."""
    lines.append("")
    lines.append("CAP TEST (every Karnataka tomato market, one whole year, in ONE request):")
    mk_all = list_markets(client, commodity, state, geographies, "price")
    pairs = [
        (int(m), int(d))
        for m, d in mk_all[["market_id", "district_id"]].itertuples(index=False, name=None)
    ]
    if len(pairs) < 10:
        lines.append(f"  only {len(pairs)} markets listed; cap test skipped")
        return
    df = client._series(
        "/agmarknet/prices", PRICE_COLUMNS, commodity[0], state[0], pairs,
        date(2022, 1, 1), date(2022, 12, 31),
    )
    lines.append(
        f"  {len(pairs)} markets listed -> {len(df)} rows | {df['date'].min()} .. {df['date'].max()} "
        f"| {df['market_id'].nunique()} markets answered | API says: {client.last_message}"
    )


def probe(cap_test: bool = False) -> list[str]:
    """Run the probe; any API problem is reported as a line, not a traceback."""
    lines: list[str] = []
    try:
        result = _probe_inner(lines, cap_test)
        if result is not lines:
            lines.extend(result)
    except CedaError as exc:
        lines.append(f"ERROR: {exc}")
    return lines


def _probe_inner(lines: list[str], cap_test: bool = False) -> list[str]:
    """Work out base URL + auth scheme, then show what a real request returns.

    Prints no secrets. The sample request also reveals the response size cap
    and whether ``to_date`` is inclusive, which the fetch code is defensive about.
    """
    s = get_settings()
    key = s.ceda_api_key
    if not key:
        return ["CEDA_API_KEY is empty. Put it in .env (CEDA_API_KEY=...) and re-run."]

    root = s.ceda_base_url.rstrip("/")
    bases = list(dict.fromkeys([root, f"{root}/v1", f"{root}/api", f"{root}/api/v1"]))
    lines.append("")  # (lines is shared with probe())
    session = requests.Session()
    found: tuple[str, str] | None = None

    for base in bases:
        for scheme, make in AUTH_SCHEMES.items():
            try:
                r = session.get(
                    f"{base}/agmarknet/commodities",
                    headers={**make(key), "Accept": "application/json"},
                    timeout=30,
                )
            except requests.RequestException as exc:
                lines.append(f"{base}  [{scheme}]  network error: {type(exc).__name__}")
                break
            lines.append(f"{base}  [{scheme}]  HTTP {r.status_code}")
            if r.status_code == 200:
                found = (base, scheme)
                break
            if r.status_code == 404:
                break  # wrong base path; no point trying other schemes here
            time.sleep(0.5)
        if found:
            break

    if not found:
        lines.append("")
        lines.append("No combination worked. Check the key is valid (it expires) and send me "
                     "the 'Authorize' dialog from the Swagger page.")
        return lines

    base, scheme = found
    lines += ["", f"WORKS -> CEDA_BASE_URL={base}  CEDA_AUTH_SCHEME={scheme}", ""]

    client = CedaClient(api_key=key, base_url=base, auth_scheme=scheme)
    raw_c = client._request("GET", "/agmarknet/commodities")
    raw_g = client._request("GET", "/agmarknet/geographies")
    lines.append("commodities shape: " + _shape(raw_c))
    lines.append("commodities raw:   " + json.dumps(raw_c)[:300])
    lines.append("geographies shape: " + _shape(raw_g))
    lines.append("geographies raw:   " + json.dumps(raw_g)[:400])
    commodities = client.commodities()
    geographies = client.geographies()
    lines.append(f"commodities: {len(commodities)} | states: {geographies['state_id'].nunique()} "
                 f"| districts: {len(geographies)}")

    try:
        commodity = resolve_commodity(commodities, "Tomato")
        state = resolve_state(geographies, "Karnataka")
    except CedaError as exc:
        lines.append(f"could not resolve sample Tomato/Karnataka: {exc}")
        return lines
    lines.append(f"Tomato -> id {commodity[0]} | Karnataka -> id {state[0]}")

    sample: list[tuple[int, int]] = []
    for d in geographies[geographies["state_id"] == state[0]].itertuples(index=False):
        m = client.markets(commodity[0], state[0], d.district_id, indicator="price")
        lines.append(f"  markets(price) in {d.district_name}: {len(m)}")
        sample += [(int(x), int(d.district_id)) for x in m["market_id"]]
        if len(sample) >= 3:
            break
    sample = sample[:3]
    if not sample:
        lines.append("no markets returned for the sample; stopping here")
        return lines

    def run(label: str, kind: str, cid: int, sid: int, mk: list[tuple[int, int]], a: date, b: date) -> None:
        # max_rows is huge on purpose: we want to SEE the raw count, not trigger the splitter.
        df = client.fetch_series(kind, cid, sid, mk, a, b, max_rows=10**9)
        msg = f" | API says: {client.last_message}" if client.last_message else ""
        if df.empty:
            lines.append(f"  {label:<22} {kind:<8} 0 rows{msg}")
        else:
            lines.append(
                f"  {label:<22} {kind:<8} {len(df):>5} rows | {df['date'].min()} .. {df['date'].max()} "
                f"| markets {df['market_id'].nunique()}{msg}"
            )

    lines.append("")
    lines.append("CONTROL (the Wheat example from the Swagger page, known to return data):")
    run("Wheat 2025-03..06", "price", 1, 8, [(255, 104), (3149, 104)], date(2025, 3, 1), date(2025, 6, 1))

    lines.append(f"Tomato / Karnataka, markets {[m for m, _ in sample]}:")
    for label, a, b in (
        ("Jul-Sep 2025", date(2025, 7, 1), date(2025, 9, 30)),
        ("Jan-Jun 2025", date(2025, 1, 1), date(2025, 6, 30)),
        ("2024", date(2024, 1, 1), date(2024, 12, 31)),
        ("2022", date(2022, 1, 1), date(2022, 12, 31)),
        ("2018", date(2018, 1, 1), date(2018, 12, 31)),
    ):
        run(label, "price", commodity[0], state[0], sample, a, b)
    run("2024", "quantity", commodity[0], state[0], sample, date(2024, 1, 1), date(2024, 12, 31))

    if cap_test:
        _cap_test(client, commodity, state, geographies, lines)
    else:
        lines.append("")
        lines.append("(cap test skipped: add --cap-test; it makes ~30 extra API calls)")
    lines.append(f"requests made by this probe: {client.requests_made}")

    lines.append("")
    lines.append("If a count above is a round number (1000, 5000...), tell me: that is the response cap.")
    return lines
