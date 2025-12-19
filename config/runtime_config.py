"""
Runtime Configuration Dataclass

This module defines the RuntimeConfig dataclass, which holds all fully-resolved
configuration values needed for the trading bot's operation. Unlike the static
settings module, this class is instantiated at startup and passed down to
components, ensuring immutability and testability.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass(frozen=True)
class RuntimeConfig:
    """
    Immutable configuration object containing all runtime values.
    """
    # API Credentials
    saxo_env: str
    saxo_auth_mode: str
    account_key: str
    client_key: str

    # Trading Configuration
    watchlist: List[Dict[str, Any]]
    cycle_interval_seconds: int
    trading_hours_mode: str
    default_quantity: float

    # Risk Management
    max_positions: int
    max_daily_trades: int
    max_position_size: float
    max_daily_loss: float
    stop_loss_percent: float
    take_profit_percent: float

    # Trading Hours (optional, for fixed mode)
    trading_start: Optional[str] = None
    trading_end: Optional[str] = None
    timezone: Optional[str] = None

    # Logging
    log_level: str = "INFO"

    # Calculated properties or derived state can be added here if needed

    def get_instrument(self, symbol: str, asset_type: str) -> Optional[Dict[str, Any]]:
        """Helper to look up an instrument from the watchlist."""
        for inst in self.watchlist:
            if inst.get("symbol") == symbol and inst.get("asset_type") == asset_type:
                return inst
        return None
