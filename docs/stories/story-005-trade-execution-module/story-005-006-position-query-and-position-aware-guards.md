# Story 005-006: Position query and position-aware execution guards

## Summary
Implement the minimal position model and guardrails required by Epic 005: prevent duplicate buys (or warn), and ensure sells only occur when a position exists.

## Background / Context
Epic 005 requires sell orders to be position-aware: only sell if there is an existing position.
Additionally, the module should prevent duplicate buys (or at least log a warning), to avoid repeatedly
increasing exposure on repeated buy signals.

## Scope
In scope:
- Implement position query via Portfolio Positions endpoints.
- Normalize positions into a simple in-memory view keyed by `(AssetType, Uic)`:
  - quantity (net)
  - side (long/short if applicable; default assume long-only strategy)
  - account_key association
- Implement guards:
  - Buy intent:
    - if position already exists (net amount > 0), skip placement (or configurable “warn only”).
  - Sell intent:
    - if no position exists, skip placement.
    - amount for sell is either:
      - configured fixed quantity, or
      - “close full position” (default safe option for strategies emitting exit signals).

## Acceptance Criteria
1. Executor can query positions for the configured account and identify net position per instrument.
2. Buy guard:
   - If a net long position exists, executor does not place an additional buy by default, and logs `duplicate_buy_prevented`.
3. Sell guard:
   - If no position exists, executor does not precheck/place the sell and logs `no_position_to_sell`.
4. Position query failures are handled gracefully and do not crash the orchestration loop.
5. Works for both Stock and FxSpot positions in SIM.

## Implementation Notes
- Prefer NetPositions if you want a consolidated view; Positions can include multiple legs/lots.
- Keep the initial implementation long-only:
  - do not open short positions unless explicitly configured later.
- Use the market-state fields returned by positions (where available) only as a supplemental signal; the primary gating is handled in Story 005-008.

## Test Plan
- Unit tests (mock positions response):
  - No position → sell skipped.
  - Existing position → buy skipped.
  - Existing position → sell amount computed correctly (full close or configured).
- Integration (SIM):
  - Create a small position via buy order, then verify subsequent buy signals are skipped.
  - Trigger sell, verify sell is placed and position reduces/closes.

## Dependencies / Assumptions
- Requires access to Portfolio positions endpoints.
- Assumes consistent instrument id mapping between market data signals and portfolio responses.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/port/v1/positions/get__port__positions
- https://www.developer.saxo/openapi/referencedocs/port/v1/netpositions/get__port__netpositions
- https://www.developer.saxo/openapi/learn/reference-data
