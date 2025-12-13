# Story 004-002: Indicator Utilities (Pure, Deterministic)

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Create a library of pure, deterministic indicator calculation functions used by all strategies. These functions enforce "closed-bar" discipline to prevent look-ahead bias and provide consistent technical analysis calculations.

## User Story
As a **strategy developer**, I want **reusable, tested indicator functions** so that **I don't duplicate logic and can trust calculations are correct and bias-free**.

## Goal
Build foundation indicator library with:
1. Simple Moving Average (SMA) calculation
2. Exponential Moving Average (EMA) - optional but useful
3. Safe bar slicing utility that enforces "closed-bar only" rules
4. Pure functions (no side effects, deterministic outputs)
5. Explicit handling of edge cases (insufficient data)

## Acceptance Criteria

### 1. Simple Moving Average Function
- [ ] `simple_moving_average(values: Sequence[float], window: int) -> Optional[float]` created
- [ ] Returns None if `len(values) < window`
- [ ] Calculates mean of last `window` values
- [ ] Raises ValueError if `window <= 0`
- [ ] Pure function (no side effects)
- [ ] Accepts `Sequence[float]` (more flexible than `List[float]`)

### 2. Exponential Moving Average Function (Optional)
- [ ] `exponential_moving_average(values: Sequence[float], window: int, smoothing: float = 2.0) -> Optional[float]`
- [ ] Returns None if `len(values) < window`
- [ ] Uses standard EMA formula: `EMA = (Close - EMA_prev) * multiplier + EMA_prev`
- [ ] Multiplier = `smoothing / (window + 1)`
- [ ] Pure function (no side effects)
- [ ] Accepts `Sequence[float]` (more flexible than `List[float]`)

### 3. Safe Bar Slicing Utility
- [ ] `safe_slice_bars(bars: List[dict], n: int, require_closed: bool = True, as_of: Optional[datetime] = None) -> Optional[List[dict]]`
- [ ] If `require_closed=True`: only returns bars with timestamp before `as_of` (or current time if as_of=None)
- [ ] `as_of` parameter makes function deterministic for backtesting
- [ ] Returns None if insufficient bars available
- [ ] Validates bar structure (has required fields)
- [ ] Returns last `n` bars if available
- [ ] **CRITICAL:** Never uses `datetime.now()` internally when `as_of` is provided (prevents time leakage)

### 4. Crossover Detection Helper
- [ ] `detect_crossover(current_short: float, current_long: float, prev_short: float, prev_long: float) -> str`
- [ ] Returns "CROSSOVER_UP" if short crossed above long
- [ ] Returns "CROSSOVER_DOWN" if long crossed above short  
- [ ] Returns "NO_CROSSOVER" if no regime change
- [ ] Uses previous vs current comparison (not just current instant)

### 5. Edge Case Handling
- [ ] All functions handle None/empty inputs gracefully
- [ ] Window size validation (positive integers only)
- [ ] Type hints on all parameters and returns
- [ ] Clear error messages for invalid inputs

### 6. Unit Tests
- [ ] Tests for SMA with exact hand-calculated values
- [ ] Tests for EMA with exact hand-calculated values
- [ ] Tests for insufficient data (returns None)
- [ ] Tests for invalid window sizes (raises ValueError)
- [ ] Tests for crossover detection (all scenarios)
- [ ] Tests for safe_slice_bars with require_closed flag

## Technical Implementation Notes

### File Structure
```
strategies/
├── __init__.py
├── base.py              # From Story 004-001
├── indicators.py        # New: Pure indicator functions
└── simple_strategy.py
```

### Simple Moving Average Implementation
```python
from typing import Sequence, Optional

def simple_moving_average(values: Sequence[float], window: int) -> Optional[float]:
    """
    Calculate Simple Moving Average of last `window` values.
    
    Args:
        values: List of numeric values (e.g., closing prices)
        window: Number of periods to average (must be > 0)
    
    Returns:
        Average of last `window` values, or None if insufficient data
    
    Raises:
        ValueError: If window <= 0
    
    Example:
        >>> simple_moving_average([100, 101, 102, 103, 104], window=3)
        103.0  # Average of [102, 103, 104]
    """
    if window <= 0:
        raise ValueError(f"Window must be positive, got {window}")
    
    if not values or len(values) < window:
        return None
    
    return sum(values[-window:]) / window
```

