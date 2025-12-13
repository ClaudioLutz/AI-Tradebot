# Epic 003: Market Data Retrieval Module (Saxo)

## Epic Overview
Enhance the market data adapter (`data/market_data.py`) to fetch **snapshot quotes** and **OHLC bars** from Saxo OpenAPI for instruments defined in the watchlist.

This epic produces **broker-agnostic, normalized** market data keyed by `instrument_id = "{asset_type}:{uic}"`, so downstream modules (strategy/orchestration/execution) do not need to understand Saxo-specific payloads or endpoints.

## Business Value
- Provides a reliable market data surface for multi-asset strategies
- Abstracts Saxo OpenAPI complexity away from strategy logic
- Encodes Saxo rate limits + backoff behavior to improve stability
- Normalizes differences across asset classes (Stock vs FX/CryptoFX)
- Enables data-driven trading decisions using consistent structures

## Scope

### In Scope
- Market data retrieval enhancements in `data/market_data.py`
- Saxo REST client usage for market data endpoints
- **Quotes / InfoPrices** retrieval (REST polling)
  - Prefer **batch** retrieval where possible
- **Chart bars** retrieval (REST polling)
  - Use **Chart v3** (Chart v1 is deprecated)
- Normalization keyed by `instrument_id` (`"{asset_type}:{uic}"`)
- Support for watchlist instruments: `{asset_type, uic, symbol}`
- Error handling (partial results, rich diagnostics)
- Rate limit awareness and retry/backoff
- Logging for all retrieval operations and anomalies

### Out of Scope
- Streaming/WebSocket subscriptions (event-driven prices)
- Building a historical database / caching layer
- Backtesting-scale historical data retrieval
- Technical indicator calculation (RSI/MACD/etc.)
- Multi-timeframe strategy orchestration (handled elsewhere)

## Saxo Market Data Surfaces (Primary-Source Grounded)

### A) Snapshot Quotes: InfoPrices (REST polling)
**Purpose:** retrieve the current quote snapshot (bid/ask/mid, market state, timestamps).

- Single instrument:
  - `GET /trade/v1/infoprices`
- Batch list (preferred):
  - `GET /trade/v1/infoprices/list` with `Uics=`

**Key parameters (typical):**
- `AssetType` (required)
- `Uic` (single) or `Uics` (batch list)
- `AccountKey` (optional)
- `FieldGroups` (optional; controls response payload)

**Freshness indicators to capture and expose:**
- `LastUpdated`
- `Quote.DelayedByMinutes`

**Important operational reality:** even if `DelayedByMinutes == 0`, `LastUpdated` may still be old for illiquid instruments.

**List endpoint nuance (important for error handling):** list-style endpoints can return **partial/omitted results** rather than a hard error for invalid input. Treat “missing in response” as a normal per-instrument failure mode.

### B) OHLC Bars: Chart v3 (REST polling)
Your previous Epic 003 draft referenced `/chart/v1/charts`, but **Saxo has deprecated Chart v1 (Feb 2025)** and recommends v3.

- **Use:** `GET /chart/v3/charts`

**Key parameters (v3):**
- `AssetType` (required)
- `Uic` (required)
- `Horizon` (required) — **minutes per bar** (`int`)
- `Count` (optional) — max **1200**
- `Time` (optional)
- `Mode` (optional) — `From` / `UpTo`
- `FieldGroups` (optional)

**Polling pattern (recommended by Saxo):**
- First request: get latest samples (usually `Mode=UpTo`, optionally without `Time`)
- Subsequent requests: use `Mode=From` and `Time=<most recent sample time>` to fetch only new/updated bars

**Illiquid instruments:** for small horizons, you may receive fewer bars than requested; missing bars are normal.

## Market Data Capability / Real-Time Prerequisites (Common Blocker)
Saxo can return **delayed prices** depending on **session capabilities** (e.g., sessions may default to `OrdersOnly`, and non-FX can remain delayed).

### What we must capture
- **Delayed status:** `Quote.DelayedByMinutes` (or `DelayedByMinutes` where applicable)
- **Update timestamp:** `LastUpdated`

### What this means operationally
- Data can still be delayed **even after subscribing** to market data if the session capability is not configured for real-time.
- Being “not delayed” (`DelayedByMinutes == 0`) does **not** guarantee “fresh”; always evaluate `LastUpdated`.

### Documentation requirement
Epic 003 and Story 003-005 / 003-007 must document:
- how to detect delay (`DelayedByMinutes`, `LastUpdated`)
- what to check when quotes are unexpectedly delayed (session capability caveat)

