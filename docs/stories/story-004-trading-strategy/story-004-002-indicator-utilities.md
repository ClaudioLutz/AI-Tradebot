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
- [ ] **NaN/None policy**: Returns None if any input is None/NaN; raises TypeError for invalid input types

### 2. Exponential Moving Average Function (Optional)
- [ ] `exponential_moving_average(values: Sequence[float], window: int, smoothing: float = 2.0) -> Optional[float]`
- [ ] Returns None if `len(values) < window`
- [ ] Uses standard EMA formula: `EMA = (Close - EMA_prev) * multiplier + EMA_prev`
- [ ] Multiplier = `smoothing / (window + 1)`
- [ ] Pure function (no side effects)
- [ ] Accepts `Sequence[float]` (more flexible than `List[float]`)
- [ ] **NaN/None policy**: Returns None if any input is None/NaN

### 3. Safe Bar Slicing Utility (Stable-Order and Time-Aware)
- [ ] `safe_slice_bars(bars: List[dict], n: int, as_of: datetime, require_closed: bool = True) -> Optional[List[dict]]`
- [ ] **`as_of` is REQUIRED** (no Optional) - caller must explicitly pass `decision_time_utc`
- [ ] If `require_closed=True`: only returns bars with timestamp strictly < `as_of`
- [ ] Returns None if insufficient bars available
- [ ] Validates bar structure (has required fields: 'close', 'timestamp')
- [ ] **Stable-order**: Slices by timestamp (not just list index) when possible - validates bars are time-ordered
- [ ] **Time-aware**: Parses timestamps and compares chronologically
- [ ] Returns last `n` bars if available
- [ ] **ELIMINATES time leakage by construction** - never calls `datetime.now()` internally

### 4. Crossover Detection Helper (Deterministic Behavior)
- [ ] `detect_crossover(current_short: float, current_long: float, prev_short: float, prev_long: float) -> str`
- [ ] Returns "CROSSOVER_UP" if short crossed above long
- [ ] Returns "CROSSOVER_DOWN" if long crossed above short  
- [ ] Returns "NO_CROSSOVER" if no regime change
- [ ] Uses previous vs current comparison (not just current instant)
- [ ] **Deterministic on equal values**: Define "touch" vs "cross" behavior when MAs are exactly equal
  - Current implementation: only true crossovers count (strict inequality change)
  - Document this in function docstring

### 5. Edge Case Handling (Numerical Robustness)
- [ ] All functions handle None/empty inputs gracefully
- [ ] Window size validation (positive integers only)
- [ ] Type hints on all parameters and returns
- [ ] Clear error messages for invalid inputs
- [ ] **Numerical robustness AC**: Test with:
  - Empty list → returns None
  - Length=1 → returns None if window > 1
  - Non-monotonic time → raises ValueError or warns
  - Missing 'close' field → raises KeyError or ValueError
  - NaN/None values → returns None
  - All-zero values → handles gracefully (no division by zero)

