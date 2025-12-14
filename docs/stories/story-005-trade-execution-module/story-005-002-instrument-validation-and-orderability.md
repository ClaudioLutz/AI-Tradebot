# Story 005-002: Instrument validation and orderability checks

## Summary
Before prechecking or placing an order, validate the instrument configuration and trading constraints using Saxo Reference Data (instrument details).

## Background / Context
Saxo instruments vary by asset class and may have specific rules (supported order types, order duration types,
amount decimals, increment size, market state, and tradability). A precheck can fail for many reasons; however,
validating obvious constraints locally improves error clarity and avoids avoidable API calls.

## Scope
In scope:
- Fetch instrument details for a specific `(Uic, AssetType)` and use it to validate:
  - `IsTradable` / `NonTradableReason` (when available in the returned field groups)
  - Amount formatting constraints (AmountDecimals, IncrementSize, LotSize / minimums when available)
  - Supported order types and duration types (SupportedOrderTypes → duration types per order type)
- Cache instrument details (in-memory) with a short TTL to avoid repeated calls.
- Produce a normalized `InstrumentConstraints` object used by precheck/placement.

Out of scope:
- Full instrument discovery workflows
- Options, futures, CFDs, mutual funds, algorithmic orders

## Acceptance Criteria
1. Executor can retrieve instrument details for `(Uic, AssetType)` using the dedicated "instrument details" endpoint.
2. For Stock and FxSpot:
   - Amount is validated to match `AmountDecimals`.
   - Amount respects `IncrementSize` when present (e.g., FX increments).
3. Module validates that `OrderType='Market'` is supported for the instrument (via SupportedOrderTypes).
4. Module validates that chosen `OrderDuration.DurationType` (default DayOrder) is supported for Market orders when the instrument provides duration-type restrictions.
5. If `IsTradable` is false (or `NonTradableReason` indicates not tradable), executor refuses to place and logs a structured reason.
6. Instrument-details lookup failures do not crash orchestration; they result in a failed execution with actionable logging.

## Technical Implementation Details

### 1. Instrument Details API Integration

```python
import requests
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

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
    
    # Supported order types
    supported_order_types: list[str] = None
    supported_durations: Dict[str, list[str]] = None  # {OrderType: [DurationTypes]}
    
    # Identifiers
    uic: int = 0
    asset_type: str = ""
    symbol: Optional[str] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        if self.supported_order_types is None:
            self.supported_order_types = []
        if self.supported_durations is None:
            self.supported_durations = {}
    
    def validate_order_type(self, order_type: str) -> tuple[bool, Optional[str]]:
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
    
    def validate_duration_type(self, order_type: str, duration_type: str) -> tuple[bool, Optional[str]]:
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
    
    def validate_amount(self, amount: float) -> tuple[bool, Optional[str]]:
        """
        Validate amount against constraints.
        Returns: (is_valid, error_message)
        """
        # Check decimals
        if self.amount_decimals is not None:
            # Count decimal places
            amount_str = f"{amount:.10f}".rstrip('0').rstrip('.')
            if '.' in amount_str:
                decimals = len(amount_str.split('.')[1])
                if decimals > self.amount_decimals:
                    return False, f"Amount has {decimals} decimals, max allowed is {self.amount_decimals}"
        
        # Check increment size
        if self.increment_size and self.increment_size > 0:
            remainder = amount % self.increment_size
            if remainder > 1e-10:  # Allow tiny floating point errors
                return False, f"Amount {amount} not aligned with increment size {self.increment_size}"
        
        # Check minimum trade size
        if self.minimum_trade_size and amount < self.minimum_trade_size:
            return False, f"Amount {amount} below minimum trade size {self.minimum_trade_size}"
        
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
        self._cache: Dict[tuple, tuple[InstrumentConstraints, float]] = {}
    
    def get_instrument_details(self, uic: int, asset_type: str, 
                               account_key: Optional[str] = None) -> InstrumentConstraints:
        """
        Fetch instrument details from Saxo API with caching.
        
        API Endpoint: GET /ref/v1/instruments/details/{Uic}/{AssetType}
        Query Parameters:
            - AccountKey (optional): For account-specific constraints
            - FieldGroups: Comma-separated list
        
        Field Groups:
            - DisplayAndFormat: Basic display info
            - InstrumentInfo: Trading constraints
            - OrderSetting: Order type and duration settings
            - TradingStatus: Tradability status
        
        Args:
            uic: Universal Instrument Code
            asset_type: Asset type (Stock, FxSpot, etc.)
            account_key: Optional account key for account-specific rules
            
        Returns:
            InstrumentConstraints object
            
        Raises:
            ValueError: If instrument not found or API error
        """
        import time
        
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
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
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
            raise ValueError(f"Error fetching instrument details: {e}")
    
    def _parse_instrument_details(self, data: dict, uic: int, asset_type: str) -> InstrumentConstraints:
        """
        Parse Saxo instrument details response into InstrumentConstraints.
        
        Response schema varies by asset type. Common fields:
        - IsTradable (bool)
        - NonTradableReason (string)
        - AmountDecimals (int)
        - IncrementSize (number) - for FX
        - LotSize (number)
        - MinimumTradeSize (number)
        - SupportedOrderTypes (array of objects)
        """
        # Tradability
        is_tradable = data.get("IsTradable", True)
        non_tradable_reason = data.get("NonTradableReason")
        
        # Format constraints
        format_info = data.get("Format", {})
        amount_decimals = format_info.get("Decimals", 0)
        
        # Trading constraints
        increment_size = data.get("IncrementSize")
        lot_size = data.get("LotSize")
        minimum_trade_size = data.get("MinimumTradeSize")
        
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
            supported_order_types=supported_order_types,
            supported_durations=supported_durations,
            uic=uic,
            asset_type=asset_type,
            symbol=symbol,
            description=description
        )
    
    def validate_order_intent(self, intent: 'OrderIntent') -> tuple[bool, Optional[str]]:
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
            
            return True, None
            
        except ValueError as e:
            return False, f"Instrument validation failed: {str(e)}"
```

