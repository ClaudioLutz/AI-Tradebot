# Epic 005: Trade Execution Module (Saxo)

## Epic Overview
Develop the execution module (`execution/trade_executor.py`) responsible for order placement via Saxo OpenAPI with a **precheck-first workflow**. This module translates strategy signals into validated orders using `{AccountKey, AssetType, Uic}` triplets, with support for DRY_RUN mode.

## Business Value
- Enables safe SIM trading with precheck validation before every order
- Converts trading signals into actionable Saxo orders
- Provides DRY_RUN mode for testing without actual placement
- Implements position management with Saxo's position model
- Establishes foundation for risk management and cost estimation

## Scope

### In Scope
- `execution/trade_executor.py` module creation
- **Precheck-first workflow**: Validate order and estimate costs BEFORE placement
- Order submission functions (buy/sell market orders via `/trade/v2/orders`)
- **DRY_RUN mode**: Precheck only, log results without placing order
- **SIM mode**: Full precheck + order placement in SIM environment
- Position checking via Saxo `/port/v1/positions`
- Basic quantity/sizing logic (fixed quantity or notional amount initially)
- Order execution confirmation and logging with Saxo OrderIds
- Comprehensive error handling with HTTP status categorization
- Support for multiple asset types (Stock, FxSpot)

### Out of Scope
- Advanced order types (limit, stop-loss, trailing stop)
- Dynamic position sizing algorithms (e.g., Kelly criterion)
- Portfolio rebalancing logic
- Multi-leg strategies (spreads, combos)
- Live trading (SIM environment only for this epic)
- Complex risk management rules (max drawdown, exposure limits)

## Technical Considerations

### Precheck-First Workflow
Saxo's `/trade/v2/orders/precheck` endpoint validates orders and estimates costs before placement:

1. **Construct order request** (AccountKey, AssetType, Uic, OrderType, BuySell, Amount)
2. **Call precheck endpoint** → Returns estimated costs, margin requirements, validation errors
3. **Evaluate precheck result**:
   - ✅ If successful: Proceed to placement (or log if DRY_RUN)
   - ❌ If failed: Log error with diagnostic info, do NOT place order
4. **Place order** (if not DRY_RUN): POST to `/trade/v2/orders` with same request
5. **Confirm and log**: Capture OrderId, status, and timestamps

### Order Request Structure
```python
order_request = {
    "AccountKey": account_key,  # from config
    "AssetType": asset_type,     # e.g., "Stock", "FxSpot"
    "Uic": uic,                  # instrument identifier
    "OrderType": "Market",
    "BuySell": "Buy",  # or "Sell"
    "Amount": 10  # quantity (shares) or notional (FX lots)
}
```

### Position Model
- Saxo positions are keyed by `{AccountKey, AssetType, Uic}`
- Use `/port/v1/positions` to query existing positions
- Position tracking ensures:
  - Don't double-buy if position already exists (unless averaging-in strategy)
  - Don't sell if no position to close

### Error Handling
Categorize errors by HTTP status and response body:
- **400 Bad Request**: Likely code bug (malformed request)
- **401/403 Unauthorized/Forbidden**: Auth failure (token expired, insufficient permissions)
- **429 Too Many Requests**: Rate limit (implement backoff)
- **500/502/503 Server Error**: Saxo API issue (retry with exponential backoff)
- **Precheck failures**: Business logic errors (insufficient funds, invalid order params)

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
- [ ] Position checking integrated (query before buy/sell)
- [ ] Fixed quantity sizing implemented (configurable)
- [ ] Order confirmations logged with OrderId and status
- [ ] Error handling categorizes failures with full context
- [ ] Module supports Stock and FxSpot asset types

## Acceptance Criteria
1. **Precheck-first:** All orders prechecked before placement (no exceptions)
2. **DRY_RUN mode:** Orders are prechecked and logged, but NOT placed
3. **SIM mode:** Orders are prechecked, then placed in SIM environment
4. **Buy signals:** Precheck successful → place market buy order with configured quantity
5. **Sell signals:** Check position exists → precheck sell order → place if valid
6. **Invalid orders:** Precheck failures logged with error details, no placement attempt
7. **Logging:** All execution activity logged with `{instrument_id, asset_type, uic, symbol, account_key, order_id, http_status}`
8. **Position management:** Duplicate buys prevented (or logged with warning)
9. **Multi-asset support:** Works with both Stock and FxSpot instruments
10. **Error recovery:** HTTP errors handled gracefully without crashing orchestration loop

