# Story 005-002: Instrument validation and orderability checks

## Summary
Before prechecking or placing an order, validate the instrument configuration and trading constraints using Saxo Reference Data (instrument details).

## Background / Context
Saxo instruments vary by asset class and may have specific rules (supported order types, order duration types,
amount decimals, increment size, market state, and tradability). A precheck can fail for many reasons; however,
validating obvious constraints locally improves error clarity and avoids avoidable API calls.

## Scope
In scope:
- Fetch instrument details for a specific `(Uic, AssetType)` and use it to validate:
  - `IsTradable` / `NonTradableReason` (when available in the returned field groups)
  - Amount formatting constraints (AmountDecimals, IncrementSize, LotSize / minimums when available)
  - Supported order types and duration types (SupportedOrderTypes → duration types per order type)
- Cache instrument details (in-memory) with a short TTL to avoid repeated calls.
- Produce a normalized `InstrumentConstraints` object used by precheck/placement.

Out of scope:
- Full instrument discovery workflows
- Options, futures, CFDs, mutual funds, algorithmic orders

## Acceptance Criteria
1. Executor can retrieve instrument details for `(Uic, AssetType)` using the dedicated “instrument details” endpoint.
2. For Stock and FxSpot:
   - Amount is validated to match `AmountDecimals`.
   - Amount respects `IncrementSize` when present (e.g., FX increments).
3. Module validates that `OrderType='Market'` is supported for the instrument (via SupportedOrderTypes).
4. Module validates that chosen `OrderDuration.DurationType` (default DayOrder) is supported for Market orders when the instrument provides duration-type restrictions.
5. If `IsTradable` is false (or `NonTradableReason` indicates not tradable), executor refuses to place and logs a structured reason.
6. Instrument-details lookup failures do not crash orchestration; they result in a failed execution with actionable logging.

## Implementation Notes
- Use `FieldGroups=MarketData` (or broader) when calling instrument details so you receive validation-relevant fields.
- Store constraints as a pure data object (no HTTP client dependency) so it can be unit-tested.
- When fields are missing for an asset type, fall back conservatively:
  - If SupportedOrderTypes is missing, rely on precheck (but log that local validation was incomplete).
- Prefer a small TTL cache (e.g., 10–60 minutes) because instrument constraints can change intraday.

## Test Plan
- Unit tests:
  - Parsing of instrument details into constraints (AmountDecimals, IncrementSize, SupportedOrderTypes).
  - Amount validation for Stock (commonly 0 decimals) and FxSpot (often 0 decimals but constrained by increment size).
- Integration (SIM):
  - Fetch instrument details for one Stock Uic and one FxSpot Uic used in existing configs.
  - Ensure market order intent passes local validation before precheck.

## Dependencies / Assumptions
- Requires access to the Reference Data service group.
- Caller must provide AccountKey (and optionally ClientKey) if required by the endpoint.

## Primary Sources
- https://www.developer.saxo/openapi/learn/reference-data
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments/get__ref__details_uic_assettype
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments/get__ref__details_uic_assettype/schema-supportedordertypesetting
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments
