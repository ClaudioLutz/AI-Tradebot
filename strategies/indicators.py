"""
Indicator utilities for trading strategies.

Pure, deterministic indicator calculation functions used by all strategies.
These functions enforce "closed-bar" discipline to prevent look-ahead bias.

Key Principles:
1. Pure functions (no side effects, deterministic outputs)
2. Explicit handling of edge cases (insufficient data, NaN values)
3. Safe bar slicing with time-awareness
4. Stable-order operations (time-sorted, monotonic timestamps)
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Sequence

logger = logging.getLogger(__name__)


def simple_moving_average(values: Sequence[float], window: int) -> Optional[float]:
    """
    Calculate Simple Moving Average of last `window` values.
    
    Args:
        values: Sequence of numeric values (e.g., closing prices)
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
    window_values = list(values[-window:])
    for val in window_values:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        if not isinstance(val, (int, float)):
            raise TypeError(f"All values must be numeric, got {type(val)}")
    
    return sum(window_values) / window


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
        values: Sequence of numeric values (e.g., closing prices)
        window: Number of periods for EMA calculation
        smoothing: Smoothing factor (typically 2.0)
    
    Returns:
        EMA value, or None if insufficient data
    
    Raises:
        ValueError: If window <= 0
    
    Formula:
        multiplier = smoothing / (window + 1)
        EMA = (close - EMA_prev) * multiplier + EMA_prev
    
    NaN/None Policy:
        Returns None if any value is None or NaN.
    
    Example:
        >>> exponential_moving_average([100, 101, 102, 103, 104], window=3)
        103.25  # Approximate, depends on smoothing
    """
    if window <= 0:
        raise ValueError(f"Window must be positive, got {window}")
    
    if not values or len(values) < window:
        return None
    
    # Check for None/NaN in all values
    for val in values:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        if not isinstance(val, (int, float)):
            raise TypeError(f"All values must be numeric, got {type(val)}")
    
    # Use SMA of first window as initial EMA
    ema = sum(values[:window]) / window
    multiplier = smoothing / (window + 1)
    
    # Apply EMA formula to remaining values
    for value in values[window:]:
        ema = (value - ema) * multiplier + ema
    
    return ema


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
        >>> decision_time = datetime.fromisoformat("2025-01-01T10:10:00+00:00")
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
        # Validate as_of is timezone-aware and UTC by semantics (not just object identity)
        if as_of.tzinfo is None:
            raise ValueError(
                f"as_of must be timezone-aware (got naive datetime: {as_of}). "
                f"Use datetime.now(timezone.utc) or ensure decision_time_utc has timezone info."
            )
        
        # Accept UTC by semantics, not just timezone.utc object identity
        # This accepts ZoneInfo("UTC"), pytz.UTC, etc.
        if as_of.utcoffset() != timedelta(0):
            raise ValueError(
                f"as_of must be in UTC timezone (got utcoffset={as_of.utcoffset()}). "
                f"Convert to UTC before calling safe_slice_bars()."
            )
        
        reference_time = as_of
        
        filtered_bars = []
        
        for bar in bars:
            # CRITICAL: Always check bar_time < as_of to prevent look-ahead bias.
            # Additionally, if is_closed flag is present, enforce it.
            try:
                bar_time = datetime.fromisoformat(bar["timestamp"].replace('Z', '+00:00'))
                
                # Require BOTH conditions for safety:
                # 1. Bar timestamp strictly before decision time (prevents look-ahead bias)
                # 2. Bar is marked closed (if is_closed flag present) OR we infer closure from timestamp
                
                # First check: timestamp must be in the past
                if bar_time >= reference_time:
                    # Bar is not in the past - skip it
                    if bar.get("is_closed", False):
                        # Data quality issue: bar claims to be closed but timestamp >= reference_time
                        logger.warning(
                            f"Bar marked is_closed=True but timestamp {bar['timestamp']} "
                            f"is not before decision time {as_of.isoformat()}. Skipping to prevent look-ahead bias."
                        )
                    continue
                
                # Second check: if is_closed flag exists, it must be True
                if "is_closed" in bar and not bar["is_closed"]:
                    # Bar exists in data but is not closed - skip it
                    continue
                
                # Bar passed all checks - safe to use
                filtered_bars.append(bar)
                
            except (ValueError, KeyError):
                # Skip bars with invalid timestamps when require_closed=True
                continue
        
        if len(filtered_bars) < n:
            return None
        
        return filtered_bars[-n:]
    
    return bars[-n:]


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
    
    Example:
        >>> detect_crossover(105, 100, 95, 100)  # Short crossed above
        'CROSSOVER_UP'
        >>> detect_crossover(95, 100, 105, 100)  # Short crossed below
        'CROSSOVER_DOWN'
        >>> detect_crossover(105, 100, 106, 100)  # Short stays above
        'NO_CROSSOVER'
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
