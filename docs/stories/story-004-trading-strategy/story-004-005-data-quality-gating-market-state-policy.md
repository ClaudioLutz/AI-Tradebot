# Story 004-005: Data-Quality Gating and Market-State Policy

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Implement safe-by-default data quality gates and market state policies that prevent strategies from trading on stale/delayed data or during inappropriate market conditions (closed markets, extended hours).

## User Story
As a **trader**, I want **strategies to automatically skip trading on bad data or closed markets** so that **I don't make trades based on stale information or during risky extended hours**.

## Goal
Create defensive data quality layer that:
1. Checks data freshness/staleness before strategy execution
2. Respects market state (open/closed/extended hours)
3. Defaults to HOLD for questionable data quality
4. Documents Saxo-specific market timing (CryptoFX weekdays, extended hours)
5. Allows opt-in for extended hours trading with explicit configuration

## Acceptance Criteria

### 1. Data Quality Checker Created
- [ ] `strategies/data_quality.py` module with:
  - `DataQualityChecker` class
  - `check_data_quality(market_data) -> Dict[instrument_id, QualityResult]`
  - Quality flags: `is_fresh`, `is_delayed`, `is_stale`, `is_market_open`

### 2. Market State Policy
- [ ] Checks `quote.MarketState` from Epic 003 data
- [ ] Default policy: Return HOLD if market is not "Open"
- [ ] Extended hours handling:
  - Default: HOLD during extended hours (pre-market/after-hours)
  - Configurable: `ALLOW_EXTENDED_HOURS=true` enables extended hours trading
  - Warning logged when trading extended hours (volatility/liquidity risk)

### 3. Saxo-Specific Documentation
- [ ] CryptoFX trading hours documented:
  - **Weekday-only trading** (not 24/7 as commonly assumed)
  - Weekend gaps expected in data
  - Reference: Saxo developer portal
- [ ] Extended hours risks documented:
  - Lower liquidity
  - Higher volatility
  - Reference: Saxo help documentation

### 4. Data Freshness Checking
- [ ] Check `LastUpdated` timestamp from quote data
- [ ] Flag as stale if older than threshold (configurable, default 5 minutes)
- [ ] Flag as delayed if quote indicates delayed data
- [ ] Log warnings for stale/delayed data

### 5. Strategy Integration
- [ ] Wrap strategy `generate_signals()` with quality checker
- [ ] Pre-check data quality before calling strategy
- [ ] Override strategy signals with HOLD if quality insufficient
- [ ] Log reason for quality-based HOLD

### 6. Configuration Options
- [ ] `ALLOW_EXTENDED_HOURS` (default: false)
- [ ] `DATA_STALENESS_THRESHOLD_SECONDS` (default: 300 = 5 min)
- [ ] `REQUIRE_MARKET_OPEN` (default: true)
- [ ] `.env.example` updated with examples and warnings

## Technical Implementation Notes

