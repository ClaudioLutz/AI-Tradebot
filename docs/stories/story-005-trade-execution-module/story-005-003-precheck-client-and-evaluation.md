# Story 005-003: Precheck client and evaluation

## Summary
Implement a robust precheck step for all orders using Saxo’s precheck endpoint, normalize the result, and block placement when precheck indicates failure.

## Background / Context
Epic 005 requires a strict “precheck-first” workflow. Saxo’s precheck endpoint can validate the order,
return estimated costs/margin, and surface required pre-trade disclaimers. Importantly, precheck may return
HTTP 200 even when the order is not valid; the client must check the response payload for errors.

## Scope
In scope:
- Implement HTTP client wrapper for POST /trade/v2/orders/precheck.
- Map `OrderIntent` → Precheck request body (Market orders, Stock + FxSpot).
- Normalize response into `PrecheckOutcome`:
  - `ok: bool`
  - `error_info` (code/message) when not ok
  - `estimated_cost`, `margin_impact` (if returned)
  - `pre_trade_disclaimers` payload (for downstream story)
- Enforce rule: placement is only attempted when precheck is ok and disclaimers policy allows.

## Acceptance Criteria
1. Every execution attempt calls precheck first (DRY_RUN and SIM).
2. Precheck response is evaluated correctly:
   - HTTP 200 is not treated as success unless `ErrorInfo` (or equivalent) indicates success.
3. Precheck errors are logged with:
   `{account_key, asset_type, uic, external_reference, http_status, error_code, error_message}`.
4. In DRY_RUN:
   - precheck is executed and logged; no placement occurs.
5. In SIM:
   - precheck must succeed before placement is attempted.
6. Precheck handling does not crash orchestration on HTTP errors/timeouts; it returns a structured failure.

## Implementation Notes
- Implement a “field groups” selection for precheck if you want costs/margin fields; keep it minimal at first.
- Capture and persist the raw precheck response in debug logs (with redaction if needed) to aid troubleshooting.
- Normalize the response model even if Saxo adds fields over time (treat unknown fields as ignorable).

## Test Plan
- Unit tests (mock HTTP):
  - HTTP 200 with ErrorInfo populated → outcome is failure.
  - HTTP 4xx/5xx → outcome is failure with http_status captured.
  - Response containing PreTradeDisclaimers → outcome carries disclaimers payload.
- Integration (SIM):
  - Precheck a small market order for a known tradable instrument.

## Dependencies / Assumptions
- Depends on Story 005-001 (schema) and Story 005-002 (instrument constraints) for request shaping/validation.
- Disclaimer handling details are specified in Story 005-005 (the precheck must forward the data).

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/learn/breaking-change-pre-trade-disclaimers-on-openapi
