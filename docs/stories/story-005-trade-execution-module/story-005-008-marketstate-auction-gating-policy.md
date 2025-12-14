# Story 005-008: MarketState / auction-state gating policy for execution

## Summary
Define a default execution policy for Saxo MarketState and auction-related states, and integrate it as a hard gate before precheck/placement.

## Background / Context
Saxo exposes market state values such as Open, OpeningAuction, ClosingAuction, IntraDayAuction, and TradingAtLast.
These states can materially impact order behavior, liquidity, and execution quality. Epic 004 already identified
auction states as a cross-cutting policy decision; Epic 005 must formalize the default so acceptance criteria remain consistent.

## Scope
In scope:
- Define and implement an execution gate `is_trading_allowed(market_state)` with safe defaults.
- Default policy (recommended):
  - Allow: Open
  - Block: Closed, Unknown, OpeningAuction, ClosingAuction, IntraDayAuction, TradingAtLast
  - Configurable overrides for advanced users (e.g., allow PreMarket/PostMarket for specific instruments)
- Determine market state using the best available source (in priority order):
  1) Latest Quote/Price snapshot MarketState (if available from market data module)
  2) Portfolio position/open-order market-state fields (if present)
  3) Instrument session state (if available in instrument details / market data)
- Integrate gate before precheck (so you don’t precheck trades you will not place).

## Acceptance Criteria
1. Default behavior blocks execution during auction and TradingAtLast states.
2. Gate is evaluated before precheck/placement and returns a structured “blocked_by_market_state” result.
3. Gate is configurable (e.g., allow PreMarket/PostMarket) without code change.
4. All blocked events are logged with `{asset_type, uic, market_state, policy_version, external_reference}`.
5. If market state is missing/unknown, behavior is conservative (block) unless explicitly configured otherwise.

## Implementation Notes
- Keep gating independent from strategy logic: strategies emit signals; executor decides whether trading is allowed *now*.
- Centralize the policy in one module so future epics (risk, live) can reuse it.
- Add “why” metadata in logs so a human can distinguish:
  - “AuctionStateBlocked” vs “Closed” vs “Unknown”

## Test Plan
- Unit tests:
  - Each MarketState value maps to allow/block correctly under default config.
  - Config override allows selected states.
  - Missing state defaults to block.
- Integration (SIM):
  - If market data provides MarketState, verify gate respects it (log-only check is sufficient if auction states are hard to reproduce).

## Dependencies / Assumptions
- Depends on a market-state signal from market data (Epic 003/004) OR a portfolio-derived fallback.
- This policy should remain stable across Epic 004 and Epic 005; document it clearly for developers.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments/get__ref__details/schema-instrumentsessionstate
- https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade/schema-quote
