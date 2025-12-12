# Epic 005: Trade Execution Module

## Epic Overview
Develop the trader.py module responsible for executing paper trades through Alpaca's API. This module translates strategy signals into actual trade orders, with support for both dry-run simulation and live paper trading modes.

## Business Value
- Enables safe paper trading without real money risk
- Converts trading signals into actionable orders
- Provides dry-run mode for testing without API calls
- Implements basic position management
- Establishes foundation for risk management features

## Scope

### In Scope
- trader.py module creation
- Order submission functions (buy/sell market orders)
- Dry-run mode (logging only, no API calls)
- Paper trading mode (submit to Alpaca paper API)
- Position checking and management
- Basic quantity/sizing logic (fixed quantity initially)
- Order execution confirmation and logging
- Error handling for failed orders
- GTC (Good-Til-Cancelled) order support

### Out of Scope
- Advanced order types (limit, stop-loss, bracket orders)
- Dynamic position sizing algorithms
- Portfolio rebalancing logic
- Multi-leg strategies
- Real money trading (only paper trading)
- Complex risk management rules

## Technical Considerations
- Use Alpaca REST API submit_order() method
- Order parameters: symbol, qty, side ("buy"/"sell"), type ("market"), time_in_force ("gtc")
- Check existing positions before placing orders (avoid duplicate buys)
- Handle both stock (shares) and crypto (fractional units) quantities
- Implement mode toggle: DRY_RUN flag from config
- Log all order attempts and API responses
- Handle API errors gracefully (insufficient funds, invalid symbol, etc.)
- Verify paper trading endpoint is used (never live trading)

## Dependencies
- Epic 001: Initial Setup and Environment Configuration
- Epic 002: Configuration Module Development
- Epic 003: Market Data Retrieval Module
- Epic 004: Trading Strategy System

## Success Criteria
- [ ] trader.py module created
- [ ] execute_buy() and execute_sell() functions implemented
- [ ] Dry-run mode logs intended trades without API calls
- [ ] Paper trading mode submits orders to Alpaca
- [ ] Position checking prevents duplicate orders
- [ ] Fixed quantity sizing implemented
- [ ] Order confirmations are logged
- [ ] Error handling prevents crashes on failed orders
- [ ] Mode can be toggled via configuration

## Acceptance Criteria
1. In dry-run mode, trades are logged but not executed
2. In paper mode, orders are successfully submitted to Alpaca
3. Buy orders increase positions, sell orders close positions
4. Invalid orders (bad symbols, insufficient funds) are caught and logged
5. All order activity is logged with timestamps
6. Position state is checked before placing orders
7. Both stock and crypto orders work correctly
8. Paper trading endpoint is verified (no live trading risk)

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- trader.py (to be created)

## Example Function Signatures
```python
def execute_buy(symbol: str, quantity: int = 1) -> bool:
    """
    Execute a buy order for the given symbol.
    
    Args:
        symbol: Ticker symbol to buy
        quantity: Number of shares/units to buy
    
    Returns:
        True if order successful, False otherwise
    """
    pass

def execute_sell(symbol: str) -> bool:
    """
    Execute a sell order for all holdings of the given symbol.
    
    Args:
        symbol: Ticker symbol to sell
    
    Returns:
        True if order successful, False otherwise
    """
    pass

def execute_signal(symbol: str, signal: str) -> None:
    """
    Execute trade based on strategy signal.
    
    Args:
        symbol: Ticker symbol
        signal: "BUY", "SELL", or "HOLD"
    """
    pass
```

## Position Management
- Check existing position before buying (api.get_position(symbol))
- Sell all holdings on SELL signal
- Skip if position already exists on BUY signal (or implement averaging)
- Log current position state for transparency

## Order Flow
1. Receive signal from strategy (BUY/SELL/HOLD)
2. If HOLD, do nothing
3. If BUY, check if position exists
   - If no position, place buy order
   - If position exists, skip or log
4. If SELL, check if position exists
   - If position exists, sell all
   - If no position, skip or log
5. Log all actions and outcomes

## Notes
- Start with market orders for simplicity
- Use fixed quantity (1 share or small amount) initially
- Add dynamic sizing in future iterations
- Ensure paper trading safety checks
- Document all API calls clearly
- Consider adding order validation before submission
