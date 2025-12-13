# Story 004-005: Data-Quality Gating and Market-State Policy (Saxo-Aligned)

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Implement safe-by-default data quality gates and market state policies that prevent strategies from trading on stale/delayed data or during inappropriate market conditions, **aligned with Saxo Bank's actual API behavior**.

## User Story
As a **trader**, I want **strategies to automatically skip trading on bad data or closed markets** so that **I don't make trades based on stale information or during risky extended hours**.

## Goal
Create defensive data quality layer that:
1. Checks data freshness/staleness using **LastUpdated timestamp** (not just DelayedByMinutes)
2. Respects Saxo **MarketState enum** (Open, Closed, PreMarket, PostMarket, auction states)
3. Treats **NoAccess** as a distinct, explainable gate with operator guidance
4. Handles **SIM environment** delayed quote behavior appropriately
5. Defaults to HOLD for questionable data quality
6. Documents Saxo-specific market timing (CryptoFX weekdays, extended hours)
7. Allows opt-in for extended hours trading with explicit configuration

## Acceptance Criteria

### 1. Data Quality Checker Created
- [ ] `strategies/data_quality.py` module with:
  - `DataQualityChecker` class
  - `check_data_quality(market_data) -> Dict[instrument_id, QualityResult]`
  - Quality flags: `is_fresh`, `is_delayed`, `is_stale`, `is_market_open`, `is_noaccess`

### 2. Market State Policy (Saxo MarketState Enum Aligned)
- [ ] Checks `quote.MarketState` from Epic 003 data using **Saxo's actual enum values**:
  - `Open`, `Closed`, `PreMarket`, `PostMarket`, `OpeningAuction`, `ClosingAuction`, `IntraDayAuction`, `TradingAtLast`
- [ ] Default policy: Return HOLD if market is not `Open`
- [ ] Extended hours handling:
  - **Tradable states (default)**: `{Open}` only
  - **Extended-hours states** (opt-in via `ALLOW_EXTENDED_HOURS=true`): `{PreMarket, PostMarket}`
  - **Auction states**: Default HOLD (document that conditional/stop orders behave differently)
  - Warning logged when trading extended hours (volatility/liquidity risk)
- [ ] **Reference**: https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate

### 3. Freshness Based on LastUpdated (Not Just DelayedByMinutes)
- [ ] **Staleness computation uses `LastUpdated` timestamp** and a threshold (default 5 min)
- [ ] **Cannot trust `DelayedByMinutes == 0` alone**: Saxo docs show cases where delay is 0 but LastUpdated is old (illiquid instruments)
- [ ] Flag as stale if `now() - LastUpdated > threshold`
- [ ] Flag as delayed if `DelayedByMinutes > 0`
- [ ] **Reference**: https://openapi.help.saxo/hc/en-us/articles/6105016299677

### 4. NoAccess Handling (Distinct Gate with Guidance)
- [ ] Treat **NoAccess / missing quote** as a **distinct quality failure mode**
- [ ] Reason code: `DQ_NOACCESS_MARKETDATA` (not "stale")
- [ ] Log actionable guidance:
  - SIM: "Market data not available for non-FX on SIM unless account is linked"
  - LIVE: "Enable market data in SaxoTraderGO or check subscriptions"
- [ ] **References**: 
  - https://openapi.help.saxo/hc/en-us/articles/4405160773661
  - https://openapi.help.saxo/hc/en-us/articles/4418427366289

### 5. SIM Environment Constraints
- [ ] **SIM behavior**: Non-FX instruments may return delayed quotes or NoAccess
- [ ] Policy controlled by `ALLOW_DELAYED_DATA_IN_SIM` (default: true for development progress)
- [ ] When enabled, loud WARNING logged on every delayed quote acceptance
- [ ] When disabled (recommended for LIVE), reject all delayed quotes
- [ ] **Reference**: https://openapi.help.saxo/hc/en-us/articles/4416934146449

### 6. PriceType Handling (Saxo Quote Semantics)
- [ ] Check `PriceTypeBid` and `PriceTypeAsk` from quote
- [ ] **`OldIndicative` price type**: Market closed / last known price - default to HOLD unless explicitly allowed
- [ ] Record PriceType values in `Signal.policy_flags`
- [ ] **References**:
  - https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade/schema-quote
  - https://www.developer.saxo/openapi/learn/pricing

