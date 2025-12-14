from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import time
import requests
import logging
from execution.models import OrderIntent, MarketState

logger = logging.getLogger(__name__)

@dataclass
class InstrumentConstraints:
    """
    Normalized instrument constraints for validation
    """
    # Tradability
    is_tradable: bool
    non_tradable_reason: Optional[str] = None
    market_state: Optional[MarketState] = None

    # Amount formatting
    amount_decimals: int = 0  # Precision for amount field
    increment_size: Optional[float] = None  # Minimum increment (FX)
    lot_size: Optional[float] = None  # Standard lot size
    minimum_trade_size: Optional[float] = None

    # Price/Tick rules
    tick_size: Optional[float] = None  # Minimum price step

    # Supported order types
    supported_order_types: List[str] = field(default_factory=list)
    supported_durations: Dict[str, List[str]] = field(default_factory=dict)  # {OrderType: [DurationTypes]}

    # Identifiers
    uic: int = 0
    asset_type: str = ""
    symbol: Optional[str] = None
    description: Optional[str] = None

    def validate_order_type(self, order_type: str) -> Tuple[bool, Optional[str]]:
        """
        Check if order type is supported.
        Returns: (is_valid, error_message)
        """
        if not self.supported_order_types:
            # If not provided, assume supported (rely on precheck)
            return True, None

        if order_type not in self.supported_order_types:
            return False, f"OrderType '{order_type}' not supported. Supported: {self.supported_order_types}"

        return True, None

    def validate_duration_type(self, order_type: str, duration_type: str) -> Tuple[bool, Optional[str]]:
        """
        Check if duration type is supported for given order type.
        Returns: (is_valid, error_message)
        """
        if not self.supported_durations or order_type not in self.supported_durations:
            # If not provided, assume supported
            return True, None

        allowed_durations = self.supported_durations.get(order_type, [])
        if duration_type not in allowed_durations:
            return False, f"DurationType '{duration_type}' not supported for {order_type}. Supported: {allowed_durations}"

        return True, None

    def validate_amount(self, amount: float) -> Tuple[bool, Optional[str]]:
        """
        Validate amount against constraints.
        Returns: (is_valid, error_message)
        """
        # Convert Decimal to float for validation if needed,
        # but amount here is float per type hint.
        # Wait, OrderIntent.amount is now Decimal.
        # This method signature should accept Decimal or float.
        # I'll update signature to accept Any or numbers.Number.
        # Or cast to float.
        amount_flt = float(amount)

        # Check decimals
        if self.amount_decimals is not None:
            # Count decimal places.
            # We use string formatting to avoid float precision issues with small decimals
            amount_str = f"{amount_flt:.10f}".rstrip('0').rstrip('.')
            if '.' in amount_str:
                decimals = len(amount_str.split('.')[1])
                if decimals > self.amount_decimals:
                    return False, f"Amount has {decimals} decimals, max allowed is {self.amount_decimals}"

        # Check increment size
        if self.increment_size and self.increment_size > 0:
            # Use epsilon for float modulo
            remainder = amount_flt % self.increment_size
            # If remainder is close to 0 or close to increment_size, it's valid
            if remainder > 1e-10 and abs(remainder - self.increment_size) > 1e-10:
                return False, f"Amount {amount} not aligned with increment size {self.increment_size}"

        # Check minimum trade size
        if self.minimum_trade_size and amount_flt < self.minimum_trade_size:
            return False, f"Amount {amount} below minimum trade size {self.minimum_trade_size}"

        return True, None

    def validate_price(self, price: float) -> Tuple[bool, Optional[str]]:
        """
        Validate price against tick size constraints (for Limit/Stop orders).
        Returns: (is_valid, error_message)
        """
        if self.tick_size and self.tick_size > 0:
            remainder = price % self.tick_size
            if remainder > 1e-10 and abs(remainder - self.tick_size) > 1e-10:
                return False, f"Price {price} not aligned with tick size {self.tick_size}"
        return True, None

    def validate_market_state(self) -> Tuple[bool, Optional[str]]:
        """
        Validate if market state allows trading.
        Fail-closed for unknown or restrictive states. (2.1)
        """
        if not self.market_state or self.market_state == MarketState.UNKNOWN:
            return False, "Market state is Unknown, blocking trade."

        # Block Auction states, Pre/Post trading, and Closed
        blocked_states = {
            MarketState.OPENING_AUCTION,
            MarketState.CLOSING_AUCTION,
            MarketState.INTRADAY_AUCTION,
            MarketState.TRADING_AT_LAST,
            MarketState.PRE_TRADING,
            MarketState.POST_TRADING,
            MarketState.CLOSED,
            MarketState.UNKNOWN
        }

        if self.market_state in blocked_states:
            return False, f"Market is in {self.market_state.value} state, trading restricted."

        return True, None