### Exponential Moving Average Implementation
```python
def exponential_moving_average(
    values: Sequence[float], 
    window: int, 
    smoothing: float = 2.0
) -> Optional[float]:
    """
    Calculate Exponential Moving Average using standard formula.
    
    EMA emphasizes recent prices more than simple average.
    Uses SMA of first `window` values as initial EMA, then applies exponential smoothing.
    
    Args:
        values: List of numeric values (e.g., closing prices)
        window: Number of periods for EMA calculation
        smoothing: Smoothing factor (typically 2.0)
    
    Returns:
        EMA value, or None if insufficient data
    
    Formula:
        multiplier = smoothing / (window + 1)
        EMA = (close - EMA_prev) * multiplier + EMA_prev
    
    Example:
        >>> exponential_moving_average([100, 101, 102, 103, 104], window=3)
        103.25  # Approximate, depends on smoothing
    """
    if window <= 0:
        raise ValueError(f"Window must be positive, got {window}")
    
    if not values or len(values) < window:
        return None
    
    # Use SMA of first window as initial EMA
    ema = sum(values[:window]) / window
    multiplier = smoothing / (window + 1)
    
    # Apply EMA formula to remaining values
    for value in values[window:]:
        ema = (value - ema) * multiplier + ema
    
    return ema
```

### Safe Bar Slicing Implementation
```python
from datetime import datetime, timezone
from typing import List, Optional, Dict

def safe_slice_bars(
    bars: List[Dict], 
    n: int, 
    require_closed: bool = True,
    as_of: Optional[datetime] = None
) -> Optional[List[Dict]]:
    """
    Safely extract last `n` bars, optionally enforcing "closed-bar only" rule.
    
    This function prevents look-ahead bias by ensuring only completed bars are used.
    
    **CRITICAL FOR BACKTESTING:** The `as_of` parameter makes this function deterministic.
    In live mode, pass current UTC time. In backtest mode, pass the bar-close timestamp
    you are evaluating. Never call without `as_of` in backtest mode.
    
    Args:
        bars: List of bar dicts with at least {"close": float, "timestamp": str}
        n: Number of bars to extract
        require_closed: If True, only use bars with timestamp before `as_of`
        as_of: Reference time for determining "closed" bars (defaults to now if None)
    
    Returns:
        Last `n` bars if available, or None if insufficient data
    
    Raises:
        ValueError: If bars have invalid structure
    
    Example (live mode):
        >>> from datetime import datetime, timezone
        >>> as_of = datetime.now(timezone.utc)
        >>> bars = [
        ...     {"close": 100, "timestamp": "2025-01-01T10:00:00Z"},
        ...     {"close": 101, "timestamp": "2025-01-01T10:05:00Z"},
        ... ]
        >>> safe_slice_bars(bars, 2, require_closed=True, as_of=as_of)
        [{"close": 100, ...}, {"close": 101, ...}]
    
    Example (backtest mode):
        >>> as_of = datetime.fromisoformat("2025-01-01T10:10:00Z")
        >>> safe_slice_bars(bars, 2, require_closed=True, as_of=as_of)
        [{"close": 100, ...}, {"close": 101, ...}]
    """
    if not bars or len(bars) < n:
        return None
    
    # Validate bar structure
    for bar in bars[-n:]:
        if "close" not in bar:
            raise ValueError(f"Bar missing 'close' field: {bar}")
        if "timestamp" not in bar:
            raise ValueError(f"Bar missing 'timestamp' field: {bar}")
    
    if require_closed:
        # Use as_of if provided, otherwise fall back to current time
        # WARNING: Fallback to now() is for live mode convenience only
        # In backtest mode, as_of MUST be provided
        reference_time = as_of if as_of is not None else datetime.now(timezone.utc)
        
        filtered_bars = []
        
        for bar in bars:
            # Check if bar is explicitly closed
            if bar.get("is_closed", False):
                filtered_bars.append(bar)
                continue
            
            # Check if bar timestamp is before reference time
            try:
                bar_time = datetime.fromisoformat(bar["timestamp"].replace('Z', '+00:00'))
                if bar_time < reference_time:
                    filtered_bars.append(bar)
            except (ValueError, KeyError):
                # Skip bars with invalid timestamps when require_closed=True
                continue
        
        if len(filtered_bars) < n:
            return None
        
        return filtered_bars[-n:]
    
    return bars[-n:]
```

