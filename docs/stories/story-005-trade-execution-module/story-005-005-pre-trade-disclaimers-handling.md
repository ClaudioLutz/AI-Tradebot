# Story 005-005: Pre-trade disclaimers handling (mandatory support plan)

## Summary
Implement support for Saxo pre-trade disclaimers surfaced via precheck/order placement, including retrieval of disclaimer details and (optionally) registering responses.

## Background / Context
Saxo has announced that handling pre-trade disclaimers will become mandatory for all OpenAPI apps from May 2025.
Orders can be rejected at any time if there are outstanding disclaimers. Precheck and/or order placement can
surface disclaimer tokens that must be handled (blocking vs normal disclaimers).

## Scope
In scope:
- Persist disclaimer tokens surfaced via precheck into `PrecheckOutcome`.
- Implement a “disclaimer resolution” service:
  - GET /dm/v2/disclaimers to fetch the disclaimer texts / metadata for tokens.
  - Policy-driven response handling:
    - Default: **block trading** and log actionable message (safe-by-default).
    - Optional (config): auto-accept *normal* disclaimers only, via POST /dm/v2/disclaimers.
- Ensure placement is blocked when disclaimers are outstanding and policy is “block”.

Out of scope:
- UI/UX for presenting disclaimers to a human
- Accepting blocking disclaimers (not possible by definition)

## Acceptance Criteria
1. If precheck returns `PreTradeDisclaimers`, executor does not place the order unless the configured policy allows it.
2. Default behavior is safe: executor logs and returns a “blocked_by_disclaimer” outcome.
3. The system can fetch disclaimer details for the provided tokens.
4. If configured for auto-accept:
   - Only “normal” disclaimers are accepted automatically.
   - Blocking disclaimers always block trading with an explicit log entry.
5. Disclaimer tokens and handling outcomes are logged with correlation fields:
   `{external_reference, request_id, account_key, asset_type, uic}`.

## Implementation Notes
- Disclaimer logic should be isolated so it can be unit-tested independently from precheck/placement.
- Store (token → disclaimer metadata) in a short TTL cache to avoid repeated DM calls during loops.
- Treat disclaimers as a “hard gate” in orchestration:
  - precheck ok + disclaimers ok → may place
  - precheck ok + disclaimers outstanding → block or resolve first, depending on policy

## Test Plan
- Unit tests (mock HTTP):
  - Precheck returns tokens → executor blocks by default.
  - GET disclaimers returns disclaimer content → stored and logged.
  - Auto-accept mode posts responses only for acceptable disclaimers; blocks if any blocking disclaimers exist.
- Integration (SIM):
  - If an instrument/account triggers disclaimers, verify blocking behavior and DM retrieval.
  - If no disclaimers occur, ensure code path remains inactive (no DM calls).

## Dependencies / Assumptions
- Depends on precheck output (Story 005-003).
- Requires DM service group permissions for the application.
- Configuration must include a disclaimer policy (block vs auto-accept).

## Primary Sources
- https://www.developer.saxo/openapi/learn/breaking-change-pre-trade-disclaimers-on-openapi
- https://www.developer.saxo/openapi/referencedocs/dm/v2/disclaimers/get__dm__disclaimers
- https://www.developer.saxo/openapi/referencedocs/dm/v2/disclaimers/post__dm__disclaimers
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
