# Story 001-2-008: Update Trade Execution Module

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to update the trade execution module to use Saxo's order API instead of Alpaca so that the application can place trades through Saxo Bank.

## Description
Modify `execution/trade_executor.py` to use Saxo's `/trade/v2/orders` endpoint with precheck functionality. The module must handle AccountKey requirements, UIC-based orders, and Saxo's order structure.

## Prerequisites
- Story 001-2-005 completed (Saxo client available)
- Story 001-2-006 completed (connection test confirms account access)
- Story 001-2-007 completed (market data provides UICs)

## Acceptance Criteria
- [ ] Alpaca-specific code removed from `trade_executor.py`
- [ ] Order precheck function implemented
- [ ] Order placement function implemented
- [ ] AccountKey handling included
- [ ] UIC + AssetType parameters required
- [ ] Error handling for order failures
- [ ] Code documented with examples
- [ ] Module can be imported without errors

## Technical Details

### Current Implementation (Alpaca)
- Uses Alpaca SDK order methods
- Symbol-based orders
- Direct order submission

### New Implementation (Saxo)
Key changes:
1. **Precheck:** Use `/trade/v2/orders/precheck` before placing orders
2. **AccountKey:** Required for all orders (from `/port/v1/accounts/me`)
3. **UIC + AssetType:** Replace symbol strings
4. **Order Structure:** Saxo's JSON format
5. **Manual Order Flag:** Set appropriately for testing

### Saxo Order Endpoints
- **Precheck:** `POST /trade/v2/orders/precheck` - Simulate order
- **Place Order:** `POST /trade/v2/orders` - Execute order
- **Response:** Order ID and confirmation details

## Implementation

### Complete Updated trade_executor.py

```python
"""
Trade Execution Module - Saxo Bank Integration
Handles order placement and execution.
"""
from data.saxo_client import SaxoClient, SaxoAPIError, SaxoAuthenticationError
from typing import Dict, Any, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderExecutionError(Exception):
    """Raised when order execution fails."""
    pass


class AccountError(Exception):
    """Raised when account operations fail."""
    pass


def get_account_key() -> str:
    """
    Retrieve the AccountKey from Saxo API.
    
    Returns:
        AccountKey string
    
    Raises:
        AccountError: If unable to retrieve account key
    
    Example:
        >>> account_key = get_account_key()
        >>> print(f"Using account: {account_key}")
    """
    client = SaxoClient()
    
    try:
        response = client.get("/port/v1/accounts/me")
        
        # Extract accounts
        accounts = []
        if isinstance(response, dict):
            accounts = response.get("Data", [])
        elif isinstance(response, list):
            accounts = response
        
        if not accounts:
            raise AccountError("No accounts found")
        
        # Return first account's key
        account_key = accounts[0].get("AccountKey")
        if not account_key:
            raise AccountError("AccountKey not found in response")
        
        logger.info(f"Retrieved AccountKey: {account_key}")
        return account_key
    
    except SaxoAPIError as e:
        raise AccountError(f"Failed to retrieve account: {e}")


def precheck_order(
    uic: int,
    asset_type: str,
    buy_sell: str,
    amount: float,
    order_type: str = "Market"
) -> Dict[str, Any]:
    """
    Precheck an order without placing it (dry run).
    
    Args:
        uic: Universal Instrument Code
        asset_type: Asset type (Stock, FxSpot, etc.)
        buy_sell: "Buy" or "Sell"
        amount: Order amount/quantity
        order_type: Order type (Market, Limit, etc.)
    
    Returns:
        Precheck response with costs and validation
    
    Raises:
        OrderExecutionError: If precheck fails
    
    Example:
        >>> result = precheck_order(211, "Stock", "Buy", 10, "Market")
        >>> print(f"Estimated cost: {result.get('EstimatedCost')}")
    """
    client = SaxoClient()
    
    try:
        # Get account key
        account_key = get_account_key()
        
        # Build order request
        order_body = {
            "AccountKey": account_key,
            "Uic": uic,
            "AssetType": asset_type,
            "BuySell": buy_sell,
            "Amount": amount,
            "OrderType": order_type,
            "ManualOrder": True,  # Set true for manual/testing
            "FieldGroups": ["Costs"]  # Request cost information
        }
        
        logger.info(f"Prechecking order: {buy_sell} {amount} {asset_type} UIC:{uic}")
        
        response = client.post("/trade/v2/orders/precheck", json_body=order_body)
        
        logger.info("Order precheck successful")
        return response
    
    except SaxoAPIError as e:
        raise OrderExecutionError(f"Order precheck failed: {e}")
    except AccountError as e:
        raise OrderExecutionError(f"Account error during precheck: {e}")


def place_order(
    uic: int,
    asset_type: str,
    buy_sell: str,
    amount: float,
    order_type: str = "Market",
    precheck_first: bool = True
) -> Dict[str, Any]:
    """
    Place an order on Saxo Bank.
    
    Args:
        uic: Universal Instrument Code
        asset_type: Asset type (Stock, FxSpot, etc.)
        buy_sell: "Buy" or "Sell"
        amount: Order amount/quantity
        order_type: Order type (Market, Limit, etc.)
        precheck_first: If True, run precheck before placing order
    
    Returns:
        Order response with OrderId
    
    Raises:
        OrderExecutionError: If order placement fails
    
    Example:
        >>> # Place market buy order for 10 shares of AAPL
        >>> result = place_order(211, "Stock", "Buy", 10)
        >>> print(f"Order ID: {result.get('OrderId')}")
    
    Warning:
        This places a REAL order in SIM environment.
        Always precheck orders before placing.
    """
    client = SaxoClient()
    
    try:
        # Optional precheck
        if precheck_first:
            logger.info("Running precheck before placing order...")
            precheck_result = precheck_order(uic, asset_type, buy_sell, amount, order_type)
            logger.info(f"Precheck passed: {precheck_result}")
        
        # Get account key
        account_key = get_account_key()
        
        # Build order request
        order_body = {
            "AccountKey": account_key,
            "Uic": uic,
            "AssetType": asset_type,
            "BuySell": buy_sell,
            "Amount": amount,
            "OrderType": order_type,
            "ManualOrder": False  # False for actual order placement
        }
        
        logger.info(f"Placing order: {buy_sell} {amount} {asset_type} UIC:{uic}")
        logger.warning("⚠ PLACING REAL ORDER (SIM environment)")
        
        response = client.post("/trade/v2/orders", json_body=order_body)
        
        order_id = response.get("OrderId")
        logger.info(f"✓ Order placed successfully: OrderId {order_id}")
        
        return response
    
    except SaxoAPIError as e:
        raise OrderExecutionError(f"Order placement failed: {e}")
    except AccountError as e:
        raise OrderExecutionError(f"Account error during order placement: {e}")


def cancel_order(order_id: str) -> Dict[str, Any]:
    """
    Cancel an existing order.
    
    Args:
        order_id: The OrderId to cancel
    
    Returns:
        Cancellation response
    
    Raises:
        OrderExecutionError: If cancellation fails
    
    Example:
        >>> result = cancel_order("12345")
        >>> print("Order cancelled")
    """
    client = SaxoClient()
    
    try:
        # Get account key
        account_key = get_account_key()
        
        logger.info(f"Cancelling order: {order_id}")
        
        response = client.delete(
            f"/trade/v2/orders/{order_id}",
            params={"AccountKey": account_key}
        )
        
        logger.info(f"✓ Order cancelled: {order_id}")
        return response
    
    except SaxoAPIError as e:
        raise OrderExecutionError(f"Order cancellation failed: {e}")
    except AccountError as e:
        raise OrderExecutionError(f"Account error during cancellation: {e}")


def get_open_orders() -> list:
    """
    Get list of open orders.
    
    Returns:
        List of open orders
    
    Raises:
        OrderExecutionError: If retrieval fails
    
    Example:
        >>> orders = get_open_orders()
        >>> print(f"Open orders: {len(orders)}")
    """
    client = SaxoClient()
    
    try:
        # Get account key
        account_key = get_account_key()
        
        response = client.get(
            "/port/v1/orders/me",
            params={"AccountKey": account_key}
        )
        
        # Extract orders
        orders = []
        if isinstance(response, dict):
            orders = response.get("Data", [])
        elif isinstance(response, list):
            orders = response
        
        logger.info(f"Retrieved {len(orders)} open order(s)")
        return orders
    
    except SaxoAPIError as e:
        raise OrderExecutionError(f"Failed to get orders: {e}")
    except AccountError as e:
        raise OrderExecutionError(f"Account error getting orders: {e}")


# Module-level information
__version__ = "2.0.0"
__api__ = "Saxo OpenAPI"

logger.info(f"Trade Execution Module v{__version__} ({__api__}) loaded")
```

## Files to Modify
- `execution/trade_executor.py` - Complete rewrite for Saxo

## Verification Steps
- [ ] File updated successfully
- [ ] No syntax errors
- [ ] Can import module
- [ ] Alpaca code removed
- [ ] Functions properly documented
- [ ] Type hints included
- [ ] Logging configured

## Testing

### Test 1: Module Import
```python
from execution import trade_executor
print("Module imported successfully")
```

Expected: No errors

### Test 2: Get Account Key
```python
from execution.trade_executor import get_account_key

try:
    account_key = get_account_key()
    print(f"AccountKey: {account_key}")
except Exception as e:
    print(f"Error: {e}")
```

Expected: Returns AccountKey string

### Test 3: Precheck Order (Safe - No Trade)
```python
from execution.trade_executor import precheck_order

# Precheck buying 1 share of AAPL (UIC 211)
try:
    result = precheck_order(211, "Stock", "Buy", 1, "Market")
    print("Precheck result:")
    print(f"  Status: Success")
    if "Costs" in result:
        print(f"  Costs: {result['Costs']}")
except Exception as e:
    print(f"Precheck failed: {e}")
```

Expected: Returns precheck response with costs

### Test 4: Get Open Orders
```python
from execution.trade_executor import get_open_orders

try:
    orders = get_open_orders()
    print(f"Open orders: {len(orders)}")
except Exception as e:
    print(f"Error: {e}")
```

Expected: Returns list (may be empty)

### ⚠️ Test 5: Place Order (PLACES REAL SIM ORDER)
**Only run when ready to test actual order placement**
```python
from execution.trade_executor import place_order

# WARNING: This places a real order in SIM
# Uncomment only when ready to test
# try:
#     result = place_order(211, "Stock", "Buy", 1, "Market")
#     print(f"Order placed: {result.get('OrderId')}")
# except Exception as e:
#     print(f"Order failed: {e}")
```

## Documentation

### Important Warnings
- Document that place_order creates REAL orders (even in SIM)
- Emphasize precheck_first=True default
- Explain AccountKey requirement
- Note ManualOrder flag usage

### Order Types
Document supported order types:
- **Market:** Immediate execution at market price
- **Limit:** Execution at specified price or better
- **Stop:** Stop-loss orders
- Others per Saxo documentation

## Time Estimate
**1 hour** (implement + test + document)

## Dependencies
- Story 001-2-005 completed (Saxo client)
- Story 001-2-006 completed (account access confirmed)
- Story 001-2-007 completed (UIC discovery available)

## Blocks
- Story 001-2-010 (integration testing)

## Safety Features

### Precheck Requirement
- Default `precheck_first=True` for safety
- Can be disabled for advanced users
- Logs warning when placing real orders

### SIM Environment Only
- All orders placed in SIM environment
- No real money at risk
- Safe for testing and development

### Logging
- All order actions logged
- Warning for actual order placement
- Success/failure clearly indicated

## Common Order Parameters

### Buy/Sell Values
- `"Buy"` - Long position
- `"Sell"` - Short position / close long

### Order Types
- `"Market"` - Market order
- `"Limit"` - Limit order (needs OrderPrice)
- `"Stop"` - Stop order (needs StopPrice)

### Amount
- For stocks: Number of shares
- For FX: Units in base currency
- Always positive number

## Error Handling

### Common Errors
1. **Insufficient Funds:** Not enough buying power
2. **Invalid Instrument:** Wrong UIC or AssetType
3. **Market Closed:** Trading outside hours
4. **Invalid Amount:** Amount too small/large

### Error Messages
Provide helpful context:
- Include order details in error
- Reference precheck for validation
- Log full error details

## API Endpoints Used

| Function | Endpoint | Method | Purpose |
|----------|----------|--------|---------|
| get_account_key | /port/v1/accounts/me | GET | Get account info |
| precheck_order | /trade/v2/orders/precheck | POST | Validate order |
| place_order | /trade/v2/orders | POST | Place order |
| cancel_order | /trade/v2/orders/{id} | DELETE | Cancel order |
| get_open_orders | /port/v1/orders/me | GET | List orders |

## Future Enhancements (Not in this story)
- Limit order support with price parameter
- Stop-loss order support
- Order status tracking
- Position management
- Order history retrieval
- Batch order operations

## Migration Notes

### Key Differences from Alpaca
| Aspect | Alpaca | Saxo |
|--------|--------|------|
| Identification | Symbol | UIC + AssetType |
| Account | Implicit | Explicit AccountKey |
| Precheck | Not available | Available & recommended |
| Order structure | SDK methods | JSON payload |

## References
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 8)
- [Saxo Trade API](https://www.developer.saxo/openapi/referencedocs/trade/)
- [Saxo Orders Endpoint](https://www.developer.saxo/openapi/referencedocs/trade/v2/orders)
- [Order Precheck Documentation](https://openapi.help.saxo/hc/en-us/articles/4418459141265)

## Success Criteria
✅ Story is complete when:
1. `trade_executor.py` updated for Saxo
2. All Alpaca code removed
3. Precheck function working
4. Account key retrieval working
5. Order placement functional (tested with precheck)
6. Open orders retrieval working
7. All verification tests pass
8. Code well-documented with warnings
9. Module imports without errors