### 7. CryptoFX Weekday-Only Trading
- [ ] **CryptoFX trades WEEKDAYS ONLY on Saxo** (not 24/7)
- [ ] Weekend check (UTC): if `asset_type == "CryptoFx" and now.weekday() >= 5`, return HOLD
- [ ] Reason code: `DQ_CRYPTOFX_WEEKEND`
- [ ] **Reference**: https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi

### 8. Extended Hours Risk Warning
- [ ] When `ALLOW_EXTENDED_HOURS=true`, log WARNING on init:
  - Lower liquidity / higher volatility
  - Wider spreads
  - Stop/conditional orders behave differently
- [ ] **Reference**: https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning

### 9. Configuration Options
- [ ] `ALLOW_EXTENDED_HOURS` (default: false)
- [ ] `DATA_STALENESS_THRESHOLD_SECONDS` (default: 300 = 5 min)
- [ ] `REQUIRE_MARKET_OPEN` (default: true)
- [ ] `ALLOW_DELAYED_DATA_IN_SIM` (default: true with loud warning)
- [ ] `.env.example` updated with examples, warnings, and Saxo reference URLs

## Technical Implementation Notes

### Data Quality Checker (`strategies/data_quality.py`)
```python
"""
Data quality checking and market state validation (Saxo-aligned).

This module prevents strategies from trading on stale/delayed data or during
inappropriate market conditions, based on Saxo Bank's actual API behavior.

Key Saxo-specific considerations:
1. DelayedByMinutes=0 does NOT guarantee fresh data (illiquid instruments)
2. NoAccess is a distinct failure mode requiring operator action
3. SIM environment may return delayed quotes for non-FX
4. CryptoFX trades weekdays only (not 24/7)
5. PriceType "OldIndicative" = market closed / last known price
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, NamedTuple
import os

from config import settings

logger = logging.getLogger(__name__)


class QualityResult(NamedTuple):
    """Result of data quality check for an instrument."""
    is_fresh: bool
    is_market_open: bool
    is_delayed: bool
    is_noaccess: bool
    reason: str
    metadata: Optional[Dict[str, Any]] = None


class DataQualityChecker:
    """
    Checks data quality and market state before allowing strategy execution.
    
    Implements safe-by-default policies aligned with Saxo API behavior:
    - HOLD on stale data (based on LastUpdated, not just DelayedByMinutes)
    - HOLD when market not Open (uses Saxo MarketState enum)
    - HOLD during extended hours (unless explicitly enabled)
    - HOLD on NoAccess (distinct from stale - requires operator action)
    - HOLD when PriceType is OldIndicative (market closed)
    
    Attributes:
        allow_extended_hours: Whether to trade during pre/post market
        staleness_threshold: Max age of LastUpdated in seconds (default 300)
        require_market_open: Whether to require Open market state
        allow_delayed_in_sim: SIM-specific: allow delayed quotes for development
    """
    
    def __init__(
        self,
        allow_extended_hours: bool = False,
        staleness_threshold_seconds: int = 300,
        require_market_open: bool = True,
        allow_delayed_in_sim: Optional[bool] = None,
    ):
        """
        Initialize data quality checker.
        
        Args:
            allow_extended_hours: Allow trading PreMarket/PostMarket (default False)
            staleness_threshold_seconds: Max LastUpdated age in seconds (default 300)
            require_market_open: Require market to be Open (default True)
            allow_delayed_in_sim: SIM-only: allow delayed quotes (default from env)
        """
        self.allow_extended_hours = allow_extended_hours
        self.staleness_threshold = timedelta(seconds=staleness_threshold_seconds)
        self.require_market_open = require_market_open
        
        # Determine SIM delayed data policy
        saxo_env = os.getenv("SAXO_ENV", "SIM").upper()
        if allow_delayed_in_sim is None:
            self.allow_delayed_in_sim = (
                saxo_env == "SIM" and
                os.getenv("ALLOW_DELAYED_DATA_IN_SIM", "true").lower() == "true"
            )
        else:
            self.allow_delayed_in_sim = allow_delayed_in_sim
        
        if allow_extended_hours:
            logger.warning(
                "⚠️  Extended hours trading ENABLED - increased volatility and reduced liquidity risk. "
                "Stop/conditional orders behave differently in extended hours. "
                "Reference: https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning"
            )
        
        if self.allow_delayed_in_sim and saxo_env == "SIM":
            logger.warning(
                "⚠️  ALLOW_DELAYED_DATA_IN_SIM is enabled. This is ONLY for SIM development "
                "(Saxo SIM does not offer live prices for many non-FX instruments). "
                "This MUST be disabled for LIVE trading."
            )
        
        logger.info(
            f"DataQualityChecker initialized: "
            f"extended_hours={allow_extended_hours}, "
            f"staleness_threshold={staleness_threshold_seconds}s, "
            f"require_open={require_market_open}, "
            f"allow_delayed_in_sim={self.allow_delayed_in_sim}"
        )
    
    def check_data_quality(
        self, 
        market_data: Dict[str, Dict],
        decision_time_utc: datetime,
    ) -> Dict[str, QualityResult]:
        """
        Check data quality for all instruments.
        
        Args:
            market_data: Dict keyed by instrument_id with market data
            decision_time_utc: Current decision time (UTC)
        
        Returns:
            Dict keyed by instrument_id with QualityResult
        """
        results = {}
        saxo_env = os.getenv("SAXO_ENV", "SIM").upper()
        
        for instrument_id, data in market_data.items():
            symbol = data.get("symbol", "UNKNOWN")
            asset_type = data.get("asset_type", "UNKNOWN")
            quote = data.get("quote", {})
            
            # Check for NoAccess (distinct from other failures)
            if not quote or quote.get("ErrorCode") == "NoAccess":
                logger.error(
                    f"🚫 {instrument_id} ({symbol}): NoAccess from Saxo API. "
                    f"{'SIM: Non-FX may require account linkage' if saxo_env == 'SIM' else 'LIVE: Enable market data in SaxoTraderGO'}. "
                    f"Ref: https://openapi.help.saxo/hc/en-us/articles/4405160773661"
                )
                results[instrument_id] = QualityResult(
                    is_fresh=False,
                    is_market_open=False,
                    is_delayed=False,
                    is_noaccess=True,
                    reason="DQ_NOACCESS_MARKETDATA",
                    metadata={"asset_type": asset_type, "saxo_env": saxo_env}
                )
                continue
            
            # Check Saxo MarketState enum
            market_state = quote.get("MarketState", "Unknown")
            is_market_open = market_state == "Open"
            
            # Extended hours check (PreMarket, PostMarket)
            is_extended_hours = market_state in {"PreMarket", "PostMarket"}
            
            # Auction states (OpeningAuction, ClosingAuction, IntraDayAuction)
            is_auction = market_state.endswith("Auction")
            
            # Check PriceType (OldIndicative = market closed / last known)
            price_type_bid = quote.get("PriceTypeBid", "Unknown")
            price_type_ask = quote.get("PriceTypeAsk", "Unknown")
            is_old_indicative = (
                price_type_bid == "OldIndicative" or 
                price_type_ask == "OldIndicative"
            )
            
            # Freshness: MUST use LastUpdated, not just DelayedByMinutes
            # Saxo docs: DelayedByMinutes=0 can still have old LastUpdated for illiquid instruments
            last_updated_str = quote.get("LastUpdated")
            is_fresh = True
            is_delayed = quote.get("DelayedByMinutes", 0) > 0
            
            if last_updated_str:
                try:
                    last_updated = datetime.fromisoformat(
                        last_updated_str.replace('Z', '+00:00')
                    )
                    age = decision_time_utc - last_updated
                    is_fresh = age <= self.staleness_threshold
                    
                    if not is_fresh:
                        logger.warning(
                            f"📊 {instrument_id} ({symbol}): Stale data - "
                            f"LastUpdated is {age.total_seconds():.0f}s old "
                            f"(threshold={self.staleness_threshold.total_seconds():.0f}s). "
                            f"DelayedByMinutes={quote.get('DelayedByMinutes', 0)}. "
                            f"Ref: https://openapi.help.saxo/hc/en-us/articles/6105016299677"
                        )
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"{instrument_id} ({symbol}): Invalid LastUpdated timestamp {last_updated_str}: {e}"
                    )
                    is_fresh = False
            else:
                logger.warning(
                    f"{instrument_id} ({symbol}): No LastUpdated timestamp in quote"
                )
                is_fresh = False
            
            # SIM delayed data policy
            delayed_is_acceptable = (not is_delayed) or self.allow_delayed_in_sim
            
            if is_delayed and self.allow_delayed_in_sim:
                logger.warning(
                    f"⚠️  {instrument_id} ({symbol}): Accepting delayed data in SIM "
                    f"(DelayedByMinutes={quote.get('DelayedByMinutes')}). "
                    f"This would be REJECTED in LIVE mode."
                )
            
            # Build reason flags
            reason_parts = []
            
            if not is_fresh:
                reason_parts.append("DQ_STALE_DATA")
            
            if is_delayed and not self.allow_delayed_in_sim:
                reason_parts.append("DQ_DELAYED_DATA")
                logger.debug(
                    f"{instrument_id} ({symbol}): Data delayed by "
                    f"{quote.get('DelayedByMinutes')} minutes"
                )
            
            if is_old_indicative:
                reason_parts.append("DQ_PRICE_TYPE_OLD_INDICATIVE")
                logger.debug(
                    f"{instrument_id} ({symbol}): PriceType is OldIndicative "
                    f"(Bid={price_type_bid}, Ask={price_type_ask}) - market likely closed"
                )
            
            if self.require_market_open and not is_market_open:
                reason_parts.append(f"DQ_MARKET_{market_state.upper()}")
                logger.debug(
                    f"{instrument_id} ({symbol}): Market state is {market_state}"
                )
            
            if is_extended_hours and not self.allow_extended_hours:
                reason_parts.append("DQ_EXTENDED_HOURS_DISABLED")
                logger.debug(
                    f"{instrument_id} ({symbol}): Extended hours ({market_state}), but not allowed"
                )
            
            if is_auction:
                reason_parts.append(f"DQ_AUCTION_{market_state.upper()}")
                logger.debug(
                    f"{instrument_id} ({symbol}): Auction state ({market_state}) - "
                    f"conditional/stop orders behave differently"
                )
            
            # CryptoFX weekend gaps (Saxo-specific: weekdays only)
            if asset_type == "CryptoFx" and decision_time_utc.weekday() >= 5:
                reason_parts.append("DQ_CRYPTOFX_WEEKEND")
                logger.info(
                    f"🪙 {instrument_id} ({symbol}): CryptoFX does not trade on weekends (Saxo-specific). "
                    f"Ref: https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi"
                )
            
            # Determine if data is acceptable
            reason = "_".join(reason_parts) if reason_parts else "OK"
            is_acceptable = (
                is_fresh and
                delayed_is_acceptable and
                not is_old_indicative and
                (not self.require_market_open or is_market_open) and
                (not is_extended_hours or self.allow_extended_hours) and
                not is_auction and
                not (asset_type == "CryptoFx" and decision_time_utc.weekday() >= 5)
            )
            
            results[instrument_id] = QualityResult(
                is_fresh=is_fresh,
                is_market_open=is_market_open,
                is_delayed=is_delayed,
                is_noaccess=False,
                reason=reason,
                metadata={
                    "market_state": market_state,
                    "delayed_by_minutes": quote.get("DelayedByMinutes", 0),
                    "price_type_bid": price_type_bid,
                    "price_type_ask": price_type_ask,
                    "asset_type": asset_type,
                    "last_updated": last_updated_str,
                }
            )
        
        return results
    
    def filter_market_data(
        self, 
        market_data: Dict[str, Dict],
        decision_time_utc: datetime,
    ) -> Dict[str, Dict]:
        """
        Filter market data to only include instruments with acceptable quality.
        
        Args:
            market_data: Dict keyed by instrument_id
            decision_time_utc: Current decision time (UTC)
        
        Returns:
            Filtered dict with only acceptable-quality data
        """
        quality_results = self.check_data_quality(market_data, decision_time_utc)
        
        filtered = {}
        for instrument_id, data in market_data.items():
            quality = quality_results[instrument_id]
            if quality.reason == "OK":
                filtered[instrument_id] = data
            else:
                logger.info(
                    f"🔒 Filtering out {instrument_id} due to: {quality.reason}"
                )
        
        return filtered


def wrap_strategy_with_quality_check(strategy, quality_checker: DataQualityChecker):
    """
    Wrap a strategy's generate_signals method with data quality checking.
    
    This ensures strategies only see high-quality data and prevents trading
    on stale/delayed data, closed markets, or NoAccess errors.
    
    Args:
        strategy: Strategy instance with generate_signals method
        quality_checker: DataQualityChecker instance
    
    Returns:
        Wrapped strategy with quality checking
    """
    original_generate_signals = strategy.generate_signals
    
    def wrapped_generate_signals(market_data: Dict[str, Dict], decision_time_utc: datetime):
        """Generate signals with quality checking."""
        from strategies.base import Signal, get_current_timestamp
        
        # Check quality for all instruments
        quality_results = quality_checker.check_data_quality(market_data, decision_time_utc)
        
        # Filter to only acceptable quality data
        acceptable_data = {
            instrument_id: data
            for instrument_id, data in market_data.items()
            if quality_results[instrument_id].reason == "OK"
        }
        
        # Generate signals for acceptable data
        signals = {}
        if acceptable_data:
            signals = original_generate_signals(acceptable_data, decision_time_utc)
        
        # Add HOLD signals for filtered-out instruments
        timestamp = get_current_timestamp()
        for instrument_id in market_data:
            if instrument_id not in signals:
                quality = quality_results[instrument_id]
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason=quality.reason,
                    timestamp=timestamp,
                    decision_time=timestamp,
                    policy_flags=quality.metadata,
                    metadata={"quality_check_failed": True}
                )
        
        return signals
    
    strategy.generate_signals = wrapped_generate_signals
    return strategy
```

