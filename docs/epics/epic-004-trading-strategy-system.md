# Epic 004: Trading Strategy System

## Epic Overview
Build a modular strategy system in the `strategies/` folder that encapsulates trading logic and signal generation. Strategies are pure functions over normalized market data, operating independently of broker-specific details.

## Business Value
- Separates trading logic from data fetching and execution
- Enables easy experimentation with different strategies
- Provides clear, broker-agnostic interface for strategy development
- Supports rapid iteration and testing of trading ideas
- Allows multiple strategies to coexist and be combined

## Scope

### In Scope
- `strategies/` folder with modular strategy files
- Example strategy (e.g., Moving Average Crossover) as template
- Common strategy interface/pattern definition
- Signal generation: `BUY`, `SELL`, `HOLD` per instrument
- Basic technical indicator calculations (moving averages)
- Strategy parameter configuration
- Clear documentation and examples
- Strategy testing framework basics

### Out of Scope
- Advanced technical indicators (RSI, MACD, Bollinger Bands)
- Multiple strategy implementations beyond example
- Strategy backtesting engine (historical simulation)
- Machine learning-based strategies
- Portfolio optimization algorithms
- Real-time strategy switching based on market regime

## Technical Considerations

### Strategy Interface
- **Pure functions:** Strategies accept normalized market data, return signals (no side effects)
- **Broker-agnostic:** Strategies do NOT know about Saxo endpoints, UICs, or AccountKeys
- **Input:** Normalized market data dict keyed by `instrument_id` (`"{asset_type}:{uic}"`)
- **Output:** Signals dict keyed by `instrument_id` with action: `"BUY"`, `"SELL"`, `"HOLD"`
- **Symbol labels:** Market data includes `symbol` field for readability, but strategies key on `instrument_id`

### Data Contract
Strategies consume the output from Epic 003 (market data module):
```python
market_data = {
    "Stock:211": {
        "instrument_id": "Stock:211",
        "asset_type": "Stock",
        "uic": 211,
        "symbol": "AAPL",  # human-readable label
        "quote": {...},
        "bars": [...]  # if OHLC data provided
    },
    ...
}
```

### Design Principles
- Keep strategies simple and well-documented for beginners
- Support multi-asset: equities, FX, CryptoFX
- Make strategy parameters configurable (e.g., MA periods)
- Design for easy addition of new strategy files
- Consider class-based approach for complex strategies with state

## Dependencies
- **Epic 001-2:** Saxo Bank Migration (broker connectivity)
- **Epic 002:** Configuration Module (watchlist, settings)
- **Epic 003:** Market Data Retrieval (normalized data feed)

## Success Criteria
- [ ] `strategies/` folder structure established
- [ ] Example strategy (e.g., `strategies/moving_average.py`) implemented
- [ ] Strategy generates valid signals keyed by `instrument_id`
- [ ] Works with normalized data format from market data module
- [ ] Strategy interface is documented and consistent
- [ ] Parameters are configurable via config or strategy constructor
- [ ] Strategy can be tested in isolation with mock data
- [ ] Code includes clear comments explaining logic

## Acceptance Criteria
1. Strategy accepts normalized market data dict keyed by `instrument_id`
2. Strategy returns signals dict: `{instrument_id: "BUY"|"SELL"|"HOLD"}`
3. Trading logic (e.g., Moving Average Crossover) is correctly implemented
4. Signals are generated for all instruments in market data
5. Strategy handles missing or incomplete data gracefully (logs warning, returns HOLD)
6. Documentation explains how to add new strategies
7. Example demonstrates both BUY and SELL signal generation
8. Strategy parameters can be adjusted without code changes (config or constructor args)

## Related Documents
- `strategies/simple_strategy.py` (example implementation)
- [Epic 003: Market Data Retrieval](./epic-003-market-data-retrieval.md) (data contract)

## Example Strategy Interface

```python
def generate_signals(market_data: Dict[str, Dict]) -> Dict[str, str]:
    """
    Analyze market data and generate trading signals.
    
    Args:
        market_data: Dict keyed by instrument_id, containing:
            {
                "instrument_id": str,
                "asset_type": str,
                "uic": int,
                "symbol": str,  # human-readable label
                "quote": {...},
                "bars": [...]  # optional OHLC data
            }
    
    Returns:
        Dict keyed by instrument_id with signal:
        {
            "Stock:211": "BUY",
            "FxSpot:21": "SELL",
            "FxSpot:1581": "HOLD"
        }
    
    Notes:
        - Use instrument_id as key (unique, deterministic)
        - symbol field is for logging/debugging only
        - Return HOLD for instruments with insufficient data
    """
    signals = {}
    
    for instrument_id, data in market_data.items():
        # Extract data
        symbol = data.get("symbol", "UNKNOWN")
        bars = data.get("bars", [])
        
        # Validate data availability
        if not bars or len(bars) < MIN_BARS_REQUIRED:
            logger.warning(f"Insufficient data for {instrument_id} ({symbol}), returning HOLD")
            signals[instrument_id] = "HOLD"
            continue
        
        # Strategy logic here
        signal = calculate_signal(bars, symbol)  # pass symbol for logging
        signals[instrument_id] = signal
    
    return signals
```