class InstrumentValidator:
    """
    Handles instrument validation using Saxo Reference Data API.
    Endpoint: GET /ref/v1/instruments/details/{Uic}/{AssetType}
    """

    def __init__(self, saxo_client, cache_ttl_seconds: int = 600):
        """
        Args:
            saxo_client: Authenticated Saxo HTTP client
            cache_ttl_seconds: Cache TTL for instrument details (default 10 min)
        """
        self.client = saxo_client
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[tuple, Tuple[InstrumentConstraints, float]] = {}

    def get_instrument_details(self, uic: int, asset_type: str,
                               account_key: Optional[str] = None) -> InstrumentConstraints:
        """
        Fetch instrument details from Saxo API with caching.
        """
        cache_key = (uic, asset_type, account_key)

        # Check cache
        if cache_key in self._cache:
            constraints, cached_at = self._cache[cache_key]
            if time.time() - cached_at < self.cache_ttl:
                return constraints

        # Build API request
        url = f"/ref/v1/instruments/details/{uic}/{asset_type}"
        params = {
            "FieldGroups": "DisplayAndFormat,InstrumentInfo,OrderSetting,TradingStatus"
        }
        if account_key:
            params["AccountKey"] = account_key

        try:
            # Assuming client.get returns a response object or dict
            response = self.client.get(url, params=params)

            # Handling if client returns requests.Response or dict
            if hasattr(response, 'json'):
                if hasattr(response, 'raise_for_status'):
                    response.raise_for_status()
                data = response.json()
            elif isinstance(response, dict):
                data = response
            else:
                data = response

            # Parse response
            constraints = self._parse_instrument_details(data, uic, asset_type)

            # Cache result
            self._cache[cache_key] = (constraints, time.time())

            return constraints

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Instrument not found: Uic={uic}, AssetType={asset_type}")
            raise ValueError(f"Failed to fetch instrument details: {e}")
        except Exception as e:
            # If the client raises its own exceptions, catch them here
            raise ValueError(f"Error fetching instrument details: {e}")

    def _parse_instrument_details(self, data: dict, uic: int, asset_type: str) -> InstrumentConstraints:
        """
        Parse Saxo instrument details response into InstrumentConstraints.
        """
        # Tradability
        # Check top-level
        is_tradable = data.get("IsTradable")
        non_tradable_reason = data.get("NonTradableReason")

        # Check nested TradingStatus if top-level is missing
        if is_tradable is None and "TradingStatus" in data:
            is_tradable = data["TradingStatus"].get("IsTradable")
            non_tradable_reason = data["TradingStatus"].get("NonTradableReason")

        # Default to True if still None? Better to be safe and default to False?
        # Saxo usually provides it. If missing, assume True but log?
        # Code used to default to True.
        if is_tradable is None:
            is_tradable = False # Fail-closed

        # Market State
        market_state_str = None
        if "TradingStatus" in data:
            market_state_str = data["TradingStatus"].get("MarketState")

        # Parse MarketState enum
        market_state = MarketState.UNKNOWN
        if market_state_str:
            try:
                market_state = MarketState(market_state_str)
            except ValueError:
                logger.warning(f"Unknown MarketState: {market_state_str}")
                market_state = MarketState.UNKNOWN

        # Format constraints
        format_info = data.get("Format", {})
        amount_decimals = format_info.get("Decimals", 0)

        # Trading constraints
        increment_size = data.get("IncrementSize")
        lot_size = data.get("LotSize")
        minimum_trade_size = data.get("MinimumTradeSize")
        tick_size = data.get("TickSize")

        # Order type support
        supported_order_types = []
        supported_durations = {}

        order_settings = data.get("SupportedOrderTypes", [])
        for setting in order_settings:
            order_type = setting.get("OrderType")
            if order_type:
                supported_order_types.append(order_type)

                # Duration types for this order type
                duration_types = setting.get("DurationTypes", [])
                if duration_types:
                    supported_durations[order_type] = duration_types

        # Identifiers
        symbol = data.get("Symbol")
        description = data.get("Description")

        return InstrumentConstraints(
            is_tradable=is_tradable,
            non_tradable_reason=non_tradable_reason,
            market_state=market_state,
            amount_decimals=amount_decimals,
            increment_size=increment_size,
            lot_size=lot_size,
            minimum_trade_size=minimum_trade_size,
            tick_size=tick_size,
            supported_order_types=supported_order_types,
            supported_durations=supported_durations,
            uic=uic,
            asset_type=asset_type,
            symbol=symbol,
            description=description
        )

    def validate_order_intent(self, intent: OrderIntent) -> Tuple[bool, Optional[str]]:
        """
        Validate OrderIntent against instrument constraints.

        Args:
            intent: The order intent to validate

        Returns:
            (is_valid, error_message)
        """
        try:
            constraints = self.get_instrument_details(
                intent.uic,
                intent.asset_type.value,
                intent.account_key
            )

            # Check tradability
            if not constraints.is_tradable:
                reason = constraints.non_tradable_reason or "Unknown reason"
                return False, f"Instrument not tradable: {reason}"

            # Check market state
            is_valid, error = constraints.validate_market_state()
            if not is_valid:
                return False, error

            # Validate order type
            is_valid, error = constraints.validate_order_type(intent.order_type.value)
            if not is_valid:
                return False, error

            # Validate duration type
            is_valid, error = constraints.validate_duration_type(
                intent.order_type.value,
                intent.order_duration.duration_type.value
            )
            if not is_valid:
                return False, error

            # Validate amount
            is_valid, error = constraints.validate_amount(intent.amount)
            if not is_valid:
                return False, error

            # Validate price
            if intent.order_type.value in ["Limit", "Stop"] and hasattr(intent, "price") and intent.price:
                 is_valid, error = constraints.validate_price(intent.price)
                 if not is_valid:
                     return False, error

            return True, None

        except ValueError as e:
            return False, f"Instrument validation failed: {str(e)}"