### Configuration Extensions (`config/settings.py`)
```python
# Data Quality and Market State Policy (Saxo-aligned)
ALLOW_EXTENDED_HOURS = os.getenv("ALLOW_EXTENDED_HOURS", "false").lower() == "true"
DATA_STALENESS_THRESHOLD_SECONDS = int(os.getenv("DATA_STALENESS_THRESHOLD_SECONDS", "300"))
REQUIRE_MARKET_OPEN = os.getenv("REQUIRE_MARKET_OPEN", "true").lower() == "true"
ALLOW_DELAYED_DATA_IN_SIM = os.getenv("ALLOW_DELAYED_DATA_IN_SIM", "true").lower() == "true"
```

### `.env.example` Updates
```bash
# Data Quality and Market State Policy (Saxo-Aligned)
# =====================================================

# Allow trading during extended hours (PreMarket/PostMarket on Saxo)
# WARNING: Extended hours have:
#   - Lower liquidity (wider spreads)
#   - Higher volatility
#   - Different stop/conditional order behavior
# Reference: https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning
ALLOW_EXTENDED_HOURS=false

# Maximum age of LastUpdated before considered stale (seconds)
# IMPORTANT: Saxo's DelayedByMinutes=0 does NOT guarantee fresh data
#            for illiquid instruments. Always check LastUpdated timestamp.
# Reference: https://openapi.help.saxo/hc/en-us/articles/6105016299677
# Default: 300 seconds (5 minutes)
DATA_STALENESS_THRESHOLD_SECONDS=300

# Require market to be in "Open" state (Saxo MarketState enum) before trading
# Default: true (safe)
# Reference: https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate
REQUIRE_MARKET_OPEN=true

# SIM ENVIRONMENT ONLY: Allow delayed quotes for development
# Saxo SIM does not offer live pricing for many non-FX instruments.
# This setting allows delayed quotes in SIM to make progress during development,
# but MUST be disabled for LIVE trading.
# Reference: https://openapi.help.saxo/hc/en-us/articles/4416934146449
ALLOW_DELAYED_DATA_IN_SIM=true

# Important Saxo-Specific Notes:
# ===============================
# 1. CryptoFX trades WEEKDAYS ONLY (not 24/7 despite common assumption)
#    Reference: https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi
#
# 2. NoAccess errors require operator action:
#    - SIM: Link Live account to SIM for non-FX market data access
#    - LIVE: Enable market data in SaxoTraderGO
#    Reference: https://openapi.help.saxo/hc/en-us/articles/4405160773661
#
# 3. PriceType "OldIndicative" means market closed / last known price
#    Reference: https://www.developer.saxo/openapi/learn/pricing
```

