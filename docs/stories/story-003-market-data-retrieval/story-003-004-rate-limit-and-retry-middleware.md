# Story 003-004: Rate Limit + Retry Middleware (Saxo-specific)

## Story Overview
Add Saxo-aware rate limit and retry behavior to market data retrieval. The goal is to prevent self-inflicted throttling, handle **HTTP 429** correctly, and expose rate budget information in logs.

This story is **market-data focused** (InfoPrices + Charts). It does not introduce streaming.

## Parent Epic
[Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)

## User Story
**As a** developer  
**I want to** respect Saxo rate limits and implement safe retries/backoff  
**So that** market data retrieval remains stable and does not break long-running bot operation

## Acceptance Criteria
- [ ] Parse and log Saxo `X-RateLimit-*` headers when present
  - Must log **all dimensions** present (e.g., Session, AppDay, Orders, etc.)
- [ ] Implement adaptive throttling:
  - configurable minimum polling interval per endpoint category (quotes vs bars)
  - optionally sleep when remaining budget is low
- [ ] Implement retry policy:
  - Retry on: 429, 5xx, timeouts/transient network errors
  - Do NOT retry on: 400, 401, 403
- [ ] For 429, respect the reset window:
  - Prefer `Retry-After` when present
  - Otherwise use the most appropriate `X-RateLimit-*-Reset` value
- [ ] Retries use exponential backoff with jitter
- [ ] 429 logging includes the JSON error payload and error code (e.g., `RateLimitExceeded`) when available
- [ ] Behavior is testable via unit tests (mocked responses)

## Technical Details

### Prerequisites
- Stories 003-002 and 003-003 exist (or are in progress) so we can apply middleware to real call sites

### Target Module(s)
- `data/saxo_client.py` (preferred location for HTTP concerns)
- and/or `data/market_data.py` (if limiting changes to the client is desired)

### Saxo Rate Limit Model (Primary Source)
Saxo rate limiting can include multiple independent limit buckets, such as:
- **App/day** limit
- **Session/service-group** limit (commonly 120/min)
- **Orders/session** limit (not used by Epic 003, but headers may still appear)

**Important note on batch request accounting:**
Some endpoints and patterns can consume quota faster than expected. Always rely on the returned `X-RateLimit-*` headers to adapt throttling, rather than assuming a fixed request-to-quota ratio.

### Headers to Parse
Saxo returns multiple rate limit headers, often in these shapes:
- `X-RateLimit-Session-Remaining`
- `X-RateLimit-Session-Reset`
- `X-RateLimit-AppDay-Remaining`
- `X-RateLimit-AppDay-Reset`

**Requirement:** do not hardcode only Session headers; parse and log whatever `X-RateLimit-.*` headers are present.

**Reset header format:**
Reset headers are expressed as **seconds-until-reset**, not epoch timestamps. Ensure backoff calculations interpret them correctly.

### 429 Response Shape
Saxo’s 429 typically includes a JSON error structure and an error code such as:
- `RateLimitExceeded`

**Requirement:** for 429s, capture (and log) the JSON body and rate limit headers.

### Retry-After Rule
Implement this precedence:
1. if `Retry-After` exists, wait that many seconds
2. else, use the best available `X-RateLimit-*-Reset` header (usually seconds until reset)
3. else, fallback to exponential backoff (bounded)

### Suggested Design
Option A (recommended):
- Extend `SaxoClient.get()` to return both JSON and headers (or provide a new method `get_with_headers()`)
- Implement a reusable helper:
  - `request_with_retry(method, path, params, ...)`

Option B:
- Wrap at `market_data.py` level by calling `requests.get` directly.

Prefer Option A to keep HTTP behavior centralized.

### Minimum Polling Interval
Add configuration values (later surfaced in config) such as:
- `MIN_QUOTES_POLL_SECONDS`
- `MIN_BARS_POLL_SECONDS`

The market data module must not poll more frequently than these values.

## Definition of Done
- [ ] 429 backoff respects Retry-After / rate reset headers (no busy-loop)
- [ ] Retries limited to a bounded max (e.g., 3)
- [ ] Logs contain rate budget information for all header dimensions present

## Testing
Unit tests in Story 003-006 should cover:
- multi-dimension header parsing (Session + AppDay at minimum)
- Retry-After precedence over X-RateLimit-*-Reset
- 429 backoff logic
- no-retry on 400/401/403

## Story Points
**Estimate:** 3 points

## Dependencies
- Stories 003-002 and 003-003

## References
- Saxo Learn - Rate limiting: https://www.developer.saxo/openapi/learn/rate-limiting
- Saxo Support - Avoid exceeding rate limits (429 details): https://openapi.help.saxo/hc/en-us/articles/4417694856849-How-do-I-avoid-exceeding-my-rate-limit
