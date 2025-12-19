"""data.market_data

Market Data Module - Saxo Bank Integration

Epic 003: Market Data Retrieval Module (Saxo)

This module provides broker-agnostic, normalized market data keyed by:

    instrument_id = f"{asset_type}:{uic}"

It supports:
- Snapshot quotes via Saxo Trade v1 InfoPrices (prefer batch /trade/v1/infoprices/list)
- OHLC bars via Saxo Chart v3 (/chart/v3/charts)

Normalization contracts are documented in Story 003-001 and implemented here as
pure helper functions that can be unit-tested.

Notes / Known Saxo Semantics:
- List endpoints may return partial results and omit invalid instruments without HTTP error.
- DelayedByMinutes == 0 does not guarantee freshness; LastUpdated can still be old.
- Chart v1 is deprecated; use Chart v3.

"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Literal

from data.saxo_client import SaxoClient, SaxoAPIError


logger = logging.getLogger(__name__)


class InstrumentNotFoundError(Exception):
    """Raised when instrument cannot be found."""


class MarketDataError(Exception):
    """Raised when market data retrieval fails."""


# =============================================================================
# Story 003-001: Contracts + Normalization
# =============================================================================

SUPPORTED_HORIZON_MINUTES: Tuple[int, ...] = (
    1,
    5,
    10,
    15,
    30,
    60,
    120,
    240,
    360,
    480,
    1440,
    10080,
    43200,
)


def _instrument_id(asset_type: str, uic: int) -> str:
    return f"{asset_type}:{uic}"


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 timestamps from Saxo.

    If a timezone offset is missing and parsing yields a naive datetime,
    we assume UTC to avoid downstream `.astimezone()` failures.
    """

    if not value:
        return None

    try:
        # Saxo commonly returns ISO-8601 with Z
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")

        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def normalize_quote_from_infoprice(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single InfoPrice item into the internal quote schema.

    Pure function (no I/O).
    """

    quote = payload.get("Quote") or {}

    bid = quote.get("Bid")
    ask = quote.get("Ask")
    mid = quote.get("Mid")

    if mid is None and bid is not None and ask is not None:
        try:
            mid = (float(bid) + float(ask)) / 2.0
        except Exception:
            mid = None

    last_updated = payload.get("LastUpdated")

    delayed_by_minutes = quote.get("DelayedByMinutes")
    market_state = quote.get("MarketState")

    price_type_bid = quote.get("PriceTypeBid")
    price_type_ask = quote.get("PriceTypeAsk")

    normalized: Dict[str, Any] = {
        "bid": float(bid) if bid is not None else None,
        "ask": float(ask) if ask is not None else None,
        "mid": float(mid) if mid is not None else None,
        "last_updated": last_updated,
        "delayed_by_minutes": int(delayed_by_minutes)
        if delayed_by_minutes is not None
        else None,
        "market_state": market_state,
        # Optional quote metadata
        "price_type_bid": price_type_bid,
        "price_type_ask": price_type_ask,
        "error_code": quote.get("ErrorCode"),
        "price_source": quote.get("PriceSource"),
        "price_source_type": quote.get("PriceSourceType"),
    }

    return normalized


def derive_data_quality_from_quote(normalized_quote: Dict[str, Any]) -> Dict[str, Any]:
    """Derive broker-agnostic safety flags.

    - is_delayed: delayed_by_minutes > 0
    - is_indicative: PriceTypeBid/Ask != Tradable (when present)
    """

    delayed_by_minutes = normalized_quote.get("delayed_by_minutes")
    is_delayed: Optional[bool] = (
        (delayed_by_minutes is not None and delayed_by_minutes > 0)
        if delayed_by_minutes is not None
        else None
    )

    ptb = normalized_quote.get("price_type_bid")
    pta = normalized_quote.get("price_type_ask")
    if ptb is None and pta is None:
        is_indicative: Optional[bool] = None
    else:
        is_indicative = (ptb is not None and ptb != "Tradable") or (
            pta is not None and pta != "Tradable"
        )

    return {"is_delayed": is_delayed, "is_indicative": is_indicative}


def normalize_bar_from_chart_sample(asset_type: str, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize a Chart v3 sample into internal bar schema.

    Supports FX/CryptoFX bid/ask OHLC -> mid OHLC.
    Pure function (no I/O).

    Returns None if required fields are missing.
    """

    time_str = sample.get("Time")
    if not time_str:
        return None

    # Stock-like OHLC
    if all(k in sample for k in ("Open", "High", "Low", "Close")):
        try:
            return {
                "time": time_str,
                "open": float(sample["Open"]),
                "high": float(sample["High"]),
                "low": float(sample["Low"]),
                "close": float(sample["Close"]),
                "volume": sample.get("Volume"),
                "raw": sample,
            }
        except Exception:
            return None

    # FX/CryptoFX style bid/ask OHLC
    bid_ask_keys = (
        "OpenBid",
        "OpenAsk",
        "HighBid",
        "HighAsk",
        "LowBid",
        "LowAsk",
        "CloseBid",
        "CloseAsk",
    )
    if all(k in sample for k in bid_ask_keys):
        try:
            open_mid = (float(sample["OpenBid"]) + float(sample["OpenAsk"])) / 2.0
            high_mid = (float(sample["HighBid"]) + float(sample["HighAsk"])) / 2.0
            low_mid = (float(sample["LowBid"]) + float(sample["LowAsk"])) / 2.0
            close_mid = (float(sample["CloseBid"]) + float(sample["CloseAsk"])) / 2.0
            return {
                "time": time_str,
                "open": open_mid,
                "high": high_mid,
                "low": low_mid,
                "close": close_mid,
                "volume": sample.get("Volume"),
                "raw": sample,
            }
        except Exception:
            return None

    # Unknown sample shape
    logger.debug(
        "Chart sample had unexpected shape for %s: keys=%s",
        asset_type,
        sorted(sample.keys()),
    )
    return None


# =============================================================================
# Story 003-005: Freshness + Market State
# =============================================================================

STALE_QUOTE_SECONDS_DEFAULT = 180  # 2-5 minutes recommended; default 3 minutes


def evaluate_quote_freshness(
    normalized_quote: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
    stale_quote_seconds: int = STALE_QUOTE_SECONDS_DEFAULT,
) -> Dict[str, Any]:
    """Evaluate quote freshness.

    Returns a broker-agnostic freshness block living at instrument container level.
    """

    if now is None:
        now = datetime.now(timezone.utc)

    if not normalized_quote:
        return {
            "is_stale": True,
            "age_seconds": None,
            "delayed_by_minutes": None,
            "reason": "NO_QUOTE",
        }

    last_updated_str = normalized_quote.get("last_updated")
    last_updated_dt = _parse_iso8601(last_updated_str)
    delayed_by_minutes = normalized_quote.get("delayed_by_minutes")

    if last_updated_dt is None:
        return {
            "is_stale": True,
            "age_seconds": None,
            "delayed_by_minutes": delayed_by_minutes,
            "reason": "MISSING_LAST_UPDATED",
        }

    age_seconds = (now - last_updated_dt.astimezone(timezone.utc)).total_seconds()
    is_stale = age_seconds > stale_quote_seconds
    reason = "STALE_LAST_UPDATED" if is_stale else None

    return {
        "is_stale": bool(is_stale),
        "age_seconds": float(age_seconds),
        "delayed_by_minutes": delayed_by_minutes,
        "reason": reason,
    }


def evaluate_bar_freshness(
    bars: List[Dict[str, Any]],
    horizon_minutes: int,
    now: Optional[datetime] = None,
    stale_multiplier: int = 5,
) -> Dict[str, Any]:
    """Evaluate bar freshness based on last bar time.

    Heuristic: stale if now - last_bar_time > stale_multiplier * horizon.
    """

    if now is None:
        now = datetime.now(timezone.utc)

    if not bars:
        return {
            "is_stale": True,
            "age_seconds": None,
            "delayed_by_minutes": None,
            "reason": "NO_BARS",
        }

    last_time_str = bars[-1].get("time")
    last_time_dt = _parse_iso8601(last_time_str)
    if last_time_dt is None:
        return {
            "is_stale": True,
            "age_seconds": None,
            "delayed_by_minutes": None,
            "reason": "MISSING_LAST_BAR_TIME",
        }

    age_seconds = (now - last_time_dt.astimezone(timezone.utc)).total_seconds()
    threshold_seconds = stale_multiplier * horizon_minutes * 60
    is_stale = age_seconds > threshold_seconds

    return {
        "is_stale": bool(is_stale),
        "age_seconds": float(age_seconds),
        "delayed_by_minutes": None,
        "reason": "STALE_LAST_BAR" if is_stale else None,
    }


def should_trade_given_market_state(market_state: Optional[str]) -> bool:
    """Default guidance: only trade when MarketState == 'Open'."""

    if market_state is None:
        return False
    return market_state == "Open"


# =============================================================================
# Existing instrument discovery helpers (kept for backwards compatibility)
# =============================================================================


def find_instruments(keyword: str, asset_types: str = "Stock", limit: int = 10) -> List[Dict[str, Any]]:
    """Search for instruments by keyword."""

    client = SaxoClient()

    try:
        params = {"Keywords": keyword, "AssetTypes": asset_types, "limit": limit}
        response = client.get("/ref/v1/instruments", params=params)

        if isinstance(response, dict):
            return response.get("Data", [])
        if isinstance(response, list):
            return response
        return []

    except SaxoAPIError as e:
        raise MarketDataError(f"Instrument search failed: {e}")


def find_instrument_uic(keyword: str, asset_type: str = "Stock") -> Optional[int]:
    """Find the UIC (Universal Instrument Code) for an instrument."""

    instruments = find_instruments(keyword, asset_type, limit=5)

    if not instruments:
        raise InstrumentNotFoundError(
            f"No instrument found for '{keyword}' with AssetType '{asset_type}'"
        )

    return instruments[0].get("Identifier")


def get_instrument_details(uic: int, asset_type: str) -> Dict[str, Any]:
    """Get detailed information about an instrument."""

    client = SaxoClient()

    try:
        params = {"Uics": uic, "AssetTypes": asset_type}
        response = client.get("/ref/v1/instruments/details", params=params)

        if isinstance(response, dict):
            data = response.get("Data", [])
            if data:
                return data[0]

        raise MarketDataError(f"No details found for UIC {uic}")

    except SaxoAPIError as e:
        raise MarketDataError(f"Failed to get instrument details: {e}")


def discover_watchlist_instruments(symbols: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Discover UICs for a list of symbols."""

    results: List[Dict[str, Any]] = []

    for symbol_info in symbols:
        name = symbol_info.get("name")
        asset_type = symbol_info.get("asset_type", "Stock")

        if not name:
            results.append(
                {
                    "name": "Unknown",
                    "asset_type": asset_type,
                    "uic": None,
                    "details": None,
                    "status": "error",
                    "error": "Missing instrument name",
                }
            )
            continue

        try:
            uic = find_instrument_uic(name, asset_type)
            if uic is None:
                raise InstrumentNotFoundError(f"No UIC found for {name}")
            details = get_instrument_details(uic, asset_type)

            results.append(
                {
                    "name": name,
                    "asset_type": asset_type,
                    "uic": uic,
                    "details": details,
                    "status": "found",
                }
            )

        except (InstrumentNotFoundError, MarketDataError) as e:
            results.append(
                {
                    "name": name,
                    "asset_type": asset_type,
                    "uic": None,
                    "details": None,
                    "status": "error",
                    "error": str(e),
                }
            )

    return results


# =============================================================================
# Story 003-002: Batch Quote Retrieval (InfoPrices list)
# =============================================================================


def get_latest_quotes(
    instruments: List[Dict[str, Any]],
    field_groups: Optional[str] = None,
    include_rate_limit_info: bool = False,
    saxo_client: Optional[SaxoClient] = None,
) -> Dict[str, Dict[str, Any]]:
    """Fetch latest quote snapshots for instruments (prefer batched InfoPrices list).

    Returns dict keyed by instrument_id.

    Missing-from-response items are represented as explicit error entries:
        {"quote": None, "error": {"code": "MISSING_FROM_RESPONSE", ...}}

    If include_rate_limit_info=True, each returned instrument container will include
    `rate_limit_info` for the request that produced it (or empty dict for invalid inputs).
    """

    client = saxo_client if saxo_client else SaxoClient()

    # Group instruments by asset_type
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    invalid: List[Dict[str, Any]] = []

    def _as_int_uic(value: Any) -> Optional[int]:
        """Best-effort int coercion; returns None if not int-convertible."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    for inst in instruments:
        asset_type = inst.get("asset_type")
        uic_raw = inst.get("uic")
        uic_int = _as_int_uic(uic_raw)

        # Preserve as much identifying info as possible for deterministic reconciliation.
        symbol = inst.get("symbol") or inst.get("name")

        if not asset_type or uic_int is None:
            # Can't request; return explicit per-item error entry
            invalid.append(
                {
                    **inst,
                    "asset_type": asset_type,
                    "uic": uic_raw,
                    "symbol": symbol,
                }
            )
            logger.warning("Invalid instrument input for quotes: %s", inst)
            continue

        grouped.setdefault(asset_type, []).append({**inst, "uic": uic_int, "symbol": symbol})

    results: Dict[str, Dict[str, Any]] = {}

    # Track invalid inputs separately (stable unique keys)
    for idx, inst in enumerate(invalid):
        at = inst.get("asset_type")
        u_raw = inst.get("uic")

        # If both fields exist and UIC is int-convertible, we can produce a deterministic id.
        try:
            u_int = int(u_raw) if (at and u_raw is not None) else None
        except (TypeError, ValueError):
            u_int = None

        best_effort_id = _instrument_id(str(at), u_int) if (at and u_int is not None) else f"INVALID:{idx}"

        container: Dict[str, Any] = {
            "instrument_id": best_effort_id,
            "asset_type": at,
            "uic": u_raw,
            "symbol": inst.get("symbol") or inst.get("name"),
            # Preserve raw identifying fields for deterministic reconciliation
            "name": inst.get("name"),
            "original_input": dict(inst),
            "quote": None,
            "bars": [],
            "data_quality": {"is_delayed": None, "is_indicative": None},
            "freshness": {
                "is_stale": True,
                "age_seconds": None,
                "delayed_by_minutes": None,
                "reason": "INVALID_INSTRUMENT_INPUT",
            },
            "error": {"code": "INVALID_INSTRUMENT_INPUT"},
        }

        if include_rate_limit_info:
            container["rate_limit_info"] = {}

        results[best_effort_id] = container

    for asset_type, insts in grouped.items():
        if asset_type == "__invalid__":
            continue

        # Deduplicate UICs within the request
        seen: set[int] = set()
        uics: List[int] = []
        duplicates: List[int] = []
        for inst in insts:
            # `uic` has already been validated/coerced to int during grouping
            uic = int(inst["uic"])
            if uic in seen:
                duplicates.append(uic)
                continue
            seen.add(uic)
            uics.append(uic)

        if duplicates:
            logger.warning("Duplicate UICs detected in quote request for %s: %s", asset_type, duplicates)

        params = {
            "AssetType": asset_type,
            "Uics": ",".join(str(u) for u in uics),
            "FieldGroups": field_groups or "Quote",
        }

        logger.debug("Requesting InfoPrices list for %s: %s", asset_type, params)

        try:
            data, _rate = client.get_with_headers(
                "/trade/v1/infoprices/list", params=params, endpoint_type="quotes"
            )
        except SaxoAPIError as e:
            # Populate per-instrument errors but continue other asset types
            for inst in insts:
                iid = _instrument_id(asset_type, int(inst["uic"]))
                container: Dict[str, Any] = {
                    "instrument_id": iid,
                    "asset_type": asset_type,
                    "uic": int(inst["uic"]),
                    "symbol": inst.get("symbol") or inst.get("name"),
                    "quote": None,
                    "bars": [],
                    "data_quality": {"is_delayed": None, "is_indicative": None},
                    "freshness": {
                        "is_stale": True,
                        "age_seconds": None,
                        "delayed_by_minutes": None,
                        "reason": "REQUEST_FAILED",
                    },
                    "error": {
                        "code": "REQUEST_FAILED",
                        "details": {"message": str(e)},
                    },
                }
                if include_rate_limit_info:
                    container["rate_limit_info"] = getattr(e, "rate_limit_info", {}) or {}
                results[iid] = container
            continue

        items = []
        if isinstance(data, dict):
            items = data.get("Data", []) or []
        elif isinstance(data, list):
            items = data

        returned_by_uic: Dict[int, Dict[str, Any]] = {}
        for item in items:
            try:
                item_uic = int(item.get("Uic"))
            except Exception:
                continue
            returned_by_uic[item_uic] = item

        requested_set = set(uics)
        returned_set = set(returned_by_uic.keys())
        missing_uics = sorted(list(requested_set - returned_set))

        if missing_uics:
            logger.warning(
                "InfoPrices list omitted %d instruments for %s (missing_uics=%s)",
                len(missing_uics),
                asset_type,
                missing_uics,
            )

        # Fill results for requested instruments
        inst_lookup = {int(i["uic"]): i for i in insts}
        for uic in uics:
            inst = inst_lookup.get(uic, {"uic": uic, "symbol": None})
            iid = _instrument_id(asset_type, uic)
            if uic in returned_by_uic:
                normalized_quote = normalize_quote_from_infoprice(returned_by_uic[uic])
                dq = derive_data_quality_from_quote(normalized_quote)
                freshness = evaluate_quote_freshness(normalized_quote)

                container: Dict[str, Any] = {
                    "instrument_id": iid,
                    "asset_type": asset_type,
                    "uic": uic,
                    "symbol": inst.get("symbol") or inst.get("name"),
                    "quote": normalized_quote,
                    "bars": [],
                    "data_quality": dq,
                    "freshness": freshness,
                }
                if include_rate_limit_info:
                    container["rate_limit_info"] = _rate
                results[iid] = container
            else:
                container: Dict[str, Any] = {
                    "instrument_id": iid,
                    "asset_type": asset_type,
                    "uic": uic,
                    "symbol": inst.get("symbol") or inst.get("name"),
                    "quote": None,
                    "bars": [],
                    "data_quality": {"is_delayed": None, "is_indicative": None},
                    "freshness": {
                        "is_stale": True,
                        "age_seconds": None,
                        "delayed_by_minutes": None,
                        "reason": "MISSING_FROM_RESPONSE",
                    },
                    "error": {
                        "code": "MISSING_FROM_RESPONSE",
                        "details": {
                            "asset_type": asset_type,
                            "uic": uic,
                            "reason": "List endpoint may omit invalid items",
                        },
                    },
                }
                if include_rate_limit_info:
                    container["rate_limit_info"] = _rate
                results[iid] = container

    return results


# =============================================================================
# Story 003-003: Bar retrieval (Chart v3)
# =============================================================================


def _validate_horizon(horizon_minutes: int):
    if horizon_minutes not in SUPPORTED_HORIZON_MINUTES:
        raise ValueError(
            f"Unsupported Horizon={horizon_minutes} minutes. "
            f"Allowed values: {list(SUPPORTED_HORIZON_MINUTES)}"
        )


def _validate_count(count: int):
    if count <= 0:
        raise ValueError("Count must be > 0")
    if count > 1200:
        raise ValueError("Count must be <= 1200")


def get_ohlc_bars(
    instrument: Dict[str, Any],
    horizon_minutes: int,
    count: int = 60,
    mode: Literal["UpTo", "From"] = "UpTo",
    time: Optional[str] = None,
    field_groups: Optional[str] = None,
    existing_bars: Optional[List[Dict[str, Any]]] = None,
    include_rate_limit_info: bool = False,
    saxo_client: Optional[SaxoClient] = None,
) -> Dict[str, Any]:
    """Fetch OHLC bars for a single instrument using Saxo Chart v3.

    Duplicate bar handling:
    - if the API returns a bar with the same Time as the most recent stored bar,
      overwrite/merge it (inclusive Mode semantics).

    Returns a container with instrument metadata and normalized bars.
    """

    client = saxo_client if saxo_client else SaxoClient()

    asset_type = instrument.get("asset_type")
    uic = instrument.get("uic")
    symbol = instrument.get("symbol") or instrument.get("name")

    if not asset_type or uic is None:
        raise ValueError(f"Invalid instrument input: {instrument}")

    uic_int = int(uic)
    instrument_id = _instrument_id(asset_type, uic_int)

    _validate_horizon(horizon_minutes)
    _validate_count(count)

    params: Dict[str, Any] = {
        "AssetType": asset_type,
        "Uic": uic_int,
        "Horizon": horizon_minutes,
        "Count": count,
        "Mode": mode,
    }
    if time:
        params["Time"] = time
    if field_groups:
        params["FieldGroups"] = field_groups

    logger.debug("Requesting Chart v3 bars for %s params=%s", instrument_id, params)

    try:
        data, rate_info = client.get_with_headers(
            "/chart/v3/charts", params=params, endpoint_type="bars"
        )
    except SaxoAPIError as e:
        raise MarketDataError(f"Chart v3 request failed for {instrument_id}: {e}")

    samples = []
    if isinstance(data, dict):
        samples = data.get("Data", []) or []

    normalized_new: List[Dict[str, Any]] = []
    for s in samples:
        bar = normalize_bar_from_chart_sample(asset_type, s)
        if bar is not None:
            normalized_new.append(bar)

    # Sort by time ascending (fallback to empty string for type-safety)
    normalized_new.sort(key=lambda b: str(b.get("time") or ""))

    merged: List[Dict[str, Any]] = list(existing_bars or [])
    if merged and normalized_new:
        # Overwrite last bar if same timestamp
        if merged[-1].get("time") == normalized_new[0].get("time"):
            merged[-1] = normalized_new[0]
            merged.extend(normalized_new[1:])
        else:
            merged.extend(normalized_new)
    else:
        merged = merged or normalized_new

    if count and len(normalized_new) < count:
        logger.warning(
            "Illiquid/missing bars normal case for %s: horizon=%s requested=%s returned=%s",
            instrument_id,
            horizon_minutes,
            count,
            len(normalized_new),
        )

    out: Dict[str, Any] = {
        "instrument_id": instrument_id,
        "asset_type": asset_type,
        "uic": uic_int,
        "symbol": symbol,
        "bars": merged,
        "requested_count": int(count),
        "returned_count": int(len(normalized_new)),
        "freshness": evaluate_bar_freshness(merged, horizon_minutes=horizon_minutes),
    }

    if include_rate_limit_info:
        out["rate_limit_info"] = rate_info

    return out


# =============================================================================
# Legacy placeholder
# =============================================================================


def get_instrument_price(uic: int, asset_type: str) -> Optional[float]:
    """Legacy placeholder for price retrieval."""

    raise NotImplementedError(
        "Price retrieval not yet implemented. "
        "Use get_latest_quotes() for InfoPrices snapshots."
    )


__version__ = "3.1.0"
__api__ = "Saxo OpenAPI"