## Testing Requirements

### Unit Tests (`tests/test_data_quality.py`)
```python
import pytest
from datetime import datetime, timezone, timedelta
from strategies.data_quality import (
    DataQualityChecker,
    QualityResult,
)

def test_fresh_data_open_market():
    """Test that fresh data with Open market passes."""
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
                "PriceTypeBid": "Tradable",
                "PriceTypeAsk": "Tradable",
            }
        }
    }
    
    results = checker.check_data_quality(market_data, now)
    assert results["Stock:211"].reason == "OK"
    assert results["Stock:211"].is_fresh is True
    assert results["Stock:211"].is_market_open is True

def test_stale_data_based_on_last_updated():
    """Test that stale LastUpdated is flagged even if DelayedByMinutes=0."""
    checker = DataQualityChecker(staleness_threshold_seconds=300)
    
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(minutes=10)
    
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "asset_type": "Stock",
            "quote": {
                "MarketState": "Open",
                "LastUpdated": stale_time.isoformat(),
                "DelayedByMinutes": 0,  # Zero delay but old timestamp!
            }
        }
    }
    
    results = checker.check_data_quality(market_data, now)
    assert "DQ_STALE_DATA" in results["Stock:211"].reason
    assert results["Stock:211"].is_fresh is False

def test_market_closed():
    """Test that Closed market state is flagged."""
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
    
    results = checker.check_data_quality(market_data, now)
    assert "DQ_MARKET_CLOSED" in results["Stock:211"].reason
    assert results["Stock:211"].is_market_open is False

def test_noaccess_distinct_from_stale():
    """Test that NoAccess is treated as distinct failure mode."""
    checker = DataQualityChecker()
    
    now = datetime.now(timezone.utc)
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "asset_type": "Stock",
            "quote": {
                "ErrorCode": "NoAccess"
            }
        }
    }
    
    results = checker.check_data_quality(market_data, now)
    assert results["Stock:211"].reason == "DQ_NOACCESS_MARKETDATA"
    assert results["Stock:211"].is_noaccess is True

def test_cryptofx_weekend():
    """Test that CryptoFX weekend is flagged."""
    checker = DataQualityChecker()
    
    # Saturday UTC
    saturday = datetime(2025, 1, 4, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
    
    market_data = {
        "CryptoFx:1581": {
            "instrument_id": "CryptoFx:1581",
            "symbol": "BTCUSD",
            "asset_type": "CryptoFx",
            "quote": {
                "MarketState": "Closed",
                "LastUpdated": saturday.isoformat(),
            }
        }
    }
    
    results = checker.check_data_quality(market_data, saturday)
    assert "DQ_CRYPTOFX_WEEKEND" in results["CryptoFx:1581"].reason

def test_old_indicative_price_type():
    """Test that OldIndicative PriceType is flagged."""
    checker = DataQualityChecker()
    
    now = datetime.now(timezone.utc)
    market_data = {
        "Stock:211": {
            "instrument_id": "Stock:211",
            "symbol": "AAPL",
            "asset_type": "Stock",
            "quote": {
                "MarketState": "Closed",
                "LastUpdated": now.isoformat(),
                "PriceTypeBid": "OldIndicative",
                "PriceTypeAsk": "OldIndicative",
            }
        }
    }
    
    results = checker.check_data_quality(market_data, now)
    assert "DQ_PRICE_TYPE_OLD_INDICATIVE" in results["Stock:211"].reason
```

