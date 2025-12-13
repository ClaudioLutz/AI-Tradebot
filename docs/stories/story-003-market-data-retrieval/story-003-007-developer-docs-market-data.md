# Story 003-007: Developer Documentation for Market Data (Saxo)

## Story Overview
Create developer-facing documentation explaining how the bot retrieves market data from Saxo OpenAPI, which endpoints are used, and the known limitations / best practices.

This story should include a **Troubleshooting** section grounded in primary sources (most common causes of “delayed/missing” confusion).

## Parent Epic
[Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)

## User Story
**As a** developer  
**I want to** understand the market data endpoints, polling strategy, and limitations  
**So that** I can safely extend market data usage without breaking rate limits or misinterpreting data

## Acceptance Criteria
- [ ] Documentation explains quote retrieval via InfoPrices and why batching is used
- [ ] Documentation explains bar retrieval via Chart v3 (and notes Chart v1 deprecation)
- [ ] Documentation explains `Horizon` as minutes per bar, including allowed values and mapping examples
- [ ] Documentation describes recommended polling pattern for charts (Mode=From + Time)
- [ ] Documentation explains rate limit headers and 429 behavior (including Retry-After precedence)
- [ ] Documentation describes known constraints:
  - illiquid instruments may have missing bars
  - `DelayedByMinutes == 0` does not guarantee freshness (`LastUpdated` can be old)
  - CryptoFX weekday trading expectation (not weekends)
  - CryptoFX history available from 2021-04-19
- [ ] Documentation includes a Troubleshooting section:
  - “Why are my bars missing?”
  - “Why are quotes delayed?”
  - “Why did I get 429?”
- [ ] Documentation includes quick code examples for `get_latest_quotes` and `get_ohlc_bars`
- [ ] Documentation includes a note that we intentionally use **InfoPrices** (not **Prices**) for polling watchlists
  - InfoPrices are **market-data snapshots**; do not assume they are tradeable quotes
  - Trade execution and tradeable pricing concerns belong to Epic 005 (orders) and its supporting Saxo surfaces

## Technical Details

### Output File
Create or update:
- `docs/MARKET_DATA_GUIDE.md`

### Suggested Sections
1. Overview
2. Endpoint cheat sheet (quick reference table)
3. Normalized data contracts (instrument_id, quote, bars, data_quality, freshness)
4. Quotes (InfoPrices list)
5. Bars (Chart v3)
6. Horizon values + validation
7. Rate limiting and safe polling
8. CryptoFX specifics
9. Troubleshooting / common issues

### Troubleshooting (Primary-source grounded)

#### Why are my bars missing?
- Illiquid instruments may not have enough trades to form bars at small horizons (< 1440 minutes).
- Fewer-than-requested bars is normal.
- Log a warning including `{instrument_id, horizon, requested_count, returned_count}`.

#### Why are quotes delayed?
- Even after subscribing, quotes can remain delayed due to session capability limitations (e.g., sessions defaulting to OrdersOnly).
- Detect delay using `DelayedByMinutes` and evaluate freshness using `LastUpdated`.

#### Why did I get HTTP 429?
- Saxo enforces multi-dimension rate limits (Session/service-group, App/day, etc.).
- Inspect and log all `X-RateLimit-*` headers.
- On 429, respect `Retry-After` first, then rate-reset headers.

### Endpoint Cheat Sheet
Include a quick-reference table covering:

| Endpoint | Purpose | Key Parameters | Common Failure Modes |
|----------|---------|----------------|---------------------|
| `/trade/v1/infoprices/list` | Batch quote retrieval | `AssetType`, `Uics`, `FieldGroups` (defaults to "Quote") | Partial omission (missing invalid UICs), 429 rate limit |
| `/chart/v3/charts` | OHLC bar retrieval | `AssetType`, `Uic`, `Horizon`, `Count` (max 1200), `Mode`, `Time`, `FieldGroups` (defaults to [Data]) | Invalid Horizon (400), missing bars for illiquid instruments, 429 rate limit |

**Key points:**
- InfoPrices `FieldGroups` defaults to `"Quote"` (per reference docs).
- Chart v3 `FieldGroups` defaults to `[Data]` (OHLC samples only).
- Chart v3 `Mode=From/UpTo` includes the specified `Time` (inclusive semantics).
- Both endpoints support multi-dimension rate limit headers (`X-RateLimit-Session-*`, `X-RateLimit-AppDay-*`).
- Reset headers are seconds-until-reset, not epoch timestamps.

## Definition of Done
- [ ] `docs/MARKET_DATA_GUIDE.md` exists and is linked from README (optional)

## Story Points
**Estimate:** 2 points

## Dependencies
- Stories 003-001 .. 003-006

## References
- InfoPrices: https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices
- InfoPrices list: https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade__list
- Pricing semantics (quote fields + list semantics): https://www.developer.saxo/openapi/learn/pricing
- Chart v3: https://developer.saxobank.com/openapi/referencedocs/chart/v3/charts
- Chart learn page: https://www.developer.saxo/openapi/learn/chart
- Rate limiting: https://www.developer.saxo/openapi/learn/rate-limiting
- Missing chart data behavior: https://openapi.help.saxo/hc/en-us/articles/6105016299677-Why-is-chart-data-missing-for-this-instrument
- Delayed quotes after subscribing: https://openapi.help.saxo/hc/en-us/articles/4416934340625-Why-are-quotes-still-delayed-after-I-subscribe-to-market-data
- Horizon values: https://openapi.help.saxo/hc/en-us/articles/4417058210961-What-horizons-can-I-use
