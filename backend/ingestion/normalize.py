"""Normalize a raw Agmarknet DataFrame into the schema of `market_daily`.

The SDK returns column names that differ slightly by version. We normalize
column names via a lenient mapping, coerce dates from DD/MM/YYYY to ISO,
coerce numeric fields, dedupe on the natural key, and drop rows that are
missing an essential field (date, market, commodity).
"""

from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd
import structlog

log = structlog.get_logger(__name__)

# Lenient mapping — lowercased, underscore-normalized source name → canonical name.
# Extend as new SDK versions surface new spellings.
_COLUMN_ALIASES: dict[str, str] = {
    "state": "state",
    "state_name": "state",

    "district": "district",
    "district_name": "district",

    "market": "market",
    "market_name": "market",

    "commodity": "commodity",
    "commodity_name": "commodity",
    "cmdt_name": "commodity",           # agmarknet v0.2.x

    "variety": "variety",
    "variety_name": "variety",           # agmarknet v0.2.x

    "price_date": "date",
    "date": "date",
    "arrival_date": "date",
    "reported_date": "date",

    "min_price": "min_price",
    "min_x0020_price": "min_price",
    "modal_price": "modal_price",
    "model_price": "modal_price",        # SDK typo — "model" instead of "modal"
    "modal_x0020_price": "modal_price",
    "max_price": "max_price",
    "max_x0020_price": "max_price",

    "arrivals": "arrival_tonnes",
    "arrival": "arrival_tonnes",
    "arrival_qty": "arrival_tonnes",     # agmarknet v0.2.x — units read from unit_name_arrival
    "arrivals_in_tonnes": "arrival_tonnes",
    "arrivals_tonnes": "arrival_tonnes",

    # Unit hint (kept for the unit-guard in normalize()).
    "unit_name_arrival": "arrival_unit",
    "unit_name_price": "price_unit",
}


def _canonical(col: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", col.strip().lower()).strip("_")
    return _COLUMN_ALIASES.get(key, key)


def _parse_date(value: object) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Agmarknet commonly emits DD/MM/YYYY. Fall back through a few known formats.
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    log.warning("date_parse_failed", value=s)
    return None


def _to_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s or s.upper() in {"NA", "NR", "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with canonical columns and deduped rows.

    Output columns: state, district, market, commodity, variety, date,
    min_price, modal_price, max_price, arrival_tonnes.
    """
    if raw.empty:
        return pd.DataFrame(
            columns=[
                "state", "district", "market", "commodity", "variety", "date",
                "min_price", "modal_price", "max_price", "arrival_tonnes",
            ]
        )

    df = raw.copy()
    df.columns = [_canonical(c) for c in df.columns]

    # Collapse duplicate canonical columns (SDK sometimes emits both `state`
    # and `state_name`). Keep first non-null.
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    required = ["state", "market", "commodity", "date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"normalize: required columns missing after aliasing: {missing}")

    # Fill missing optional columns.
    for col in ("district", "variety", "min_price", "modal_price", "max_price", "arrival_tonnes"):
        if col not in df.columns:
            df[col] = None

    df["date"] = df["date"].map(_parse_date)
    for col in ("min_price", "modal_price", "max_price", "arrival_tonnes"):
        df[col] = df[col].map(_to_float)

    # Unit guard on arrivals. The SDK reports the unit per row in
    # `unit_name_arrival` (aliased to `arrival_unit`). Convert Quintal→Tonne
    # (100 kg → 1000 kg, i.e. divide by 10). Log unknown units so we notice.
    if "arrival_unit" in df.columns:
        units = df["arrival_unit"].fillna("").astype(str).str.strip().str.lower()
        quintal_mask = units.isin({"quintal", "quintals", "qtl"})
        tonne_mask = units.isin({"tonne", "tonnes", "ton", "tons", "t", "mt"})
        unknown_mask = ~(quintal_mask | tonne_mask | units.eq(""))
        if quintal_mask.any():
            df.loc[quintal_mask, "arrival_tonnes"] = (
                df.loc[quintal_mask, "arrival_tonnes"].astype(float) / 10.0
            )
            log.info("normalize_units_converted", from_unit="quintal", to_unit="tonne",
                     rows=int(quintal_mask.sum()))
        if unknown_mask.any():
            unknown_vals = sorted(set(units[unknown_mask]))
            log.warning("normalize_unknown_arrival_unit", samples=unknown_vals[:5],
                        rows=int(unknown_mask.sum()))

    for col in ("state", "district", "market", "commodity", "variety"):
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Drop rows with no date or no market — they cannot map to `market_daily`.
    before = len(df)
    df = df.dropna(subset=["date"])
    df = df[(df["market"] != "") & (df["commodity"] != "") & (df["state"] != "")]
    dropped = before - len(df)
    if dropped:
        log.warning("normalize_dropped_rows", count=dropped, reason="missing_key_field")

    # Dedupe on natural key. Keep last occurrence — later revisions win.
    df = df.drop_duplicates(
        subset=["date", "state", "district", "market", "commodity", "variety"],
        keep="last",
    )

    return df[
        [
            "state", "district", "market", "commodity", "variety", "date",
            "min_price", "modal_price", "max_price", "arrival_tonnes",
        ]
    ].reset_index(drop=True)