## Related Documents
- [Saxo OpenAPI - Orders Precheck](https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/precheck)
- [Saxo OpenAPI - Orders Placement](https://www.developer.saxo/openapi/referencedocs/trade/v2/orders)
- [Saxo OpenAPI - Positions](https://www.developer.saxo/openapi/referencedocs/port/v1/positions)
- `execution/trade_executor.py` (to be enhanced)
- `data/saxo_client.py` (Saxo REST client)

## Example Function Signatures

```python
def precheck_order(
    account_key: str,
    asset_type: str,
    uic: int,
    buy_sell: str,
    amount: int,
    symbol: str = None  # for logging only
) -> Dict:
    """
    Precheck an order with Saxo OpenAPI.
    
    Args:
        account_key: Saxo AccountKey
        asset_type: "Stock", "FxSpot", etc.
        uic: Instrument UIC
        buy_sell: "Buy" or "Sell"
        amount: Quantity (shares for Stock, lots/units for FX)
        symbol: Human-readable label for logging
    
    Returns:
        Dict with precheck result:
        {
            "success": True/False,
            "estimated_cost": 1500.25,  # if success
            "error_code": "...",  # if failure
            "error_message": "...",
            "raw_response": {...}
        }
    
    Raises:
        APIError: If HTTP request fails
    """
    pass


def place_order(
    account_key: str,
    asset_type: str,
    uic: int,
    buy_sell: str,
    amount: int,
    symbol: str = None
) -> Dict:
    """
    Place a market order (after successful precheck).
    
    Args:
        Same as precheck_order
    
    Returns:
        Dict with order result:
        {
            "success": True/False,
            "order_id": "123456",  # Saxo OrderId
            "status": "Placed",
            "error_message": None  # if failure
        }
    
    Raises:
        APIError: If HTTP request fails
    """
    pass


def execute_signal(
    instrument: Dict,
    signal: str,
    account_key: str,
    amount: int = 1,
    dry_run: bool = False
) -> bool:
    """
    Execute trade based on strategy signal with precheck-first workflow.
    
    Args:
        instrument: Dict with {asset_type, uic, symbol, instrument_id}
        signal: "BUY", "SELL", or "HOLD"
        account_key: Saxo AccountKey for order placement
        amount: Quantity to trade
        dry_run: If True, precheck only (no placement)
    
    Returns:
        True if execution successful (or precheck passed in dry_run), False otherwise
    
    Workflow:
        1. If HOLD → return immediately
        2. If BUY → check position → precheck → place (if not dry_run)
        3. If SELL → check position exists → precheck → place (if not dry_run)
    """
    pass


def get_positions(account_key: str) -> Dict[str, Dict]:
    """
    Fetch current positions from Saxo.
    
    Args:
        account_key: Saxo AccountKey
    
    Returns:
        Dict keyed by instrument_id:
        {
            "Stock:211": {
                "instrument_id": "Stock:211",
                "asset_type": "Stock",
                "uic": 211,
                "symbol": "AAPL",
                "amount": 10,  # current position size
                "market_value": 1500.50
            },
            ...
        }
    """
    pass
```

## Execution Workflow

### Full Cycle for BUY Signal
```
1. Receive signal: {"Stock:211": "BUY"}
2. Extract instrument data: asset_type=Stock, uic=211, symbol=AAPL
3. Check existing positions
   → If position exists: Log "Already holding Stock:211 (AAPL)", skip or average-in
   → If no position: Proceed
4. Precheck order:
   → POST /trade/v2/orders/precheck
   → Payload: {AccountKey, AssetType:Stock, Uic:211, BuySell:Buy, Amount:10, OrderType:Market}
   → Result: {EstimatedCost: 1500.25, IsValid: true}
5. Evaluate precheck:
   → If DRY_RUN: Log "DRY_RUN: Would buy Stock:211 (AAPL), est. cost $1500.25", DONE
   → If SIM: Proceed to placement
6. Place order:
   → POST /trade/v2/orders (same payload as precheck)
   → Result: {OrderId: "12345", Status: "Placed"}
7. Log confirmation:
   → "Order placed: Stock:211 (AAPL) BUY 10 shares, OrderId=12345, Status=Placed"
```

### Full Cycle for SELL Signal
```
1. Receive signal: {"FxSpot:21": "SELL"}
2. Extract instrument data: asset_type=FxSpot, uic=21, symbol=EURUSD
3. Check existing positions
   → If no position: Log "No position for FxSpot:21 (EURUSD), skipping SELL", DONE
   → If position exists (e.g., 1000 units): Proceed
4. Precheck sell order:
   → POST /trade/v2/orders/precheck
   → Payload: {AccountKey, AssetType:FxSpot, Uic:21, BuySell:Sell, Amount:1000, OrderType:Market}
   → Result: {EstimatedProceeds: 1050.00, IsValid: true}
5. Evaluate precheck:
   → If DRY_RUN: Log "DRY_RUN: Would sell FxSpot:21 (EURUSD), est. proceeds $1050", DONE
   → If SIM: Proceed to placement
6. Place order:
   → POST /trade/v2/orders
   → Result: {OrderId: "12346", Status: "Placed"}
7. Log confirmation:
   → "Order placed: FxSpot:21 (EURUSD) SELL 1000 units, OrderId=12346, Status=Placed"
```

## Position Management

### Position Query
```python
def check_position_exists(account_key: str, asset_type: str, uic: int) -> bool:
    """Check if a position exists for the given instrument."""
    positions = get_positions(account_key)
    instrument_id = f"{asset_type}:{uic}"
    return instrument_id in positions
```

### Position-Aware Logic
- **Before BUY:** Check if position already exists
  - If exists: Skip (or implement averaging-in with partial quantity)
  - If not: Proceed with buy
- **Before SELL:** Check if position exists
  - If exists: Proceed with sell (use position amount or signal-specified amount)
  - If not: Skip and log warning

## Error Categorization

### Precheck Failures
- **Insufficient funds:** `"InsufficientFunds"` error code
- **Invalid instrument:** `"InvalidUic"` or `"UnsupportedAssetType"`
- **Invalid amount:** `"InvalidOrderQuantity"` (e.g., fractional shares for non-fractional stocks)
- **Market closed:** `"MarketClosed"` (if applicable)

### Placement Failures
- **Order rejected:** Saxo rejected despite precheck passing (rare, log as anomaly)
- **HTTP errors:** Network/server issues (implement retry with backoff)

### Logging Template
```python
logger.error(
    f"Order execution failed: {instrument_id} ({symbol}) {buy_sell} {amount}, "
    f"AccountKey={account_key_masked}, HTTP={http_status}, "
    f"Error={error_code}: {error_message}"
)
```

## DRY_RUN vs SIM Mode

### DRY_RUN Mode (`dry_run=True`)
- Precheck ALL orders
- Log precheck results with estimated costs
- **DO NOT** call placement endpoint
- Use for: Testing strategy logic, verifying order construction, cost estimation

### SIM Mode (`dry_run=False`)
- Precheck ALL orders
- If precheck passes: Place order in SIM environment
- Log full workflow: precheck → placement → confirmation
- Use for: End-to-end testing, validating execution flow with Saxo

## Risk Management Integration (Future)

This epic establishes the foundation for future risk management features:
- **Max position size:** Reject orders exceeding configured limits
- **Daily loss limit:** Track P&L and halt trading if threshold breached
- **Exposure limits:** Aggregate exposure across instruments, reject if exceeding limit
- **Order frequency throttling:** Prevent excessive trading (protect against runaway strategies)

## Notes
- **Always precheck first** - This is non-negotiable for Saxo execution
- Start with market orders for simplicity (most liquid, immediate execution)
- Use fixed quantity initially; add dynamic sizing in future iterations
- Ensure SIM environment safety checks (verify base URL, account type)
- Document all API calls with request/response samples
- Consider adding order validation before precheck (sanity checks on quantity, asset type)
- Position synchronization: Query positions at start of each cycle to maintain accurate state

## Testing Strategy

### Unit Tests
- Mock precheck responses (success and various failure scenarios)
- Mock placement responses
- Test position checking logic
- Test DRY_RUN vs SIM mode branching

### Integration Tests (SIM)
- **Precheck-only test:** Precheck valid orders, verify response structure
- **Full execution test:** Place real order in SIM, verify OrderId returned
- **Error handling test:** Precheck invalid order, verify graceful failure
- **Position query test:** Fetch positions, verify data structure

### Safety Checklist
- [ ] All tests use SIM environment (never Live)
- [ ] DRY_RUN mode confirmed working (no actual placement)
- [ ] HTTP errors handled without crashes
- [ ] Precheck failures logged with diagnostics
- [ ] AccountKey validated before execution