### 2. Example API Response

```json
{
  "AssetType": "Stock",
  "Uic": 211,
  "Symbol": "AAPL:xnas",
  "Description": "Apple Inc.",
  "IsTradable": true,
  "Format": {
    "Decimals": 0,
    "Format": "Normal"
  },
  "MinimumTradeSize": 1,
  "TradableAs": ["Stock"],
  "SupportedOrderTypes": [
    {
      "OrderType": "Market",
      "DurationTypes": ["DayOrder", "GoodTillCancel"]
    },
    {
      "OrderType": "Limit",
      "DurationTypes": ["DayOrder", "GoodTillCancel", "GoodTillDate"]
    }
  ]
}
```

FxSpot example:
```json
{
  "AssetType": "FxSpot",
  "Uic": 21,
  "Symbol": "EURUSD",
  "Description": "Euro/US Dollar",
  "IsTradable": true,
  "Format": {
    "Decimals": 0
  },
  "IncrementSize": 1000,
  "MinimumTradeSize": 1000,
  "SupportedOrderTypes": [
    {
      "OrderType": "Market",
      "DurationTypes": ["FillOrKill", "ImmediateOrCancel"]
    }
  ]
}
```

### 3. Integration with Execution Pipeline

```python
class TradeExecutorImpl(TradeExecutor):
    """
    Trade executor implementation with instrument validation.
    """
    
    def __init__(self, saxo_client, account_key: str):
        self.client = saxo_client
        self.account_key = account_key
        self.instrument_validator = InstrumentValidator(saxo_client)
    
    def execute(self, intent: OrderIntent, dry_run: bool = True) -> ExecutionResult:
        """
        Execute with instrument validation as first step.
        """
        # Step 1: Validate instrument constraints
        is_valid, error_msg = self.instrument_validator.validate_order_intent(intent)
        
        if not is_valid:
            return ExecutionResult(
                status=ExecutionStatus.FAILED_PRECHECK,
                order_intent=intent,
                error_message=f"Instrument validation failed: {error_msg}",
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Continue with precheck, placement, etc.
        # ... (rest of execution pipeline)
```

### 4. Unit Tests