### Crossover Detection Implementation
```python
def detect_crossover(
    current_short: float, 
    current_long: float,
    prev_short: float,
    prev_long: float
) -> str:
    """
    Detect moving average crossover by comparing current vs previous relationship.
    
    This implements the academically-studied MA crossover rule from Brock et al. (1992),
    which treats signals as regime changes, not just instantaneous comparisons.
    
    Args:
        current_short: Current short-period MA value
        current_long: Current long-period MA value
        prev_short: Previous short-period MA value
        prev_long: Previous long-period MA value
    
    Returns:
        "CROSSOVER_UP": Short crossed above long (bullish)
        "CROSSOVER_DOWN": Short crossed below long (bearish)
        "NO_CROSSOVER": No regime change
    
    Reference:
        Brock, Lakonishok, LeBaron (1992) - Simple Technical Trading Rules
    """
    prev_short_above = prev_short > prev_long
    current_short_above = current_short > current_long
    
    if not prev_short_above and current_short_above:
        return "CROSSOVER_UP"
    elif prev_short_above and not current_short_above:
        return "CROSSOVER_DOWN"
    else:
        return "NO_CROSSOVER"
```

## Rationale

### Why Pure Functions?
1. **Testability:** Easy to test with known inputs/outputs
2. **Determinism:** Same inputs always produce same outputs
3. **Composability:** Can be combined without side effects
4. **Debugging:** No hidden state makes issues easier to trace

### Why require_closed Flag and as_of Parameter?
The `require_closed` flag enforces "closed-bar only" discipline to prevent look-ahead bias. In backtesting, using the current bar's high/low before it closes is a classic mistake that produces misleadingly good results.

The `as_of` parameter is **critical for deterministic backtesting**:
- **Live mode:** Pass `datetime.now(timezone.utc)` to filter bars up to current time
- **Backtest mode:** Pass the bar-close timestamp you're evaluating (e.g., "2025-01-15T10:30:00Z")
- **Why it matters:** Without `as_of`, the function uses wall-clock time internally, which changes between calls and creates non-reproducible results in backtests ("time leakage")

**Reference:** Evidence-Based Technical Analysis (Aronson) - Look-ahead bias prevention

### Why Crossover Detection Function?
Academic literature treats MA signals as regime changes (crossovers), not just MA_short > MA_long at one instant. This function enforces proper crossover detection.

**Reference:** Brock, Lakonishok, LeBaron (1992) - Simple Technical Trading Rules and the Stochastic Properties of Stock Returns

## Testing Requirements

