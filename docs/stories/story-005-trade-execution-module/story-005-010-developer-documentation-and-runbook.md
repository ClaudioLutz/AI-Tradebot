# Story 005-010: Developer documentation and runbook

## Summary
Provide developer-facing documentation for configuring, running, and troubleshooting the trade execution module, including a clear safety checklist.

## Background / Context
Trade execution involves many moving parts: environment configuration, rate limits, disclaimers, market state gating,
and portfolio reconciliation. Without clear documentation and a runbook, developers will misconfigure the system or
misinterpret failures.

## Scope
In scope:
- Add a doc page describing:
  - DRY_RUN vs SIM behavior
  - required config keys (SIM base URL, account key, instrument mapping)
  - safe defaults (market state gating, disclaimer policy)
  - logging fields and how to correlate executions to Saxo orders (ExternalReference, OrderId)
  - common failure modes and remediation:
    - 429 rate limiting
    - 409 duplicate-operation conflicts (x-request-id)
    - TradeNotCompleted timeouts (portfolio reconciliation)
    - outstanding disclaimers
- Add “Safety Checklist” for running SIM tests.

## Acceptance Criteria
1. Documentation includes a “Quickstart” with a DRY_RUN example and a SIM example.
2. Documentation includes a troubleshooting section covering:
   - rate limiting headers
   - duplicate-operation window and x-request-id
   - TradeNotCompleted reconciliation
   - disclaimers blocking
3. Documentation lists all structured log fields and their meaning.
4. Documentation clarifies the default auction/market-state policy and how to override it.

## Implementation Notes
- Keep the runbook close to code (e.g., docs/stories/story-005-trade-execution/README.md or docs/epics/epic-005...).
- Include copy/paste curl examples for the key endpoints (precheck, place order, query orders, query positions).

## Test Plan
- Manual doc review:
  - Another developer can configure SIM and run DRY_RUN and SIM example without reading code.
- Link checker (optional):
  - Validate primary-source links are reachable.

## Dependencies / Assumptions
- Requires stable configuration keys and logging structure from Stories 005-001 through 005-008.

## Primary Sources
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/learn/breaking-change-pre-trade-disclaimers-on-openapi
- https://www.developer.saxo/openapi/learn/reference-data
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/referencedocs/port/v1/orders/get__port
- https://www.developer.saxo/openapi/referencedocs/port/v1/positions/get__port__positions