### Data Quality Checker (`strategies/data_quality.py`)
```python
"""
Data quality checking and market state validation.

This module prevents strategies from trading on stale/delayed data or during
inappropriate market conditions, protecting against common real-world issues.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, NamedTuple
from config import settings

logger = logging.getLogger(__name__)


class QualityResult(NamedTuple):
    """Result of data quality check for an instrument."""
    is_fresh: bool
    is_market_open: bool
    is_delayed: bool
    reason: str
    metadata: Optional[Dict[str, Any]] = None


class DataQualityChecker:
    """
    Checks data quality and market state before allowing strategy execution.
    
    Implements safe-by-default policies:
    - HOLD on stale/delayed data
    - HOLD when market closed
    - HOLD during extended hours (unless explicitly enabled)
    
    Attributes:
        allow_extended_hours: Whether to trade during pre/post market
        staleness_threshold: Max age of data in seconds (default 300 = 5 min)
        require_market_open: Whether to require open market state
    """
    
    def __init__(
        self,
        allow_extended_hours: bool = False,
        staleness_threshold_seconds: int = 300,
        require_market_open: bool = True,
    ):
        """
        Initialize data quality checker.
        
        Args:
            allow_extended_hours: Allow trading during extended hours (default False)
            staleness_threshold_seconds: Max data age in seconds (default 300)
            require_market_open: Require market to be open (default True)
        """
        self.allow_extended_hours = allow_extended_hours
        self.staleness_threshold = timedelta(seconds=staleness_threshold_seconds)
        self.require_market_open = require_market_open
        
        if allow_extended_hours:
            logger.warning(
                "Extended hours trading ENABLED - be aware of increased volatility "
                "and reduced liquidity risk. "
                "Reference: https://www.help.saxo/hc/en-ch/articles/7574076258589"
            )
        
        logger.info(
            f"DataQualityChecker initialized: "
            f"extended_hours={allow_extended_hours}, "
            f"staleness_threshold={staleness_threshold_seconds}s, "
            f"require_open={require_market_open}"
        )
    
    def check_data_quality(
        self, 
        market_data: Dict[str, Dict]
    ) -> Dict[str, QualityResult]:
        """
        Check data quality for all instruments.
        
        Args:
            market_data: Dict keyed by instrument_id with market data
        
        Returns:
            Dict keyed by instrument_id with QualityResult
        """
        results = {}
        now = datetime.now(timezone.utc)
        
        for instrument_id, data in market_data.items():
            symbol = data.get("symbol", "UNKNOWN")
            asset_type = data.get("asset_type", "UNKNOWN")
            quote = data.get("quote", {})
            
            # Check market state
            market_state = quote.get("MarketState", "Unknown")
            is_market_open = market_state == "Open"
            
            # Check for extended hours (if market is "Open" but outside regular hours)
            # This would need market hours data, simplified here
            is_extended_hours = market_state == "OpenExtended"  # Hypothetical
            
            # Check data freshness
            last_updated_str = quote.get("LastUpdated")
            is_fresh = True
            is_delayed = quote.get("DelayedByMinutes", 0) > 0
            
            if last_updated_str:
                try:
                    last_updated = datetime.fromisoformat(
                        last_updated_str.replace('Z', '+00:00')
                    )
                    age = now - last_updated
                    is_fresh = age <= self.staleness_threshold
                    
                    if not is_fresh:
                        logger.warning(
                            f"{instrument_id} ({symbol}): Stale data "
                            f"(age={age.total_seconds():.0f}s > "
                            f"threshold={self.staleness_threshold.total_seconds():.0f}s)"
                        )
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"{instrument_id} ({symbol}): Invalid timestamp {last_updated_str}: {e}"
                    )
                    is_fresh = False
            else:
                logger.warning(
                    f"{instrument_id} ({symbol}): No LastUpdated timestamp"
                )
                is_fresh = False
            
            # Determine if data is acceptable
            reason_parts = []
            
            if not is_fresh:
                reason_parts.append("STALE_DATA")
            
            if is_delayed:
                reason_parts.append("DELAYED_DATA")
                logger.debug(
                    f"{instrument_id} ({symbol}): Data is delayed by "
                    f"{quote.get('DelayedByMinutes')} minutes"
                )
            
            if self.require_market_open and not is_market_open:
                reason_parts.append(f"MARKET_{market_state.upper()}")
                logger.debug(
                    f"{instrument_id} ({symbol}): Market is {market_state}"
                )
            
            if is_extended_hours and not self.allow_extended_hours:
                reason_parts.append("EXTENDED_HOURS_DISABLED")
                logger.debug(
                    f"{instrument_id} ({symbol}): Extended hours, but not allowed"
                )
            
            # Special handling for CryptoFX weekend gaps
            if asset_type == "CryptoFx" and now.weekday() >= 5:  # Saturday=5, Sunday=6
                reason_parts.append("CRYPTOFX_WEEKEND")
                logger.info(
                    f"{instrument_id} ({symbol}): CryptoFX does not trade on weekends "
                    f"(Saxo-specific). "
                    f"Reference: https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi"
                )
            
            # Create result
            reason = "_".join(reason_parts) if reason_parts else "OK"
            is_acceptable = (
                is_fresh and 
                (not self.require_market_open or is_market_open) and
                (not is_extended_hours or self.allow_extended_hours) and
                not (asset_type == "CryptoFx" and now.weekday() >= 5)
            )
            
            results[instrument_id] = QualityResult(
                is_fresh=is_fresh,
                is_market_open=is_market_open,
                is_delayed=is_delayed,
                reason=reason,
                metadata={
                    "market_state": market_state,
                    "asset_type": asset_type,
                    "last_updated": last_updated_str,
                }
            )
        
        return results
    
    def filter_market_data(
        self, 
        market_data: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """
        Filter market data to only include instruments with acceptable quality.
        
        Args:
            market_data: Dict keyed by instrument_id
        
        Returns:
            Filtered dict with only acceptable-quality data
        """
        quality_results = self.check_data_quality(market_data)
        
        filtered = {}
        for instrument_id, data in market_data.items():
            quality = quality_results[instrument_id]
            if quality.reason == "OK":
                filtered[instrument_id] = data
            else:
                logger.info(
                    f"Filtering out {instrument_id} due to: {quality.reason}"
                )
        
        return filtered


def wrap_strategy_with_quality_check(strategy, quality_checker: DataQualityChecker):
    """
    Wrap a strategy's generate_signals method with data quality checking.
    
    This ensures strategies only see high-quality data and prevents trading
    on stale/delayed data or during closed markets.
    
    Args:
        strategy: Strategy instance with generate_signals method
        quality_checker: DataQualityChecker instance
    
    Returns:
        Wrapped strategy with quality checking
    """
    original_generate_signals = strategy.generate_signals
    
    def wrapped_generate_signals(market_data: Dict[str, Dict]):
        """Generate signals with quality checking."""
        from strategies.base import Signal, get_current_timestamp
        
        # Check quality for all instruments
        quality_results = quality_checker.check_data_quality(market_data)
        
        # Filter to only acceptable quality data
        acceptable_data = {
            instrument_id: data
            for instrument_id, data in market_data.items()
            if quality_results[instrument_id].reason == "OK"
        }
        
        # Generate signals for acceptable data
        signals = {}
        if acceptable_data:
            signals = original_generate_signals(acceptable_data)
        
        # Add HOLD signals for filtered-out instruments
        timestamp = get_current_timestamp()
        for instrument_id in market_data:
            if instrument_id not in signals:
                quality = quality_results[instrument_id]
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason=f"DATA_QUALITY_{quality.reason}",
                    timestamp=timestamp,
                    metadata=quality.metadata,
                )
        
        return signals
    
    strategy.generate_signals = wrapped_generate_signals
    return strategy
```

