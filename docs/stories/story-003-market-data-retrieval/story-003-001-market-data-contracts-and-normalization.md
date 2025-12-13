# Story 003-001: Define Market Data Contracts + Normalization Schema

## Story Overview
Define the **normalized market data contracts** used by the bot and implement the parsing/normalization helpers that convert Saxo OpenAPI payloads into a stable internal schema.

This story focuses on **data shapes and conversion rules** only. Endpoint-specific fetching and retries are covered in subsequent stories.

## Parent Epic
[Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)

## User Story
**As a** developer  
**I want to** have consistent internal quote/bar schemas and normalization rules  
**So that** strategies can operate on broker-agnostic market data without knowing Saxo response structures

## Acceptance Criteria
- [ ] Define and document the market data keys used by downstream modules
- [ ] `instrument_id` is standardized as `"{asset_type}:{uic}"`
- [ ] Normalized **quote** structure is defined and produced from Saxo InfoPrices fields
- [ ] Normalized **bar** structure is defined and produced from Saxo Chart v3 fields
- [ ] FX/CryptoFX bid/ask OHLC is normalized into **mid OHLC** by default
- [ ] Normalizers tolerate missing/None fields (partial data) without raising
- [ ] Normalizers are pure functions (no I/O) and are unit-testable
- [ ] Quote normalization captures additional Saxo “what is in a quote” fields when present:
  - `PriceTypeBid`, `PriceTypeAsk`, `ErrorCode`, `PriceSource`, `PriceSourceType`
- [ ] Normalized output includes a broker-agnostic `data_quality` block:
  - `is_delayed` (DelayedByMinutes > 0)
  - `is_indicative` (PriceType != Tradable)

## Technical Details

### Prerequisites
- Epic 001-2 completed (Saxo client + auth available)
- Epic 002 completed (watchlist provides `{asset_type, uic, symbol}`)

### Target Module(s)
- `data/market_data.py`

### Contract: Instrument Identity
- **Input instrument:**
  - `{ "asset_type": str, "uic": int, "symbol": str }`
- **Internal key:**
  - `instrument_id = f"{asset_type}:{uic}"`

### Contract: Normalized Quote
Minimum normalized quote fields:

```python
{
  "bid": float | None,
  "ask": float | None,
  "mid": float | None,
  "last_updated": str | None,           # ISO-8601
  "delayed_by_minutes": int | None,
  "market_state": str | None,

  # Optional quote metadata (when present in Saxo payload)
  "price_type_bid": str | None,         # e.g., Tradable / Indicative / ...
  "price_type_ask": str | None,
  "error_code": str | None,
  "price_source": str | None,
  "price_source_type": str | None,
}
```

**Freshness placement decision:**
- `freshness` data (evaluated in Story 003-005) lives at the **top-level instrument container** (not inside `quote`).
- This prevents schema drift and allows freshness evaluation for both quotes and bars from a single location.

Normalization rules:
- `last_updated` comes from top-level `LastUpdated`
- Prefer `Quote.Mid` when present
- If `Quote.Mid` missing and both bid/ask exist, derive `mid = (bid + ask) / 2`
- If optional fields are missing, keep them as `None` (do not raise)

### Contract: Broker-agnostic `data_quality` (separate from freshness)
Add a small “safe strategy usage” block:

```python
{
  "data_quality": {
    "is_delayed": bool | None,      # derived from delayed_by_minutes
    "is_indicative": bool | None,   # derived from price_type_* when present
  }
}
```

Rules:
- `is_delayed = (delayed_by_minutes is not None and delayed_by_minutes > 0)`
- `is_indicative = (price_type_bid != "Tradable" or price_type_ask != "Tradable")` when price types are present

Rationale:
- `freshness` answers “how old is it?” (Story 003-005)
- `data_quality` answers “is it suitable for trading?” (delayed/indicative)

### Contract: Normalized Bars
Minimum normalized bar fields:

```python
{
  "time": str,                           # ISO-8601
  "open": float,
  "high": float,
  "low": float,
  "close": float,
  "volume": float | int | None,
  "raw": dict | None                     # optional debugging payload
}
```

#### FX/CryptoFX bid/ask OHLC → mid OHLC
When Chart v3 returns bid/ask OHLC fields (common for FX-style assets), derive mid fields:

- `open  = (OpenBid  + OpenAsk) / 2`
- `high  = (HighBid  + HighAsk) / 2`
- `low   = (LowBid   + LowAsk) / 2`
- `close = (CloseBid + CloseAsk) / 2`

Keep the raw bid/ask values available in `raw` (or a dedicated debug structure) for troubleshooting.

### Output Container
Normalized market data should be returned keyed by instrument_id:

```python
{
  "Stock:211": {
    "instrument_id": "Stock:211",
    "asset_type": "Stock",
    "uic": 211,
    "symbol": "AAPL",
    "quote": { ... },
    "bars": [ ... ],

    # Optional: additional broker-agnostic safety info
    "data_quality": { ... },
    
    # Freshness evaluation (Story 003-005)
    "freshness": { ... },
  }
}
```

**Note:** `freshness` is placed at the top-level container (not inside `quote`) to allow unified freshness evaluation for both quotes and bars, preventing schema drift.

## Definition of Done
- [ ] Contract is documented in code docstrings (and/or module-level comments)
- [ ] Normalization helper functions exist for quotes and bars
- [ ] Helper functions are deterministic and independently testable
- [ ] Quote normalization returns the optional quote-metadata fields when present
- [ ] data_quality derivation is documented and implemented

## Testing
- Unit tests will be implemented in Story 003-006.

## Story Points
**Estimate:** 2 points

## Dependencies
- Epic 002 watchlist format and instrument resolution

## References
- Epic 003: `docs/epics/epic-003-market-data-retrieval.md`
- Saxo Learn - Pricing (“What is in a Quote” fields like PriceType*/ErrorCode): https://www.developer.saxo/openapi/learn/pricing
- Saxo Learn - Chart sample variations (FX bid/ask OHLC): https://www.developer.saxo/openapi/learn/chart
