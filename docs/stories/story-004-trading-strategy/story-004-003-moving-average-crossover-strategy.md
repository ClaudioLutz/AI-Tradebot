# Story 004-003: Moving Average Crossover Strategy (Reference Implementation)

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Implement a Moving Average Crossover strategy as the reference implementation that demonstrates best practices, proper crossover detection, and serves as a template for future strategies.

## User Story
As a **strategy developer**, I want a **complete, working MA crossover strategy** so that **I have a tested template to follow when creating new strategies**.

## Goal
Create production-ready Moving Average Crossover strategy that:
1. Implements BaseStrategy interface from Story 004-001
2. Uses indicator utilities from Story 004-002
3. Detects crossovers properly (previous vs current comparison)
4. Handles all edge cases gracefully
5. Provides configurable parameters
6. Serves as the reference template for future strategies

## Acceptance Criteria

### 1. Strategy Class Created
- [ ] `strategies/moving_average.py` file created
- [ ] `MovingAverageCrossoverStrategy` class inherits from `BaseStrategy`
- [ ] Constructor accepts configurable parameters:
  - `short_window: int = 5`
  - `long_window: int = 20`
  - `threshold_bps: Optional[int] = None` (noise filter in basis points)
- [ ] Validates `short_window < long_window` at initialization

### 2. Crossover Detection Implemented
- [ ] Uses last `long_window + 1` bars to compute:
  - Previous short/long MA relationship
  - Current short/long MA relationship
- [ ] Emits `BUY` only if crosses from below to above
- [ ] Emits `SELL` only if crosses from above to below
- [ ] Emits `HOLD` if no crossover or insufficient bars

### 3. Signal Generation
- [ ] Returns `Signal` objects (not just action strings)
- [ ] Includes proper reason codes:
  - "INSUFFICIENT_BARS" - not enough data
  - "CROSSOVER_UP" - bullish crossover detected
  - "CROSSOVER_DOWN" - bearish crossover detected
  - "NO_CROSSOVER" - MA relationship stable
- [ ] Timestamps generated at decision time
- [ ] Metadata includes MA values for audit trail

### 4. Optional Threshold/Noise Filter
- [ ] If `threshold_bps` provided, requires MA separation > threshold before signaling
- [ ] Prevents whipsaw trades in ranging markets
- [ ] Documented in strategy comments

### 5. Edge Case Handling
- [ ] Returns HOLD with "INSUFFICIENT_BARS" if `len(bars) < long_window + 1`
- [ ] Handles missing `bars` field gracefully
- [ ] Handles None/invalid bar data
- [ ] Logs informative messages at appropriate levels

### 6. Integration Test
- [ ] Test with deterministic fixture data showing:
  - BUY signal on golden cross
  - SELL signal on death cross
  - HOLD on insufficient bars
  - HOLD when no crossover
- [ ] Verify signals are deterministic (same input → same output)

## Technical Implementation Notes

### File Structure
```
strategies/
├── __init__.py
├── base.py                    # From Story 004-001
├── indicators.py              # From Story 004-002
├── moving_average.py          # New: Reference strategy
└── simple_strategy.py         # Old placeholder (can be deprecated)
```

