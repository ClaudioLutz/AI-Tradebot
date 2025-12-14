# Story 005-001: Execution interface and OrderIntent schema

## Summary
Define the public interface for the trade execution module, and a stable internal schema to convert strategy signals into *order intents* (precheck + placement).

## Background / Context
Epic 004 introduced strategies that emit signals. Epic 005 must convert those signals into orders
in a way that is safe, testable, and debuggable. A stable schema is needed so downstream concerns
(instrument validation, precheck, placement, reconciliation, logging) are consistent and reusable.

## Scope
In scope:
- Define `TradeExecutor` (or equivalent) interface and core DTOs:
  - `OrderIntent` (instrument, side, quantity, order type, duration, correlation fields)
  - `PrecheckResult` (normalized success/failure + cost/margin fields + disclaimers payload)
  - `ExecutionResult` (dry-run vs sim outcomes, order id(s), reconciliation status)
- Define correlation fields:
  - `external_reference` (<= 50 chars) for Saxo order and precheck calls
  - `request_id` (x-request-id header) for order mutations to protect against duplicates and enable safe retries
- Standardize execution logging payload shape.

Out of scope:
- Any live trading (LIVE environment)
- Advanced order types (Limit/Stop/OCO/related orders) beyond what the epic requires

## Acceptance Criteria
1. `OrderIntent` supports the minimum fields needed to place Stock and FxSpot market orders:
   `(account_key, asset_type, uic, buy_sell, amount, order_type='Market', order_duration, external_reference, request_id)`.
2. `external_reference` is generated for every intent and is validated to be <= 50 characters.
3. `request_id` is generated for every mutation attempt and is emitted as `x-request-id` for:
   - POST /trade/v2/orders
   - PATCH /trade/v2/orders (future)
   - DELETE /trade/v2/orders (future)
4. Logging context contains at minimum:
   `{instrument_id, asset_type, uic, symbol, account_key, external_reference, request_id, order_id?, http_status?}`.
5. Interface supports `dry_run: bool` to drive DRY_RUN vs SIM behavior, without changing caller code.

## Implementation Notes
- Treat `(AssetType, Uic)` as the canonical instrument key (Saxo docs consistently describe instruments by UIC + AssetType).
- Use an internal `ExecutionContext` to carry correlation/log metadata through all steps.
- ExternalReference:
  - Keep short and deterministic enough for tracing (e.g., "E005:{strategy}:{ts}:{hash}").
  - Enforce max-length and ensure truncation is logged when applied.
- x-request-id:
  - Generate a UUIDv4 per placement attempt and persist it in logs.
  - Do not reuse request_id across attempts unless you explicitly want Saxo to treat the operation as the same.
- Default order duration:
  - For market orders, prefer `DayOrder` unless strategy-specific configuration says otherwise.

## Test Plan
- Unit tests:
  - Validate `external_reference` length handling (accept <= 50; reject/trim > 50 with log).
  - Validate `request_id` generation and header injection into HTTP client.
  - Validate serialization of `OrderIntent` into the exact request body fields expected by Saxo.
- Contract-style tests:
  - Snapshot JSON for a Stock market order and an FxSpot market order.

## Dependencies / Assumptions
- Requires environment configuration providing:
  - AccountKey for SIM trading
  - Base URL for SIM: `https://gateway.saxobank.com/sim/openapi/`
  - OAuth token handling (already implemented elsewhere)
- Signals produced by Epic 004 must provide enough information to map to an instrument (AssetType + Uic) and a side.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade/schema-orderdurationtype
- https://www.developer.saxo/openapi/learn/reference-data
