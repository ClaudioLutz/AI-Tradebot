from decimal import Decimal
from typing import Optional, Any
from execution.models import OrderIntent, BuySell, AssetType
from execution.position import PositionManager
from config.runtime_config import RuntimeConfig

def signal_to_intent(
    signal: Any,
    instrument: dict,
    cfg: RuntimeConfig,
    position_manager: PositionManager
) -> Optional[OrderIntent]:
    """
    Maps a trading signal to an execution intent.
    Handles sizing (Decimal) and position lookups for exits.
    """
    action = signal.action
    if action == "HOLD":
        return None

    # Resolve AssetType enum
    try:
        asset_type_enum = AssetType(instrument["asset_type"])
    except ValueError:
        return None

    if action == "BUY":
        qty = cfg.default_quantity
        if not isinstance(qty, Decimal):
            qty = Decimal(str(qty))

        return OrderIntent(
            asset_type=asset_type_enum,
            uic=instrument["uic"],
            buy_sell=BuySell.BUY,
            amount=qty,
            account_key=cfg.account_key,
            client_key=cfg.client_key,
            strategy_id=getattr(signal, "strategy_id", "unknown"),
        )

    if action == "SELL":
        # For SELL, we must find the existing position to close it.
        # We rely on the position manager (which should be refreshed).
        pos = position_manager.get_position(instrument["asset_type"], instrument["uic"])
        if not pos:
            return None

        qty = pos.net_quantity
        if not isinstance(qty, Decimal):
            qty = Decimal(str(qty))

        # Can only sell positive quantity
        if qty <= 0:
            return None

        return OrderIntent(
            asset_type=asset_type_enum,
            uic=instrument["uic"],
            buy_sell=BuySell.SELL,
            amount=qty,
            account_key=cfg.account_key,
            client_key=cfg.client_key,
            strategy_id=getattr(signal, "strategy_id", "unknown"),
        )

    return None
