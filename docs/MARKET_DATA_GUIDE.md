# Market Data Guide (Saxo OpenAPI)

This project retrieves **snapshot quotes** and **OHLC bars** from Saxo OpenAPI and normalizes them into broker-agnostic shapes so strategies do not need to understand Saxo payloads.

> Scope note: we intentionally use **InfoPrices** (not **Prices**) for polling watchlists.
> InfoPrices are market-data snapshots; do not assume they are tradeable quotes.
> Tradeable pricing and execution concerns belong to the order/execution epic.

## Endpoint cheat sheet

| Endpoint | Purpose | Key Parameters | Common Failure Modes |
|----------|---------|----------------|----------------------|
| `/trade/v1/infoprices/list` | Batch quote retrieval | `AssetType`, `Uics`, `FieldGroups` (defaults to `Quote`) | Partial omission (missing invalid UICs), HTTP 429 |
| `/chart/v3/charts` | OHLC bar retrieval (Chart v3) | `AssetType`, `Uic`, `Horizon`, `Count` (<= 1200), `Mode`, `Time` | Invalid Horizon (400), missing bars for illiquid instruments, HTTP 429 |

## Normalized contracts

All outputs are keyed by:

```python
instrument_id = f"{asset_type}:{uic}"
```

### Quote (normalized)

```python
{
  "bid": float | None,
  "ask": float | None,
  "mid": float | None,
  "last_updated": str | None,           # ISO-8601
  "delayed_by_minutes": int | None,
  "market_state": str | None,

  # Optional metadata
  "price_type_bid": str | None,
  "price_type_ask": str | None,
  "error_code": str | None,
  "price_source": str | None,
  "price_source_type": str | None,
}
```

Rules:
- If `Mid` is absent but `Bid` and `Ask` exist, we derive `mid = (bid + ask) / 2`.

### Bars (normalized)

```python
{
  "time": str,                     # ISO-8601
  "open": float,
  "high": float,
  "low": float,
  "close": float,
  "volume": float | int | None,
  "raw": dict | None               # debugging payload
}
```

FX/CryptoFX note:
- When Chart v3 returns bid/ask OHLC fields, we normalize to **mid OHLC**:
  - `open  = (OpenBid  + OpenAsk) / 2`
  - `high  = (HighBid  + HighAsk) / 2`
  - `low   = (LowBid   + LowAsk) / 2`
  - `close = (CloseBid + CloseAsk) / 2`

### data_quality

```python
{
  "is_delayed": bool | None,
  "is_indicative": bool | None,
}
```

- `is_delayed = delayed_by_minutes > 0` (when present)
- `is_indicative = PriceTypeBid != "Tradable" or PriceTypeAsk != "Tradable"` (when present)

### freshness

Freshness is stored at the **instrument container level** (not inside `quote`) so it can describe quote and/or bar freshness.

```python
{
  "is_stale": bool,
  "age_seconds": float | None,
  "delayed_by_minutes": int | None,
  "reason": str | None,
}
```

## Quotes: InfoPrices list (batch)

Implementation: `data.market_data.get_latest_quotes()`.

Optional diagnostics:
- pass `include_rate_limit_info=True` to attach `rate_limit_info` to each instrument container (useful for orchestrators).

Behavior:
- Instruments are grouped by `asset_type`.
- Per `asset_type` we call `/trade/v1/infoprices/list` with a comma-separated `Uics` list.
- `FieldGroups` defaults to `Quote`.

Important: **partial omission semantics**
- `/list` endpoints can return HTTP 200 but omit invalid instruments from the `Data` list.
- We treat that as a normal per-instrument failure mode and return:

```python
{"quote": None, "error": {"code": "MISSING_FROM_RESPONSE"}}
```

## Bars: Chart v3

Implementation: `data.market_data.get_ohlc_bars()`.

Return shape includes:
- `bars`: merged list (optionally merged with `existing_bars`)
- `freshness`: bar freshness block (see Freshness section)
- `requested_count` / `returned_count`: useful for orchestration / diagnostics

Key points:
- We use `/chart/v3/charts` (Chart v1 is deprecated).
- `Horizon` is **minutes per bar**.
- `Count` must be `<= 1200`.

### Supported Horizon values

Validated by default against the stable Support-page set:

```
1, 5, 10, 15, 30, 60, 120, 240, 360, 480, 1440, 10080, 43200
```

### Incremental polling pattern

Saxo guidance:
1. First call: `Mode=UpTo` to fetch the latest bars
2. Next calls: `Mode=From` and `Time=<last_bar_time>`

Note: `Time` is **inclusive**, so the response can include a bar with the same time as the last stored bar; the implementation overwrites the last bar instead of appending a duplicate.

### Missing bars

Illiquid instruments may return fewer bars than requested; this is normal.
The implementation logs a warning including `{instrument_id, horizon, requested_count, returned_count}`.

## Rate limiting and safe polling

Rate-limiting is handled in `data.saxo_client.SaxoClient.get_with_headers()`:
- Parses and logs **all** `X-RateLimit-*` headers present (Session, AppDay, etc.)
- Enforces minimum polling intervals per endpoint category (`quotes` vs `bars`)
- Retries only on: 429, 5xx, timeouts, transient network errors
- Does NOT retry on: 400, 401, 403

429 handling precedence:
1. `Retry-After` header
2. best available `X-RateLimit-*-Reset` (seconds until reset)
3. exponential backoff with jitter

## Freshness, delay, and market state

Important caveat:
- `DelayedByMinutes == 0` does **not** guarantee freshness.
- Always inspect `LastUpdated` and compute quote age.

Guidance:
- strategies should not trade when `MarketState != Open` unless they explicitly opt in.

## CryptoFX specifics

- Do not assume 24/7 trading: CryptoFX behaves FX-like (weekday trading; do not expect weekend bars).
- History in OpenAPI only goes back to **2021-04-19**; treat insufficient history as a normal warning condition.

## Troubleshooting

### Why are my bars missing?
- Illiquid instruments may not have enough trades to form bars for small horizons.
- Fewer-than-requested bars is normal; check logs for `{instrument_id, horizon, requested_count, returned_count}`.

### Why are quotes delayed?
- Even after subscribing, quotes can remain delayed due to **session capability** limitations (sessions can default to `OrdersOnly`).
- Detect delay using `DelayedByMinutes` and evaluate freshness using `LastUpdated`.

### Why did I get HTTP 429?
- Saxo has multi-dimension rate limits (Session/service-group, App/day, etc.).
- Inspect `X-RateLimit-*` headers.
- On 429 we respect `Retry-After` first, then reset headers.

## Code examples

```python
from data.market_data import get_latest_quotes, get_ohlc_bars

watchlist = [
    {"asset_type": "Stock", "uic": 211, "symbol": "AAPL"},
]

quotes = get_latest_quotes(watchlist)
print(quotes["Stock:211"]["quote"]["mid"])

bars_out = get_ohlc_bars(watchlist[0], horizon_minutes=5, count=60, mode="UpTo")
print(len(bars_out["bars"]))
print(bars_out["freshness"])  # bar freshness block
```
