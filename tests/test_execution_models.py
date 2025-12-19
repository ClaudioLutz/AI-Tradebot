import pytest
import time
from decimal import Decimal
from execution.models import OrderIntent, AssetType, BuySell, OrderType, OrderDurationType
from execution.utils import intent_to_saxo_order_request, generate_request_id, generate_external_reference

def test_external_reference_max_length():
    """Test that external_reference exceeding 50 chars raises error"""
    with pytest.raises(ValueError, match="external_reference must be <= 50 chars"):
        OrderIntent(
            client_key="client_123",
            account_key="test_key",
            asset_type=AssetType.STOCK,
            uic=211,
            buy_sell=BuySell.BUY,
            amount=Decimal("100"),
            external_reference="x" * 51  # Too long
        )

def test_intent_to_saxo_request_mapping():
    """Test OrderIntent maps correctly to Saxo API format"""
    intent = OrderIntent(
        client_key="client_123",
        account_key="Cf4xZWiYL6W1nMKpygBLLA==",
        asset_type=AssetType.STOCK,
        uic=211,
        buy_sell=BuySell.BUY,
        amount=Decimal("100"),
        external_reference="E005:TEST:211:abc12",
        manual_order=True
    )

    request = intent_to_saxo_order_request(intent)

    assert request["AccountKey"] == "Cf4xZWiYL6W1nMKpygBLLA=="
    assert request["AssetType"] == "Stock"
    assert request["Uic"] == 211
    assert request["BuySell"] == "Buy"
    assert request["Amount"] == Decimal("100")
    assert request["OrderType"] == "Market"
    assert request["ExternalReference"] == "E005:TEST:211:abc12"
    assert request["ManualOrder"] is True
    assert request["OrderDuration"]["DurationType"] == "DayOrder"

def test_request_id_uniqueness():
    """Test that request_id values are unique"""
    ids = {generate_request_id() for _ in range(1000)}
    assert len(ids) == 1000  # All unique

def test_generate_external_reference_length():
    """Test that generated external reference is always <= 50 chars"""
    ref = generate_external_reference("VERY_LONG_STRATEGY_ID_THAT_MIGHT_CAUSE_ISSUES", "Stock", 123456789)
    assert len(ref) <= 50
    assert ref.startswith("E005:")

def test_market_order_enforces_day_order():
    """Test that Market orders are forced to DayOrder duration"""
    intent = OrderIntent(
        client_key="client_123",
        account_key="acc_123",
        asset_type=AssetType.STOCK,
        uic=211,
        buy_sell=BuySell.BUY,
        amount=Decimal("100"),
        order_type=OrderType.MARKET,
    )
    # The default is DayOrder, so let's try to change it
    from execution.models import OrderDuration
    intent.order_duration = OrderDuration(OrderDurationType.GOOD_TILL_CANCEL)

    request = intent_to_saxo_order_request(intent)
    assert request["OrderDuration"]["DurationType"] == "DayOrder"