### 6. Unit Tests (Comprehensive Edge Cases)
- [ ] Tests for SMA with exact hand-calculated values
- [ ] Tests for EMA with exact hand-calculated values
- [ ] Tests for insufficient data (returns None)
- [ ] Tests for invalid window sizes (raises ValueError)
- [ ] Tests for crossover detection (all scenarios including equal values)
- [ ] Tests for safe_slice_bars with require_closed flag
- [ ] **Edge case tests**:
  - Empty list input
  - Length=1 list
  - Non-monotonic timestamps
  - Missing 'close' field in bars
  - NaN/None values in data
  - All-zero values
  - "Touch" vs "cross" (equal MA values)

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
        TypeError: If values contain non-numeric types
    
    NaN/None Policy:
        Returns None if any value is None or NaN (ensures numeric robustness).
    
    Example:
        >>> simple_moving_average([100, 101, 102, 103, 104], window=3)
        103.0  # Average of [102, 103, 104]
        >>> simple_moving_average([100, None, 102], window=2)
        None  # Contains None value
    """
    if window <= 0:
        raise ValueError(f"Window must be positive, got {window}")
    
    if not values or len(values) < window:
        return None
    
    # Check for None/NaN in last window values
    window_values = values[-window:]
    for val in window_values:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        if not isinstance(val, (int, float)):
            raise TypeError(f"All values must be numeric, got {type(val)}")
    
    return sum(window_values) / window
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
    as_of: datetime,
    require_closed: bool = True,
) -> Optional[List[Dict]]:
    """
    Safely extract last `n` bars, enforcing "closed-bar only" discipline.
    
    This function prevents look-ahead bias by ensuring only completed bars are used.
    
    **TIME DISCIPLINE:** The `as_of` parameter is REQUIRED (not Optional).
    - Live mode: Pass `datetime.now(timezone.utc)` or current decision time
    - Backtest mode: Pass the bar-close timestamp (event time) you are evaluating
    - This eliminates time leakage by construction - no hidden `datetime.now()` calls
    
    **STABLE-ORDER:** Slices by timestamp, not just list index. Validates bars are
    time-ordered (monotonic increasing timestamps).
    
    Args:
        bars: List of bar dicts with at least {"close": float, "timestamp": str}
        n: Number of bars to extract
        as_of: Reference time for determining "closed" bars (REQUIRED, must be explicit)
        require_closed: If True, only use bars with timestamp strictly < as_of
    
    Returns:
        Last `n` bars if available, or None if insufficient data
    
    Raises:
        ValueError: If bars have invalid structure or non-monotonic timestamps
    
    Example (live mode):
        >>> from datetime import datetime, timezone
        >>> decision_time = datetime.now(timezone.utc)
        >>> bars = [
        ...     {"close": 100, "timestamp": "2025-01-01T10:00:00Z"},
        ...     {"close": 101, "timestamp": "2025-01-01T10:05:00Z"},
        ... ]
        >>> safe_slice_bars(bars, 2, as_of=decision_time, require_closed=True)
        [{"close": 100, ...}, {"close": 101, ...}]
    
    Example (backtest mode):
        >>> decision_time = datetime.fromisoformat("2025-01-01T10:10:00Z")
        >>> safe_slice_bars(bars, 2, as_of=decision_time, require_closed=True)
        [{"close": 100, ...}, {"close": 101, ...}]
    """
    if not bars or len(bars) < n:
        return None
    
    # Validate bar structure AND check for monotonic timestamps
    prev_time = None
    for i, bar in enumerate(bars):
        if "close" not in bar:
            raise ValueError(f"Bar missing 'close' field at index {i}: {bar}")
        if "timestamp" not in bar:
            raise ValueError(f"Bar missing 'timestamp' field at index {i}: {bar}")
        
        # Parse timestamp to validate format and check monotonicity
        try:
            bar_time = datetime.fromisoformat(bar["timestamp"].replace('Z', '+00:00'))
            if prev_time is not None and bar_time <= prev_time:
                raise ValueError(
                    f"Non-monotonic timestamps at index {i}: "
                    f"{bar['timestamp']} is not after {bars[i-1]['timestamp']}"
                )
            prev_time = bar_time
        except ValueError as e:
            raise ValueError(f"Invalid timestamp at index {i}: {e}")
    
    if require_closed:
        # as_of is now required - no fallback to datetime.now()
        reference_time = as_of
        
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
    
    Deterministic Behavior on Equal Values ("Touch" vs "Cross"):
        When MAs are exactly equal, this is treated as "not crossed" (requires strict
        inequality change). For example:
        - prev_short=100, prev_long=100 (equal) → current_short=101, current_long=100
          Result: NO_CROSSOVER (was already touching, not a true cross)
        - prev_short=99, prev_long=100 (below) → current_short=101, current_long=100
          Result: CROSSOVER_UP (crossed from below to above)
        
        This prevents spurious signals when MAs merely "touch" without regime change.
    
    Reference:
        Brock, Lakonishok, LeBaron (1992) - Simple Technical Trading Rules
    """
    # Use strict inequality: only count as "above" if strictly greater
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
    result = safe_slice_bars(bars, 2, as_of=as_of, require_closed=True)
    assert result is not None
    assert len(result) == 2
    assert result[0]["close"] == 101

