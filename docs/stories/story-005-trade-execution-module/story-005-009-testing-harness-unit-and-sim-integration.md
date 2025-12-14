# Story 005-009: Testing harness: unit + SIM integration for execution module

## Summary
Create a testing strategy and harness that validates execution behavior with deterministic unit tests and optional SIM integration tests.

## Background / Context
The execution module is safety-critical; regressions can cause duplicate orders or unintended exposure.
A dedicated harness helps validate request-shaping, retry behavior, and gating rules, and provides a clear path
for running end-to-end tests in SIM.

## Scope
In scope:
- Unit test suite with mocked HTTP client responses for:
  - instrument details
  - precheck
  - placement
  - portfolio positions / orders
  - disclaimer APIs
- SIM integration tests (opt-in, environment variable gated):
  - Precheck-only test (DRY_RUN style)
  - Place-and-reconcile test (SIM)
- Deterministic “clock” abstraction to test rate limiting and backoff without real sleeps.

## Acceptance Criteria
1. Unit tests cover:
   - precheck-first behavior
   - DRY_RUN vs SIM behavior
   - duplicate buy prevention and sell-without-position skip
   - rate limiting and 429 backoff behavior
   - timeout/TradeNotCompleted reconciliation path
   - disclaimers blocking behavior
2. Integration tests can run against SIM when credentials are present and are skipped otherwise.
3. Test harness produces readable logs/artifacts to debug failures (request/response snapshots with redaction).

## Implementation Notes
- For integration tests:
  - Use a dedicated SIM account key and restrict order sizes to minimal safe amounts.
  - Ensure tests clean up or at least log created orders/positions.
- Consider contract fixtures with recorded JSON (VCR-style) for non-sensitive endpoints (ref data), if allowed.

## Test Plan
- This story is itself the testing plan:
  - Implement mocks and fixtures.
  - Add CI target “unit”.
  - Add optional CI/manual target “sim-integration”.

## Dependencies / Assumptions
- Depends on all prior stories for the concrete executor components.
- Requires a way to inject HTTP client and clock into executor.

## Primary Sources
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/referencedocs/port/v1/positions/get__port__positions
- https://www.developer.saxo/openapi/referencedocs/port/v1/orders/get__port
