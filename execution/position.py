from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from decimal import Decimal
import logging
from datetime import datetime
import asyncio
import time

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Normalized position representation"""
    asset_type: str  # "Stock", "FxSpot", "FxCrypto"
    uic: int
    account_key: str
    position_id: str
    net_quantity: Decimal  # Positive for long, negative for short
    average_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    currency: str
    symbol: Optional[str] = None
    market_state: Optional[str] = None
    can_be_closed: bool = True

@dataclass
class PositionGuardResult:
    """Result of position-aware guard evaluation"""
    allowed: bool
    reason: str
    position_quantity: Optional[Decimal] = None
    recommended_action: Optional[str] = None

@dataclass
class ExecutionConfig:
    """Configuration for position-aware guards"""

    # Position guard behavior
    duplicate_buy_policy: str = "block"  # "block", "warn", "allow"
    allow_short_covering: bool = False
    position_cache_ttl_seconds: int = 30

    # Position query retry settings
    position_query_retries: int = 2
    position_query_timeout_seconds: int = 10

class PositionManager:
    """Manages position queries and caching"""

    def __init__(self, saxo_client, client_key: str, cache_ttl_seconds: int = 30):
        self.client = saxo_client
        self.client_key = client_key
        self.cache_ttl = cache_ttl_seconds
        self._position_cache: Dict[Tuple[str, int], Position] = {}
        self._cache_timestamp: Optional[datetime] = None

    def get_position(self, asset_type: str, uic: int) -> Optional[Position]:
        """Helper to get a single position by key."""
        return self._position_cache.get((asset_type, uic))

    def get_positions(self, force_refresh: bool = False) -> Dict[Tuple[str, int], Position]:
        """
        Fetch and cache positions keyed by (AssetType, Uic)
        Synchronous wrapper since client is sync.
        """
        if not force_refresh and self._is_cache_valid():
            return self._position_cache

        try:
            # Query NetPositions with mandatory FieldGroups
            # Assuming saxo_client.get returns a dict (the response body)
            response = self.client.get(
                "/port/v1/netpositions",
                params={
                    "ClientKey": self.client_key,
                    "FieldGroups": "NetPositionBase,NetPositionView"
                }
            )

            positions = {}
            # response might be a requests.Response object or a dict depending on client wrapper
            data = response
            if hasattr(response, 'json'):
                 data = response.json()

            for item in data.get("Data", []):
                pos_base = item.get("NetPositionBase", {})
                pos_view = item.get("NetPositionView", {})

                if "AssetType" not in pos_base or "Uic" not in pos_base:
                    continue

                key = (pos_base["AssetType"], pos_base["Uic"])
                positions[key] = Position(
                    asset_type=pos_base["AssetType"],
                    uic=pos_base["Uic"],
                    account_key=pos_base.get("AccountKey", ""),
                    position_id=item.get("NetPositionId", ""),
                    net_quantity=Decimal(str(pos_base.get("Amount", 0))),
                    average_price=Decimal(str(pos_view.get("AverageOpenPrice", 0))),
                    market_value=Decimal(str(pos_view.get("MarketValue", 0))),
                    unrealized_pnl=Decimal(str(pos_view.get("ProfitLossOnTrade", 0))),
                    currency=pos_base.get("Currency", "USD"),
                    can_be_closed=pos_base.get("CanBeClosed", True)
                )

            self._position_cache = positions
            self._cache_timestamp = datetime.utcnow()

            logger.info(
                f"positions_refreshed count={len(positions)} client_key={self.client_key}"
            )

            return positions

        except Exception as e:
            logger.error(
                f"position_query_failed error={str(e)} client_key={self.client_key}"
            )
            # Return cached data if available, otherwise empty dict
            return self._position_cache if self._position_cache else {}

    def _is_cache_valid(self) -> bool:
        """Check if cached positions are still valid"""
        if not self._cache_timestamp:
            return False
        age = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return age < self.cache_ttl

class PositionAwareGuards:
    """Implements position-based execution guards"""

    def __init__(self, position_manager: PositionManager, config: ExecutionConfig):
        self.position_manager = position_manager
        self.config = config

    def evaluate_buy_intent(
        self,
        asset_type: str,
        uic: int,
        intended_quantity: Decimal
    ) -> PositionGuardResult:
        """
        Evaluate if a buy order should be allowed
        """
        positions = self.position_manager.get_positions()
        key = (asset_type, uic)

        if key not in positions:
            return PositionGuardResult(
                allowed=True,
                reason="no_existing_position",
                position_quantity=Decimal(0)
            )

        position = positions[key]

        # Long position exists - prevent duplicate buy
        if position.net_quantity > 0:
            logger.warning(
                f"duplicate_buy_prevented asset_type={asset_type} uic={uic} "
                f"existing={float(position.net_quantity)} intended={float(intended_quantity)}"
            )

            if self.config.duplicate_buy_policy == "block":
                return PositionGuardResult(
                    allowed=False,
                    reason="duplicate_buy_prevented",
                    position_quantity=position.net_quantity,
                    recommended_action="skip_or_increase_existing"
                )
            else:
                 return PositionGuardResult(
                    allowed=True,
                    reason="duplicate_buy_warned",
                    position_quantity=position.net_quantity,
                )

        # Short position exists - could reduce short
        elif position.net_quantity < 0:
            if self.config.allow_short_covering:
                logger.info(
                    f"buy_to_cover_short asset_type={asset_type} uic={uic} short={float(position.net_quantity)}"
                )
                return PositionGuardResult(
                    allowed=True,
                    reason="reducing_short_position",
                    position_quantity=position.net_quantity
                )
            else:
                logger.warning(
                    f"short_covering_disabled asset_type={asset_type} uic={uic}"
                )
                return PositionGuardResult(
                    allowed=False,
                    reason="short_covering_not_configured",
                    position_quantity=position.net_quantity
                )

        return PositionGuardResult(
            allowed=True,
            reason="zero_position",
            position_quantity=Decimal(0)
        )

    def evaluate_sell_intent(
        self,
        asset_type: str,
        uic: int,
        intended_quantity: Optional[Decimal] = None
    ) -> PositionGuardResult:
        """
        Evaluate if a sell order should be allowed
        """
        positions = self.position_manager.get_positions()
        key = (asset_type, uic)

        if key not in positions:
            logger.warning(
                f"no_position_to_sell asset_type={asset_type} uic={uic}"
            )

            return PositionGuardResult(
                allowed=False,
                reason="no_position_to_sell",
                position_quantity=Decimal(0)
            )

        position = positions[key]

        # Position exists but is short
        if position.net_quantity < 0:
            logger.warning(
                f"cannot_sell_short_position asset_type={asset_type} uic={uic} qty={float(position.net_quantity)}"
            )
            return PositionGuardResult(
                allowed=False,
                reason="position_is_short",
                position_quantity=position.net_quantity
            )

        # Position exists but is zero (should not happen if in map, but safe guard)
        if position.net_quantity == 0:
            logger.warning(
                f"zero_position_cannot_sell asset_type={asset_type} uic={uic}"
            )
            return PositionGuardResult(
                allowed=False,
                reason="zero_position",
                position_quantity=Decimal(0)
            )

        # Check if position can be closed
        if not position.can_be_closed:
            logger.error(
                f"position_locked asset_type={asset_type} uic={uic}"
            )
            return PositionGuardResult(
                allowed=False,
                reason="position_locked_by_broker",
                position_quantity=position.net_quantity
            )

        # Determine quantity to sell
        sell_quantity = intended_quantity if intended_quantity else position.net_quantity

        if sell_quantity > position.net_quantity:
            logger.warning(
                f"sell_quantity_exceeds_position asset_type={asset_type} uic={uic} "
                f"pos={float(position.net_quantity)} req={float(sell_quantity)}"
            )
            sell_quantity = position.net_quantity

        logger.info(
            f"sell_allowed asset_type={asset_type} uic={uic} sell_qty={float(sell_quantity)}"
        )

        return PositionGuardResult(
            allowed=True,
            reason="position_exists",
            position_quantity=sell_quantity,
            recommended_action=f"sell_{sell_quantity}"
        )
