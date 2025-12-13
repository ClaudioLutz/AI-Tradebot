# Strategy Development Guide

Complete guide to writing, testing, and deploying trading strategies for the AI Trader system.

## Table of Contents
- [Quick Start](#quick-start)
- [Strategy Interface Contract](#strategy-interface-contract)
- [Common Mistakes](#common-mistakes)
- [Best Practices](#best-practices)
- [Saxo-Specific Considerations](#saxo-specific-considerations)
- [Testing Your Strategy](#testing-your-strategy)
- [Configuration](#configuration)
- [Resources](#resources)

## Quick Start: Add a New Strategy in 5 Steps

1. **Create strategy file** in `strategies/my_strategy.py`
2. **Implement BaseStrategy interface**
3. **Register in registry** (one line)
4. **Write tests** using fixtures
5. **Configure parameters** in `.env`

### Minimal Working Example

```python
from datetime import datetime
from typing import Dict

from strategies.base import BaseStrategy, Signal, get_current_timestamp
from strategies.indicators import simple_moving_average

class MyStrategy(BaseStrategy):
    def __init__(self, threshold: float = 0.02):
        self.threshold = threshold
    
    def generate_signals(
        self, 
        market_data: Dict[str, Dict],
        decision_time_utc: datetime,
    ) -> Dict[str, Signal]:
        signals = {}
        timestamp = get_current_timestamp()
        
        for instrument_id, data in market_data.items():
            bars = data.get("bars", [])
            
            if len(bars) < 2:
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="SIG_INSUFFICIENT_BARS",
                    timestamp=timestamp,
                    decision_time=timestamp,
                    strategy_version="my_strategy_v1.0"
                )
                continue
            
            # Your logic here
            price_change = (bars[-1]["close"] - bars[-2]["close"]) / bars[-2]["close"]
            
            if price_change > self.threshold:
                action = "BUY"
                reason = "SIG_PRICE_UP"
            elif price_change < -self.threshold:
                action = "SELL"
                reason = "SIG_PRICE_DOWN"
            else:
                action = "HOLD"
                reason = "SIG_NO_SIGNAL"
            
            signals[instrument_id] = Signal(
                action=action,
                reason=reason,
                timestamp=timestamp,
                decision_time=bars[-1]["timestamp"],
                strategy_version="my_strategy_v1.0",
                price_ref=bars[-1]["close"],
                price_type="close",
                metadata={"price_change": price_change}
            )
        
        return signals
```

### Register Your Strategy

```python
# In strategies/registry.py, add:
from strategies.my_strategy import MyStrategy
register_strategy("my_strategy")(MyStrategy)
```

## Strategy Interface Contract

All strategies MUST:

1. **Inherit from `BaseStrategy`**
2. **Implement `generate_signals(market_data, decision_time_utc) -> Dict[str, Signal]`**
3. **Return Signal objects** (not plain strings)
4. **Handle all instruments** in market_data
5. **Use only closed bars** (no look-ahead bias)
6. **Generate timestamps** for all signals
7. **Accept explicit decision_time_utc** parameter

### Input Format

```python
market_data = {
    "Stock:211": {
        "instrument_id": "Stock:211",
        "asset_type": "Stock",
        "uic": 211,
        "symbol": "AAPL",  # Human-readable label
        "quote": {...},    # From Saxo API
        "bars": [...]      # OHLC data
    },
    ...
}
```

### Output Format

```python
signals = {
    "Stock:211": Signal(
        action="BUY",
        reason="SIG_CROSSOVER_UP",
        timestamp="2025-01-15T10:30:00Z",
        decision_time="2025-01-15T10:30:00Z",
        strategy_version="moving_average_v1.0",
        price_ref=150.25,
        price_type="close",
        metadata={"short_ma": 151.0, "long_ma": 149.5}
    ),
    ...
}
```

## Common Mistakes and How to Avoid Them

### 1. Look-Ahead Bias ⚠️

**What it is:** Using future information not available at decision time.

**Common sources:**
- Using current bar's high/low before bar closes
- Using end-of-day adjusted prices for intraday decisions
- Peeking at next bar's data

**How we prevent it:**
- `safe_slice_bars(require_closed=True, as_of=decision_time_utc)` enforces closed-bar discipline
- Explicit `decision_time_utc` parameter passed to all strategies
- Bar data includes `is_closed` flag
- Signal validation ensures `decision_time ≤ timestamp`

**Reference:** Evidence-Based Technical Analysis (Aronson), Chapter 1
https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf

### 2. Backtest Overfitting ⚠️

**What it is:** Testing many parameter sets and selecting the best produces misleadingly good in-sample results that fail out-of-sample.

**How to avoid:**
- Log ALL parameter sets you test (we do this automatically)
- Keep holdout data for final validation
- Use walk-forward analysis
- Document strategy rationale BEFORE tuning parameters

**Why parameter logging matters:** Creates audit trail preventing "data snooping bias"

**Reference:** Bailey et al. - The Probability of Backtest Overfitting
https://carmamaths.org/jon/backtest2.pdf

### 3. Incorrect Crossover Detection ❌

**Mistake:** Checking if `short_ma > long_ma` at one instant

**Correct:** Compare previous vs current relationship to detect regime change

```python
# WRONG: Just comparing current values
if short_ma > long_ma:
    action = "BUY"

# RIGHT: Detecting crossover (regime change)
from strategies.indicators import detect_crossover

crossover = detect_crossover(
    current_short, current_long,
    prev_short, prev_long
)
if crossover == "CROSSOVER_UP":
    action = "BUY"
```

**Reference:** Brock, Lakonishok, LeBaron (1992) - MA crossovers as regime changes

### 4. Missing None Checks ❌

```python
# WRONG: Assumes MA calculation always succeeds
short_ma = simple_moving_average(closes, 5)
long_ma = simple_moving_average(closes, 20)
if short_ma > long_ma:  # Crashes if either is None!
    action = "BUY"

# RIGHT: Check for None
short_ma = simple_moving_average(closes, 5)
long_ma = simple_moving_average(closes, 20)

if short_ma is None or long_ma is None:
    return Signal("HOLD", "SIG_INSUFFICIENT_DATA", ...)

# Now safe to use
if short_ma > long_ma:
    action = "BUY"
```

## Best Practices

### 1. Use Indicator Utilities

```python
from strategies.indicators import (
    simple_moving_average,
    exponential_moving_average,
    safe_slice_bars,
    detect_crossover,
)

# These are pure, tested functions with proper edge case handling
```

### 2. Validate Parameters

```python
def __init__(self, short_window: int = 5, long_window: int = 20):
    if short_window <= 0 or long_window <= 0:
        raise ValueError("Window sizes must be positive")
    
    if short_window >= long_window:
        raise ValueError("short_window must be < long_window")
    
    self.short_window = short_window
    self.long_window = long_window
```

### 3. Log Strategy Decisions

```python
import logging
logger = logging.getLogger(__name__)

if crossover == "CROSSOVER_UP":
    logger.info(
        f"{instrument_id} ({symbol}): Golden cross detected - BUY "
        f"(short_MA={short_ma:.2f}, long_MA={long_ma:.2f})"
    )
```

### 4. Include Rich Metadata

```python
signals[instrument_id] = Signal(
    action="BUY",
    reason="SIG_CROSSOVER_UP",
    timestamp=wall_clock_timestamp,
    decision_time=last_bar_timestamp,
    strategy_version="my_strategy_v1.0",
    price_ref=last_close,
    price_type="close",
    data_time_range={
        "first_bar": bars[0]["timestamp"],
        "last_bar": bars[-1]["timestamp"]
    },
    metadata={
        "short_ma": short_ma,
        "long_ma": long_ma,
        "bars_used": len(bars)
    }
)
```

## Saxo-Specific Considerations

### SIM vs LIVE Pricing Behavior

Saxo's **SIM** environment may return **delayed quotes** for non-FX instruments.

**Policy:** This project includes `ALLOW_DELAYED_DATA_IN_SIM` (default `true`) to allow progress in SIM while being safe-by-default for LIVE.

- In **SIM**: Allow delayed quotes with loud warnings
- In **LIVE**: Reject all delayed quotes (enforce fresh data only)

**Reference:** https://openapi.help.saxo/hc/en-us/articles/4416934146449

### CryptoFX Trading Hours ⚠️

**IMPORTANT:** Saxo CryptoFX trades **WEEKDAYS ONLY** (not 24/7).

- Weekend data will have gaps
- Markets closed Saturday-Sunday
- Strategies should return HOLD on weekends

**Reference:** https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi

### Extended Hours Trading

US exchanges support pre-market and after-hours trading.

**Risks:**
- Lower liquidity (wider spreads)
- Higher volatility
- Fewer participants
- Stop/conditional orders behave differently

**Default:** Extended hours disabled (safe)  
**Enable:** Set `ALLOW_EXTENDED_HOURS=true` (use with caution)

**Reference:** https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning

### Market State Handling

Strategies receive `quote.MarketState` in market data:
- `"Open"` - Regular trading hours (default: trade)
- `"Closed"` - Market closed (default: HOLD)
- `"PreMarket"` / `"PostMarket"` - Extended hours (default: HOLD unless enabled)
- `"*Auction"` - Auction states (default: HOLD)

**Reference:** https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate

### Illiquid Instruments

Saxo may return fewer bars than requested for illiquid instruments.

**Solution:** Use `safe_slice_bars()` with `require_closed=True` - it handles this gracefully and returns `None` if insufficient data.

**Reference:** https://openapi.help.saxo/hc/en-us/articles/6105016299677

## Testing Your Strategy

### Use Provided Test Fixtures

```python
from datetime import datetime, timezone
from tests.fixtures.strategy_fixtures import create_crossover_scenario
from strategies.my_strategy import MyStrategy

def test_my_strategy():
    strategy = MyStrategy(threshold=0.02)
    market_data = create_crossover_scenario("golden")
    decision_time = datetime.now(timezone.utc)
    
    signals = strategy.generate_signals(market_data, decision_time)
    
    # Verify signals generated
    assert len(signals) > 0
    
    # Check signal structure
    for inst_id, signal in signals.items():
        assert signal.action in ["BUY", "SELL", "HOLD"]
        assert signal.reason.startswith(("SIG_", "DQ_"))
        assert signal.strategy_version is not None
```

### Test Determinism

```python
def test_determinism():
    """Ensure same inputs produce same outputs."""
    strategy = MyStrategy()
    market_data = create_crossover_scenario("golden")
    decision_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    signals1 = strategy.generate_signals(market_data, decision_time)
    signals2 = strategy.generate_signals(market_data, decision_time)
    
    # Actions and reasons should match
    for inst_id in signals1:
        assert signals1[inst_id].action == signals2[inst_id].action
        assert signals1[inst_id].reason == signals2[inst_id].reason
```

## Configuration

### Add to `.env`

```bash
# Strategy Selection
STRATEGY_NAME=my_strategy

# Option 1: JSON format
STRATEGY_PARAMS_JSON={"threshold": 0.02}

# Option 2: Individual parameters
STRATEGY_THRESHOLD=0.02
```

### Load in Code

```python
from strategies.registry import get_strategy

# Get strategy by name with parameters
strategy = get_strategy("my_strategy", {"threshold": 0.02})

# Generate signals
signals = strategy.generate_signals(market_data, decision_time_utc)
```

## Operational Checklist

Before trusting signals in production:

- [ ] Confirm decision_time_utc (UTC) is passed into every strategy call
- [ ] Confirm closed-bar filtering uses `timestamp < decision_time_utc`
- [ ] Confirm SIM delayed-data policy is set intentionally
- [ ] Confirm extended-hours trading is disabled by default
- [ ] Test with historical data (no look-ahead)
- [ ] Verify logs show strategy reasoning
- [ ] Check edge cases (insufficient bars, None values)
- [ ] Document parameter rationale

## Resources

### Code References
- Base interface: `strategies/base.py`
- Indicators: `strategies/indicators.py`
- Registry: `strategies/registry.py`
- Example: `strategies/moving_average.py`
- Test fixtures: `tests/fixtures/strategy_fixtures.py`

### Academic References
1. [Evidence-Based Technical Analysis (Aronson)](https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf) - Look-ahead bias
2. [Bailey et al. - Backtest Overfitting](https://carmamaths.org/jon/backtest2.pdf) - Parameter optimization risks
3. [Brock et al. - MA Crossovers](https://law-journals-books.vlex.com/vid/simple-technical-trading-rules-stochastic-855602882) - Academic validation of MA strategies

### Saxo References
- [CryptoFX Hours](https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi)
- [Extended Hours Risks](https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning)
- [Market State Enum](https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate)
- [Illiquid Instruments](https://openapi.help.saxo/hc/en-us/articles/6105016299677)
- [NoAccess Errors](https://openapi.help.saxo/hc/en-us/articles/4405160773661)
- [Pricing Documentation](https://www.developer.saxo/openapi/learn/pricing)

## Need Help?

- Review example strategy: `strategies/moving_average.py`
- Check test examples: `tests/test_strategy_*.py`
- See Epic 004 documentation: `docs/epics/epic-004-trading-strategy-system.md`
- Read story details: `docs/stories/story-004-trading-strategy/`

---

**Remember:** Strategies should be simple, well-tested, and well-documented. Focus on correctness over complexity.