(Primary source: Saxo support: “Why are quotes still delayed after I subscribe to market data?”)

## Data Model / Normalization

### Input
- Watchlist instruments from Epic 002:
  - `[{"asset_type": "Stock", "uic": 211, "symbol": "AAPL"}, ...]`

### Keying
- `instrument_id = f"{asset_type}:{uic}"`

### Output Shape
Return a dict keyed by `instrument_id`:

```python
{
  "Stock:211": {
    "instrument_id": "Stock:211",
    "asset_type": "Stock",
    "uic": 211,
    "symbol": "AAPL",
    "quote": {
      "bid": 150.25,
      "ask": 150.30,
      "mid": 150.275,
      "last_updated": "2025-12-13T08:30:00Z",
      "delayed_by_minutes": 0,
      "market_state": "Open"
    },
    "bars": [
      {"time": "2025-12-13T08:29:00Z", "open": 150.10, "high": 150.35, "low": 150.05, "close": 150.28, "volume": 1234}
    ]
  }
}
```

### Normalized Quote Rules
- Always capture:
  - `LastUpdated` → `quote.last_updated`
  - `Quote.Bid` → `quote.bid`
  - `Quote.Ask` → `quote.ask`
  - `Quote.Mid` → `quote.mid` (if provided)
  - `Quote.DelayedByMinutes` → `quote.delayed_by_minutes`
  - `Quote.MarketState` → `quote.market_state`
- If `Mid` is not provided, derive `mid = (bid + ask) / 2` when both exist.

### Normalized Bar Rules
- Bars should expose `{time, open, high, low, close}`.
- If volume is available for the asset type, include it.

**FX/CryptoFX bid/ask OHLC:** Saxo may return bid/ask OHLC fields for FX-style assets.
- Normalize `open/high/low/close` as **mid** by default:
  - `mid_close = (CloseBid + CloseAsk) / 2` (and similarly for open/high/low)
- Preserve raw bid/ask values in debug fields (or `raw` payloads) for troubleshooting.

## Horizon Validation (Avoid “mysterious 400s”)
Validate `Horizon` against Saxo supported values (minutes):

> `1, 5, 10, 15, 30, 60, 120, 240, 360, 480, 1440, 10080, 43200`

Reject unsupported horizons early with a clear error (include `instrument_id`, horizon value, and allowed list).

(Primary source: Saxo support: “What horizons can I use?”)

## “Missing Data Is Normal” Semantics (Make It Actionable)
Saxo notes that for **illiquid instruments**, horizons below 1440 minutes are based on trading activity and may yield fewer samples.

### Requirement
If fewer bars than requested are returned, treat it as normal and emit a warning:

- message should include `{instrument_id, horizon, requested_count, returned_count, last_updated, delayed_by_minutes}` (as applicable)

(Primary source: Saxo support: “Why is chart data missing for this instrument?”)

## Rate Limiting & Backoff

### Saxo rate limit model (primary-source grounded)
Saxo rate limiting can include multiple “dimensions”, such as:
- **App/day** limits
- **Session/service-group** limits (commonly 120/min)
- **Orders/session** limits (not relevant for this epic, but headers may still appear)

Batch requests can count as multiple “requests” in the rate limit model.

### Requirements
- Parse and log **all** `X-RateLimit-*` headers present (not just session remaining/reset)
- Implement proactive throttling by monitoring the rate-limit headers and enforcing a configurable minimum polling interval
- On **429**, handle the documented JSON error payload; surface error code (e.g., `RateLimitExceeded`) in logs
- On **429**, prefer `Retry-After` header when present; otherwise use the best available `X-RateLimit-*-Reset`
- Retry only on: 429, 5xx, timeouts/transient network failures
- Do not retry on: 400, 401, 403

## CryptoFX-Specific Notes (Primary-Source Grounded)
- **Do not assume 24/7**: CryptoFX behaves FX-like (weekday trading; no weekend expectation).
- **History limits:** CryptoFX history in OpenAPI only goes back to **2021-04-19**.
  - “Insufficient history” should be handled as a normal condition (warning, not hard failure).

## Dependencies
- **Epic 001-2:** Saxo Bank Migration (Saxo client + authentication)
- **Epic 002:** Configuration Module (watchlist with resolved instruments)