### Configuration Extensions (`config/settings.py`)
```python
# Data Quality and Market State Policy
ALLOW_EXTENDED_HOURS = os.getenv("ALLOW_EXTENDED_HOURS", "false").lower() == "true"
DATA_STALENESS_THRESHOLD_SECONDS = int(os.getenv("DATA_STALENESS_THRESHOLD_SECONDS", "300"))
REQUIRE_MARKET_OPEN = os.getenv("REQUIRE_MARKET_OPEN", "true").lower() == "true"
```

### `.env.example` Updates
```bash
# Data Quality and Market State Policy
# =====================================

# Allow trading during extended hours (pre-market/after-hours)
# WARNING: Extended hours have lower liquidity and higher volatility risk
# Reference: https://www.help.saxo/hc/en-ch/articles/7574076258589
ALLOW_EXTENDED_HOURS=false

# Maximum age of market data before considered stale (seconds)
# Default: 300 seconds (5 minutes)
DATA_STALENESS_THRESHOLD_SECONDS=300

# Require market to be in "Open" state before trading
# Default: true (safe)
REQUIRE_MARKET_OPEN=true

# Important Notes:
# - CryptoFX trades WEEKDAYS ONLY (not 24/7 despite common assumption)
#   Reference: https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi
# - Weekend gaps are expected in CryptoFX data
# - Extended hours trading is disabled by default for safety
```

## Rationale

### Why Safe-by-Default?
Real-world trading involves many edge cases (stale data, market closures, connectivity issues). A safe-by-default approach prevents accidental trades during inappropriate conditions.

### Why Document CryptoFX Hours?
The common assumption is that cryptocurrency markets are 24/7. However, Saxo's CryptoFX trades **weekdays only**, which can surprise developers and cause confusion about weekend data gaps.

**Reference:** [Saxo Developer Portal - Crypto FX](https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi)

