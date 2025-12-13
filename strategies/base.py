"""
Base strategy interface and signal schema for trading strategies.

This module defines the contract that all trading strategies must implement,
along with the rich signal schema for auditable, timestamp-aware signal generation.

Key Principles:
1. Strategies are pure functions over normalized market data
2. Strategies accept explicit decision_time_utc to prevent look-ahead bias
3. Strategies return rich Signal objects (not just action strings)
4. Every signal must be explainable via reason + metadata
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Literal, Optional

logger = logging.getLogger(__name__)


# Reason Code Registry - Standard prefixes for consistency
REASON_CODE_REGISTRY = {
    # Data Quality (DQ_*) - Data quality gating outcomes
    "DQ_NOACCESS_MARKETDATA": "Saxo API returned NoAccess error - market data unavailable",
    "DQ_STALE_DATA": "Data timestamp exceeds staleness threshold",
    "DQ_DELAYED_DATA": "Data is delayed (DelayedByMinutes > 0) and not allowed in current mode",
    "DQ_MARKET_CLOSED": "Market state is Closed",
    "DQ_MARKET_PREMARKET": "Market state is PreMarket (extended hours disabled)",
    "DQ_MARKET_POSTMARKET": "Market state is PostMarket (extended hours disabled)",
    "DQ_EXTENDED_HOURS_DISABLED": "Extended hours trading disabled by policy",
    "DQ_PRICE_TYPE_OLD_INDICATIVE": "PriceType is OldIndicative (market closed, last known price)",
    "DQ_CRYPTOFX_WEEKEND": "CryptoFX does not trade on weekends (Saxo-specific)",
    "DQ_AUCTION": "Market in auction state (conditional/stop orders behave differently)",
    
    # Strategy Logic (SIG_*) - Strategy decision reasons
    "SIG_INSUFFICIENT_BARS": "Not enough bars for strategy calculation",
    "SIG_INSUFFICIENT_CLOSED_BARS": "Not enough closed bars as of decision time (illiquid instrument)",
    "SIG_CROSSOVER_UP": "Short MA crossed above long MA (golden cross)",
    "SIG_CROSSOVER_DOWN": "Short MA crossed below long MA (death cross)",
    "SIG_NO_CROSSOVER": "No MA crossover detected",
    "SIG_COOLDOWN_ACTIVE": "Signal suppressed due to cooldown period",
    "SIG_INSUFFICIENT_DATA": "Missing or incomplete data",
}


@dataclass
class Signal:
    """
    Rich signal object that captures trading decision and context.
    
    This schema creates a complete audit trail for every trading decision,
    preventing look-ahead bias and enabling reproducible backtesting.
    
    Attributes:
        action: Trading action to take (BUY/SELL/HOLD)
        reason: Structured reason code (use DQ_* for data quality, SIG_* for strategy logic)
        timestamp: ISO8601 timestamp when signal was generated (wall clock)
        decision_time: ISO8601 timestamp of the data used (bar close or quote time, must be ≤ timestamp)
        strategy_version: Version/hash of strategy for reproducibility
        schema_version: Signal schema version (default "1.0")
        valid_until: Optional expiration time for signal
        confidence: Optional confidence score (0.0 to 1.0)
        price_ref: Reference price used for decision (e.g., last close price)
        price_type: Type of price used ("close", "mid", "bid", "ask")
        data_time_range: Time range of data used (first/last bar timestamps)
        decision_context: Market state + freshness summary for audit trail
        policy_flags: Data quality flags (market_state, delayed_by_minutes, etc.)
        metadata: Optional strategy-specific data (e.g., indicator values)
    
    Action Semantics:
        - BUY: Enter long position or add to existing long position
        - SELL: Exit long position (or enter short if execution module supports)
        - HOLD: No action, maintain current position
        - Execution module (Epic 005) defines whether SELL can initiate shorts
    
    Explainability Contract:
        Every signal must be explainable: reason + metadata provide complete context.
        Required log fields: strategy_id, strategy_version, instrument_id, decision_time_utc,
        market_state, freshness.age_seconds, data_quality flags, reason_code
    
    Time Discipline:
        - timestamp: Wall clock time when signal was generated (for system logging)
        - decision_time: Timestamp of actual data used (for backtesting validation)
        - decision_time must be ≤ timestamp (no time leakage)
        - In backtests: decision_time = bar close time, timestamp = simulated event time
        - In live mode: decision_time = last bar/quote time, timestamp = wall clock
    """
    action: Literal["BUY", "SELL", "HOLD"]
    reason: str
    timestamp: str  # ISO8601 format - signal generation time (wall clock)
    decision_time: str  # ISO8601 format - data timestamp (bar close or quote time)
    strategy_version: str = "unknown"
    schema_version: str = "1.0"
    valid_until: Optional[str] = None
    confidence: Optional[float] = None
    price_ref: Optional[float] = None
    price_type: Optional[str] = None
    data_time_range: Optional[Dict] = None
    decision_context: Optional[Dict] = None
    policy_flags: Optional[Dict] = None
    metadata: Optional[Dict] = None
    
    def __post_init__(self):
        """Validate signal fields to prevent silent schema drift."""
        if self.action not in ["BUY", "SELL", "HOLD"]:
            raise ValueError(f"Invalid action: {self.action}. Must be BUY, SELL, or HOLD")
        
        if self.confidence is not None:
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")
        
        # Validate timestamp format (basic check)
        try:
            datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
            datetime.fromisoformat(self.decision_time.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid ISO8601 timestamp: {e}")
        
        # Ensure decision_time <= timestamp (no time leakage)
        dt_decision = datetime.fromisoformat(self.decision_time.replace('Z', '+00:00'))
        dt_signal = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        if dt_decision > dt_signal:
            raise ValueError(
                f"decision_time ({self.decision_time}) cannot be after timestamp ({self.timestamp}). "
                f"This would indicate time leakage (using future information)."
            )
    
    def to_dict(self) -> Dict:
        """Convert Signal to dict for JSON serialization with explicit rules."""
        return {
            "action": self.action,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "decision_time": self.decision_time,
            "strategy_version": self.strategy_version,
            "schema_version": self.schema_version,
            "valid_until": self.valid_until,
            "confidence": self.confidence,
            "price_ref": self.price_ref,
            "price_type": self.price_type,
            "data_time_range": self.data_time_range,
            "decision_context": self.decision_context,
            "policy_flags": self.policy_flags,
            "metadata": self.metadata,
        }


class BaseStrategy(ABC):
    """
    Base class for all trading strategies.

    All strategies must implement generate_signals() method that:
    1. Accepts normalized market data dict keyed by instrument_id
    2. Accepts explicit decision_time_utc (UTC) to prevent look-ahead bias
    3. Returns signals dict keyed by instrument_id with Signal objects
    4. Uses only bars whose timestamps are strictly < decision_time_utc
    5. Returns HOLD for instruments with insufficient data
    
    Contract (Idempotency):
        Same inputs ⇒ same outputs (same market_data + decision_time_utc → same signals).
        Important for retries and testing.
    
    Contract (Time Semantics):
        - decision_time_utc is the "as-of" timestamp
        - Bars must have timestamps strictly < decision_time_utc
        - No look-ahead bias: cannot use future information
    
    Contract (Explainability):
        - Every signal must have a clear reason code
        - Reason + metadata must fully explain the decision
    """

    @abstractmethod
    def generate_signals(
        self,
        market_data: Dict[str, Dict],
        decision_time_utc: datetime,
    ) -> Dict[str, Signal]:
        """
        Generate trading signals for all instruments in market_data.

        Args:
            market_data: Dict keyed by instrument_id, containing normalized quote/bars.
                Format from Epic 003 market data module:
                {
                    "Stock:211": {
                        "instrument_id": "Stock:211",
                        "asset_type": "Stock",
                        "uic": 211,
                        "symbol": "AAPL",
                        "quote": {...},
                        "bars": [...]
                    },
                    ...
                }
            decision_time_utc: The decision timestamp in UTC. Strategy must only use
                bars strictly < decision_time_utc. This prevents look-ahead bias.

        Returns:
            Dict keyed by instrument_id with Signal objects.
            Must return a signal for EVERY instrument in market_data (even if HOLD).

        Raises:
            ValueError: If market_data structure is invalid
        
        Example:
            >>> from datetime import datetime, timezone
            >>> decision_time = datetime.now(timezone.utc)
            >>> signals = strategy.generate_signals(market_data, decision_time)
            >>> for inst_id, signal in signals.items():
            ...     print(f"{inst_id}: {signal.action} - {signal.reason}")
        """
        raise NotImplementedError("Strategies must implement generate_signals()")


def signals_to_actions(signals: Dict[str, Signal]) -> Dict[str, str]:
    """
    Extract actions from Signal objects for execution module.
    
    This helper provides backward compatibility with execution modules that
    only need action strings, not the full Signal schema.
    
    Args:
        signals: Dict of instrument_id -> Signal
    
    Returns:
        Dict of instrument_id -> action string ("BUY"|"SELL"|"HOLD")
    
    Example:
        >>> signals = {
        ...     "Stock:211": Signal("BUY", "CROSSOVER_UP", "2025-01-15T10:30:00Z", "2025-01-15T10:30:00Z"),
        ...     "FxSpot:21": Signal("HOLD", "NO_CROSSOVER", "2025-01-15T10:30:00Z", "2025-01-15T10:30:00Z")
        ... }
        >>> signals_to_actions(signals)
        {'Stock:211': 'BUY', 'FxSpot:21': 'HOLD'}
    """
    return {instrument_id: signal.action for instrument_id, signal in signals.items()}


def get_current_timestamp(timestamp_provider=None) -> str:
    """
    Generate ISO8601 timestamp for signal creation (wall clock).
    
    Args:
        timestamp_provider: Optional callable that returns datetime. If None, uses datetime.now(timezone.utc).
                           For testing/backtesting, inject a fixed time provider for true idempotency.
    
    Returns:
        Current UTC time in ISO8601 format with Z suffix
    
    Example:
        >>> timestamp = get_current_timestamp()
        >>> print(timestamp)
        '2025-01-15T10:30:45.123456Z'
        
        >>> # For deterministic testing:
        >>> from datetime import datetime, timezone
        >>> fixed_time = datetime(2025, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        >>> timestamp = get_current_timestamp(lambda: fixed_time)
    """
    if timestamp_provider is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = timestamp_provider()
    return dt.isoformat().replace('+00:00', 'Z')


def validate_decision_time_utc(decision_time_utc: datetime) -> None:
    """
    Validate that decision_time_utc is timezone-aware and in UTC.
    
    This prevents accidental use of naive datetimes which can cause subtle
    time-related bugs and look-ahead bias.
    
    Args:
        decision_time_utc: The decision timestamp to validate
    
    Raises:
        ValueError: If decision_time_utc is not timezone-aware or not UTC
    
    Example:
        >>> from datetime import datetime, timezone
        >>> decision_time = datetime.now(timezone.utc)
        >>> validate_decision_time_utc(decision_time)  # OK
        
        >>> naive_time = datetime.now()
        >>> validate_decision_time_utc(naive_time)  # Raises ValueError
    """
    if decision_time_utc.tzinfo is None:
        raise ValueError(
            f"decision_time_utc must be timezone-aware (got naive datetime: {decision_time_utc}). "
            f"Use datetime.now(timezone.utc) for UTC time."
        )
    
    if decision_time_utc.tzinfo != timezone.utc:
        raise ValueError(
            f"decision_time_utc must be in UTC timezone (got tzinfo={decision_time_utc.tzinfo}). "
            f"Convert to UTC before calling strategy.generate_signals()."
        )


def get_bar_timestamp(bar: Dict) -> str:
    """
    Extract timestamp from bar data.
    
    Args:
        bar: Bar dict with 'timestamp' field (from Epic 003 market data)
    
    Returns:
        ISO8601 timestamp string
    
    Raises:
        KeyError: If bar missing 'timestamp' field
    
    Example:
        >>> bar = {"close": 100.0, "timestamp": "2025-01-15T10:30:00Z"}
        >>> get_bar_timestamp(bar)
        '2025-01-15T10:30:00Z'
    """
    if "timestamp" not in bar:
        raise KeyError("Bar missing required 'timestamp' field")
    return bar["timestamp"]
