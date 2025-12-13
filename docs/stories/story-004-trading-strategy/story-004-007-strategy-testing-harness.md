# Story 004-007: Strategy Unit Testing Harness and Fixtures

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Create reusable testing fixtures and harness for strategy development, enabling robust isolation testing and preventing common testing pitfalls.

## User Story
As a **strategy developer**, I want **ready-made test fixtures and helpers** so that **I can thoroughly test strategies without duplicating test code**.

## Goal
Build comprehensive testing infrastructure with:
1. Deterministic market data fixtures
2. Edge case fixtures (gaps, stale data, closed markets)
3. Helper functions for strategy testing
4. Example tests demonstrating best practices

## Acceptance Criteria

### 1. Test Fixtures Module
- [ ] `tests/fixtures/strategy_fixtures.py` created with:
  - `create_mock_market_data()` - generates deterministic test data
  - `create_trending_bars()` - uptrend/downtrend scenarios
  - `create_crossover_scenario()` - golden/death cross patterns
  - `create_insufficient_bars()` - edge case testing
  - `create_stale_data()` - data quality testing
  - `create_closed_market()` - market state testing

### 2. Test Helpers
- [ ] `assert_signal_valid(signal)` - validates Signal structure
- [ ] `assert_all_instruments_have_signals(signals, market_data)` - completeness check
- [ ] Helper to verify determinism (same input → same output)

### 3. Example Test Suite
- [ ] `tests/test_strategy_harness_example.py` demonstrates:
  - Crossover detection testing
  - Insufficient bars handling
  - Stale data handling
  - Market closed handling
  - Determinism verification

### 4. Documentation
- [ ] README in tests/fixtures/ explaining fixtures
- [ ] Examples of how to use fixtures for new strategies
- [ ] Common testing patterns documented

## Technical Implementation

### Fixtures Module (`tests/fixtures/strategy_fixtures.py`)
```python
"""
Test fixtures for strategy testing.

Provides deterministic, reusable market data scenarios for strategy unit tests.
"""

from datetime import datetime, timezone, timedelta

# IMPORTANT: Prefer fixed timestamps in fixtures to keep tests deterministic.
# Avoid datetime.now() for bars/quotes unless the test explicitly targets "freshness" logic.
from typing import List, Dict

def create_mock_market_data(
    instrument_id: str = "Stock:211",
    symbol: str = "AAPL",
    asset_type: str = "Stock",
    num_bars: int = 30,
    starting_price: float = 100.0,
    price_increment: float = 1.0,
    market_state: str = "Open",
    is_fresh: bool = True,
) -> Dict:
    """
    Create deterministic mock market data for testing.
    
    Args:
        instrument_id: Instrument ID
        symbol: Symbol name
        asset_type: Asset type
        num_bars: Number of bars to generate
        starting_price: Starting close price
        price_increment: Price change per bar
        market_state: Market state
        is_fresh: Whether data is fresh
    
    Returns:
        Mock market data dict matching Epic 003 format
    """
    # Fixed base time to keep fixtures deterministic
    now = datetime.fromisoformat("2025-01-01T00:00:00+00:00")
    last_updated = now if is_fresh else now - timedelta(minutes=10)
    
    bars = []
    for i in range(num_bars):
        bar_time = now - timedelta(minutes=(num_bars - i) * 5)
        close_price = starting_price + (i * price_increment)
        
        bars.append({
            "open": close_price - 0.5,
            "high": close_price + 0.5,
            "low": close_price - 0.75,
            "close": close_price,
            "volume": 1000000,
            "timestamp": bar_time.isoformat(),
            "is_closed": True,
        })
    
    return {
        instrument_id: {
            "instrument_id": instrument_id,
            "symbol": symbol,
            "asset_type": asset_type,
            "uic": int(instrument_id.split(':')[1]),
            "quote": {
                "MarketState": market_state,
                "LastUpdated": last_updated.isoformat(),
                "DelayedByMinutes": 0,
                "Ask": close_price + 0.05,
                "Bid": close_price - 0.05,
            },
            "bars": bars,
        }
    }


def create_crossover_scenario(
    crossover_type: str = "golden",  # "golden" or "death"
    short_window: int = 3,
    long_window: int = 5,
) -> Dict:
    """
    Create market data showing a clear MA crossover.
    
    Args:
        crossover_type: "golden" (short crosses above) or "death" (short crosses below)
        short_window: Short MA window
        long_window: Long MA window
    
    Returns:
        Market data dict with crossover pattern
    """
    num_bars = long_window + 5  # Extra bars to establish pattern
    
    if crossover_type == "golden":
        # Start low, trend up to create golden cross
        starting_price = 95.0
        increment = 2.0  # Strong uptrend
    else:  # death cross
        # Start high, trend down
        starting_price = 110.0
        increment = -2.0  # Strong downtrend
    
    return create_mock_market_data(
        num_bars=num_bars,
        starting_price=starting_price,
        price_increment=increment,
    )


def create_insufficient_bars(required_bars: int) -> Dict:
    """Create market data with insufficient bars."""
    return create_mock_market_data(num_bars=required_bars - 5)


def create_stale_data() -> Dict:
    """Create market data with stale timestamp."""
    return create_mock_market_data(is_fresh=False)


def create_closed_market() -> Dict:
    """Create market data with closed market state."""
    return create_mock_market_data(market_state="Closed")


def create_weekend_cryptofx() -> Dict:
    """Create CryptoFX data on weekend (should be blocked)."""
    data = create_mock_market_data(
        instrument_id="CryptoFx:1581",
        symbol="BTCUSD",
        asset_type="CryptoFx",
        market_state="Closed"
    )
    # Set bars to weekend timestamps (would need datetime manipulation)
    return data
```

