"""Map CEDA market identities onto OUR market rows.

Rule of this module: **our `markets` table is canonical.** It was built from
the live data.gov.in feed and the recommender, API and UI all use its names.
We never rename, merge or edit an existing market. CEDA rows are translated
*into* our (state, district, name) triple, or left unmatched for a human to
review. If CEDA calls a mandi ``Hyderabad_Bowenpally`` and we call it
``Hyderabad_BWP``, the CEDA history is stored under ``Hyderabad_BWP``.

Matching is deliberately conservative (a wrong match silently mixes two
mandis' price histories, which is worse than a missing one):

1. manual overrides in ``data/reference/market_aliases.csv`` always win;
2. otherwise names are normalised (case, punctuation, noise words such as
   "APMC", and known spelling groups such as "Rythu Bazar" / "RBZ") and
   compared, restricted to the same state;
3. an exact normalised match is accepted (district breaks ties);
4. a fuzzy match is accepted only when it is strong, the district agrees (or
   the score is very high) and it clearly beats the runner-up;
5. everything else is reported as ``unmatched`` / ``ambiguous`` together with
   the closest candidates.

Pure functions only (pandas + stdlib) so they are easy to test.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

import pandas as pd

ALIASES_COLUMNS = ["ceda_market_id", "state", "district", "market", "ignore", "notes"]

# Words that carry no identity ("Kukatpally APMC" == "Kukatpally"). PMY / SMY are the
# Principal / Sub Market Yard prefixes Himachal Pradesh uses ("PMY Bilaspur" == "Bilaspur").
_NOISE_TOKENS = {"apmc", "market", "mandi", "yard", "mkt", "pmy", "smy"}

# Spelling groups seen in Agmarknet / data.gov.in. Applied before tokenising.
_SYNONYMS: list[tuple[str, str]] = [
    (r"\brythu\s*ba[sz]aa?r\b", "rythubazar"),
    (r"\brythubazaa?r\b", "rythubazar"),
    (r"\brbz\b", "rythubazar"),
    (r"\buzhavar\s*sandhai\b", "uzhavarsandhai"),
    (r"\bkrishi\s*utpanna\b", "krishiutpanna"),
]

# State spellings that differ between sources. Keys/values are already normalised.
_STATE_ALIASES = {
    "keralam": "kerala",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "pondicherry": "puducherry",
    "nct of delhi": "delhi",
    "jammu and kashmir": "jammu kashmir",
    "andaman and nicobar islands": "andaman nicobar",
}

# Thresholds (see module docstring).
EXACT = 1.0
FUZZY_MIN = 0.88
FUZZY_NO_DISTRICT_MIN = 0.95
FUZZY_MARGIN = 0.04
CANDIDATE_MIN = 0.60


def _clean(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    text = str(s).casefold().replace("&", " and ")
    return text


def norm_state(s: object) -> str:
    """Normalise a state name so 'Keralam' == 'Kerala' etc."""
    t = re.sub(r"[^a-z0-9]+", " ", _clean(s)).strip()
    return _STATE_ALIASES.get(t, t)


def norm_name(s: object) -> str:
    """Normalise a market name for comparison (never used to *store* a name).

    Lower-cases, applies spelling groups, drops punctuation and noise words,
    and sorts the remaining tokens so word order does not matter
    ('RYTHU BAZAR MEHDIPATNAM' ~ 'Mehdipatnam(Rythu Bazar)').
    """
    t = _clean(s)
    for pattern, repl in _SYNONYMS:
        t = re.sub(pattern, repl, t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    tokens = [tok for tok in t.split() if tok not in _NOISE_TOKENS]
    return " ".join(sorted(tokens))


def norm_district(s: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(s)).strip()


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _district_agrees(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return a == b or _ratio(a, b) >= 0.85


def read_aliases(path: Path) -> pd.DataFrame:
    """Read the manual override file; a missing/empty file means no overrides."""
    if not path.exists():
        return pd.DataFrame(columns=ALIASES_COLUMNS)
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in ALIASES_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[ALIASES_COLUMNS]


def _find_ours(ours: pd.DataFrame, state: str, district: str, name: str) -> pd.Series | None:
    """Exact (case-insensitive) lookup of one of OUR markets by its natural key."""
    hit = ours[
        (ours["state"].map(norm_state) == norm_state(state))
        & (ours["district"].map(norm_district) == norm_district(district))
        & (ours["name"].str.strip().str.casefold() == str(name).strip().casefold())
    ]
    return hit.iloc[0] if len(hit) else None


def _paren_match(raw_name: object, c_dist: str, scored: list) -> tuple | None:
    """'Kangra(Baijnath)' is the Baijnath yard in Kangra district: match on the bracketed part.

    Accepted only if exactly one of our markets has that name AND its district agrees, so
    'Kangra(Jassour)' can never be mistaken for the main 'Kangra' market.
    """
    inner = re.findall(r"\(([^)]*)\)", str(raw_name))
    inner_n = norm_name(inner[0]) if inner else ""
    if not inner_n:
        return None
    if inner_n == norm_name(c_dist):
        # 'Namhol(Bilaspur)': the bracket names the DISTRICT, not the market. Matching it
        # would blend Namhol into the main Bilaspur market.
        return None
    hits = [t for t in scored if t[2].name_n == inner_n and t[1]]  # t[1]: district agrees
    return hits[0] if len(hits) == 1 else None


def build_crosswalk(
    ceda: pd.DataFrame,
    ours: pd.DataFrame,
    overrides: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Match each CEDA market to one of our markets (or to nothing).

    Args:
        ceda: columns ``ceda_market_id, ceda_market_name, ceda_state, ceda_district``
            (and optionally ``n_rows``), one row per CEDA market.
        ours: columns ``market_id, state, district, name`` from our DB. Read-only.
        overrides: contents of ``market_aliases.csv`` (see ``ALIASES_COLUMNS``).

    Returns one row per CEDA market with ``market_id`` (ours, NaN if none),
    the matched ``our_state/our_district/our_name``, ``score``, ``method`` and
    the best alternative ``candidates`` for review.
    """
    ours = ours.copy()
    ours["state_n"] = ours["state"].map(norm_state)
    ours["name_n"] = ours["name"].map(norm_name)
    ours["dist_n"] = ours["district"].map(norm_district)

    ov: dict[str, pd.Series] = {}
    if overrides is not None and len(overrides):
        for _, r in overrides.iterrows():
            key = str(r["ceda_market_id"]).strip()
            if key:
                ov[key] = r

    out: list[dict] = []
    for c in ceda.drop_duplicates("ceda_market_id").itertuples(index=False):
        rec = {
            "ceda_market_id": c.ceda_market_id,
            "ceda_market_name": c.ceda_market_name,
            "ceda_state": c.ceda_state,
            "ceda_district": c.ceda_district,
            "n_rows": getattr(c, "n_rows", None),
            "market_id": None,
            "our_state": None,
            "our_district": None,
            "our_name": None,
            "score": 0.0,
            "method": "unmatched",
            "candidates": "",
        }

        # 1) manual override
        o = ov.get(str(c.ceda_market_id))
        if o is not None:
            if str(o["ignore"]).strip().lower() in {"1", "true", "yes", "y"}:
                rec["method"] = "ignored"
                out.append(rec)
                continue
            hit = _find_ours(ours, o["state"], o["district"], o["market"])
            if hit is None:
                rec["method"] = "override_not_found"
                rec["candidates"] = f"override points at missing market: {o['state']}/{o['district']}/{o['market']}"
            else:
                rec.update(
                    market_id=int(hit["market_id"]), our_state=hit["state"],
                    our_district=hit["district"], our_name=hit["name"],
                    score=1.0, method="override",
                )
            out.append(rec)
            continue

        # 2) candidates in the same state
        c_state = norm_state(c.ceda_state)
        c_name = norm_name(c.ceda_market_name)
        c_dist = norm_district(c.ceda_district)
        pool = ours[ours["state_n"] == c_state]
        if pool.empty or not c_name:
            out.append(rec)
            continue

        scored = []
        for m in pool.itertuples(index=False):
            s = 1.0 if m.name_n == c_name else _ratio(c_name, m.name_n)
            scored.append((s, _district_agrees(c_dist, m.dist_n), m))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)

        rec["candidates"] = "; ".join(
            f"{m.name} [{m.district}] {s:.2f}" for s, _, m in scored[:3] if s >= CANDIDATE_MIN
        )

        exact = [t for t in scored if t[0] >= EXACT]
        chosen = None
        method = "unmatched"
        if exact:
            if len(exact) == 1:
                chosen, method = exact[0], "exact"
            else:
                same_dist = [t for t in exact if t[1]]
                if len(same_dist) == 1:
                    chosen, method = same_dist[0], "exact"
                else:
                    method = "ambiguous"
        else:
            paren = _paren_match(c.ceda_market_name, c_dist, scored)
            best = scored[0]
            runner = scored[1][0] if len(scored) > 1 else 0.0
            strong = best[0] >= FUZZY_MIN and (best[1] or best[0] >= FUZZY_NO_DISTRICT_MIN)
            if paren is not None:
                chosen, method = paren, "exact_paren"
            elif strong and best[0] - runner >= FUZZY_MARGIN:
                chosen, method = best, "fuzzy"
            elif best[0] >= FUZZY_MIN:
                method = "ambiguous"

        rec["method"] = method
        if chosen is not None:
            s, _, m = chosen
            rec.update(
                market_id=int(m.market_id), our_state=m.state, our_district=m.district,
                our_name=m.name, score=0.99 if method == "exact_paren" else round(float(s), 3),
            )
        out.append(rec)

    return pd.DataFrame(out)


MATCHED_METHODS = {"exact", "exact_paren", "fuzzy", "override"}


def is_matched(method: str) -> bool:
    return method in MATCHED_METHODS
