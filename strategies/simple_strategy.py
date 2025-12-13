"""
DEPRECATED: This file is deprecated and will be removed in a future version.

This was a placeholder from Epic 001. The proper strategy implementation
is now in strategies/moving_average.py which implements the BaseStrategy
interface and returns Signal objects.

For new strategies, please:
1. Inherit from strategies.base.BaseStrategy
2. Implement generate_signals() method
3. Return Signal objects with full audit trail
4. Register your strategy using @register_strategy decorator

See strategies/moving_average.py for a reference implementation.
"""

import warnings

warnings.warn(
    "strategies.simple_strategy is deprecated. "
    "Use strategies.moving_average.MovingAverageCrossoverStrategy or implement "
    "your own strategy by inheriting from strategies.base.BaseStrategy",
    DeprecationWarning,
    stacklevel=2
)


def generate_signal(data):
    """
    DEPRECATED: Use BaseStrategy.generate_signals() instead.
    
    Args:
        data: Market data for analysis
    
    Returns:
        str: Trading signal ('BUY', 'SELL', or 'HOLD')
    
    Raises:
        DeprecationWarning: This function is deprecated
    """
    raise NotImplementedError(
        "This function is deprecated. Use MovingAverageCrossoverStrategy or "
        "implement your own strategy by inheriting from BaseStrategy."
    )


def calculate_indicators(data):
    """
    DEPRECATED: Use strategies.indicators module instead.
    
    Args:
        data: Historical price data
    
    Returns:
        dict: Calculated indicators
    
    Raises:
        DeprecationWarning: This function is deprecated
    """
    raise NotImplementedError(
        "This function is deprecated. Use functions from strategies.indicators "
        "like simple_moving_average(), exponential_moving_average(), etc."
    )
