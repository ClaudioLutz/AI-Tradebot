# Story 004-001: Define Strategy Interface and Signal Schema

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Create a standardized strategy interface and rich signal schema that all strategies must implement. This prevents ad-hoc implementations and establishes the foundation for auditable, timestamp-aware signal generation.

## User Story
As a **developer**, I want a **consistent strategy interface** so that **all strategies can be tested, audited, and integrated uniformly**.

## Goal
Standardize inputs/outputs and eliminate ad-hoc strategy implementations by defining:
1. Clear interface contract for all strategies
2. Rich signal schema with action, reason, confidence, and timestamp
3. Helper function to extract actions for execution
4. Default behavior for missing/insufficient data

## Acceptance Criteria

### 1. Strategy Interface Exists
- [ ] `strategies/base.py` created with:
  - `BaseStrategy` abstract class or protocol
  - `generate_signals(market_data: dict, decision_time_utc: datetime) -> dict[instrument_id, Signal]` method signature
  - Clear docstrings explaining inputs/outputs
  - Contract: strategy may only use bars strictly **< decision_time_utc** (UTC)

### 2. Signal Schema Defined
- [ ] `Signal` dataclass/TypedDict created with fields:
  - `action`: Literal["BUY", "SELL", "HOLD"]
  - `reason`: str (e.g., "INSUFFICIENT_BARS", "CROSSOVER_UP", "CROSSOVER_DOWN", "NO_CROSSOVER")
  - `timestamp`: str (ISO8601 format - signal generation timestamp)
  - `decision_time`: str (bar-close time or quote last-updated time - actual data timestamp)
  - `valid_until`: Optional[str] (ISO8601) (optional future: invalidate stale signals)
  - `confidence`: Optional[float] (0.0 to 1.0, for future use)
  - `price_ref`: Optional[float] (reference price: close, mid, bid/ask)
  - `price_type`: Optional[str] (e.g., "close", "mid", "bid", "ask")
  - `data_time_range`: Optional[dict] (e.g., {"first_bar": "...", "last_bar": "..."})
  - `policy_flags`: Optional[dict] (e.g., {"used_delayed_data": false, "market_state": "Open"})
  - `metadata`: Optional[dict] (for strategy-specific info like MA values)

### 2a. Action Semantics Defined
- [ ] Document action semantics explicitly:
  - `BUY`: Enter long position (or add to existing long)
  - `SELL`: Exit long position OR enter short (define in execution module)
  - `HOLD`: No action - maintain current position
- [ ] Note for Epic 005: Execution module must define whether SELL can initiate short positions

### 3. Helper Function Created
- [ ] `signals_to_actions(signals: dict) -> dict[instrument_id, str]` function:
  - Extracts just the action field from Signal objects
  - Returns simple dict compatible with execution module
  - Preserves instrument_id keys

### 4. Default Behavior Implemented
- [ ] Missing data handling:
  - If `bars` is None or empty → return HOLD with reason "INSUFFICIENT_DATA"
  - If `len(bars) < required_window` → return HOLD with reason "INSUFFICIENT_BARS"
  - Generate current timestamp in ISO8601 format

### 5. Type Hints and Validation
- [ ] All functions have complete type hints
- [ ] Input validation for market_data structure
- [ ] Signal validation (action must be valid, timestamp must be ISO8601)

### 6. Documentation
- [ ] Interface docstrings explain contract clearly
- [ ] Example usage provided in module docstring
- [ ] Rationale for rich signal schema documented (auditability, no look-ahead bias)

## Technical Implementation Notes

### File Structure
```
strategies/
├── __init__.py
├── base.py              # New: BaseStrategy interface + Signal schema
└── simple_strategy.py   # Existing placeholder
```

### Signal Schema Design
```python
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime, timezone

@dataclass
class Signal:
    """
    Rich signal object that captures trading decision and context.
    
    Attributes:
        action: Trading action to take (BUY=enter/add long, SELL=exit long or short, HOLD=no action)
        reason: Human-readable explanation for the signal
        timestamp: ISO8601 timestamp when signal was generated (wall clock)
        decision_time: ISO8601 timestamp of the data used (bar close or quote last-updated)
        confidence: Optional confidence score (0.0 to 1.0)
        price_ref: Reference price used for decision (e.g., last close price)
        price_type: Type of price used ("close", "mid", "bid", "ask")
        data_time_range: Time range of data used (first/last bar timestamps)
        policy_flags: Data quality flags (delayed_data, market_state, etc.)
        metadata: Optional strategy-specific data (e.g., indicator values)
    
    Notes on action semantics:
        - BUY: Enter long position or add to existing long position
        - SELL: Exit long position (or enter short if execution module supports)
        - HOLD: No action, maintain current position
        - Execution module (Epic 005) defines whether SELL can initiate shorts
    """
    action: Literal["BUY", "SELL", "HOLD"]
    reason: str
    timestamp: str  # ISO8601 format - signal generation time
    decision_time: str  # ISO8601 format - data timestamp (bar close or quote time)
    valid_until: Optional[str] = None
    confidence: Optional[float] = None
    price_ref: Optional[float] = None
    price_type: Optional[str] = None
    data_time_range: Optional[dict] = None
    policy_flags: Optional[dict] = None
    metadata: Optional[dict] = None
    
    def __post_init__(self):
        """Validate signal fields."""
        if self.action not in ["BUY", "SELL", "HOLD"]:
            raise ValueError(f"Invalid action: {self.action}")
        
        if self.confidence is not None:
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")
        
        # Validate timestamp format (basic check)
        try:
            datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid ISO8601 timestamp: {self.timestamp}")
```

### Interface Design
```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict

class BaseStrategy(ABC):
    """Base class for all trading strategies.

    All strategies must implement generate_signals() method that:
    1. Accepts normalized market data dict keyed by instrument_id
    2. Accepts explicit decision_time_utc (UTC) to prevent look-ahead bias
    3. Returns signals dict keyed by instrument_id with Signal objects
    4. Uses only bars whose timestamps are strictly < decision_time_utc
    5. Returns HOLD for instruments with insufficient data
    """

    @abstractmethod
    def generate_signals(
        self,
        market_data: Dict[str, dict],
        decision_time_utc: datetime,
    ) -> Dict[str, Signal]:
        """Generate trading signals for all instruments in market_data.

        Args:
            market_data: Dict keyed by instrument_id, containing normalized quote/bars.
            decision_time_utc: The decision timestamp in UTC. Strategy must only use
                bars strictly < decision_time_utc.

        Returns:
            Dict keyed by instrument_id with Signal objects.

        Raises:
            ValueError: If market_data structure is invalid
        """
        raise NotImplementedError
```

```python

def signals_to_actions(signals: Dict[str, Signal]) -> Dict[str, str]:
    """
    Extract actions from Signal objects for execution module.
    
    Args:
        signals: Dict of instrument_id -> Signal
    
    Returns:
        Dict of instrument_id -> action string ("BUY"|"SELL"|"HOLD")
    
    Example:
        >>> signals = {"Stock:211": Signal("BUY", "CROSSOVER_UP", "2025-01-15T10:30:00Z")}
        >>> signals_to_actions(signals)
        {"Stock:211": "BUY"}
    """
    return {instrument_id: signal.action for instrument_id, signal in signals.items()}
```

### Helper for Creating Timestamps
```python
def get_current_timestamp() -> str:
    """Generate ISO8601 timestamp for signal creation (wall clock)."""
    return datetime.now(timezone.utc).isoformat()

def get_bar_timestamp(bar: dict) -> str:
    """
    Extract timestamp from bar data.
    
    Args:
        bar: Bar dict with 'timestamp' field
    
    Returns:
        ISO8601 timestamp string
    
    Raises:
        KeyError: If bar missing 'timestamp' field
    """
    return bar["timestamp"]
```

## Rationale

