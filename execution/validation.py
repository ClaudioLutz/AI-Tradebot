from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import time
import requests
import logging
from execution.models import OrderIntent

logger = logging.getLogger(__name__)

@dataclass
class InstrumentConstraints:
    """
    Normalized instrument constraints for validation
    """
    # Tradability
    is_tradable: bool
    non_tradable_reason: Optional[str] = None

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
        # Check decimals
        if self.amount_decimals is not None:
            # Count decimal places.
            # We use string formatting to avoid float precision issues with small decimals
            amount_str = f"{amount:.10f}".rstrip('0').rstrip('.')
            if '.' in amount_str:
                decimals = len(amount_str.split('.')[1])
                if decimals > self.amount_decimals:
                    return False, f"Amount has {decimals} decimals, max allowed is {self.amount_decimals}"

        # Check increment size
        if self.increment_size and self.increment_size > 0:
            # Use epsilon for float modulo
            remainder = amount % self.increment_size
            # If remainder is close to 0 or close to increment_size, it's valid
            if remainder > 1e-10 and abs(remainder - self.increment_size) > 1e-10:
                return False, f"Amount {amount} not aligned with increment size {self.increment_size}"

        # Check minimum trade size
        if self.minimum_trade_size and amount < self.minimum_trade_size:
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
                # requests.Response like
                if hasattr(response, 'raise_for_status'):
                    response.raise_for_status()
                data = response.json()
            elif isinstance(response, dict):
                data = response
            else:
                # Assuming it's already parsed data if not a Response object
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
        # Saxo response "IsTradable" might be in different places depending on field groups,
        # but usually at root or in TradingStatus
        is_tradable = data.get("IsTradable", True)
        non_tradable_reason = data.get("NonTradableReason")

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

            # Validate price (if Limit/Stop and price is present in intent - extending intent dynamically or checking attributes)
            # Standard OrderIntent might not have price for Market orders.
            # If we add Limit support later, we'd add 'price' to OrderIntent.
            if intent.order_type.value in ["Limit", "Stop"] and hasattr(intent, "price") and intent.price:
                 is_valid, error = constraints.validate_price(intent.price)
                 if not is_valid:
                     return False, error

            return True, None

        except ValueError as e:
            return False, f"Instrument validation failed: {str(e)}"