### Strategy Implementation
```python
"""
Moving Average Crossover Strategy

This is the reference implementation demonstrating best practices for all strategies.

Strategy Logic:
- Calculate short-term MA (e.g., 5 periods) and long-term MA (e.g., 20 periods)
- BUY signal: Short MA crosses ABOVE long MA (golden cross)
- SELL signal: Short MA crosses BELOW long MA (death cross)
- HOLD: No crossover detected or insufficient data

Academic Reference:
- Brock, Lakonishok, LeBaron (1992) - "Simple Technical Trading Rules and
  the Stochastic Properties of Stock Returns"
- Crossovers are treated as regime changes, not instantaneous MA comparisons
"""

import logging
from typing import Dict, Optional
from strategies.base import BaseStrategy, Signal, get_current_timestamp
from strategies.indicators import (
    simple_moving_average,
    safe_slice_bars,
    detect_crossover,
)

logger = logging.getLogger(__name__)


class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover strategy with proper crossover detection.
    
    Generates BUY/SELL signals when short MA crosses long MA, using
    previous vs current comparison to detect regime changes.
    
    Attributes:
        short_window: Number of periods for short MA (must be < long_window)
        long_window: Number of periods for long MA
        threshold_bps: Optional noise filter in basis points (e.g., 50 = 0.5%)
    """
    
    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        threshold_bps: Optional[int] = None,
    ):
        """
        Initialize Moving Average Crossover strategy.
        
        Args:
            short_window: Short MA period (default 5)
            long_window: Long MA period (default 20)
            threshold_bps: Minimum MA separation in bps to trigger signal (optional)
        
        Raises:
            ValueError: If short_window >= long_window or windows invalid
        """
        if short_window <= 0 or long_window <= 0:
            raise ValueError("Window sizes must be positive integers")
        
        if short_window >= long_window:
            raise ValueError(
                f"short_window ({short_window}) must be < long_window ({long_window})"
            )
        
        if threshold_bps is not None and threshold_bps < 0:
            raise ValueError(f"threshold_bps must be non-negative, got {threshold_bps}")
        
        self.short_window = short_window
        self.long_window = long_window
        self.threshold_bps = threshold_bps
        
        logger.info(
            f"Initialized MovingAverageCrossoverStrategy: "
            f"short={short_window}, long={long_window}, "
            f"threshold={threshold_bps}bps"
        )
    
    def generate_signals(self, market_data: Dict[str, dict]) -> Dict[str, Signal]:
        """
        Generate trading signals for all instruments using MA crossover logic.
        
        Args:
            market_data: Dict keyed by instrument_id with market data
        
        Returns:
            Dict keyed by instrument_id with Signal objects
        """
        signals = {}
        timestamp = get_current_timestamp()
        
        for instrument_id, data in market_data.items():
            symbol = data.get("symbol", "UNKNOWN")
            bars = data.get("bars", [])
            
            # Validate sufficient bars (need long_window + 1 for current + previous)
            required_bars = self.long_window + 1
            if not bars or len(bars) < required_bars:
                logger.debug(
                    f"{instrument_id} ({symbol}): Insufficient bars "
                    f"({len(bars) if bars else 0}/{required_bars})"
                )
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="INSUFFICIENT_BARS",
                    timestamp=timestamp,
                    metadata={"required": required_bars, "available": len(bars) if bars else 0}
                )
                continue
            
            # Use safe_slice_bars to enforce closed-bar discipline
            valid_bars = safe_slice_bars(bars, required_bars, require_closed=True)
            if valid_bars is None:
                logger.warning(
                    f"{instrument_id} ({symbol}): No closed bars available"
                )
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="INSUFFICIENT_BARS",
                    timestamp=timestamp,
                )
                continue
            
            # Extract closing prices
            closes = [bar["close"] for bar in valid_bars]
            
            # Calculate current MAs (using all available bars)
            current_short_ma = simple_moving_average(closes, self.short_window)
            current_long_ma = simple_moving_average(closes, self.long_window)
            
            # Calculate previous MAs (excluding most recent bar)
            prev_closes = closes[:-1]
            prev_short_ma = simple_moving_average(prev_closes, self.short_window)
            prev_long_ma = simple_moving_average(prev_closes, self.long_window)
            
            # Handle None returns (shouldn't happen given our validation, but be safe)
            if None in [current_short_ma, current_long_ma, prev_short_ma, prev_long_ma]:
                logger.warning(
                    f"{instrument_id} ({symbol}): MA calculation returned None"
                )
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="INSUFFICIENT_BARS",
                    timestamp=timestamp,
                )
                continue
            
            # Detect crossover (previous vs current comparison)
            crossover_type = detect_crossover(
                current_short_ma, current_long_ma,
                prev_short_ma, prev_long_ma
            )
            
            # Apply optional threshold filter
            if self.threshold_bps is not None and crossover_type != "NO_CROSSOVER":
                separation_pct = abs(current_short_ma - current_long_ma) / current_long_ma
                threshold_decimal = self.threshold_bps / 10000.0
                
                if separation_pct < threshold_decimal:
                    logger.debug(
                        f"{instrument_id} ({symbol}): Crossover detected but below "
                        f"threshold ({separation_pct:.4%} < {threshold_decimal:.4%})"
                    )
                    crossover_type = "NO_CROSSOVER"
            
            # Generate signal based on crossover
            if crossover_type == "CROSSOVER_UP":
                action = "BUY"
                reason = "CROSSOVER_UP"
                logger.info(
                    f"{instrument_id} ({symbol}): Golden cross detected - BUY "
                    f"(short_MA={current_short_ma:.2f}, long_MA={current_long_ma:.2f})"
                )
            elif crossover_type == "CROSSOVER_DOWN":
                action = "SELL"
                reason = "CROSSOVER_DOWN"
                logger.info(
                    f"{instrument_id} ({symbol}): Death cross detected - SELL "
                    f"(short_MA={current_short_ma:.2f}, long_MA={current_long_ma:.2f})"
                )
            else:
                action = "HOLD"
                reason = "NO_CROSSOVER"
                logger.debug(
                    f"{instrument_id} ({symbol}): No crossover "
                    f"(short_MA={current_short_ma:.2f}, long_MA={current_long_ma:.2f})"
                )
            
            # Create signal with metadata
            signals[instrument_id] = Signal(
                action=action,
                reason=reason,
                timestamp=timestamp,
                metadata={
                    "short_ma": round(current_short_ma, 2),
                    "long_ma": round(current_long_ma, 2),
                    "prev_short_ma": round(prev_short_ma, 2),
                    "prev_long_ma": round(prev_long_ma, 2),
                    "bars_used": len(valid_bars),
                }
            )
        
        return signals
```

