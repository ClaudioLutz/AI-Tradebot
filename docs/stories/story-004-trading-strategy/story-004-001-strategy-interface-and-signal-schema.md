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
  - `generate_signals(market_data: dict) -> dict[instrument_id, Signal]` method signature
  - Clear docstrings explaining inputs/outputs

### 2. Signal Schema Defined
- [ ] `Signal` dataclass/TypedDict created with fields:
  - `action`: Literal["BUY", "SELL", "HOLD"]
  - `reason`: str (e.g., "INSUFFICIENT_BARS", "CROSSOVER_UP", "CROSSOVER_DOWN", "NO_CROSSOVER")
  - `confidence`: Optional[float] (0.0 to 1.0, for future use)
  - `timestamp`: str (ISO8601 format)
  - `metadata`: Optional[dict] (for strategy-specific info like MA values)

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
        action: Trading action to take
        reason: Human-readable explanation for the signal
        confidence: Optional confidence score (0.0 to 1.0)
        timestamp: ISO8601 timestamp of signal generation
        metadata: Optional strategy-specific data (e.g., indicator values)
    """
    action: Literal["BUY", "SELL", "HOLD"]
    reason: str
    timestamp: str  # ISO8601 format
    confidence: Optional[float] = None
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
from typing import Dict

class BaseStrategy(ABC):
    """
    Base class for all trading strategies.
    
    All strategies must implement generate_signals() method that:
    1. Accepts normalized market data dict keyed by instrument_id
    2. Returns signals dict keyed by instrument_id with Signal objects
    3. Uses only closed bars (no look-ahead bias)
    4. Generates signals with explicit timestamps
    5. Returns HOLD for instruments with insufficient data
    """
    
    @abstractmethod
    def generate_signals(self, market_data: Dict[str, dict]) -> Dict[str, Signal]:
        """
        Generate trading signals for all instruments in market_data.
        
        Args:
            market_data: Dict keyed by instrument_id, containing:
                {
                    "instrument_id": str,
                    "asset_type": str,
                    "uic": int,
                    "symbol": str,
                    "quote": {...},
                    "bars": [...]  # optional OHLC data with timestamps
                }
        
        Returns:
            Dict keyed by instrument_id with Signal objects
        
        Raises:
            ValueError: If market_data structure is invalid
        """
        pass

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
    """Generate ISO8601 timestamp for signal creation."""
    return datetime.now(timezone.utc).isoformat()
```

## Rationale

### Why Rich Signals vs Simple Actions?
1. **Auditability:** Reason field explains why BUY/SELL was chosen (crucial for debugging)
2. **Timestamp discipline:** Explicit timestamps prevent look-ahead bias in future backtesting
3. **Metadata capture:** Allows strategies to record indicator values for analysis
4. **Confidence scores:** Enables future portfolio optimization and signal weighting

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
    # Valid signal
    signal = Signal("BUY", "TEST", get_current_timestamp())
    assert signal.action == "BUY"
    
    # Invalid action
    with pytest.raises(ValueError):
        Signal("INVALID", "TEST", get_current_timestamp())
    
    # Invalid confidence
    with pytest.raises(ValueError):
        Signal("BUY", "TEST", get_current_timestamp(), confidence=1.5)
    
    # Invalid timestamp
    with pytest.raises(ValueError):
        Signal("BUY", "TEST", "not-a-timestamp")

def test_signals_to_actions():
    """Test action extraction from signals."""
    signals = {
        "Stock:211": Signal("BUY", "CROSSOVER_UP", "2025-01-15T10:00:00Z"),
        "FxSpot:21": Signal("HOLD", "NO_CROSSOVER", "2025-01-15T10:00:00Z"),
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
