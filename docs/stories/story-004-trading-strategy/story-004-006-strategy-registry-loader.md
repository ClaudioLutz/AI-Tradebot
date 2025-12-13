# Story 004-006: Strategy Registry / Loader (Extensibility)

**Epic:** [Epic 004 - Trading Strategy System](../../epics/epic-004-trading-strategy-system.md)

## Story Description
Create a strategy registry system that avoids hard-coded "if strategy == ..." logic, making it easy to add new strategies without modifying core code.

## User Story
As a **developer**, I want a **strategy registry** so that **adding new strategies requires minimal boilerplate and no core code changes**.

## Goal
Build extensible strategy loading system with:
1. Strategy registry that maps names to classes
2. Factory function to instantiate strategies by name
3. Automatic discovery or explicit registration
4. Minimal boilerplate for new strategies

## Acceptance Criteria

### 1. Strategy Registry Module
- [ ] `strategies/registry.py` created with:
  - `STRATEGY_REGISTRY` dict mapping names to strategy classes
  - `register_strategy(name, strategy_class)` decorator/function
  - `get_strategy(name, params) -> Strategy` factory function
  - `list_available_strategies() -> List[str]`

### 2. Registration Methods
- [ ] Manual registration for built-in strategies
- [ ] Decorator-based registration for easy extension
- [ ] Clear error messages for unknown strategies

### 3. Integration with Config Loader
- [ ] `create_strategy_from_config()` uses registry
- [ ] Strategy name validation against registry
- [ ] Documentation of available strategies

### 4. Extensibility Pattern
- [ ] Adding new strategy requires:
  1. Create strategy file in `strategies/`
  2. Implement `BaseStrategy` interface
  3. Register in registry (one line)
  4. No modification to core orchestration code

## Technical Implementation

### Registry Module (`strategies/registry.py`)
```python
"""Strategy registry for extensible strategy loading."""

import logging
from typing import Dict, Type, Any, List
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

# Global registry: strategy_name -> strategy_class
STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {}


def register_strategy(name: str):
    """
    Decorator to register a strategy in the global registry.
    
    Usage:
        @register_strategy("my_strategy")
        class MyStrategy(BaseStrategy):
            ...
    """
    def decorator(strategy_class: Type[BaseStrategy]):
        if name in STRATEGY_REGISTRY:
            logger.warning(f"Overwriting existing strategy '{name}'")
        STRATEGY_REGISTRY[name] = strategy_class
        logger.info(f"Registered strategy: {name} -> {strategy_class.__name__}")
        return strategy_class
    return decorator


def get_strategy(name: str, params: Dict[str, Any] = None) -> BaseStrategy:
    """
    Factory function to create strategy instance by name.
    
    Args:
        name: Strategy name (must be in registry)
        params: Parameters to pass to strategy constructor
    
    Returns:
        Initialized strategy instance
    
    Raises:
        ValueError: If strategy name not found
    """
    if name not in STRATEGY_REGISTRY:
        available = list_available_strategies()
        raise ValueError(
            f"Unknown strategy '{name}'. Available: {available}"
        )
    
    strategy_class = STRATEGY_REGISTRY[name]
    params = params or {}
    
    logger.info(f"Creating strategy '{name}' with params: {params}")
    return strategy_class(**params)


def list_available_strategies() -> List[str]:
    """Return list of registered strategy names."""
    return list(STRATEGY_REGISTRY.keys())


# Register built-in strategies
def _register_builtin_strategies():
    """Register all built-in strategies."""
    try:
        from strategies.moving_average import MovingAverageCrossoverStrategy
        register_strategy("moving_average")(MovingAverageCrossoverStrategy)
    except ImportError:
        logger.warning("Could not import MovingAverageCrossoverStrategy")


# Auto-register on module import
_register_builtin_strategies()
```

### Updated Config Loader (`strategies/config.py`)
```python
def create_strategy_from_config(strategy_name: str = None):
    """
    Factory function to create strategy from configuration using registry.
    
    Args:
        strategy_name: Strategy name (defaults to STRATEGY_NAME from config)
    
    Returns:
        Initialized strategy instance
    """
    from strategies.registry import get_strategy, list_available_strategies
    
    if strategy_name is None:
        strategy_name = settings.STRATEGY_NAME
    
    # Load parameters
    params = load_strategy_params(strategy_name)
    
    # Validate parameters (strategy-specific)
    if strategy_name == "moving_average":
        validate_moving_average_params(params)
    
    # Create via registry
    try:
        return get_strategy(strategy_name, params)
    except ValueError as e:
        available = list_available_strategies()
        logger.error(f"Strategy creation failed: {e}")
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. "
            f"Available strategies: {available}"
        )
```

## Testing Requirements

### Unit Tests (`tests/test_strategy_registry.py`)
```python
import pytest
from strategies.registry import (
    register_strategy,
    get_strategy,
    list_available_strategies,
    STRATEGY_REGISTRY,
)
from strategies.base import BaseStrategy

def test_register_and_get_strategy():
    """Test strategy registration and retrieval."""
    @register_strategy("test_strategy")
    class TestStrategy(BaseStrategy):
        def __init__(self, param1=10):
            self.param1 = param1
        
        def generate_signals(self, market_data):
            return {}
    
    strategy = get_strategy("test_strategy", {"param1": 20})
    assert isinstance(strategy, TestStrategy)
    assert strategy.param1 == 20

def test_get_unknown_strategy():
    """Test error for unknown strategy."""
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_strategy("nonexistent_strategy")

def test_list_available_strategies():
    """Test listing registered strategies."""
    strategies = list_available_strategies()
    assert isinstance(strategies, list)
    assert "moving_average" in strategies  # Built-in
```

## Estimated Effort
**2-3 hours**

## Definition of Done
- [ ] `strategies/registry.py` created
- [ ] Registry integrates with config loader
- [ ] Unit tests pass
- [ ] Documentation for adding new strategies
- [ ] Example decorator usage provided

## References
- Design pattern: Factory Method + Registry
