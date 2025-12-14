import pytest
from unittest.mock import Mock, patch
from execution.validation import InstrumentConstraints, InstrumentValidator
from execution.models import OrderIntent, AssetType, BuySell, OrderType

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
        client_key="client_123",
        account_key="test_key",
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
    # Mocking response for caching test
    mock_client.get.return_value = {
        "IsTradable": True,
        "Format": {"Decimals": 0}
    }

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