def test_safe_slice_bars_insufficient():
    """Test bar slicing with insufficient data."""
    from datetime import datetime, timezone
    as_of = datetime.fromisoformat("2025-01-01T10:15:00Z")
    bars = [{"close": 100, "timestamp": "2025-01-01T10:00:00Z"}]
    result = safe_slice_bars(bars, 3, as_of=as_of, require_closed=False)
    assert result is None

def test_safe_slice_bars_deterministic():
    """Test that required as_of parameter enforces determinism."""
    from datetime import datetime, timezone
    
    as_of = datetime.fromisoformat("2025-01-01T10:15:00Z")
    bars = [
        {"close": 100, "timestamp": "2025-01-01T10:00:00Z"},
        {"close": 101, "timestamp": "2025-01-01T10:05:00Z"},
        {"close": 102, "timestamp": "2025-01-01T10:10:00Z"},
        {"close": 103, "timestamp": "2025-01-01T10:20:00Z"},  # After as_of, should be excluded
    ]
    
    result1 = safe_slice_bars(bars, 3, as_of=as_of, require_closed=True)
    result2 = safe_slice_bars(bars, 3, as_of=as_of, require_closed=True)
    
    # Should return same bars both times (deterministic)
    assert result1 == result2
    assert len(result1) == 3
    assert result1[-1]["close"] == 102  # Last bar before as_of
    
    # Bar at 10:20 should be excluded since it's after as_of
    assert all(bar["close"] != 103 for bar in result1)

def test_safe_slice_bars_requires_as_of():
    """Test that as_of is required (no default fallback to now())."""
    bars = [{"close": 100, "timestamp": "2025-01-01T10:00:00Z"}]
    
    # This should fail at the type-checker level, but we test runtime behavior
    # If as_of were Optional with default None, this would work - we want it to fail
    with pytest.raises(TypeError):
        safe_slice_bars(bars, 1)  # Missing required as_of argument

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

def test_detect_crossover_equal_values():
    """Test deterministic behavior when MAs are exactly equal (touch vs cross)."""
    # Case 1: MAs were equal, now short is above → NO_CROSSOVER (touch, not cross)
    result = detect_crossover(
        current_short=101, current_long=100,
        prev_short=100, prev_long=100
    )
    assert result == "NO_CROSSOVER"
    
    # Case 2: Short crossed from below to above through equality → CROSSOVER_UP
    result = detect_crossover(
        current_short=101, current_long=100,
        prev_short=99, prev_long=100
    )
    assert result == "CROSSOVER_UP"
    
    # Case 3: Both equal now, were equal before → NO_CROSSOVER
    result = detect_crossover(
        current_short=100, current_long=100,
        prev_short=100, prev_long=100
    )
    assert result == "NO_CROSSOVER"

def test_sma_nan_handling():
    """Test SMA returns None for NaN/None values."""
    import math
    assert simple_moving_average([100, None, 102], window=2) is None
    assert simple_moving_average([100, math.nan, 102], window=2) is None

def test_safe_slice_bars_non_monotonic():
    """Test that non-monotonic timestamps raise ValueError."""
    from datetime import datetime, timezone
    as_of = datetime.now(timezone.utc)
    
    bars = [
        {"close": 100, "timestamp": "2025-01-01T10:05:00Z"},  # Later time first
        {"close": 101, "timestamp": "2025-01-01T10:00:00Z"},  # Earlier time second
    ]
    
    with pytest.raises(ValueError, match="Non-monotonic"):
        safe_slice_bars(bars, 2, as_of=as_of)

def test_sma_empty_list():
    """Test SMA handles empty list gracefully."""
    assert simple_moving_average([], window=1) is None

def test_sma_length_one():
    """Test SMA with length=1 list."""
    assert simple_moving_average([100], window=1) == 100.0
    assert simple_moving_average([100], window=2) is None
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
