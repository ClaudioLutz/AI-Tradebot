"""
Tests for trading strategy module.
"""

import pytest
import math
from datetime import datetime, timezone, timedelta
from strategies.indicators import (
    simple_moving_average,
    exponential_moving_average,
    safe_slice_bars,
    detect_crossover
)

def test_simple_moving_average():
    """Test Simple Moving Average calculation."""
    # Basic calculation
    values = [10.0, 11.0, 12.0, 13.0, 14.0]
    assert simple_moving_average(values, 3) == 13.0  # (12+13+14)/3 = 13.0

    # Insufficient data
    assert simple_moving_average(values, 10) is None

    # None/NaN handling
    values_with_none = [10.0, None, 12.0]
    assert simple_moving_average(values_with_none, 2) is None

    values_with_nan = [10.0, float('nan'), 12.0]
    assert simple_moving_average(values_with_nan, 2) is None

    # Edge cases
    with pytest.raises(ValueError):
        simple_moving_average(values, 0)

    with pytest.raises(TypeError):
        simple_moving_average([10.0, "invalid"], 2)


def test_exponential_moving_average():
    """Test Exponential Moving Average calculation."""
    # Basic calculation
    values = [10.0, 11.0, 12.0, 13.0, 14.0]
    # Window=3, Smoothing=2 -> Multiplier = 2/(3+1) = 0.5
    # SMA(first 3) = (10+11+12)/3 = 11.0 (Initial EMA)
    # Next: (13 - 11) * 0.5 + 11 = 1 + 11 = 12.0
    # Next: (14 - 12) * 0.5 + 12 = 1 + 12 = 13.0
    assert exponential_moving_average(values, 3, smoothing=2.0) == 13.0

    # Insufficient data
    assert exponential_moving_average(values, 10) is None

    # None/NaN handling
    values_with_none = [10.0, None, 12.0]
    assert exponential_moving_average(values_with_none, 3) is None

    # Edge cases
    with pytest.raises(ValueError):
        exponential_moving_average(values, 0)


def test_safe_slice_bars():
    """Test safe bar slicing with time discipline."""
    t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    bars = [
        {"close": 100, "timestamp": (t0 + timedelta(minutes=0)).isoformat().replace("+00:00", "Z")},
        {"close": 101, "timestamp": (t0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")},
        {"close": 102, "timestamp": (t0 + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")},
    ]

    # Test as_of logic (live mode behavior)
    # Decision time at 10:11 -> can see all bars
    decision_time = t0 + timedelta(minutes=11)
    sliced = safe_slice_bars(bars, 2, as_of=decision_time, require_closed=True)
    assert len(sliced) == 2
    assert sliced[0]["close"] == 101
    assert sliced[1]["close"] == 102

    # Decision time at 10:06 -> can see first two bars
    decision_time = t0 + timedelta(minutes=6)
    sliced = safe_slice_bars(bars, 2, as_of=decision_time, require_closed=True)
    assert len(sliced) == 2
    assert sliced[0]["close"] == 100
    assert sliced[1]["close"] == 101

    # Decision time at 10:06 -> requesting 3 bars, but only 2 available (closed)
    sliced = safe_slice_bars(bars, 3, as_of=decision_time, require_closed=True)
    assert sliced is None

    # Test future leakage prevention
    # Bar 2 is at 10:10. If decision time is 10:09, we should NOT see Bar 2.
    decision_time = t0 + timedelta(minutes=9)
    # Bars closed before 10:09 are 10:00 and 10:05.
    sliced = safe_slice_bars(bars, 2, as_of=decision_time, require_closed=True)
    assert len(sliced) == 2
    assert sliced[-1]["timestamp"] == bars[1]["timestamp"]

    # Test is_closed flag
    bars_with_flag = [
        {"close": 100, "timestamp": (t0 + timedelta(minutes=0)).isoformat().replace("+00:00", "Z"), "is_closed": True},
        {"close": 101, "timestamp": (t0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), "is_closed": False}, # Not closed
    ]
    decision_time = t0 + timedelta(minutes=10) # Time is past, but flag says not closed
    sliced = safe_slice_bars(bars_with_flag, 1, as_of=decision_time, require_closed=True)
    # Bar 0: time < decision, is_closed=True -> Keep
    # Bar 1: time < decision, is_closed=False -> Skip
    # Filtered: [Bar 0]
    assert sliced[0]["close"] == 100

    # Validation errors
    with pytest.raises(ValueError, match="as_of must be timezone-aware"):
        safe_slice_bars(bars, 1, as_of=datetime(2025, 1, 1), require_closed=True)

    with pytest.raises(ValueError, match="as_of must be in UTC"):
        safe_slice_bars(bars, 1, as_of=t0.astimezone(timezone(timedelta(hours=1))), require_closed=True)

    # Test non-monotonic timestamps
    bad_bars = [
        {"close": 100, "timestamp": (t0 + timedelta(minutes=5)).isoformat()},
        {"close": 101, "timestamp": (t0 + timedelta(minutes=0)).isoformat()},
    ]
    with pytest.raises(ValueError, match="Non-monotonic timestamps"):
        safe_slice_bars(bad_bars, 1, as_of=decision_time)


def test_detect_crossover():
    """Test MA crossover detection."""
    # Up crossover
    assert detect_crossover(101, 100, 99, 100) == "CROSSOVER_UP"

    # Down crossover
    assert detect_crossover(99, 100, 101, 100) == "CROSSOVER_DOWN"

    # No crossover (staying above)
    assert detect_crossover(102, 100, 101, 100) == "NO_CROSSOVER"

    # No crossover (staying below)
    assert detect_crossover(98, 100, 99, 100) == "NO_CROSSOVER"

    # Touch case (equal values)
    # Prev equal (100, 100) -> Current above (101, 100)
    # prev_short_above = 100 > 100 (False)
    # current_short_above = 101 > 100 (True)
    # -> CROSSOVER_UP
    assert detect_crossover(101, 100, 100, 100) == "CROSSOVER_UP"

    # Prev below (99, 100) -> Current equal (100, 100)
    # prev_short_above = 99 > 100 (False)
    # current_short_above = 100 > 100 (False)
    # -> NO_CROSSOVER
    assert detect_crossover(100, 100, 99, 100) == "NO_CROSSOVER"


def test_calculate_indicators():
    """Wrapper to aggregate indicator tests if run as a single suite."""
    test_simple_moving_average()
    test_exponential_moving_average()
    test_safe_slice_bars()
    test_detect_crossover()
