# Epic 003 Stories: Market Data Retrieval

This folder contains the implementation stories for **Epic 003: Market Data Retrieval Module (Saxo)**.

## Prereqs (avoid implementation churn)
- Requires **Epic 002 instrument resolution**: watchlist entries must provide `{asset_type, uic, symbol}`.
- Requires working **OAuth tokens** / Saxo session for live calls.
- Real-time market data can still appear delayed depending on **session capability** (common pitfall).
  - Always inspect `DelayedByMinutes` and `LastUpdated`.

## Key Technical Decisions (Post-Review)
Based on technical review against Saxo primary documentation, these stories incorporate critical refinements:

1. **Horizon Validation (Story 003-003)**
   - Default validation uses Saxo Support Center's stable "supported" set: `1, 5, 10, 15, 30, 60, 120, 240, 360, 480, 1440, 10080, 43200`
   - Saxo reference docs list additional values (2, 3, 180, 300, etc.) that may not be consistently supported across all instruments/environments
   - Escape hatch available via config flag for advanced mode

2. **FieldGroups Defaults (Stories 003-002 & 003-003)**
   - InfoPrices `/list`: defaults to `"Quote"` when not specified (per reference docs)
   - Chart v3: defaults to `[Data]` only (OHLC samples) when not specified (per reference docs)
   - This reduces over-fetching and bandwidth issues

3. **Rate Limiting (Story 003-004)**
   - Multi-dimension headers (`X-RateLimit-Session-*`, `X-RateLimit-AppDay-*`) must all be parsed and logged
   - Reset headers are **seconds-until-reset**, not epoch timestamps
   - Some endpoints/patterns can consume quota faster than expected; always rely on returned headers
   - Removed specific "batch counts as N+1" claim; use header-based adaptive throttling instead

4. **Chart v3 Mode Semantics (Story 003-003)**
   - `Mode=From/UpTo` with `Time` parameter is **inclusive** (the bar at that timestamp is included)
   - This is critical for correct duplicate bar overwrite logic

5. **Freshness Threshold (Story 003-005)**
   - Recommended default: `STALE_QUOTE_SECONDS = 120–300` seconds (2–5 minutes)
   - Instrument liquidity dependent; illiquid instruments can have old `LastUpdated` even when `DelayedByMinutes == 0`

6. **Freshness Placement (Story 003-001)**
   - `freshness` data lives at top-level instrument container (not inside `quote`)
   - Allows unified freshness evaluation for both quotes and bars

## Story List
- **Story 003-001** — Define market data contracts + normalization schema
- **Story 003-002** — Batch quote retrieval via InfoPrices list
- **Story 003-003** — Bar retrieval via Chart v3
- **Story 003-004** — Rate limit + retry middleware (Saxo-specific)
- **Story 003-005** — Data freshness + market-state heuristics
- **Story 003-006** — Unit tests with mocked Saxo responses
- **Story 003-007** — Developer docs for market data

## Parent Epic
- [Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)