## Rationale

### Why long_window + 1 Bars?
To detect crossovers, we need:
- Current MAs (using last `long_window` bars)
- Previous MAs (using last `long_window` bars, excluding most recent)

This requires `long_window + 1` bars total, ensuring proper "previous vs current" comparison.

### Why Threshold Filter?
In ranging markets, MAs can cross frequently without meaningful trend changes. The threshold filter (e.g., 50bps = 0.5%) prevents whipsaw trades by requiring minimum MA separation.

### Why Extensive Metadata?
The metadata field captures MA values at decision time, creating an audit trail. This is crucial for:
- Debugging signal generation
- Verifying strategy correctness
- Future backtesting analysis

**Reference:** Evidence-Based Technical Analysis (Aronson) - Importance of audit trails

## Testing Requirements

### Unit Tests (`tests/test_moving_average_strategy.py`)
```python
import pytest
from strategies.moving_average import MovingAverageCrossoverStrategy
from strategies.base import Signal

def test_strategy_initialization():
    """Test strategy initializes with valid parameters."""
    strategy = MovingAverageCrossoverStrategy(short_window=5, long_window=20)
    assert strategy.short_window == 5
    assert strategy.long_window == 20
    assert strategy.threshold_bps is None

def test_invalid_windows():
    """Test strategy rejects invalid window configurations."""
    # short >= long
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(short_window=20, long_window=5)
    
    # negative windows
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(short_window=-1, long_window=20)

def test_golden_cross_signal():
    """Test BUY signal on golden cross (short crosses above long)."""
    strategy = MovingAverageCrossoverStrategy(short_window=3, long_window=5)
    
    # Prices trending up, creating golden cross
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "bars": [
                {"close": 95, "timestamp": "2025-01-01T10:00:00Z", "is_closed": True},
                {"close": 96, "timestamp": "2025-01-01T10:05:00Z", "is_closed": True},
                {"close": 97, "timestamp": "2025-01-01T10:10:00Z", "is_closed": True},
                {"close": 98, "timestamp": "2025-01-01T10:15:00Z", "is_closed": True},
                {"close": 99, "timestamp": "2025-01-01T10:20:00Z", "is_closed": True},
                {"close": 105, "timestamp": "2025-01-01T10:25:00Z", "is_closed": True},  # Jump creates crossover
            ]
        }
    }
    
    signals = strategy.generate_signals(market_data)
    
    assert "Stock:211" in signals
    signal = signals["Stock:211"]
    assert signal.action == "BUY"
    assert signal.reason == "CROSSOVER_UP"
    assert "short_ma" in signal.metadata
    assert "long_ma" in signal.metadata

def test_death_cross_signal():
    """Test SELL signal on death cross (short crosses below long)."""
    strategy = MovingAverageCrossoverStrategy(short_window=3, long_window=5)
    
    # Prices trending down, creating death cross
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "bars": [
                {"close": 105, "timestamp": "2025-01-01T10:00:00Z", "is_closed": True},
                {"close": 104, "timestamp": "2025-01-01T10:05:00Z", "is_closed": True},
                {"close": 103, "timestamp": "2025-01-01T10:10:00Z", "is_closed": True},
                {"close": 102, "timestamp": "2025-01-01T10:15:00Z", "is_closed": True},
                {"close": 101, "timestamp": "2025-01-01T10:20:00Z", "is_closed": True},
                {"close": 95, "timestamp": "2025-01-01T10:25:00Z", "is_closed": True},  # Drop creates crossover
            ]
        }
    }
    
    signals = strategy.generate_signals(market_data)
    
    assert "Stock:211" in signals
    signal = signals["Stock:211"]
    assert signal.action == "SELL"
    assert signal.reason == "CROSSOVER_DOWN"

def test_insufficient_bars():
    """Test HOLD signal when insufficient bars."""
    strategy = MovingAverageCrossoverStrategy(short_window=5, long_window=20)
    
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "bars": [
                {"close": 100, "timestamp": "2025-01-01T10:00:00Z", "is_closed": True},
                {"close": 101, "timestamp": "2025-01-01T10:05:00Z", "is_closed": True},
            ]  # Only 2 bars, need 21
        }
    }
    
    signals = strategy.generate_signals(market_data)
    
    assert "Stock:211" in signals
    signal = signals["Stock:211"]
    assert signal.action == "HOLD"
    assert signal.reason == "INSUFFICIENT_BARS"

def test_no_crossover():
    """Test HOLD signal when MAs maintain relationship."""
    strategy = MovingAverageCrossoverStrategy(short_window=3, long_window=5)
    
    # Steady uptrend, short stays above long (no crossover)
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "bars": [
                {"close": 100, "timestamp": "2025-01-01T10:00:00Z", "is_closed": True},
                {"close": 101, "timestamp": "2025-01-01T10:05:00Z", "is_closed": True},
                {"close": 102, "timestamp": "2025-01-01T10:10:00Z", "is_closed": True},
                {"close": 103, "timestamp": "2025-01-01T10:15:00Z", "is_closed": True},
                {"close": 104, "timestamp": "2025-01-01T10:20:00Z", "is_closed": True},
                {"close": 105, "timestamp": "2025-01-01T10:25:00Z", "is_closed": True},
            ]
        }
    }
    
    signals = strategy.generate_signals(market_data)
    
    assert "Stock:211" in signals
    signal = signals["Stock:211"]
    assert signal.action == "HOLD"
    assert signal.reason == "NO_CROSSOVER"

def test_deterministic_signals():
    """Test that same input produces same output."""
    strategy = MovingAverageCrossoverStrategy(short_window=5, long_window=10)
    
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "bars": [{"close": 100 + i, "timestamp": f"2025-01-01T10:{i:02d}:00Z", "is_closed": True} 
                     for i in range(15)]
        }
    }
    
    signals1 = strategy.generate_signals(market_data)
    signals2 = strategy.generate_signals(market_data)
    
    # Timestamps will differ, but actions/reasons should match
    assert signals1["Stock:211"].action == signals2["Stock:211"].action
    assert signals1["Stock:211"].reason == signals2["Stock:211"].reason
```

## Dependencies
- Story 004-001 (BaseStrategy interface)
- Story 004-002 (Indicator utilities)
- Python 3.10+
- `logging` (standard library)

## Estimated Effort
**4-5 hours** (including comprehensive tests and documentation)

## Definition of Done
- [ ] `strategies/moving_average.py` created with complete implementation
- [ ] All edge cases handled gracefully
- [ ] Unit tests pass with >90% coverage
- [ ] Integration test with deterministic data passes
- [ ] Docstrings explain strategy logic and rationale
- [ ] Logs at appropriate levels
- [ ] Code reviewed and approved
- [ ] No pylint/mypy warnings

## Related Stories
- **Depends on:** Story 004-001, Story 004-002
- **Next:** Story 004-004 (Parameter handling uses this strategy)
- **Next:** Story 004-007 (Testing harness uses this as fixture)

## References
1. [Brock, Lakonishok, LeBaron (1992)](https://law-journals-books.vlex.com/vid/simple-technical-trading-rules-stochastic-855602882) - MA crossover as regime change
2. [Evidence-Based Technical Analysis (Aronson)](https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf) - Importance of audit trails and look-ahead bias prevention