### Why Extended Hours Opt-In?
Extended hours trading involves:
- Lower liquidity (wider spreads)
- Higher volatility
- Fewer market participants

Making this opt-in with explicit warnings protects inexperienced traders.

**Reference:** [Saxo Extended Trading Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589)

## Testing Requirements

### Unit Tests (`tests/test_data_quality.py`)
```python
import pytest
from datetime import datetime, timezone, timedelta
from strategies.data_quality import (
    DataQualityChecker,
    QualityResult,
    wrap_strategy_with_quality_check,
)

def test_fresh_data_open_market():
    """Test that fresh data with open market passes."""
    checker = DataQualityChecker()
    
    now = datetime.now(timezone.utc)
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "asset_type": "Stock",
            "quote": {
                "MarketState": "Open",
                "LastUpdated": now.isoformat(),
                "DelayedByMinutes": 0,
            }
        }
    }
    
    results = checker.check_data_quality(market_data)
    assert results["Stock:211"].reason == "OK"
    assert results["Stock:211"].is_fresh is True
    assert results["Stock:211"].is_market_open is True

def test_stale_data():
    """Test that stale data is flagged."""
    checker = DataQualityChecker(staleness_threshold_seconds=300)
    
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "asset_type": "Stock",
            "quote": {
                "MarketState": "Open",
                "LastUpdated": stale_time.isoformat(),
            }
        }
    }
    
    results = checker.check_data_quality(market_data)
    assert "STALE_DATA" in results["Stock:211"].reason
    assert results["Stock:211"].is_fresh is False

def test_market_closed():
    """Test that closed market is flagged."""
    checker = DataQualityChecker(require_market_open=True)
    
    now = datetime.now(timezone.utc)
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "asset_type": "Stock",
            "quote": {
                "MarketState": "Closed",
                "LastUpdated": now.isoformat(),
            }
        }
    }
    
    results = checker.check_data_quality(market_data)
    assert "MARKET_CLOSED" in results["Stock:211"].reason
    assert results["Stock:211"].is_market_open is False

def test_cryptofx_weekend():
    """Test that CryptoFX weekend is flagged."""
    checker = DataQualityChecker()
    
    # Note: This test would need to be run on a weekend or mock datetime
    # Simplified for illustration
    now = datetime.now(timezone.utc)
    market_data = {
        "CryptoFx:1581": {
            "instrument_id": "CryptoFx:1581",
            "symbol": "BTCUSD",
            "asset_type": "CryptoFx",
            "quote": {
                "MarketState": "Closed",
                "LastUpdated": now.isoformat(),
            }
        }
    }
    
    # Would check for CRYPTOFX_WEEKEND on weekends
    results = checker.check_data_quality(market_data)
    assert results["CryptoFx:1581"] is not None

def test_filter_market_data():
    """Test that low-quality data is filtered out."""
    checker = DataQualityChecker()
    
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(minutes=10)
    
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "quote": {"MarketState": "Open", "LastUpdated": now.isoformat()}
        },
        "Stock:212": {
            "instrument_id": "Stock:212",
            "quote": {"MarketState": "Closed", "LastUpdated": now.isoformat()}
        },
    }
    
    filtered = checker.filter_market_data(market_data)
    assert "Stock:211" in filtered
    assert "Stock:212" not in filtered
```

## Dependencies
- Epic 003 (market data with MarketState and LastUpdated)
- Story 004-001 (Signal schema)
- Python 3.10+

## Estimated Effort
**4-5 hours** (including tests and documentation)

## Definition of Done
- [ ] `strategies/data_quality.py` created with complete implementation
- [ ] Configuration options added to `config/settings.py`
- [ ] `.env.example` updated with warnings and references
- [ ] Unit tests pass with >90% coverage
- [ ] CryptoFX weekday-only documented with reference
- [ ] Extended hours risks documented with reference
- [ ] Integration with strategy wrapper tested
- [ ] Code reviewed and approved

## Related Stories
- **Depends on:** Story 004-001 (Signal schema)
- **Depends on:** Epic 003 (market data format)
- **Next:** Story 004-006 (Strategy registry)

## References
1. [Saxo Developer Portal - Crypto FX](https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi) - CryptoFX weekday-only trading
2. [Saxo Extended Trading Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589) - Extended hours risks