## Dependencies
- Epic 003 (market data with MarketState and LastUpdated)
- Story 004-001 (Signal schema)
- Python 3.10+

## Estimated Effort
**5-6 hours** (including comprehensive tests, Saxo-specific handling, and documentation)

## Definition of Done
- [ ] `strategies/data_quality.py` created with Saxo-aligned implementation
- [ ] Configuration options added to `config/settings.py`
- [ ] `.env.example` updated with warnings and Saxo reference URLs
- [ ] Unit tests pass with >90% coverage
- [ ] All Saxo-specific behaviors documented with references
- [ ] NoAccess handling with actionable guidance
- [ ] CryptoFX weekday-only behavior tested
- [ ] Extended hours risks documented
- [ ] PriceType handling implemented
- [ ] Integration with strategy wrapper tested
- [ ] Code reviewed and approved

## Related Stories
- **Depends on:** Story 004-001 (Signal schema)
- **Depends on:** Epic 003 (market data format)
- **Next:** Story 004-006 (Strategy registry)

## References
1. [Saxo MarketState Enum](https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate) - Official enum values
2. [Saxo Chart Data Missing](https://openapi.help.saxo/hc/en-us/articles/6105016299677) - DelayedByMinutes vs LastUpdated
3. [Saxo NoAccess Error](https://openapi.help.saxo/hc/en-us/articles/4405160773661) - Why NoAccess occurs
4. [Saxo Enable Market Data](https://openapi.help.saxo/hc/en-us/articles/4418427366289) - How to enable market data
5. [Saxo Quote Schema](https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade/schema-quote) - Quote structure & PriceType
6. [Saxo Crypto FX](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi) - CryptoFX weekday-only
7. [Saxo Risk Warning](https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning) - Extended hours risks
8. [Saxo Pricing Learn](https://www.developer.saxo/openapi/learn/pricing) - PriceType semantics
9. [Saxo SIM Account Linkage](https://openapi.help.saxo/hc/en-us/articles/4416934146449) - SIM/Live account connection
