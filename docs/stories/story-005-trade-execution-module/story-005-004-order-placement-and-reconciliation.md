# Story 005-004: Order placement and reconciliation (SIM)

## Summary
Place market orders in SIM after a successful precheck, and reconcile uncertain outcomes (timeouts / TradeNotCompleted) by querying Portfolio open orders.

## Background / Context
Order placement can be subject to timeouts or uncertain status, especially on exchange-based products.
Saxo explicitly documents the `TradeNotCompleted` scenario and recommends querying the portfolio using the returned OrderId (when present).
Additionally, duplicate order protections and rate limiting must be respected.

## Scope
In scope:
- Implement POST /trade/v2/orders for market orders (Stock + FxSpot) in SIM.
- Use `external_reference` and `x-request-id`.
- Handle outcomes:
  - Success with OrderId
  - Failure with ErrorInfo
  - Timeout / TradeNotCompleted → run reconciliation logic:
    - if OrderId present → query Portfolio open orders by OrderId
    - else → query open orders filtered by ExternalReference (if present in order response model in portfolio) OR fall back to time-window logging-only
- Ensure DRY_RUN never places orders.

## Acceptance Criteria
1. In SIM (`dry_run=False`), a successful precheck leads to exactly one placement attempt.
2. Placement uses the SIM base URL and correct endpoint for /trade/v2/orders.
3. Placement response handling:
   - On success, OrderId is captured and logged.
   - On failure, ErrorInfo is logged and no further action is attempted for that intent.
4. Timeouts / TradeNotCompleted handling:
   - If OrderId is present, executor queries Portfolio orders to determine current order status.
   - Reconciliation outcome is logged (e.g., “placed”, “not found”, “unknown”).
5. Placement is never attempted if precheck failed or disclaimers policy blocks the trade.

## Implementation Notes
- Prefer `OrderDuration.DurationType = DayOrder` for Market orders unless there is a strategy-level override.
- Ensure the body uses the Saxo field names exactly (AccountKey, Amount, BuySell, OrderType, Uic, AssetType, OrderDuration, ExternalReference, ManualOrder).
- Build reconciliation around `GET /port/v1/orders` using `OrderId` filter.
- Keep reconciliation bounded (e.g., single query, then mark unknown; do not loop indefinitely).

## Test Plan
- Unit tests (mock HTTP):
  - Success path returns OrderId.
  - Failure path returns ErrorInfo.
  - Timeout path triggers portfolio query by OrderId.
- Integration (SIM):
  - Place a small market order.
  - Verify order appears in open orders or is immediately filled (depending on instrument), and logs show OrderId.

## Dependencies / Assumptions
- Depends on precheck (Story 005-003).
- Depends on portfolio orders query endpoint for reconciliation.
- Assumes OAuth token already available and SIM environment configured.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/referencedocs/port/v1/orders/get__port
- https://www.developer.saxo/openapi/learn/rate-limiting