### Why Rich Signals vs Simple Actions?
1. **Auditability:** Reason field explains why BUY/SELL was chosen (crucial for debugging)
2. **Timestamp discipline:** Explicit timestamps (both generation and decision time) prevent look-ahead bias in future backtesting
3. **Price reference tracking:** Knowing which price was used helps execution module reason about slippage
4. **Data provenance:** `data_time_range` and `policy_flags` create audit trail of what data was used
5. **Metadata capture:** Allows strategies to record indicator values for analysis
6. **Confidence scores:** Enables future portfolio optimization and signal weighting

### Why Separate `timestamp` and `decision_time`?
- `timestamp`: When the signal was generated (wall clock) - for system logging
- `decision_time`: The timestamp of the actual data used (bar close or quote time) - for backtesting validation
- This separation prevents "time leakage" where wall clock time contaminates data timestamps
- In backtests, `decision_time` should be the bar close; `timestamp` can be simulated event time

### Why Separate signals_to_actions()?
- Keeps execution module simple (just needs actions)
- Maintains backward compatibility with existing interfaces
- Signal richness is opt-in, not forced on consumers

### Prevention of Look-Ahead Bias
By requiring explicit timestamps on all signals, we establish a clear "decision point" that can be validated in backtests. Strategies cannot "retroactively" claim they made a decision before data was available.

**Reference:** Evidence-Based Technical Analysis (Aronson), Chapter 1 - Look-Ahead Bias

## Testing Requirements

### Unit Tests (`tests/test_strategy_interface.py`)
```python
def test_signal_validation():
    """Test Signal dataclass validation."""
    # Valid signal with required fields
    ts = get_current_timestamp()
    signal = Signal("BUY", "TEST", ts, ts)
    assert signal.action == "BUY"
    
    # Valid signal with all fields
    signal_full = Signal(
        action="BUY",
        reason="CROSSOVER_UP",
        timestamp=ts,
        decision_time=ts,
        confidence=0.8,
        price_ref=100.50,
        price_type="close",
        data_time_range={"first_bar": ts, "last_bar": ts},
        policy_flags={"market_state": "Open", "used_delayed_data": False},
        metadata={"short_ma": 101.0, "long_ma": 99.0}
    )
    assert signal_full.price_ref == 100.50
    
    # Invalid action
    with pytest.raises(ValueError):
        Signal("INVALID", "TEST", ts, ts)
    
    # Invalid confidence
    with pytest.raises(ValueError):
        Signal("BUY", "TEST", ts, ts, confidence=1.5)
    
    # Invalid timestamp
    with pytest.raises(ValueError):
        Signal("BUY", "TEST", "not-a-timestamp", ts)

def test_signals_to_actions():
    """Test action extraction from signals."""
    ts = "2025-01-15T10:00:00Z"
    signals = {
        "Stock:211": Signal("BUY", "CROSSOVER_UP", ts, ts),
        "FxSpot:21": Signal("HOLD", "NO_CROSSOVER", ts, ts),
    }
    actions = signals_to_actions(signals)
    
    assert actions == {"Stock:211": "BUY", "FxSpot:21": "HOLD"}
    assert isinstance(actions["Stock:211"], str)

def test_base_strategy_is_abstract():
    """Ensure BaseStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseStrategy()
```

## Dependencies
- Python 3.10+ (for better type hints)
- `dataclasses` (standard library)
- `typing` (standard library)
- `datetime` (standard library)

## Estimated Effort
**2-3 hours** (including tests and documentation)

## Definition of Done
- [ ] `strategies/base.py` created with BaseStrategy and Signal
- [ ] `signals_to_actions()` helper implemented
- [ ] All type hints complete
- [ ] Unit tests pass with >90% coverage
- [ ] Documentation includes examples
- [ ] Code reviewed and approved
- [ ] No pylint/mypy warnings

## Related Stories
- **Next:** Story 004-002 (Indicator utilities use this interface)
- **Next:** Story 004-003 (Moving Average strategy implements this interface)
- **Depends on:** Epic 003 (market data format established)

## References
1. [Evidence-Based Technical Analysis](https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf) - Look-ahead bias prevention
2. [Epic 003: Market Data Retrieval](../../epics/epic-003-market-data-retrieval.md) - Input data contract
