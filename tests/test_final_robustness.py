import pytest
import unittest.mock
from unittest.mock import Mock, MagicMock
from decimal import Decimal
from execution.trade_executor import SaxoTradeExecutor
from execution.models import OrderIntent, AssetType, BuySell, ExecutionStatus, PrecheckResult, MarketState
from execution.validation import InstrumentValidator
from execution.placement import ExecutionOutcome

@pytest.fixture
def mock_saxo_client():
    client = Mock()
    # Basic mock setup
    client.get.return_value = {
        "IsTradable": True,
        "Format": {"Decimals": 0},
        "SupportedOrderTypes": [{"OrderType": "Market", "DurationTypes": ["DayOrder"]}],
        "TradingStatus": {"MarketState": "Open"}
    }
    client.client_key = "ck"
    return client

def test_dry_run_short_circuit(mock_saxo_client):
    """Test that DRY_RUN does not instantiate placement client"""
    executor = SaxoTradeExecutor(mock_saxo_client, "ak", "ck")

    # Mock precheck to pass
    executor.precheck_client = MagicMock()
    executor.precheck_client.execute_precheck.return_value = PrecheckResult(success=True, request_id="req1")
    executor.validator = MagicMock()
    executor.validator.validate_order_intent.return_value = (True, None)
    executor.guards = MagicMock()
    executor.guards.evaluate_buy_intent.return_value = MagicMock(allowed=True)
    executor.disclaimer_service = MagicMock()
    executor.disclaimer_service.evaluate_disclaimers.return_value = MagicMock(allow_trading=True)

    intent = OrderIntent("ck", "ak", AssetType.STOCK, 1, BuySell.BUY, Decimal(100))
    intent.external_reference = "ref"

    # Patch OrderPlacementClient to ensure it's NOT called
    with unittest.mock.patch("execution.trade_executor.OrderPlacementClient") as mock_placer_cls:
        result = executor.execute(intent, dry_run=True)

        assert result.status == ExecutionStatus.DRY_RUN
        mock_placer_cls.assert_not_called()

    # Also verify request_id propagated
    assert intent.request_id == "req1"

def test_invariant_enforcement(mock_saxo_client):
    """Test mismatching keys are overridden"""
    executor = SaxoTradeExecutor(mock_saxo_client, "ak", "ck")
    intent = OrderIntent("wrong_ck", "wrong_ak", AssetType.STOCK, 1, BuySell.BUY, Decimal(100))
    intent.external_reference = "ref"

    # Mock validation/guards
    executor.validator = MagicMock()
    executor.validator.validate_order_intent.return_value = (True, None)
    executor.guards = MagicMock()
    executor.guards.evaluate_buy_intent.return_value = MagicMock(allowed=True)
    executor.precheck_client = MagicMock()
    executor.precheck_client.execute_precheck.return_value = PrecheckResult(success=True)
    executor.disclaimer_service = MagicMock()
    executor.disclaimer_service.evaluate_disclaimers.return_value = MagicMock(allow_trading=True)

    executor.execute(intent, dry_run=True)

    assert intent.client_key == "ck"
    assert intent.account_key == "ak"

def test_market_state_block_status(mock_saxo_client):
    """Test market state block maps to correct status"""
    executor = SaxoTradeExecutor(mock_saxo_client, "ak", "ck")
    intent = OrderIntent("ck", "ak", AssetType.STOCK, 1, BuySell.BUY, Decimal(100))

    executor.validator = MagicMock()
    executor.validator.validate_order_intent.return_value = (False, "Market state is Unknown")

    result = executor.execute(intent, dry_run=True)

    assert result.status == ExecutionStatus.BLOCKED_BY_MARKET_STATE

def test_validator_default_fail(mock_saxo_client):
    """Test validator defaults is_tradable to False if missing"""
    validator = InstrumentValidator(mock_saxo_client)

    mock_saxo_client.get.return_value = {
        # Missing IsTradable
        "Format": {"Decimals": 0}
    }

    constraints = validator.get_instrument_details(1, "Stock")
    assert constraints.is_tradable is False
