# Epic 004: Trading Strategy System

## Epic Overview
Build a modular strategy system in the strategies/ folder that encapsulates trading logic and signal generation. This epic establishes the framework for implementing various trading strategies and provides an example strategy to demonstrate the pattern.

## Business Value
- Separates trading logic from data fetching and execution
- Enables easy experimentation with different strategies
- Provides clear interface for strategy development
- Supports rapid iteration and testing of trading ideas
- Allows multiple strategies to coexist

## Scope

### In Scope
- strategies/ folder creation
- example_strategy.py with Moving Average Crossover logic
- Common strategy interface/pattern definition
- Signal generation function (BUY/SELL/HOLD)
- Basic technical indicator calculations (moving averages)
- Strategy parameter configuration
- Clear documentation and examples
- Strategy testing framework basics

### Out of Scope
- Advanced technical indicators (RSI, MACD, Bollinger Bands)
- Multiple strategy implementations beyond the example
- Strategy backtesting engine
- Machine learning-based strategies
- Portfolio optimization algorithms
- Real-time strategy switching

## Technical Considerations
- Each strategy module should follow common interface: generate_signals(data) -> dict
- Return format: {"SYMBOL": "BUY"|"SELL"|"HOLD"}
- Keep strategies simple and well-documented for beginners
- Support both stock and crypto symbols
- Make strategy parameters configurable (e.g., MA periods)
- Design for easy addition of new strategy files
- Consider class-based approach for more complex strategies

## Dependencies
- Epic 001: Initial Setup and Environment Configuration
- Epic 002: Configuration Module Development
- Epic 003: Market Data Retrieval Module

## Success Criteria
- [ ] strategies/ folder created
- [ ] example_strategy.py implements Moving Average Crossover
- [ ] Strategy generates valid signals (BUY/SELL/HOLD)
- [ ] Works with data format from data_fetcher module
- [ ] Strategy interface is documented
- [ ] Parameters are configurable
- [ ] Strategy can be easily tested in isolation
- [ ] Code includes clear comments explaining logic

## Acceptance Criteria
1. Strategy accepts market data and returns actionable signals
2. Moving Average Crossover logic is correctly implemented
3. Signals are generated for all symbols in watchlist
4. Strategy handles missing or incomplete data gracefully
5. Documentation explains how to add new strategies
6. Example demonstrates both BUY and SELL signal generation
7. Strategy parameters can be adjusted without code changes

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- strategies/example_strategy.py (to be created)

## Example Strategy Interface
```python
def generate_signals(market_data: dict) -> dict:
    """
    Analyze market data and generate trading signals.
    
    Args:
        market_data: Dict with symbol -> price data
    
    Returns:
        Dict with symbol -> signal ("BUY", "SELL", "HOLD")
    
    Example:
        {"AAPL": "BUY", "MSFT": "SELL", "BTC/USD": "HOLD"}
    """
    signals = {}
    
    for symbol, data in market_data.items():
        # Strategy logic here
        signals[symbol] = calculate_signal(data)
    
    return signals
```

## Moving Average Crossover Strategy
- Calculate short-term MA (e.g., 5 periods) and long-term MA (e.g., 20 periods)
- Signal BUY when short MA crosses above long MA (golden cross)
- Signal SELL when short MA crosses below long MA (death cross)
- Signal HOLD otherwise

## Notes
- Start with simple strategy to establish pattern
- Focus on code clarity over sophistication
- Add more strategies after validating framework
- Consider strategy base class for future expansion
- Document strategy parameters and expected behavior
