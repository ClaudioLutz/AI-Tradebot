# Story 004-008: Developer Documentation - How to Write Strategies

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Create comprehensive developer documentation explaining how to write, test, and deploy strategies with research-backed best practices and warnings about common pitfalls.

## User Story
As a **new strategy developer**, I want **clear documentation with examples** so that **I can write correct, testable strategies without making common mistakes**.

## Goal
Create documentation covering:
1. Strategy interface contract
2. How to add a new strategy (step-by-step)
3. Common mistakes and how to avoid them
4. Research-backed best practices
5. Testing guidelines
6. Saxo-specific considerations

## Acceptance Criteria

### 1. Strategy Development Guide Created
- [ ] `docs/STRATEGY_DEVELOPMENT_GUIDE.md` with sections:
  - Quick start (add a new strategy in 5 steps)
  - Interface contract explanation
  - Parameter handling
  - Testing your strategy
  - Common mistakes
  - Best practices
  - Saxo-specific notes

### 2. Look-Ahead Bias Section
- [ ] Explains what look-ahead bias is
- [ ] Common sources (same-bar high/low, future data)
- [ ] How our design prevents it (closed bars, timestamps)
- [ ] Reference to academic source

### 3. Backtest Overfitting Warning
- [ ] Explains parameter overfitting risk
- [ ] Why parameter logging matters
- [ ] Recommendation for out-of-sample validation
- [ ] Reference to Bailey et al.

### 4. Saxo-Specific Sections
- [ ] CryptoFX weekday-only trading documented with reference
- [ ] Extended hours risks documented with reference
- [ ] Market state handling explained
- [ ] Data quality expectations

### 5. Code Examples
- [ ] Minimal working strategy example
- [ ] Crossover detection example
- [ ] Parameter validation example
- [ ] Test example

## Technical Implementation

