import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from execution.trade_executor import SaxoTradeExecutor
from execution.models import OrderIntent, AssetType, BuySell, ExecutionStatus, PrecheckResult
import logging

@pytest.fixture
def mock_saxo_client():
    client = Mock()
    # Mock instrument details for validation
    # Updated to include MarketState because updated validation requires it
    client.get.return_value = {
        "IsTradable": True,
        "Format": {"Decimals": 0},
        "SupportedOrderTypes": [{"OrderType": "Market", "DurationTypes": ["DayOrder"]}],
        "TradingStatus": {"MarketState": "Open"}
    }
    return client

@pytest.fixture
def order_intent():
    return OrderIntent(
        client_key="client_1",
        account_key="acc_1",
        asset_type=AssetType.STOCK,
        uic=211,
        buy_sell=BuySell.BUY,
        amount=Decimal(100),
        external_reference="ref_1"
    )

def test_execution_dry_run(mock_saxo_client, order_intent):
    """Test full execution flow in DRY_RUN mode"""
    executor = SaxoTradeExecutor(mock_saxo_client, "acc_1", "client_1")

    # Mock position (no position)
    with patch("execution.position.PositionManager.get_positions", return_value={}):
        # Mock precheck success
        with patch("execution.precheck.PrecheckClient.execute_precheck",
                   return_value=PrecheckResult(success=True)):

            result = executor.execute(order_intent, dry_run=True)

            assert result.status == ExecutionStatus.DRY_RUN
            assert result.order_id == "DRY_RUN_ID"
            # Verify placement was NOT called (mock client post not called for order)

def test_execution_success(mock_saxo_client, order_intent):
    """Test successful execution in SIM mode"""
    executor = SaxoTradeExecutor(mock_saxo_client, "acc_1", "client_1")

    with patch("execution.position.PositionManager.get_positions", return_value={}):
        with patch("execution.precheck.PrecheckClient.execute_precheck",
                   return_value=PrecheckResult(success=True)):
            # Mock placement response
            mock_saxo_client.post.return_value = {"OrderId": "12345"}

            result = executor.execute(order_intent, dry_run=False)

            assert result.status == ExecutionStatus.SUCCESS
            assert result.order_id == "12345"

def test_execution_validation_fail(mock_saxo_client, order_intent):
    """Test execution fails validation"""
    executor = SaxoTradeExecutor(mock_saxo_client, "acc_1", "client_1")

    # Mock validation fail
    with patch("execution.validation.InstrumentValidator.validate_order_intent",
               return_value=(False, "Bad Instrument")):

        result = executor.execute(order_intent, dry_run=False)

        assert result.status == ExecutionStatus.FAILED_PRECHECK
        assert "validation failed" in result.error_message

def test_execution_position_guard_fail(mock_saxo_client, order_intent):
    """Test execution blocked by position guard"""
    executor = SaxoTradeExecutor(mock_saxo_client, "acc_1", "client_1")

    # Mock position guard fail
    with patch("execution.position.PositionAwareGuards.evaluate_buy_intent") as mock_guard:
        mock_guard.return_value.allowed = False
        mock_guard.return_value.reason = "Duplicate Buy"

        # We need validation to pass
        with patch("execution.validation.InstrumentValidator.validate_order_intent",
                   return_value=(True, None)):

            result = executor.execute(order_intent, dry_run=False)

            assert result.status == ExecutionStatus.BLOCKED_BY_POSITION
            assert "Duplicate Buy" in result.error_message

def test_execution_precheck_fail(mock_saxo_client, order_intent):
    """Test execution fails precheck"""
    executor = SaxoTradeExecutor(mock_saxo_client, "acc_1", "client_1")

    with patch("execution.position.PositionManager.get_positions", return_value={}):
        with patch("execution.precheck.PrecheckClient.execute_precheck",
                   return_value=PrecheckResult(success=False, error_code="ERR", error_message="Fail")):

             result = executor.execute(order_intent, dry_run=False)

             assert result.status == ExecutionStatus.FAILED_PRECHECK
             assert "Fail" in result.error_message

def test_execution_disclaimer_block(mock_saxo_client, order_intent):
    """Test execution blocked by disclaimers"""
    executor = SaxoTradeExecutor(mock_saxo_client, "acc_1", "client_1")

    with patch("execution.position.PositionManager.get_positions", return_value={}):
        with patch("execution.precheck.PrecheckClient.execute_precheck",
                   return_value=PrecheckResult(success=True)):

            # Mock disclaimer service blocking
            with patch("execution.disclaimers.DisclaimerService.evaluate_disclaimers") as mock_disc:
                mock_disc.return_value.allow_trading = False
                mock_disc.return_value.blocking_disclaimers = [Mock(token="BLK")]
                mock_disc.return_value.normal_disclaimers = []
                mock_disc.return_value.errors = []
                mock_disc.return_value.policy_applied = Mock(value="BLOCK_ALL")

                result = executor.execute(order_intent, dry_run=False)

                assert result.status == ExecutionStatus.BLOCKED_BY_DISCLAIMER
                assert "Blocking" in result.error_message
