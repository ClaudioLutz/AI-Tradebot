import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from execution.models import OrderIntent, AssetType, BuySell, PrecheckResult, MarketState, OrderType
from execution.validation import InstrumentConstraints
from execution.disclaimers import DisclaimerService, DisclaimerDetails, DisclaimerConfig, DisclaimerPolicy
from execution.placement import OrderPlacementClient

# 1. Decimal Test
def test_decimal_amount_validation():
    """Verify that validation works with Decimal amounts"""
    constraints = InstrumentConstraints(
        is_tradable=True,
        amount_decimals=2,
        uic=211,
        asset_type="Stock"
    )

    # Valid Decimal
    amount = Decimal("100.50")
    is_valid, error = constraints.validate_amount(amount)
    assert is_valid, f"Decimal validation failed: {error}"

    # Invalid Decimal (too many decimals)
    amount_bad = Decimal("100.505")
    is_valid, error = constraints.validate_amount(amount_bad)
    assert not is_valid
    assert "decimals" in error.lower()

# 2. Market State Test
def test_market_state_gating():
    """Verify market state gating"""
    # Open - Valid
    c1 = InstrumentConstraints(is_tradable=True, market_state=MarketState.OPEN)
    assert c1.validate_market_state()[0] is True

    # Auction - Invalid
    c2 = InstrumentConstraints(is_tradable=True, market_state=MarketState.OPENING_AUCTION)
    assert c2.validate_market_state()[0] is False

    # Closed - Invalid
    c3 = InstrumentConstraints(is_tradable=True, market_state=MarketState.CLOSED)
    assert c3.validate_market_state()[0] is False

    # Pre/Post Market - Invalid (New Logic)
    c4 = InstrumentConstraints(is_tradable=True, market_state=MarketState.PRE_MARKET)
    assert c4.validate_market_state()[0] is False

    c5 = InstrumentConstraints(is_tradable=True, market_state=MarketState.POST_MARKET)
    assert c5.validate_market_state()[0] is False

# 3. Disclaimer Conditions Test
def test_disclaimer_conditions_prevent_auto_accept():
    """Verify disclaimers with conditions are not auto-accepted"""
    mock_client = Mock()
    config = DisclaimerConfig()
    config.policy = DisclaimerPolicy.AUTO_ACCEPT_NORMAL
    service = DisclaimerService(mock_client, config=config)

    # Mock details with conditions
    token = "condition_token"
    details = DisclaimerDetails(
        disclaimer_token=token,
        is_blocking=False,
        title="Test",
        body="Body",
        response_options=[{"Value": "Accepted"}],
        conditions=[{"Title": "Accept Terms", "Type": "Checkbox"}],
        retrieved_at=None
    )
    service._cache[token] = (details, 9999999999)

    intent = OrderIntent("k", "a", AssetType.STOCK, 1, BuySell.BUY, Decimal(100))
    precheck = PrecheckResult(
        success=True,
        disclaimer_tokens=[token],
        disclaimer_context="ctx"
    )

    # Override fetch to return cached list
    service._fetch_disclaimer_details_batch = Mock(return_value=[details])

    outcome = service.evaluate_disclaimers(precheck, intent)

    # Should NOT be auto-accepted because of conditions
    assert not outcome.allow_trading
    assert not outcome.auto_accepted
    assert outcome.errors # Should contain error about conditions

# 4. Placement Reconciliation URL
def test_placement_reconciliation_url():
    """Verify direct reconciliation URL is used"""
    mock_client = Mock()
    mock_client.post.side_effect = Exception("Network Error")

    placer = OrderPlacementClient(mock_client)

    intent = OrderIntent("client_k", "acc_k", AssetType.STOCK, 1, BuySell.BUY, Decimal(100))
    intent.external_reference = "ref123"

    mock_client.reset_mock()
    mock_client.get.return_value = {"OrderId": "123", "Status": "Placed"}

    outcome = placer._reconcile_by_order_id("123", intent)

    mock_client.get.assert_called_with("/port/v1/orders/client_k/123")
    assert outcome.final_status == "success"