### Developer Guide (`docs/STRATEGY_DEVELOPMENT_GUIDE.md`)
```markdown
# Strategy Development Guide

Complete guide to writing, testing, and deploying trading strategies.

## Quick Start: Add a New Strategy in 5 Steps

1. **Create strategy file** in `strategies/my_strategy.py`
2. **Implement BaseStrategy interface**
3. **Register in registry**
4. **Write tests** using fixtures
5. **Configure parameters** in `.env`

### Minimal Working Example

\`\`\`python
from strategies.base import BaseStrategy, Signal, get_current_timestamp
from strategies.indicators import simple_moving_average

class MyStrategy(BaseStrategy):
    def __init__(self, threshold: float = 0.02):
        self.threshold = threshold
    
    def generate_signals(self, market_data):
        signals = {}
        timestamp = get_current_timestamp()
        
        for instrument_id, data in market_data.items():
            bars = data.get("bars", [])
            
            if len(bars) < 2:
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="INSUFFICIENT_BARS",
                    timestamp=timestamp
                )
                continue
            
            # Your logic here
            price_change = (bars[-1]["close"] - bars[-2]["close"]) / bars[-2]["close"]
            
            if price_change > self.threshold:
                action = "BUY"
                reason = "PRICE_UP"
            elif price_change < -self.threshold:
                action = "SELL"
                reason = "PRICE_DOWN"
            else:
                action = "HOLD"
                reason = "NO_SIGNAL"
            
            signals[instrument_id] = Signal(
                action=action,
                reason=reason,
                timestamp=timestamp,
                metadata={"price_change": price_change}
            )
        
        return signals
\`\`\`

## Interface Contract

All strategies MUST:
1. Inherit from `BaseStrategy`
2. Implement `generate_signals(market_data) -> Dict[instrument_id, Signal]`
3. Return Signal objects (not plain strings)
4. Handle all instruments in market_data
5. Use only closed bars (no look-ahead bias)
6. Generate timestamps for all signals

## Common Mistakes and How to Avoid Them

### 1. Look-Ahead Bias

**What it is:** Using future information not available at decision time.

**Common sources:**
- Using current bar's high/low before bar closes
- Using end-of-day adjusted prices for intraday decisions
- Peeking at next bar's data

**How we prevent it:**
- `safe_slice_bars(require_closed=True)` enforces closed-bar discipline
- Explicit timestamps on all signals
- Bar data includes `is_closed` flag

**Reference:** Evidence-Based Technical Analysis (Aronson), Chapter 1
https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf

### 2. Backtest Overfitting

**What it is:** Testing many parameter sets and selecting the best produces misleadingly good in-sample results that fail out-of-sample.

**How to avoid:**
- Log ALL parameter sets you test (we do this automatically)
- Keep holdout data for final validation
- Use walk-forward analysis
- Document strategy rationale BEFORE tuning parameters

**Why parameter logging matters:** Creates audit trail preventing "data snooping bias"

**Reference:** Bailey et al. - The Probability of Backtest Overfitting
https://carmamaths.org/jon/backtest2.pdf

### 3. Incorrect Crossover Detection

**Mistake:** Checking if `short_ma > long_ma` at one instant

**Correct:** Compare previous vs current relationship to detect regime change

\`\`\`python
# WRONG: Just comparing current values
if short_ma > long_ma:
    action = "BUY"

# RIGHT: Detecting crossover (regime change)
crossover = detect_crossover(
    current_short, current_long,
    prev_short, prev_long
)
if crossover == "CROSSOVER_UP":
    action = "BUY"
\`\`\`

**Reference:** Brock, Lakonishok, LeBaron (1992) - MA crossovers as regime changes
https://law-journals-books.vlex.com/vid/simple-technical-trading-rules-stochastic-855602882

## Saxo-Specific Considerations

### SIM vs LIVE Pricing Behavior (Delayed Quotes)
Saxo’s **SIM** environment may return **delayed quotes** for non-FX instruments. If your data-quality gate rejects any delayed quote, you may unintentionally force **everything to HOLD** during development.

**Policy:** This project includes `ALLOW_DELAYED_DATA_IN_SIM` (default `true`) to allow progress in SIM while still being safe-by-default for LIVE.

- In **SIM**: allow delayed quotes when `ALLOW_DELAYED_DATA_IN_SIM=true` (log a loud warning)
- In **LIVE**: recommended to enforce `DelayedByMinutes == 0` (reject delayed)

Reference: https://openapi.help.saxo/hc/en-us/articles/4416934340625

### CryptoFX Trading Hours

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

**Default:** Extended hours disabled (safe)
**Enable:** Set `ALLOW_EXTENDED_HOURS=true` (use with caution)

**Reference:** https://www.help.saxo/hc/en-ch/articles/7574076258589

### Market State Handling

Strategies receive `quote.MarketState` in market data:
- `"Open"` - Regular trading hours
- `"Closed"` - Market closed
- `"PreMarket"` / `"AfterMarket"` - Extended hours

**Default behavior:** HOLD when not "Open"

## Operational Checklist (Before You Trust Signals)
- [ ] Confirm the end-to-end flow passes `decision_time_utc` (UTC) into every strategy call
- [ ] Confirm closed-bar filtering uses `timestamp < decision_time_utc` (no partial bars)
- [ ] Confirm SIM delayed-data policy (`ALLOW_DELAYED_DATA_IN_SIM`) is set intentionally
- [ ] Confirm extended-hours trading is **disabled by default** unless you explicitly opt-in

## Testing Your Strategy

Use provided test fixtures:

\`\`\`python
from tests.fixtures.strategy_fixtures import create_crossover_scenario
from tests.helpers.strategy_helpers import verify_strategy_determinism

def test_my_strategy():
    strategy = MyStrategy(threshold=0.02)
    market_data = create_crossover_scenario("golden")
    
    signals = strategy.generate_signals(market_data)
    
    # Verify determinism
    verify_strategy_determinism(strategy, market_data)
    
    # Check signals
    assert signals["Stock:211"].action in ["BUY", "SELL", "HOLD"]
\`\`\`

## Parameter Best Practices

1. **Document rationale:** Why these parameter values?
2. **Validate at init:** Check ranges, relationships
3. **Log all values:** Automatic via config system
4. **Use configuration:** Don't hard-code
5. **Test edge cases:** Min/max parameter values

## Adding Strategy to Registry

\`\`\`python
# In strategies/registry.py
from strategies.my_strategy import MyStrategy
register_strategy("my_strategy")(MyStrategy)
\`\`\`

Or use decorator in your strategy file:

\`\`\`python
from strategies.registry import register_strategy

@register_strategy("my_strategy")
class MyStrategy(BaseStrategy):
    ...
\`\`\`

## Configuration

Add to `.env`:

\`\`\`bash
STRATEGY_NAME=my_strategy
STRATEGY_PARAMS_JSON={"threshold": 0.02}
\`\`\`

## Resources

- Base interface: `strategies/base.py`
- Indicators: `strategies/indicators.py`
- Test fixtures: `tests/fixtures/strategy_fixtures.py`
- Example: `strategies/moving_average.py`
\`\`\`

## Estimated Effort
**3-4 hours**

## Definition of Done
- [ ] Complete developer guide created
- [ ] All common mistakes documented with examples
- [ ] Research references included
- [ ] Saxo-specific sections complete with URLs
- [ ] Code examples tested
- [ ] Quick-start section clear for beginners

## References
1. [Evidence-Based Technical Analysis](https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf) - Look-ahead bias
2. [Bailey et al.](https://carmamaths.org/jon/backtest2.pdf) - Backtest overfitting
3. [Brock et al.](https://law-journals-books.vlex.com/vid/simple-technical-trading-rules-stochastic-855602882) - MA crossovers
4. [Saxo CryptoFX](https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi) - Trading hours
5. [Saxo Extended Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589) - Risks
