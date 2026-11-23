"""Client for the CEDA Agri-Market Data API (https://api.ceda.ashoka.edu.in).

CEDA republishes Agmarknet market-level daily prices and arrivals. It is the
project's source of *history* now that the Agmarknet API itself sits behind a
CAPTCHA and data.gov.in only serves the current day.

Endpoints used (documentation: https://api.ceda.ashoka.edu.in/documentation/):

    GET  /agmarknet/commodities
    GET  /agmarknet/geographies
    POST /agmarknet/markets     {commodity_id, state_id, district_id, indicator}
    POST /agmarknet/prices      {commodity_id, state_id, district_id[], market_id[], from_date, to_date}
    POST /agmarknet/quantities  (same body as prices)

Terms of use: free, non-commercial, rate limited, and CEDA must be credited
wherever its data is shown. The API key lives in ``CEDA_API_KEY`` (.env, which
is git-ignored). Never hard-code it; it also expires.

Two defensive behaviours matter more than they look:

* **Truncation guard.** The CEDA web CSV silently stops at 1,000 rows. The API
  documents no paging, so a response with ``>= ceda_max_rows`` rows is assumed
  to be cut off and is re-requested in halves (by market, then by date) until
  every piece comes back below the cap.
* **Overlapping windows.** Whether ``to_date`` is inclusive is not documented,
  so consecutive windows share their boundary day and results are de-duplicated
  on (date, market). Over-fetching one day is harmless; losing one is not.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import date, timedelta

import pandas as pd
import requests
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings

log = structlog.get_logger(__name__)

REQUEST_TIMEOUT_SEC = 60

PRICE_COLUMNS = [
    "date", "commodity_id", "census_state_id", "census_district_id",
    "market_id", "min_price", "max_price", "modal_price",
]
QUANTITY_COLUMNS = [
    "date", "commodity_id", "census_state_id", "census_district_id",
    "market_id", "quantity",
]
_NUMERIC = {
    "commodity_id", "census_state_id", "census_district_id", "market_id",
    "min_price", "max_price", "modal_price", "quantity",
}

# How the key is sent. The Swagger page marks the endpoints as locked but the
# scheme is not in the endpoint documentation, so `ceda-probe` tries these.
AUTH_SCHEMES = {
    "x-api-key": lambda key: {"x-api-key": key},
    "bearer": lambda key: {"Authorization": f"Bearer {key}"},
    "authorization": lambda key: {"Authorization": key},
    "api-key": lambda key: {"api-key": key},
}


class CedaError(RuntimeError):
    """Unusable response from the CEDA API."""


class CedaAuthError(CedaError):
    """401/403: bad, missing or expired key (or wrong auth scheme)."""


class CedaTransientError(CedaError):
    """5xx / network problem — safe to retry shortly."""


class CedaRateLimited(CedaError):
    """429 Too Many Requests. Not retried here: the caller decides how long to wait.

    ``retry_after`` is the server's Retry-After in seconds (None if it sent none);
    ``info`` holds any rate-limit headers it returned.
    """

    def __init__(self, retry_after: float | None, info: dict[str, str], body: str = "") -> None:
        self.retry_after = retry_after
        self.info = info
        super().__init__(f"429 too many requests | retry-after={retry_after} | headers={info} | body={body}")


def quarter_windows(start: date, end: date, days: int = 92) -> list[tuple[date, date]]:
    """Consecutive ~quarterly windows covering [start, end].

    Neighbouring windows share their boundary day on purpose (see module doc).
    """
    if start >= end:
        return [(start, end)]
    out: list[tuple[date, date]] = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        if (end - nxt).days <= 7:
            nxt = end  # fold a leftover few days into this window: each window costs API calls
        out.append((cur, nxt))
        cur = nxt
    return out


def _combine(parts: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    parts = [p for p in parts if len(p)]
    if not parts:
        return pd.DataFrame(columns=columns)
    df = pd.concat(parts, ignore_index=True)
    return df.drop_duplicates(subset=["date", "market_id"], keep="last").reset_index(drop=True)


def _coerce(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for c in columns:
        if c not in df.columns:
            df[c] = None
    df = df[columns].copy()
    for c in columns:
        if c in _NUMERIC:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = df["date"].astype(str).str[:10]
    return df


def _first_list(body: object, preferred: Sequence[str] = (), _depth: int = 0) -> list:
    """The list of records inside a response, however deeply it is wrapped.

    Real responses look like ``{"output": {"data": [...]}}`` even where the
    Swagger example shows a bare ``{"data": [...]}``.
    """
    if isinstance(body, list):
        return body
    if not isinstance(body, dict) or _depth > 4:
        return []
    for k in preferred:  # explicit wrapper keys win, even when the list is empty
        if isinstance(body.get(k), list):
            return body[k]
    for v in body.values():  # otherwise any non-empty list of records
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    for v in body.values():  # otherwise look one wrapper deeper
        if isinstance(v, dict):
            found = _first_list(v, preferred, _depth + 1)
            if found:
                return found
    return []


def _get(d: dict, *keys: str) -> object:
    for k in keys:
        if k in d:
            return d[k]
    return None


def _shape(body: object, _depth: int = 0) -> str:
    """Compact, recursive description of a JSON response (no values, just structure).

    Used in error messages and `ceda-probe` so a wrong guess about the API's
    response format can be corrected from one pasted line.
    """
    if _depth > 5:
        return "..."
    if isinstance(body, list):
        if not body:
            return "list[0]"
        return f"list[{len(body)}] of {_shape(body[0], _depth + 1)}"
    if isinstance(body, dict):
        inner = ", ".join(f"{k}: {_shape(v, _depth + 1)}" for k, v in list(body.items())[:25])
        return "{" + inner + "}"
    return type(body).__name__


def _frame(
    body: object,
    preferred: Sequence[str],
    aliases: dict[str, tuple[str, ...]],
    required: Sequence[str] = (),
) -> pd.DataFrame:
    """Records -> DataFrame with canonical column names (first matching alias wins).

    The published Swagger examples do not always match the real responses
    (e.g. commodities come back as commodity_id/commodity_name, not id/name),
    so field names are accepted under several spellings.
    """
    raw = pd.DataFrame(_first_list(body, preferred))
    if raw.empty:
        return pd.DataFrame(columns=list(aliases))
    out = pd.DataFrame(index=raw.index)
    for canon, alts in aliases.items():
        src = next((a for a in alts if a in raw.columns), None)
        out[canon] = raw[src] if src else None
    for col in required:
        if out[col].isna().all():
            raise CedaError(f"unexpected response shape (no {col!r}): {_shape(body)}")
    return out


class CedaClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        auth_scheme: str | None = None,
        delay_sec: float | None = None,
        session: requests.Session | None = None,
        wait_on_limit: bool = False,
    ) -> None:
        s = get_settings()
        self.key = api_key or s.ceda_api_key
        if not self.key:
            raise CedaError("CEDA_API_KEY is not set. Add it to .env (never commit it).")
        self.base_url = (base_url or s.ceda_base_url).rstrip("/")
        self.auth_scheme = auth_scheme or s.ceda_auth_scheme
        self.delay_sec = s.ceda_request_delay_sec if delay_sec is None else delay_sec
        self.session = session or requests.Session()
        self._last_call = 0.0
        # False (default): when this hour's budget is spent, raise CedaRateLimited instead
        # of sleeping, so a long run stops cleanly and is simply re-started after the reset.
        self.wait_on_limit = wait_on_limit
        self._pause_until = 0.0  # monotonic time before which no call may be made
        self.requests_made = 0
        self.rate_info: dict[str, str] = {}  # last rate-limit headers the server sent
        self.last_message = ""  # the API's own `output.type: output.message` for the last series call

    # ------------------------------------------------------------------ http
    def _headers(self) -> dict[str, str]:
        if self.auth_scheme not in AUTH_SCHEMES:
            raise CedaError(
                f"CEDA_AUTH_SCHEME={self.auth_scheme!r} is not usable. Run "
                "`python -m backend.cli ceda-probe` and set the value it reports in .env."
            )
        return {**AUTH_SCHEMES[self.auth_scheme](self.key), "Accept": "application/json"}

    def _throttle(self) -> None:
        now = time.monotonic()
        if self._pause_until > now:
            wait = self._pause_until - now
            if not self.wait_on_limit:
                raise CedaRateLimited(wait, self.rate_info, "this hour's request budget is used up")
            log.warning("ceda_waiting_for_rate_limit_reset", seconds=round(wait))
            time.sleep(wait)
        wait = self.delay_sec - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)

    def _pace_from_headers(self) -> None:
        """If the server says this window's budget is spent, sleep before the NEXT call.

        CEDA allows 40 requests per hour per key (``ratelimit-policy: 40;w=3600``).
        Pacing ourselves avoids burning calls on 429s.
        """
        def num(key: str) -> float | None:
            try:
                return float(self.rate_info.get(key, ""))
            except ValueError:
                return None

        remaining, reset = num("ratelimit-remaining"), num("ratelimit-reset")
        if remaining is not None and remaining <= 0 and reset:
            self._pause_until = time.monotonic() + reset + 5

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(CedaTransientError),
    )
    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        self._throttle()
        url = f"{self.base_url}{path}"
        try:
            r = self.session.request(
                method, url, headers=self._headers(), json=json_body,
                timeout=REQUEST_TIMEOUT_SEC,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise CedaTransientError(f"network error on {path}: {exc}") from exc
        finally:
            self._last_call = time.monotonic()

        self.requests_made += 1
        self.rate_info = {
            k.lower(): v for k, v in r.headers.items()
            if "ratelimit" in k.lower() or k.lower() == "retry-after"
        }
        self._pace_from_headers()

        if r.status_code in (401, 403):
            raise CedaAuthError(
                f"{r.status_code} on {path}: key rejected, expired, or wrong auth scheme "
                f"({self.auth_scheme}). Body: {r.text[:200]}"
            )
        if r.status_code == 429:
            ra = r.headers.get("Retry-After", "")
            if ra.isdigit():
                self._pause_until = max(self._pause_until, time.monotonic() + float(ra) + 5)
            raise CedaRateLimited(float(ra) if ra.isdigit() else None, self.rate_info, r.text[:200])
        if r.status_code >= 500:
            raise CedaTransientError(f"{r.status_code} on {path}: {r.text[:200]}")
        if r.status_code != 200:
            raise CedaError(f"{r.status_code} on {path}: {r.text[:300]}")
        try:
            return r.json()
        except ValueError as exc:
            raise CedaError(f"non-JSON response on {path}") from exc

    # ---------------------------------------------------------------- lookups
    def commodities(self) -> pd.DataFrame:
        body = self._request("GET", "/agmarknet/commodities")
        return _frame(
            body,
            ("commodities", "data"),
            {"id": ("id", "commodity_id"), "name": ("name", "commodity_name")},
            required=("id", "name"),
        )

    def geographies(self) -> pd.DataFrame:
        """One row per (state, district)."""
        body = self._request("GET", "/agmarknet/geographies")
        rows = []
        for st in _first_list(body, ("geographies", "states", "data")):
            if not isinstance(st, dict):
                continue
            sid = _get(st, "state_id", "census_state_id", "id")
            sname = _get(st, "state_name", "census_state_name", "name")
            districts = _get(st, "districts", "district_list") or []
            for d in districts:
                rows.append(
                    {
                        "state_id": sid,
                        "state_name": sname,
                        "district_id": _get(d, "district_id", "census_district_id", "id"),
                        "district_name": _get(d, "district_name", "census_district_name", "name"),
                    }
                )
            flat_did = _get(st, "district_id", "census_district_id")
            if not districts and flat_did is not None:
                # Flat layout (what the live API returns): one record per district
                # with the state fields alongside, all named census_*.
                rows.append(
                    {
                        "state_id": sid,
                        "state_name": sname,
                        "district_id": flat_did,
                        "district_name": _get(st, "district_name", "census_district_name"),
                    }
                )
        df = pd.DataFrame(
            rows, columns=["state_id", "state_name", "district_id", "district_name"]
        )
        if df.empty or df["state_id"].isna().all() or df["district_id"].isna().all():
            raise CedaError(f"unexpected geographies response: {_shape(body)}")
        return df

    def markets(
        self, commodity_id: int, state_id: int, district_id: int, indicator: str
    ) -> pd.DataFrame:
        body = self._request(
            "POST",
            "/agmarknet/markets",
            {
                "commodity_id": int(commodity_id),
                "state_id": int(state_id),
                "district_id": int(district_id),
                "indicator": indicator,
            },
        )
        return _frame(
            body,
            ("data", "markets"),
            {
                "census_state_id": ("census_state_id",),
                "census_district_id": ("census_district_id",),
                "market_id": ("market_id", "id"),
                "market_name": ("market_name", "name"),
            },
            required=("market_id", "market_name"),
        )

    # ------------------------------------------------------------ time series
    def _series(
        self,
        path: str,
        columns: list[str],
        commodity_id: int,
        state_id: int,
        markets: Sequence[tuple[int, int]],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        body = {
            "commodity_id": int(commodity_id),
            "state_id": int(state_id),
            "from_date": start.isoformat(),
            "to_date": end.isoformat(),
        }
        if markets is not None:  # None = ask for the whole state (used by `ceda-explore`)
            body["district_id"] = sorted({int(d) for _, d in markets})
            body["market_id"] = [int(m) for m, _ in markets]
        resp = self._request("POST", path, body)
        out = resp.get("output") if isinstance(resp, dict) else None
        self.last_message = (
            f"{out.get('type')}: {out.get('message')}" if isinstance(out, dict) else ""
        )
        raw = pd.DataFrame(_first_list(resp, ("data",)))
        required = {"date", "market_id", "modal_price" if "modal_price" in columns else "quantity"}
        if len(raw) and not required <= set(raw.columns):
            # Fail loudly: silently coercing a differently-named field would load all-NULL rows.
            raise CedaError(
                f"unexpected columns from {path}: {sorted(raw.columns)} (need {sorted(required)})"
            )
        return _coerce(raw, columns)

    def fetch_series(
        self,
        kind: str,
        commodity_id: int,
        state_id: int,
        markets: Sequence[tuple[int, int]],
        start: date,
        end: date,
        max_rows: int | None = None,
    ) -> pd.DataFrame:
        """Fetch prices (``kind='price'``) or arrivals (``kind='quantity'``).

        ``markets`` is a list of ``(market_id, district_id)``. Responses at or
        above ``max_rows`` are split (by market, then by date) and re-fetched.
        """
        if kind not in {"price", "quantity"}:
            raise ValueError(f"kind must be 'price' or 'quantity', got {kind!r}")
        max_rows = max_rows or get_settings().ceda_max_rows
        path, columns = (
            ("/agmarknet/prices", PRICE_COLUMNS)
            if kind == "price"
            else ("/agmarknet/quantities", QUANTITY_COLUMNS)
        )

        df = self._series(path, columns, commodity_id, state_id, markets, start, end)
        n = len(df)
        # Evidence from real runs: the API returns 1,300-1,500 rows without cutting them, so
        # a fixed row limit is only a last resort (ceda_max_rows, effectively off by default).
        # A silent cap would show up as a suspiciously round count (multiples of 100, or a
        # power of two like 1024/2048/4096), so those are treated as possibly truncated.
        # Splitting such a response costs a few extra calls and never loses data.
        looks_capped = (
            n >= max_rows
            or (n >= 100 and n % 100 == 0)
            or (n >= 512 and n & (n - 1) == 0)
        )
        if not looks_capped:
            return df

        log.warning(
            "ceda_response_may_be_truncated",
            kind=kind, rows=len(df), markets=len(markets),
            start=start.isoformat(), end=end.isoformat(),
        )
        if len(markets) > 1:
            half = len(markets) // 2
            parts = [
                self.fetch_series(kind, commodity_id, state_id, markets[:half], start, end, max_rows),
                self.fetch_series(kind, commodity_id, state_id, markets[half:], start, end, max_rows),
            ]
        elif (end - start).days >= 2:
            mid = start + (end - start) // 2
            parts = [
                self.fetch_series(kind, commodity_id, state_id, markets, start, mid, max_rows),
                self.fetch_series(kind, commodity_id, state_id, markets, mid, end, max_rows),
            ]
        else:
            log.error(
                "ceda_window_still_full",
                kind=kind, market=markets[0][0], start=start.isoformat(), rows=len(df),
            )
            return df
        return _combine(parts, columns)