## Moving Average Crossover Strategy Example

### Strategy Logic
- Calculate short-term MA (e.g., 5 periods) and long-term MA (e.g., 20 periods) from OHLC bars
- **BUY signal:** Short MA crosses above long MA (golden cross)
- **SELL signal:** Short MA crosses below long MA (death cross)
- **HOLD:** No crossover detected or insufficient data

### Implementation Notes
```python
class MovingAverageStrategy:
    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window
    
    def generate_signals(self, market_data: Dict[str, Dict]) -> Dict[str, str]:
        signals = {}
        
        for instrument_id, data in market_data.items():
            symbol = data.get("symbol", "UNKNOWN")
            bars = data.get("bars", [])
            
            # Need at least long_window bars
            if len(bars) < self.long_window:
                logger.info(f"{instrument_id} ({symbol}): Insufficient bars, HOLD")
                signals[instrument_id] = "HOLD"
                continue
            
            # Calculate MAs
            closes = [bar["close"] for bar in bars[-self.long_window:]]
            short_ma = sum(closes[-self.short_window:]) / self.short_window
            long_ma = sum(closes) / self.long_window
            
            # Detect crossover (requires previous values for true crossover detection)
            # Simplified: compare current MA relationship
            if short_ma > long_ma * 1.01:  # 1% threshold to avoid noise
                logger.info(f"{instrument_id} ({symbol}): Golden cross detected - BUY")
                signals[instrument_id] = "BUY"
            elif short_ma < long_ma * 0.99:
                logger.info(f"{instrument_id} ({symbol}): Death cross detected - SELL")
                signals[instrument_id] = "SELL"
            else:
                signals[instrument_id] = "HOLD"
        
        return signals
```

## Multi-Asset Considerations

### Asset-Specific Logic
Strategies may need asset-type-specific handling:
```python
def generate_signals(market_data: Dict[str, Dict]) -> Dict[str, str]:
    signals = {}
    
    for instrument_id, data in market_data.items():
        asset_type = data["asset_type"]
        symbol = data["symbol"]
        
        # Asset-specific thresholds
        if asset_type in ["Stock"]:
            signal = apply_equity_strategy(data)
        elif asset_type in ["FxSpot"]:
            # FX may need different MA periods or volatility adjustments
            signal = apply_fx_strategy(data)
        else:
            logger.warning(f"Unknown asset type {asset_type} for {instrument_id}, HOLD")
            signal = "HOLD"
        
        signals[instrument_id] = signal
    
    return signals
```

### CryptoFX Notes
- CryptoFX (e.g., BTCUSD) may exhibit higher volatility
- Consider wider thresholds or different MA periods
- 24/7 trading means no weekend gaps in data

## Testing Strategies

### Unit Test Example
```python
def test_moving_average_strategy():
    # Mock market data
    mock_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "asset_type": "Stock",
            "uic": 211,
            "symbol": "AAPL",
            "bars": [
                {"close": 100}, {"close": 101}, {"close": 102},
                {"close": 103}, {"close": 104}, {"close": 105},
                {"close": 106}, {"close": 107}, {"close": 108},
                {"close": 109}, {"close": 110}, {"close": 111},
                {"close": 112}, {"close": 113}, {"close": 114},
                {"close": 115}, {"close": 116}, {"close": 117},
                {"close": 118}, {"close": 119}, {"close": 120}
            ]
        }
    }
    
    strategy = MovingAverageStrategy(short_window=5, long_window=20)
    signals = strategy.generate_signals(mock_data)
    
    assert "Stock:211" in signals
    assert signals["Stock:211"] in ["BUY", "SELL", "HOLD"]
```

## Notes
- Start with simple strategy to establish pattern
- Focus on code clarity over sophistication
- Strategies should log their reasoning (why BUY/SELL chosen)
- Add more strategies after validating framework
- Consider strategy composition (combine multiple strategies with voting)
- Document strategy parameters and expected behavior clearly