### Unit Tests (`tests/test_indicators.py`)
```python
import pytest
from strategies.indicators import (
    simple_moving_average,
    exponential_moving_average,
    safe_slice_bars,
    detect_crossover,
)

def test_sma_normal():
    """Test SMA with sufficient data."""
    values = [100, 101, 102, 103, 104]
    assert simple_moving_average(values, 3) == 103.0
    assert simple_moving_average(values, 5) == 102.0

def test_sma_insufficient_data():
    """Test SMA returns None with insufficient data."""
    values = [100, 101]
    assert simple_moving_average(values, 3) is None
    assert simple_moving_average([], 1) is None

def test_sma_invalid_window():
    """Test SMA raises ValueError for invalid window."""
    with pytest.raises(ValueError):
        simple_moving_average([100, 101], window=0)
    with pytest.raises(ValueError):
        simple_moving_average([100, 101], window=-1)

def test_ema_calculation():
    """Test EMA calculation with known values."""
    # Hand-calculated EMA with window=3, smoothing=2.0
    values = [100, 102, 104, 106, 108]
    result = exponential_moving_average(values, 3)
    assert result is not None
    assert 106 < result < 108  # Should be weighted toward recent values

def test_safe_slice_bars_sufficient():
    """Test bar slicing with sufficient data."""
    from datetime import datetime, timezone
    
    as_of = datetime.fromisoformat("2025-01-01T10:15:00Z")
    bars = [
        {"close": 100, "timestamp": "2025-01-01T10:00:00Z"},
        {"close": 101, "timestamp": "2025-01-01T10:05:00Z"},
        {"close": 102, "timestamp": "2025-01-01T10:10:00Z"},
    ]
    result = safe_slice_bars(bars, 2, require_closed=True, as_of=as_of)
    assert result is not None
    assert len(result) == 2
    assert result[0]["close"] == 101

def test_safe_slice_bars_insufficient():
    """Test bar slicing with insufficient data."""
    bars = [{"close": 100, "timestamp": "2025-01-01T10:00:00Z"}]
    result = safe_slice_bars(bars, 3, require_closed=False)
    assert result is None

def test_safe_slice_bars_deterministic():
    """Test that as_of parameter makes function deterministic."""
    from datetime import datetime, timezone
    
    as_of = datetime.fromisoformat("2025-01-01T10:15:00Z")
    bars = [
        {"close": 100, "timestamp": "2025-01-01T10:00:00Z"},
        {"close": 101, "timestamp": "2025-01-01T10:05:00Z"},
        {"close": 102, "timestamp": "2025-01-01T10:10:00Z"},
        {"close": 103, "timestamp": "2025-01-01T10:20:00Z"},  # After as_of, should be excluded
    ]
    
    result1 = safe_slice_bars(bars, 3, require_closed=True, as_of=as_of)
    result2 = safe_slice_bars(bars, 3, require_closed=True, as_of=as_of)
    
    # Should return same bars both times (deterministic)
    assert result1 == result2
    assert len(result1) == 3
    assert result1[-1]["close"] == 102  # Last bar before as_of
    
    # Bar at 10:20 should be excluded since it's after as_of
    assert all(bar["close"] != 103 for bar in result1)

def test_detect_crossover_up():
    """Test bullish crossover detection."""
    result = detect_crossover(
        current_short=105, current_long=100,
        prev_short=95, prev_long=100
    )
    assert result == "CROSSOVER_UP"

def test_detect_crossover_down():
    """Test bearish crossover detection."""
    result = detect_crossover(
        current_short=95, current_long=100,
        prev_short=105, prev_long=100
    )
    assert result == "CROSSOVER_DOWN"

def test_detect_no_crossover():
    """Test no crossover when relationship maintains."""
    result = detect_crossover(
        current_short=105, current_long=100,
        prev_short=106, prev_long=100
    )
    assert result == "NO_CROSSOVER"
```

## Dependencies
- Python 3.10+
- `typing` (standard library)
- `datetime` (standard library)

## Estimated Effort
**3-4 hours** (including comprehensive tests)

## Definition of Done
- [ ] `strategies/indicators.py` created with all functions
- [ ] All functions are pure (no side effects)
- [ ] Complete type hints on all signatures
- [ ] Unit tests pass with >95% coverage
- [ ] Docstrings include examples
- [ ] Edge cases handled gracefully
- [ ] No pylint/mypy warnings

## Related Stories
- **Depends on:** Story 004-001 (for Signal schema understanding)
- **Next:** Story 004-003 (Moving Average strategy uses these indicators)

## References
1. [Evidence-Based Technical Analysis (Aronson)](https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf) - Look-ahead bias prevention via closed bars
2. [Brock, Lakonishok, LeBaron (1992)](https://law-journals-books.vlex.com/vid/simple-technical-trading-rules-stochastic-855602882) - MA crossover as regime change
