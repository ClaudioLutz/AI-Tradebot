"""
Tests for trade execution module.
"""
from unittest.mock import Mock, patch, MagicMock
import pytest
from decimal import Decimal
from execution.trade_executor import SaxoTradeExecutor, OrderIntent, ExecutionStatus
from execution.models import AssetType, BuySell, PrecheckResult, ExecutionResult
from execution.placement import ExecutionOutcome, PlacementStatus
from execution.position import PositionGuardResult
from execution.disclaimers import DisclaimerResolutionOutcome, DisclaimerPolicy

@pytest.fixture
def mock_saxo_client():
    return Mock()

@pytest.fixture
def valid_intent():
    return OrderIntent(
        client_key="client_key",
        account_key="acc_key",
        asset_type=AssetType.STOCK,
        uic=12345,
        buy_sell=BuySell.BUY,
        amount=Decimal(100),
        external_reference="ref_1"
    )

@patch("execution.trade_executor.InstrumentValidator")
@patch("execution.trade_executor.PositionAwareGuards")
@patch("execution.trade_executor.PrecheckClient")
@patch("execution.trade_executor.DisclaimerService")
@patch("execution.trade_executor.OrderPlacementClient")
def test_place_order(
    mock_placement_class,
    mock_disclaimer_class,
    mock_precheck_class,
    mock_guards_class,
    mock_validator_class,
    mock_saxo_client,
    valid_intent
):
    """Test order placement through SaxoTradeExecutor."""

    # 1. Instantiate executor within the test to ensure patches are applied during __init__
    executor = SaxoTradeExecutor(mock_saxo_client, account_key="acc_key", client_key="client_key")

    # Setup Validator Mock
    executor.validator.validate_order_intent.return_value = (True, "")

    # Setup Guards
    executor.guards.evaluate_buy_intent.return_value = PositionGuardResult(allowed=True, reason="ok")

    # Setup Precheck
    precheck_result = PrecheckResult(success=True)
    executor.precheck_client.execute_precheck.return_value = precheck_result

    # Setup Disclaimers
    executor.disclaimer_service.evaluate_disclaimers.return_value = DisclaimerResolutionOutcome(
        allow_trading=True,
        blocking_disclaimers=[],
        normal_disclaimers=[],
        auto_accepted=[],
        errors=[],
        policy_applied=DisclaimerPolicy.AUTO_ACCEPT_NORMAL
    )

    # Setup Placement
    # OrderPlacementClient is instantiated inside execute()
    placement_client_instance = mock_placement_class.return_value
    placement_client_instance.place_order.return_value = ExecutionOutcome(
        final_status="success",
        order_id="ORDER_123",
        placement=PlacementStatus(http_status=200)
    )

    # 2. Execute
    result = executor.execute(valid_intent, dry_run=False)

    # 3. Verify
    assert result.status == ExecutionStatus.SUCCESS
    assert result.order_id == "ORDER_123"
    assert result.error_message is None

    # Verify calls
    executor.validator.validate_order_intent.assert_called_once_with(valid_intent)
    executor.guards.evaluate_buy_intent.assert_called_once()
    executor.precheck_client.execute_precheck.assert_called_once_with(valid_intent)
    executor.disclaimer_service.evaluate_disclaimers.assert_called_once()

    # Verify Placement Client was instantiated and called
    # Note: mock_placement_class is the Class, so we check if it was called (instantiated)
    mock_placement_class.assert_called_once()
    placement_client_instance.place_order.assert_called_once_with(valid_intent, precheck_result)

def test_get_positions():
    """Test position retrieval."""
    # TODO: Implement test
    pass

def test_close_position():
    """Test position closing."""
    # TODO: Implement test
    pass
