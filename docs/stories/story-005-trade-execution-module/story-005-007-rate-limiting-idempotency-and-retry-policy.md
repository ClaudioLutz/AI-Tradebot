# Story 005-007: Rate limiting, idempotency, and retry policy

## Summary
Define and implement a robust execution reliability layer: enforce Saxo rate limits, avoid duplicate order operations, and implement safe retry/backoff behavior.

## Background / Context
Saxo OpenAPI enforces global and per-session limits, including a max of 1 order per session per second.
It also rejects identical order operations within a rolling 15-second window unless the caller uses distinct
`x-request-id` values. Placement can also timeout (TradeNotCompleted) where the order may still have been placed.
These constraints must be reflected in acceptance criteria and implementation to prevent accidental duplication
and to maintain system stability.

## Scope
In scope:
- Enforce a local rate limiter for order placement (and other order mutations) to respect 1 order/sec/session.
- Implement retry policy by error category:
  - 429 Too Many Requests → backoff until reset (respect rate limit headers when present)
  - 5xx / transient network errors → limited retries with exponential backoff + jitter
  - 409 Conflict (duplicate operation) → do not retry automatically; treat as de-bounce failure
  - TradeNotCompleted → do not retry placement; reconcile via portfolio
- Ensure the orchestrator loop never crashes on HTTP exceptions.

## Acceptance Criteria
1. Executor enforces max 1 order placement per second per session (local limiter).
2. On 429, executor backs off and retries up to N times (configurable), and logs rate limit headers when present.
3. On 409 conflict (duplicate operation), executor does not retry automatically and logs an explicit message
   referencing x-request-id / duplicate-window behavior.
4. On TradeNotCompleted/timeouts for exchange-based products, executor performs reconciliation instead of retrying placement.
5. All retries include correlation fields (`external_reference`, `request_id`) and do not violate duplicate-operation protections.

## Implementation Notes
- Use a token-bucket or simple “sleep until next slot” approach for 1 order/sec; keep it deterministic.
- Parse rate limit headers if present:
  - X-RateLimit-SessionOrders-Limit / Remaining / Reset
  - X-RateLimit-SessionRequests-* (as applicable)
- Keep retry budget low (e.g., 2–3 retries) to avoid cascading actions in fast loops.
- Ensure request_id changes between separate intentional order operations; for “retry same operation” you must decide whether to reuse or change.
  - Default: do NOT re-try order placement; reconcile.

## Test Plan
- Unit tests:
  - Rate limiter blocks/queues a second order attempt within 1 second.
  - 429 response triggers backoff (simulate header Reset=1).
  - 409 conflict is treated as terminal for that intent.
  - Timeout triggers reconciliation path, not a second placement.

## Dependencies / Assumptions
- Depends on Story 005-004 reconciliation mechanics and Story 005-001 request_id header.
- Requires a clock abstraction or injectable sleep for deterministic tests.

## Primary Sources
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
