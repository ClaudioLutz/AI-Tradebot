# Story 003-005: Data Freshness + Market-State Heuristics

## Story Overview
Add freshness evaluation and market-state heuristics for quotes and bars. This allows the bot to detect stale data (common in illiquid instruments) and to surface warnings that can be used by orchestration/strategy layers.

This story also documents a common operational pitfall: `DelayedByMinutes == 0` does not guarantee freshness; `LastUpdated` can still be old.

## Parent Epic
[Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)

## User Story
**As a** developer  
**I want to** detect stale or delayed market data and expose diagnostics  
**So that** strategies and orchestration can make safer decisions (skip trading, warn, or degrade gracefully)

## Acceptance Criteria
- [ ] Implement a quote freshness evaluator based on:
  - `LastUpdated`
  - `Quote.DelayedByMinutes`
- [ ] Implement a precise stale quote heuristic:
  - `quote_age_seconds = now - LastUpdated`
  - `is_stale = quote_age_seconds > STALE_QUOTE_SECONDS` (configurable)
- [ ] Implement a bar freshness evaluator based on:
  - last bar timestamp
  - configured `Horizon` (minutes per bar)
- [ ] Stale-data detection does not hard-fail market data retrieval
- [ ] Freshness results are logged with instrument context
- [ ] Market state usage guidance is documented:
  - strategies should not trade when `MarketState != Open` unless they explicitly opt in
- [ ] Document the “real-time capability” caveat:
  - unexpectedly delayed quotes often indicate session capability limitations
- [ ] CryptoFX rules are encoded in documentation/diagnostics:
  - weekday trading expectation (not weekends)
  - history only available from 2021-04-19

## Technical Details

### Prerequisites
- Stories 003-002 and 003-003 (quotes and bars retrieval)

### Suggested Freshness Output
Add a field like:

```python
{
  "freshness": {
    "is_stale": bool,
    "age_seconds": float | None,
    "delayed_by_minutes": int | None,
    "reason": str | None,
  }
}
```

This can live inside the instrument container and/or inside `quote`.

### Heuristic Guidance

#### Quotes
- Treat `DelayedByMinutes` as a *policy indicator* (data may be delayed)
- Treat `LastUpdated` as the actual freshness clock
- Important: `DelayedByMinutes == 0` does not guarantee recency

Suggested rule:
- compute `quote_age_seconds`
- `is_stale = quote_age_seconds > STALE_QUOTE_SECONDS`

**Recommended default for `STALE_QUOTE_SECONDS`:**
- Start with **120–300 seconds** (2–5 minutes) as a reasonable default threshold.
- This value is instrument liquidity dependent; illiquid instruments may need higher thresholds.
- This is consistent with Saxo's guidance that illiquid instruments can have old `LastUpdated` values even when `DelayedByMinutes == 0`.

#### Bars
- Compare `now - last_bar_time` against a multiple of `Horizon` (e.g., `> 5×Horizon minutes = stale`)

#### Market State
`Quote.MarketState` is not just informational — it should influence behavior.

Guidance:
- default behavior: strategies should not trade when `MarketState != Open`
- override must be explicit in strategy config/implementation

### Logging
Use warning logs (not errors) for stale data; reserve errors for request failures.

Log fields to include:
- `{instrument_id, asset_type, uic, symbol}`
- `last_updated`, `quote_age_seconds`, `delayed_by_minutes`, `market_state`

### “Why are quotes delayed?” (Docs requirement)
If you see delayed quotes unexpectedly:
- subscription might not be sufficient
- session capability may be restricted (e.g., `OrdersOnly`)

This is a docs-only note (we are not implementing streaming/capability changes inside Epic 003).

## Definition of Done
- [ ] Freshness functions are unit-testable
- [ ] Warnings are emitted for stale data scenarios
- [ ] MarketState guidance is present in docs

## Testing
Covered in Story 003-006.

## Story Points
**Estimate:** 2 points

## Dependencies
- Stories 003-002 and 003-003

## References
- Saxo Support - Missing chart data + freshness caveats: https://openapi.help.saxo/hc/en-us/articles/6105016299677-Why-is-chart-data-missing-for-this-instrument
- Saxo Support - Delayed quotes after subscribing: https://openapi.help.saxo/hc/en-us/articles/4416934340625-Why-are-quotes-still-delayed-after-I-subscribe-to-market-data
- Crypto FX in OpenAPI: https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi
