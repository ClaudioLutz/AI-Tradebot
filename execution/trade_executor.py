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