### Test Helpers (`tests/helpers/strategy_helpers.py`)
```python
"""Helper functions for strategy testing."""

from strategies.base import Signal

def assert_signal_valid(signal: Signal):
    """
    Assert that a Signal object is valid.
    
    Checks:
    - action is one of BUY/SELL/HOLD
    - reason is non-empty string
    - timestamp is present
    """
    assert signal.action in ["BUY", "SELL", "HOLD"], f"Invalid action: {signal.action}"
    assert isinstance(signal.reason, str), "Reason must be string"
    assert len(signal.reason) > 0, "Reason cannot be empty"
    assert isinstance(signal.timestamp, str), "Timestamp must be string"
    assert len(signal.timestamp) > 0, "Timestamp cannot be empty"


def assert_all_instruments_have_signals(signals: dict, market_data: dict):
    """
    Assert that every instrument in market_data has a signal.
    
    Strategies must return signals for all instruments, even if HOLD.
    """
    for instrument_id in market_data:
        assert instrument_id in signals, f"Missing signal for {instrument_id}"
        assert_signal_valid(signals[instrument_id])


def verify_strategy_determinism(strategy, market_data: dict, num_runs: int = 3):
    """
    Verify that strategy produces consistent results on multiple runs.
    
    Args:
        strategy: Strategy instance
        market_data: Test market data
        num_runs: Number of times to run strategy
    
    Raises:
        AssertionError: If results differ across runs
    """
    results = []
    
    for i in range(num_runs):
        signals = strategy.generate_signals(market_data)
        # Extract just actions and reasons (timestamps will differ)
        run_results = {
            inst_id: (signal.action, signal.reason)
            for inst_id, signal in signals.items()
        }
        results.append(run_results)
    
    # All runs should produce identical actions/reasons
    for i in range(1, num_runs):
        assert results[i] == results[0], \
            f"Run {i} produced different results than run 0"
```

### Example Test (`tests/test_strategy_harness_example.py`)
```python
"""
Example test suite demonstrating strategy testing best practices.

Use this as a template for testing your own strategies.
"""

import pytest
from tests.fixtures.strategy_fixtures import (
    create_crossover_scenario,
    create_insufficient_bars,
    create_stale_data,
    create_closed_market,
)
from tests.helpers.strategy_helpers import (
    assert_signal_valid,
    assert_all_instruments_have_signals,
    verify_strategy_determinism,
)
from strategies.moving_average import MovingAverageCrossoverStrategy


class TestStrategyHarnessExample:
    """Example strategy tests using harness."""
    
    def test_golden_cross_detection(self):
        """Test that golden cross generates BUY signal."""
        strategy = MovingAverageCrossoverStrategy(short_window=3, long_window=5)
        market_data = create_crossover_scenario("golden", 3, 5)
        
        signals = strategy.generate_signals(market_data)
        
        assert_all_instruments_have_signals(signals, market_data)
        
        instrument_id = list(market_data.keys())[0]
        signal = signals[instrument_id]
        assert signal.action == "BUY", "Expected BUY on golden cross"
        assert "CROSSOVER_UP" in signal.reason
    
    def test_death_cross_detection(self):
        """Test that death cross generates SELL signal."""
        strategy = MovingAverageCrossoverStrategy(short_window=3, long_window=5)
        market_data = create_crossover_scenario("death", 3, 5)
        
        signals = strategy.generate_signals(market_data)
        
        instrument_id = list(market_data.keys())[0]
        signal = signals[instrument_id]
        assert signal.action == "SELL", "Expected SELL on death cross"
        assert "CROSSOVER_DOWN" in signal.reason
    
    def test_insufficient_bars(self):
        """Test HOLD on insufficient bars."""
        strategy = MovingAverageCrossoverStrategy(short_window=5, long_window=20)
        market_data = create_insufficient_bars(required_bars=21)
        
        signals = strategy.generate_signals(market_data)
        
        instrument_id = list(market_data.keys())[0]
        signal = signals[instrument_id]
        assert signal.action == "HOLD"
        assert "INSUFFICIENT_BARS" in signal.reason
    
    def test_determinism(self):
        """Test that strategy produces consistent results."""
        strategy = MovingAverageCrossoverStrategy(short_window=3, long_window=5)
        market_data = create_crossover_scenario("golden", 3, 5)
        
        verify_strategy_determinism(strategy, market_data, num_runs=5)
```

## References
- Testing best practices: Deterministic fixtures prevent flaky tests
- Look-ahead bias prevention: Fixed timestamps in fixtures

## Estimated Effort
**3-4 hours**

## Definition of Done
- [ ] Fixture module created with all scenarios
- [ ] Helper functions implemented
- [ ] Example test suite demonstrates usage
- [ ] Documentation explains how to use fixtures
- [ ] All fixtures return valid Epic 003 format data
