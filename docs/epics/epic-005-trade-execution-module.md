# Epic 005: Trade Execution Module (Saxo)

## Epic Overview
Develop the execution module (`execution/trade_executor.py`) responsible for order placement via Saxo OpenAPI with a **precheck-first workflow**. This module translates strategy signals into validated orders using `{ClientKey, AccountKey, AssetType, Uic}` tuples, with strict adherence to Saxo's institutional infrastructure constraints.

## Business Value
- Enables safe SIM trading with precheck validation before every order
- Converts trading signals into actionable Saxo orders
- Provides DRY_RUN mode for testing without actual placement
- Implements position management using Saxo's **NetPosition** model for accurate exposure tracking
- Establishes foundation for risk management and cost estimation
- Ensures regulatory compliance via correct `ManualOrder` flagging

## Scope

### In Scope
- `execution/trade_executor.py` module creation
- **Precheck-first workflow**: Validate order and estimate costs BEFORE placement
- Order submission functions (buy/sell market orders via `/trade/v2/orders`)
- **DRY_RUN mode**: Precheck only, log results without placing order
- **SIM mode**: Full precheck + order placement in SIM environment
- Position checking via Saxo `/port/v1/netpositions` (preferred over raw positions)
- Basic quantity/sizing logic (Base Units for FX, Shares for Stock)
- Order execution confirmation and logging with Saxo OrderIds
- Comprehensive error handling with HTTP status and `ModelState` parsing
- Support for multiple asset types (`Stock`, `FxSpot`, `FxCrypto`)
- **Idempotency**: Client-side duplicate prevention via `ExternalReference` scanning

### Out of Scope
- Advanced order types (limit, stop-loss, trailing stop)
- Dynamic position sizing algorithms (e.g., Kelly criterion)
- Portfolio rebalancing logic
- Multi-leg strategies (spreads, combos)
- Live trading (SIM environment only for this epic)
- Complex risk management rules (max drawdown, exposure limits)
- GUI development (though backend must support `ManualOrder` toggling)

## Technical Considerations

### 1. Client-Account Hierarchy
Saxo distinguishes between `ClientKey` (legal entity/user) and `AccountKey` (settlement container).
- **ClientKey**: Used for consolidated portfolio views.
- **AccountKey**: Used for specific ledger and P&L.
- The execution module must explicitly manage this context.
- **Currency Normalization**: Querying by ClientKey aggregates exposure in client base currency; AccountKey returns account currency.

### 2. Regulatory Compliance (ManualOrder)
The `ManualOrder` boolean in `/trade/v2/orders` is a regulatory classification, not just metadata.
- **`true`**: Order originated from human interaction (GUI click).
- **`false`**: Order originated from automated system (Algo/Bot).
- **Requirement**: This epic focuses on automated execution, so defaults to `false`, but the schema must support `true` for future hybrid/GUI use cases.

### 3. Order Duration Constraints
- **Market Orders**: Must explicitly use `{"DurationType": "DayOrder"}`.
- Saxo rejects Market orders without a duration or with semantically ambiguous durations like GTC.

### 4. Asset Identification & Migration
- Instruments identified by `Uic` + `AssetType`.
- **Migration Alert**: Crypto FX pairs are moving from `FxSpot` to `FxCrypto`.
- Logic must dynamically handle `AssetType` to support this migration.

### 5. Quantity Semantics
- **FX**: Amount is in **Base Units** (e.g., 100,000), NOT Lots.
- **Equities**: Amount is in **Shares**.
- UI/Config interpretation of "Lots" must be converted to base units *before* the API call.

### 6. Idempotency & Duplicate Prevention
- `ExternalReference` is **NOT** unique on the server side.
- **Strategy**:
  1. Generate UUID for `ExternalReference`.
  2. If placement response is uncertain (timeout/5xx), **SCAN** `/port/v1/orders` filtering by that `ExternalReference`.
  3. Only retry if the scan confirms the order is missing.

### 7. NetPositions vs Positions
- Use `/port/v1/netpositions` for exposure monitoring.
- **Netting Modes**: Handles Intraday vs End-of-Day netting correctly.
- Prevents "gross exposure" fallacies (e.g., seeing Long 10k and Short 10k as separate risks instead of Flat).

## Precheck-First Workflow
Saxo's `/trade/v2/orders/precheck` endpoint validates orders and estimates costs before placement:

1. **Construct order request** (AccountKey, AssetType, Uic, OrderType, BuySell, Amount, ManualOrder=False, Duration=DayOrder)
2. **Call precheck endpoint** → Returns estimated costs, margin requirements, validation errors
3. **Evaluate precheck result**:
   - ✅ If successful: Proceed to placement (or log if DRY_RUN)
   - ❌ If failed: Log error with diagnostic info, do NOT place order
4. **Place order** (if not DRY_RUN): POST to `/trade/v2/orders` with same request
5. **Confirm and log**: Capture OrderId, status, and timestamps

## Execution Workflow

### Full Cycle for BUY Signal
```
1. Receive signal: {"Stock:211": "BUY"}
2. Extract instrument data: asset_type=Stock, uic=211, symbol=AAPL
3. Check existing NetPositions (/port/v1/netpositions)
   → If NetPosition > 0: Log "Already holding Stock:211 (AAPL)", skip or average-in
   → If Flat/Short: Proceed
4. Precheck order:
   → POST /trade/v2/orders/precheck
   → Payload: {
        AccountKey: "...",
        AssetType: "Stock",
        Uic: 211,
        BuySell: "Buy",
        Amount: 10,
        OrderType: "Market",
        ManualOrder: False,
        OrderDuration: {"DurationType": "DayOrder"}
      }
   → Result: {EstimatedTotalCost: 5.00, EstimatedCashRequired: 1500.00, IsValid: true}
5. Evaluate precheck:
   → If DRY_RUN: Log "DRY_RUN: Would buy Stock:211 (AAPL), est. cost $5.00", DONE
   → If SIM: Proceed to placement
6. Place order:
   → POST /trade/v2/orders (same payload + ExternalReference)
   → Result: {OrderId: "12345", Status: "Placed"}
7. Log confirmation:
   → "Order placed: Stock:211 (AAPL) BUY 10 shares, OrderId=12345"
```

## Dependencies
- **Epic 001-2:** Saxo Bank Migration (Saxo client + authentication)
- **Epic 002:** Configuration Module (AccountKey, watchlist)
- **Epic 003:** Market Data Retrieval (normalized instrument data)
- **Epic 004:** Trading Strategy System (signals keyed by instrument_id)

## Success Criteria
- [ ] `execution/trade_executor.py` module created
- [ ] Precheck workflow implemented and tested
- [ ] DRY_RUN mode logs precheck results without placing orders
- [ ] SIM mode executes full precheck + placement workflow
- [ ] Position checking uses `/port/v1/netpositions`
- [ ] Correct `ManualOrder` flag usage (False for bot)
- [ ] Market orders use `DayOrder` duration
- [ ] Idempotency implemented via `ExternalReference` scanning
- [ ] Error handling parses `ModelState` for validation errors
- [ ] Module supports Stock, FxSpot, and FxCrypto asset types

## Related Documents
- [Saxo OpenAPI - Orders Precheck](https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/precheck)
- [Saxo OpenAPI - Orders Placement](https://www.developer.saxo/openapi/referencedocs/trade/v2/orders)
- [Saxo OpenAPI - NetPositions](https://www.developer.saxo/openapi/referencedocs/port/v1/netpositions)