```python
import pytest
from unittest.mock import Mock, patch

def test_validate_amount_decimals():
    """Test amount decimal validation"""
    constraints = InstrumentConstraints(
        is_tradable=True,
        amount_decimals=0,  # Stock: no decimals
        uic=211,
        asset_type="Stock"
    )
    
    # Valid: whole number
    is_valid, error = constraints.validate_amount(100.0)
    assert is_valid
    
    # Invalid: has decimals
    is_valid, error = constraints.validate_amount(100.5)
    assert not is_valid
    assert "decimals" in error.lower()

def test_validate_increment_size():
    """Test FX increment size validation"""
    constraints = InstrumentConstraints(
        is_tradable=True,
        amount_decimals=0,
        increment_size=1000,  # FX: multiples of 1000
        uic=21,
        asset_type="FxSpot"
    )
    
    # Valid: multiple of 1000
    is_valid, error = constraints.validate_amount(5000.0)
    assert is_valid
    
    # Invalid: not multiple of 1000
    is_valid, error = constraints.validate_amount(5500.0)
    assert not is_valid
    assert "increment" in error.lower()

def test_not_tradable_instrument():
    """Test handling of non-tradable instrument"""
    validator = InstrumentValidator(Mock())
    
    # Mock API response
    validator._parse_instrument_details = Mock(return_value=InstrumentConstraints(
        is_tradable=False,
        non_tradable_reason="Market closed",
        uic=211,
        asset_type="Stock"
    ))
    
    intent = OrderIntent(
        account_key="test",
        asset_type=AssetType.STOCK,
        uic=211,
        buy_sell=BuySell.BUY,
        amount=100
    )
    
    is_valid, error = validator.validate_order_intent(intent)
    assert not is_valid
    assert "not tradable" in error.lower()
    assert "Market closed" in error

def test_unsupported_order_type():
    """Test validation of unsupported order type"""
    constraints = InstrumentConstraints(
        is_tradable=True,
        amount_decimals=0,
        supported_order_types=["Market", "Limit"],
        uic=211,
        asset_type="Stock"
    )
    
    is_valid, error = constraints.validate_order_type("Stop")
    assert not is_valid
    assert "not supported" in error.lower()

def test_cache_behavior():
    """Test instrument details caching"""
    import time
    
    mock_client = Mock()
    mock_response = Mock()
    mock_response.json.return_value = {
        "IsTradable": True,
        "Format": {"Decimals": 0}
    }
    mock_client.get.return_value = mock_response
    
    validator = InstrumentValidator(mock_client, cache_ttl_seconds=1)
    
    # First call - should hit API
    constraints1 = validator.get_instrument_details(211, "Stock")
    assert mock_client.get.call_count == 1
    
    # Second call - should use cache
    constraints2 = validator.get_instrument_details(211, "Stock")
    assert mock_client.get.call_count == 1  # Still 1
    
    # Wait for cache expiry
    time.sleep(1.1)
    
    # Third call - should hit API again
    constraints3 = validator.get_instrument_details(211, "Stock")
    assert mock_client.get.call_count == 2
```

## Implementation Notes
- Use `FieldGroups=DisplayAndFormat,InstrumentInfo,OrderSetting,TradingStatus` when calling instrument details to receive all validation-relevant fields.
- Store constraints as a pure data object (no HTTP client dependency) so it can be unit-tested.
- When fields are missing for an asset type, fall back conservatively:
  - If SupportedOrderTypes is missing, rely on precheck (but log that local validation was incomplete).
- Prefer a small TTL cache (e.g., 10–60 minutes) because instrument constraints can change intraday.
- Amount decimal validation should account for floating-point precision issues (use epsilon comparison).

## Test Plan
- Unit tests:
  - Parsing of instrument details into constraints (AmountDecimals, IncrementSize, SupportedOrderTypes).
  - Amount validation for Stock (commonly 0 decimals) and FxSpot (often 0 decimals but constrained by increment size).
  - Cache hit/miss behavior and TTL expiry.
- Integration (SIM):
  - Fetch instrument details for one Stock Uic and one FxSpot Uic used in existing configs.
  - Ensure market order intent passes local validation before precheck.
  - Test with non-tradable instrument (if available).

## Dependencies / Assumptions
- Requires access to the Reference Data service group.
- Caller must provide AccountKey (and optionally ClientKey) if required by the endpoint.
- Assumes instrument details schema is stable across Saxo API versions.

## Primary Sources
- https://www.developer.saxo/openapi/learn/reference-data
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments/get__ref__details_uic_assettype
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments/get__ref__details_uic_assettype/schema-supportedordertypesetting
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments
