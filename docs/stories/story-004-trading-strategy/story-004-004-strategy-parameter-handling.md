# Story 004-004: Strategy Parameter Handling (Config Integration)

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Enable configuration-based strategy parameter management so strategies can be tuned without code changes, with explicit parameter validation and logging to prevent backtest overfitting.

## User Story
As a **trader**, I want to **adjust strategy parameters via configuration** so that **I can experiment with different settings without modifying code**.

## Goal
Create a parameter management system that:
1. Loads strategy parameters from configuration
2. Validates parameters at initialization
3. Logs all parameter values for audit trail
4. Makes parameter tuning explicit and traceable
5. Prevents common parameter mistakes

## Acceptance Criteria

### 1. Configuration Support
- [ ] `config/settings.py` extended with strategy configuration:
  - `STRATEGY_NAME` (e.g., "moving_average")
  - `STRATEGY_PARAMS_JSON` (JSON string or dict)
- [ ] Alternative: `STRATEGY_SHORT_WINDOW`, `STRATEGY_LONG_WINDOW`, etc. as individual env vars
- [ ] `.env.example` updated with strategy parameter examples

### 2. Parameter Loader Function
- [ ] `strategies/config.py` created with:
  - `load_strategy_params(strategy_name: str) -> dict`
  - Reads from environment or config file
  - Returns dict of parameter name → value
  - Logs loaded parameters (creates audit trail)

### 3. Parameter Validation
- [ ] Strategy constructors validate all parameters:
  - Type checking (int, float, bool as appropriate)
  - Range checking (positive values, percentage bounds, etc.)
  - Relationship checks (e.g., short < long window)
  - Clear error messages for invalid parameters

### 4. Parameter Schema Documentation
- [ ] Each strategy documents its parameters in docstring:
  - Parameter name and type
  - Default value
  - Valid range/constraints
  - Example values
  - Impact on strategy behavior

### 5. Audit Trail (Bailey et al. Anti-Overfitting)
- [ ] All parameter loads logged at INFO level
- [ ] Parameter validation failures logged at ERROR level
- [ ] Strategy initialization logs include full parameter set
- [ ] **Add STRATEGY_CONFIG_ID**: hash of (sorted params + strategy name + code version) logged at INFO
- [ ] **Add optional experiment metadata** fields logged when parameter sweeps are run:
  - `EXPERIMENT_NAME`: Name of parameter sweep/optimization run
  - `CONFIGS_TRIED_COUNT`: Total number of configurations tested
  - `SELECTION_RATIONALE`: Why this configuration was chosen
- [ ] Prevents "silent parameter experimentation" (backtest overfitting risk)
- [ ] **Reference**: https://carmamaths.org/jon/backtest2.pdf - Must disclose how many configs were tried

### 6. Integration with Moving Average Strategy
- [ ] MovingAverageCrossoverStrategy can be instantiated from config
- [ ] Example configuration provided in `.env.example`
- [ ] Unit test verifies config loading works

## Technical Implementation Notes

### Config File Extensions (`config/settings.py`)
```python
"""Strategy configuration loading."""

import os
import json
from typing import Dict, Any, Optional

# Strategy selection
STRATEGY_NAME = os.getenv("STRATEGY_NAME", "moving_average")

# Strategy parameters (JSON format for flexibility)
STRATEGY_PARAMS_JSON = os.getenv("STRATEGY_PARAMS_JSON", None)

# Alternative: individual parameters (easier for beginners)
STRATEGY_SHORT_WINDOW = int(os.getenv("STRATEGY_SHORT_WINDOW", "5"))
STRATEGY_LONG_WINDOW = int(os.getenv("STRATEGY_LONG_WINDOW", "20"))
STRATEGY_THRESHOLD_BPS = os.getenv("STRATEGY_THRESHOLD_BPS", None)
if STRATEGY_THRESHOLD_BPS is not None:
    STRATEGY_THRESHOLD_BPS = int(STRATEGY_THRESHOLD_BPS)
```

### Parameter Loader (`strategies/config.py`)
```python
"""Strategy configuration management."""

import logging
import json
from typing import Dict, Any

from config import settings
from strategies.registry import get_strategy_spec

logger = logging.getLogger(__name__)


def load_strategy_params(strategy_name: str) -> Dict[str, Any]:
    """
    Load strategy parameters from configuration.
    
    This function creates an audit trail by logging all loaded parameters,
    which helps prevent backtest overfitting through undocumented parameter
    experimentation.
    
    Args:
        strategy_name: Name of strategy (e.g., "moving_average")
    
    Returns:
        Dict of parameter name → value
    
    Raises:
        ValueError: If parameters are invalid or missing
    
    Reference:
        Bailey et al. - The Probability of Backtest Overfitting
        "Record all parameter sets tested to avoid data snooping bias"
    """
    params = {}
    
    # Try JSON format first (more flexible)
    if settings.STRATEGY_PARAMS_JSON:
        try:
            params = json.loads(settings.STRATEGY_PARAMS_JSON)
            logger.info(
                f"Loaded strategy parameters from JSON: {strategy_name} = {params}"
            )
            return params
        except json.JSONDecodeError as e:
            logger.error(f"Invalid STRATEGY_PARAMS_JSON: {e}")
            raise ValueError(f"Invalid strategy parameters JSON: {e}")
    
    # Fall back to individual env vars (generic baseline for beginners)
    # NOTE: Keep this generic; strategy-specific validation/defaulting lives in the strategy.
    params = {
        "short_window": getattr(settings, "STRATEGY_SHORT_WINDOW", None),
        "long_window": getattr(settings, "STRATEGY_LONG_WINDOW", None),
        "threshold_bps": getattr(settings, "STRATEGY_THRESHOLD_BPS", None),
    }
    # Drop None keys
    params = {k: v for k, v in params.items() if v is not None}

    if params:
        logger.info(
            f"Loaded baseline strategy params from env vars: {strategy_name} = {params}"
        )
        return params

    logger.warning(
        f"No parameters configured for strategy '{strategy_name}', using defaults"
    )
    return {}


# NOTE: Strategy-specific validation should live with the strategy itself.
# Each strategy should expose:
#   - default_params() -> Dict[str, Any]
#   - validate_params(params: Dict[str, Any]) -> None
# so the config loader remains generic and extensible.


def create_strategy_from_config(strategy_name: str):
    """Factory function to create strategy from configuration.

    This function is intentionally generic: it loads user-specified params,
    merges them with strategy defaults, validates them via the strategy’s
    own validator, then instantiates via the registry.

    Args:
        strategy_name: Name of strategy to create

    Returns:
        Initialized strategy instance

    Raises:
        ValueError: If strategy name unknown or parameters invalid
    """
    user_params = load_strategy_params(strategy_name)

    spec = get_strategy_spec(strategy_name)

    params = {
        **spec.default_params(),
        **user_params,
    }

    spec.validate_params(params)

    logger.info(f"Final strategy params (validated): {strategy_name} = {params}")
    return spec.create(params)
```

### `.env.example` Updates
```bash
# Strategy Configuration
# =====================

# Strategy selection
STRATEGY_NAME=moving_average

# Option 1: JSON format (flexible, can specify any parameters)
# STRATEGY_PARAMS_JSON={"short_window": 5, "long_window": 20, "threshold_bps": 50}

# Option 2: Individual parameters (easier for beginners)
STRATEGY_SHORT_WINDOW=5
STRATEGY_LONG_WINDOW=20
# STRATEGY_THRESHOLD_BPS=50  # Optional: Minimum MA separation in basis points (e.g., 50 = 0.5%)

# Parameter Guidelines:
# - short_window: Typical range 3-10 (shorter = more sensitive)
# - long_window: Typical range 20-50 (longer = smoother)
# - Ensure short_window < long_window
# - threshold_bps: Optional noise filter (0-100 typical)
#
# WARNING: Excessive parameter tuning can lead to backtest overfitting.
# Document rationale for parameter changes. Consider out-of-sample validation.
```

## Rationale

### Why Explicit Parameter Logging?
Bailey et al. warn about "backtest overfitting" - trying many parameter sets and selecting the best can produce misleadingly good in-sample results that fail out-of-sample.

By logging all parameter loads, we create an audit trail that:
1. Makes parameter experimentation explicit (not silent)
2. Enables tracking which parameters were tested
3. Supports future out-of-sample validation

**Reference:** Bailey et al. - The Probability of Backtest Overfitting

### Why Both JSON and Individual Env Vars?
- **JSON format:** Flexible, scales to complex parameters, single variable
- **Individual vars:** Easier for beginners, more discoverable, type-safe

Supporting both gives flexibility for different use cases.

### Why Parameter Validation?
Common mistakes like `short_window >= long_window` cause runtime errors or incorrect signals. Validating at initialization catches these early with clear error messages.

## Testing Requirements

### Unit Tests (`tests/test_strategy_config.py`)
```python
import pytest
import os
from unittest.mock import patch
from strategies.config import (
    load_strategy_params,
    validate_moving_average_params,
    create_strategy_from_config,
)
from strategies.moving_average import MovingAverageCrossoverStrategy

def test_load_params_from_json():
    """Test parameter loading from JSON string."""
    with patch.dict(os.environ, {
        "STRATEGY_PARAMS_JSON": '{"short_window": 10, "long_window": 30}'
    }):
        params = load_strategy_params("moving_average")
        assert params["short_window"] == 10
        assert params["long_window"] == 30

def test_load_params_from_individual_vars():
    """Test parameter loading from individual env vars."""
    with patch.dict(os.environ, {
        "STRATEGY_PARAMS_JSON": "",  # Ensure JSON is not used
        "STRATEGY_SHORT_WINDOW": "7",
        "STRATEGY_LONG_WINDOW": "25",
    }, clear=True):
        params = load_strategy_params("moving_average")
        assert params["short_window"] == 7
        assert params["long_window"] == 25

def test_validate_params_valid():
    """Test validation passes for valid parameters."""
    params = {"short_window": 5, "long_window": 20}
    validate_moving_average_params(params)  # Should not raise

def test_validate_params_invalid_relationship():
    """Test validation fails when short >= long."""
    params = {"short_window": 20, "long_window": 10}
    with pytest.raises(ValueError, match="short_window.*must be <"):
        validate_moving_average_params(params)

def test_validate_params_negative_window():
    """Test validation fails for negative window."""
    params = {"short_window": -5, "long_window": 20}
    with pytest.raises(ValueError, match="positive integer"):
        validate_moving_average_params(params)

def test_create_strategy_from_config():
    """Test factory function creates strategy with config parameters."""
    with patch.dict(os.environ, {
        "STRATEGY_NAME": "moving_average",
        "STRATEGY_SHORT_WINDOW": "8",
        "STRATEGY_LONG_WINDOW": "21",
    }):
        strategy = create_strategy_from_config("moving_average")
        assert isinstance(strategy, MovingAverageCrossoverStrategy)
        assert strategy.short_window == 8
        assert strategy.long_window == 21

def test_create_strategy_unknown():
    """Test factory fails for unknown strategy name."""
    with pytest.raises(ValueError, match="Unknown strategy"):
        create_strategy_from_config("nonexistent_strategy")
```

## Dependencies
- Story 004-003 (MovingAverageCrossoverStrategy exists)
- Epic 002 (config module established)
- Python 3.10+
- `json` (standard library)

## Estimated Effort
**3-4 hours** (including tests and documentation)

## Definition of Done
- [ ] `strategies/config.py` created with loader and validator
- [ ] `config/settings.py` extended with strategy parameters
- [ ] `.env.example` updated with examples and warnings
- [ ] Unit tests pass with >90% coverage
- [ ] Parameter loading logged at INFO level
- [ ] Validation errors have clear messages
- [ ] Code reviewed and approved
- [ ] No pylint/mypy warnings

## Related Stories
- **Depends on:** Story 004-003 (MovingAverage strategy)
- **Related:** Epic 002 (configuration module)
- **Next:** Story 004-005 (Data quality gating)

## References
1. [Bailey et al. - The Probability of Backtest Overfitting](https://carmamaths.org/jon/backtest2.pdf) - Importance of recording all parameter sets tested
2. Epic 002 - Configuration Module (parameter loading patterns)
