"""
Strategy registry for extensible strategy loading.

Provides a central registry for all available strategies, enabling:
1. Dynamic strategy instantiation by name
2. Easy addition of new strategies
3. Clear listing of available strategies
4. Minimal boilerplate for strategy developers
"""

import logging
from typing import Dict, Type, List, Any

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
    
    Args:
        name: Strategy identifier (e.g., "moving_average")
    
    Returns:
        Decorator function that registers the strategy class
    """
    def decorator(strategy_class: Type[BaseStrategy]):
        if name in STRATEGY_REGISTRY:
            logger.warning(f"Overwriting existing strategy '{name}'")
        STRATEGY_REGISTRY[name] = strategy_class
        logger.debug(f"Registered strategy: {name} -> {strategy_class.__name__}")
        return strategy_class
    return decorator


def get_strategy(name: str, params: Dict[str, Any] | None = None) -> BaseStrategy:
    """
    Factory function to create strategy instance by name.
    
    Args:
        name: Strategy name (must be in registry)
        params: Parameters to pass to strategy constructor (default: empty dict)
    
    Returns:
        Initialized strategy instance
    
    Raises:
        ValueError: If strategy name not found
    
    Example:
        >>> strategy = get_strategy("moving_average", {"short_window": 5, "long_window": 20})
        >>> signals = strategy.generate_signals(market_data, decision_time)
    """
    if name not in STRATEGY_REGISTRY:
        available = list_available_strategies()
        raise ValueError(
            f"Unknown strategy '{name}'. Available strategies: {available}"
        )
    
    strategy_class = STRATEGY_REGISTRY[name]
    strategy_params = params if params is not None else {}
    
    logger.info(f"Creating strategy '{name}' with params: {strategy_params}")
    return strategy_class(**strategy_params)


def list_available_strategies() -> List[str]:
    """
    Return list of registered strategy names (stable sort order).
    
    Returns:
        Sorted list of strategy names
    
    Example:
        >>> strategies = list_available_strategies()
        >>> print(strategies)
        ['moving_average']
    """
    return sorted(STRATEGY_REGISTRY.keys())


# Auto-register built-in strategies
def _register_builtin_strategies():
    """Register all built-in strategies on module import."""
    try:
        from strategies.moving_average import MovingAverageCrossoverStrategy
        register_strategy("moving_average")(MovingAverageCrossoverStrategy)
        logger.info("Registered built-in strategy: moving_average")
    except ImportError as e:
        logger.warning(f"Could not import MovingAverageCrossoverStrategy: {e}")


# Auto-register on module import
_register_builtin_strategies()
