"""Load cached CEDA data into `market_daily`, under OUR market names.

Pipeline (offline — never calls the CEDA API):

    data/raw/ceda/**.parquet  --join price+quantity-->  panel keyed by CEDA market id
        --crosswalk-->  OUR (state, district, market)  --upsert_panel-->  market_daily

Only CEDA markets that map to an existing row of our `markets` table are
loaded; nothing in our table is renamed and no new markets are created from
CEDA spellings. Unmatched markets are listed (largest first) in
``data/processed/ceda_market_crosswalk.csv`` so they can be resolved through
``data/reference/market_aliases.csv`` and the load re-run.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import structlog
from sqlalchemy import text

from backend.db.connection import session_scope
from backend.ingestion.ceda_fetch import RAW_DIR, SCOPE_PATH, markets_cache_path, slug
from backend.ingestion.market_crosswalk import (
    build_crosswalk,
    is_matched,
    read_aliases,
)
from backend.ingestion.upsert import upsert_panel

log = structlog.get_logger(__name__)

CROSSWALK_PATH = Path("data/processed/ceda_market_crosswalk.csv")
ALIASES_PATH = Path("data/reference/market_aliases.csv")
SOURCE = "ceda"
UPSERT_CHUNK = 20_000


# ------------------------------------------------------------------ readers
def read_chunks(kind: str, commodity: str, state: str) -> pd.DataFrame:
    folder = RAW_DIR / kind / f"{slug(commodity)}__{slug(state)}"
    files = sorted(folder.glob("*.parquet"))
    frames = [pd.read_parquet(f) for f in files]
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(subset=["date", "market_id"], keep="last")


def read_market_meta(commodity: str, state: str) -> pd.DataFrame:
    frames = []
    for kind in ("price", "quantity"):
        for scoped in (False, True):
            p = markets_cache_path(kind, commodity, state, scoped=scoped)
            if p.exists():
                frames.append(pd.read_parquet(p))
    if not frames:
        return pd.DataFrame(columns=["market_id", "market_name", "district_name", "state_name"])
    return pd.concat(frames, ignore_index=True).drop_duplicates("market_id")


def build_panel(commodity: str, state: str) -> pd.DataFrame:
    """Price + arrivals per (date, CEDA market). Quantity is tonnes/day."""
    prices = read_chunks("price", commodity, state)
    qty = read_chunks("quantity", commodity, state)
    if prices.empty and qty.empty:
        return pd.DataFrame()

    if prices.empty:
        prices = pd.DataFrame(columns=["date", "market_id", "min_price", "max_price", "modal_price"])
    if qty.empty:
        qty = pd.DataFrame(columns=["date", "market_id", "quantity"])

    panel = prices[["date", "market_id", "min_price", "max_price", "modal_price"]].merge(
        qty[["date", "market_id", "quantity"]], on=["date", "market_id"], how="outer"
    )
    # A zero price is a placeholder, not a price.
    for c in ("min_price", "max_price", "modal_price", "quantity"):
        panel[c] = pd.to_numeric(panel[c], errors="coerce")
    for c in ("min_price", "max_price", "modal_price"):
        panel.loc[panel[c] <= 0, c] = float("nan")
    panel.loc[panel["quantity"] < 0, "quantity"] = float("nan")
    panel = panel.dropna(subset=["modal_price", "quantity"], how="all")
    panel["market_id"] = panel["market_id"].astype("int64")
    return panel.reset_index(drop=True)


def load_our_markets() -> pd.DataFrame:
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT m.id AS market_id, s.name AS state, COALESCE(m.district, '') AS district, "
                "m.name AS name FROM markets m JOIN states s ON s.id = m.state_id"
            )
        ).all()
    return pd.DataFrame([tuple(r) for r in rows], columns=["market_id", "state", "district", "name"])


def write_scope(path: Path = SCOPE_PATH) -> pd.DataFrame:
    """Write (state, district, market, commodity) for every mandi in our live data.

    This is the list of mandis the download is limited to. It is a small CSV so it can
    be committed and handed to anyone running a slice of `ceda-fetch` (no DB needed there).
    """
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT DISTINCT s.name AS state, COALESCE(m.district, '') AS district, "
                "m.name AS market, c.name AS commodity "
                "FROM market_daily d "
                "JOIN markets m ON m.id = d.market_id "
                "JOIN states s ON s.id = m.state_id "
                "JOIN commodities c ON c.id = d.commodity_id"
            )
        ).all()
    df = pd.DataFrame([tuple(r) for r in rows], columns=["state", "district", "market", "commodity"])
    df = df.sort_values(["state", "commodity", "district", "market"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("ceda_scope_written", path=str(path), rows=len(df),
             markets=df[["state", "district", "market"]].drop_duplicates().shape[0])
    return df


# ---------------------------------------------------------------- crosswalk
def run_map(states: list[str], commodities: list[str]) -> pd.DataFrame:
    """Build the crosswalk for all cached (state, commodity) pairs and write the review CSV."""
    ours = load_our_markets()
    if ours.empty:
        raise RuntimeError(
            "Our `markets` table is empty. Run `pull-datagovin` (or `load-snapshots`) first."
        )

    metas, counts = [], []
    for st in states:
        for cm in commodities:
            meta = read_market_meta(cm, st)
            if meta.empty:
                continue
            metas.append(meta)
            panel = build_panel(cm, st)
            if not panel.empty:
                counts.append(panel.groupby("market_id").size().rename("n_rows").reset_index())

    if not metas:
        raise RuntimeError(
            "No cached CEDA market lists found under data/raw/ceda/markets/. Run `ceda-fetch` first."
        )

    meta = pd.concat(metas, ignore_index=True).drop_duplicates("market_id")
    ceda = meta.rename(columns={
        "market_id": "ceda_market_id", "market_name": "ceda_market_name",
        "state_name": "ceda_state", "district_name": "ceda_district",
    })[["ceda_market_id", "ceda_market_name", "ceda_state", "ceda_district"]]
    if counts:
        n = pd.concat(counts).groupby("market_id")["n_rows"].sum().reset_index()
        ceda = ceda.merge(
            n.rename(columns={"market_id": "ceda_market_id"}), on="ceda_market_id", how="left"
        )
    if "n_rows" not in ceda.columns:
        ceda["n_rows"] = 0
    ceda["n_rows"] = ceda["n_rows"].fillna(0).astype(int)

    cw = build_crosswalk(ceda, ours, read_aliases(ALIASES_PATH))
    cw["matched"] = cw["method"].map(is_matched)
    cw = cw.sort_values(["matched", "n_rows"], ascending=[True, False])
    CROSSWALK_PATH.parent.mkdir(parents=True, exist_ok=True)
    cw.to_csv(CROSSWALK_PATH, index=False)

    total = cw["n_rows"].sum()
    got = cw.loc[cw["matched"], "n_rows"].sum()
    log.info(
        "ceda_crosswalk_built",
        ceda_markets=len(cw),
        matched=int(cw["matched"].sum()),
        by_method=cw["method"].value_counts().to_dict(),
        rows_covered_pct=round(100 * got / total, 1) if total else None,
        path=str(CROSSWALK_PATH),
    )
    return cw


# --------------------------------------------------------------------- load
def _to_upsert_frame(joined: pd.DataFrame, commodity: str) -> pd.DataFrame:
    """Shape matched rows like `normalize()` output, using OUR market names."""
    out = pd.DataFrame({
        "state": joined["our_state"],               # OUR names, untouched
        "district": joined["our_district"].fillna(""),
        "market": joined["our_name"],
        "commodity": commodity,
        "variety": "",
        "date": pd.to_datetime(joined["date"]).dt.date,
        "min_price": joined["min_price"].astype(float),
        "modal_price": joined["modal_price"].astype(float),
        "max_price": joined["max_price"].astype(float),
        "arrival_tonnes": joined["quantity"].astype(float),
    })
    # Two CEDA ids can map to one of our markets: keep the row that has a price.
    out = (
        out.assign(_has_price=out["modal_price"].notna())
        .sort_values("_has_price", ascending=False)
        .drop_duplicates(["state", "district", "market", "commodity", "date"])
        .drop(columns="_has_price")
        .reset_index(drop=True)
    )
    # NaN must become SQL NULL — a float NaN would be stored as numeric 'NaN'.
    num = ["min_price", "modal_price", "max_price", "arrival_tonnes"]
    out[num] = out[num].astype(object).where(out[num].notna(), None)
    return out


def run_load(states: list[str], commodities: list[str], dry_run: bool = False) -> dict[str, int]:
    markets_before = len(load_our_markets())
    cw = run_map(states, commodities)
    mapping = cw[cw["matched"]].set_index("ceda_market_id")[
        ["our_state", "our_district", "our_name"]
    ]

    summary = {
        "markets_matched": int(cw["matched"].sum()),
        "markets_unmatched": int((~cw["matched"]).sum()),
        "rows_total": 0,
        "rows_matched": 0,
        "rows_loaded": 0,
    }

    for st in states:
        for cm in commodities:
            panel = build_panel(cm, st)
            if panel.empty:
                log.warning("ceda_no_cached_rows", state=st, commodity=cm)
                continue
            summary["rows_total"] += len(panel)

            joined = panel.join(mapping, on="market_id", how="inner")
            summary["rows_matched"] += len(joined)
            if joined.empty:
                continue

            out = _to_upsert_frame(joined, cm)
            first, last = str(out["date"].min()), str(out["date"].max())

            if dry_run:
                log.info("ceda_dry_run", state=st, commodity=cm, rows=len(out), first=first, last=last)
                continue

            for i in range(0, len(out), UPSERT_CHUNK):
                with session_scope() as session:
                    summary["rows_loaded"] += upsert_panel(
                        session, out.iloc[i:i + UPSERT_CHUNK], source=SOURCE
                    )
            log.info("ceda_loaded", state=st, commodity=cm, rows=len(out), first=first, last=last)

    if not dry_run:
        markets_after = len(load_our_markets())
        if markets_after != markets_before:
            # Should never happen: we pass our own names back in. If it does, a name
            # round-trip (e.g. NULL vs '' district) created a duplicate market.
            log.error("ceda_load_created_markets", before=markets_before, after=markets_after)
        summary["new_markets_created"] = markets_after - markets_before
    return summary