## Success Criteria
- [ ] Market data module provides quote and bar retrieval using Saxo REST endpoints
- [ ] Quote retrieval uses InfoPrices list batching by default
- [ ] Chart retrieval uses **Chart v3** with `Horizon` (minutes) and `Count <= 1200`
- [ ] `Horizon` is validated against supported values
- [ ] Data returned normalized and keyed by `instrument_id`
- [ ] Handles partial failures without crashing (including list endpoints omitting invalid instruments)
- [ ] Rate limiting is respected with proactive throttle + 429 backoff
- [ ] Data freshness heuristics are exposed/logged (LastUpdated + DelayedByMinutes)
- [ ] Unit tests cover parsing and edge cases with mocked Saxo responses

## Acceptance Criteria
1. Fetch latest quotes for all watchlist instruments using `/trade/v1/infoprices/list` when possible
2. Fetch OHLC bars using `/chart/v3/charts` (no Chart v1 usage)
3. `Horizon` is represented in minutes (int), validated, and restricted to Saxo supported values
4. `Count` is validated to be `<= 1200`
5. Returns normalized data keyed by `instrument_id`
6. Handles illiquid instruments (missing bars) as a normal case and logs `{instrument_id, horizon, requested_count, returned_count}` warnings
7. Handles CryptoFX limitations (weekday trading; history start 2021-04-19)
8. Logs all requests with instrument context and surfaces freshness warnings based on `LastUpdated`
9. Implements rate limit awareness via all available `X-RateLimit-*` headers, prefers `Retry-After` when present, and handles 429 correctly

## Related Documents
- [Saxo OpenAPI - InfoPrices](https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices)
- [Saxo OpenAPI - InfoPrices list (Reference)](https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade__list)
- [Saxo OpenAPI - Chart v3 (Reference)](https://developer.saxobank.com/openapi/referencedocs/chart/v3/charts)
- [Saxo Learn - Chart polling guidance](https://www.developer.saxo/openapi/learn/chart)
- [Saxo Learn - Pricing semantics (InfoPrices/Quotes)](https://www.developer.saxo/openapi/learn/pricing)
- [Saxo Learn - Rate limiting](https://www.developer.saxo/openapi/learn/rate-limiting)
- [Saxo Support - Avoid rate limits](https://openapi.help.saxo/hc/en-us/articles/4417694856849-How-do-I-avoid-exceeding-my-rate-limit)
- [Saxo Support - Missing chart data](https://openapi.help.saxo/hc/en-us/articles/6105016299677-Why-is-chart-data-missing-for-this-instrument)
- [Saxo Support - Horizon values](https://openapi.help.saxo/hc/en-us/articles/4417058210961-What-horizons-can-I-use)
- [Saxo Support - Delayed quotes after subscribing](https://openapi.help.saxo/hc/en-us/articles/4416934340625-Why-are-quotes-still-delayed-after-I-subscribe-to-market-data)
- [Saxo Learn - Crypto FX in OpenAPI](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)

## Example Function Signatures (Proposed)

```python
from typing import Any, Dict, List, Optional, Literal


def get_latest_quotes(
    instruments: List[Dict[str, Any]],
    field_groups: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Fetch latest quote snapshots for instruments (prefer batched InfoPrices list).

    Notes:
      - List endpoints can omit invalid instruments without error; treat missing items as per-instrument failures.
      - Always evaluate LastUpdated, even when DelayedByMinutes == 0.
    """
    ...


def get_ohlc_bars(
    instrument: Dict[str, Any],
    horizon_minutes: int,
    count: int = 60,
    mode: Literal["UpTo", "From"] = "UpTo",
    time: Optional[str] = None,
    field_groups: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch OHLC bars using Chart v3.

    Notes:
      - Validate horizon_minutes against supported values.
      - Use Mode=From with Time for incremental polling.
      - Fewer-than-requested bars are normal for illiquid instruments; log warnings.
    """
    ...
```

## Technical Notes

### Interval Mapping (Friendly API)
Saxo uses `Horizon` as **minutes per bar**. If the bot exposes friendly intervals, map them:
- `"1m" → 1`
- `"5m" → 5`
- `"1h" → 60`

But validate that the REST call uses `Horizon=<minutes>` and that the value is supported.

### Batching Strategy
- `/trade/v1/infoprices/list` batches by **AssetType**; group instruments by asset type.
- Chart requests are per-instrument.

### Logging
Every request/response error log should include:
- `instrument_id`, `asset_type`, `uic`, `symbol`
- HTTP status code
- relevant payload snippets / response body
- rate limit headers (when present)

### Freshness Warnings
- Quotes: warn on stale `LastUpdated` (and consider `DelayedByMinutes`)
- Bars: warn if last bar timestamp is stale relative to `Horizon`
