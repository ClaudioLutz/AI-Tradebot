import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout
from execution.placement import (
    OrderPlacementClient, PlacementConfig, PlacementStatus,
    ReconciliationStatus, ExecutionOutcome
)
from execution.models import OrderIntent, AssetType, BuySell
from execution.precheck import PrecheckOutcome, ErrorInfo

@pytest.fixture
def mock_saxo_client():
    return Mock()

@pytest.fixture
def order_intent():
    return OrderIntent(
        client_key="client_1",
        account_key="acc_1",
        asset_type=AssetType.STOCK,
        uic=211,
        buy_sell=BuySell.BUY,
        amount=100,
        external_reference="ref_1"
    )

@pytest.fixture
def successful_precheck():
    return PrecheckOutcome(ok=True)

def test_dry_run_skips_placement(mock_saxo_client, order_intent, successful_precheck):
    """Test DRY_RUN mode"""
    config = PlacementConfig(dry_run=True)
    client = OrderPlacementClient(mock_saxo_client, config)

    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "success"
    assert outcome.placement.order_id is None
    assert mock_saxo_client.post.call_count == 0

def test_failed_precheck_skips_placement(mock_saxo_client, order_intent):
    """Test failed precheck blocks placement"""
    failed_precheck = PrecheckOutcome(
        ok=False,
        error_info=ErrorInfo("ERR", "Msg")
    )
    client = OrderPlacementClient(mock_saxo_client)

    outcome = client.place_order(order_intent, failed_precheck)

    assert outcome.final_status == "failure"
    assert mock_saxo_client.post.call_count == 0

def test_placement_success(mock_saxo_client, order_intent, successful_precheck):
    """Test successful placement"""
    mock_saxo_client.post.return_value = {"OrderId": "12345"}
    client = OrderPlacementClient(mock_saxo_client)

    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "success"
    assert outcome.order_id == "12345"
    assert outcome.placement.status == PlacementStatus.SUCCESS

def test_placement_failure_error_info(mock_saxo_client, order_intent, successful_precheck):
    """Test placement failure with ErrorInfo"""
    mock_saxo_client.post.return_value = {
        "ErrorInfo": {"ErrorCode": "Fail", "Message": "Bad order"}
    }
    client = OrderPlacementClient(mock_saxo_client)

    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "failure"
    assert outcome.placement.status == PlacementStatus.FAILURE
    assert outcome.placement.error_info.error_code == "Fail"

def test_trade_not_completed_triggers_reconciliation(mock_saxo_client, order_intent, successful_precheck):
    """Test TradeNotCompleted triggers reconciliation"""
    # Placement returns TradeNotCompleted
    mock_saxo_client.post.return_value = {
        "ErrorInfo": {"ErrorCode": "TradeNotCompleted"},
        "OrderId": "12345"
    }

    # Reconciliation finds the order
    mock_saxo_client.get.return_value = {
        "Data": [{"OrderId": "12345", "Status": "Filled"}]
    }

    client = OrderPlacementClient(mock_saxo_client)
    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "success"
    assert outcome.reconciliation.status == ReconciliationStatus.FOUND_FILLED
    assert mock_saxo_client.get.called

def test_timeout_triggers_reconciliation_scan(mock_saxo_client, order_intent, successful_precheck):
    """Test timeout triggers reconciliation scan by external reference"""
    # Placement times out
    mock_saxo_client.post.side_effect = Timeout("Timeout")

    # Reconciliation scan finds order
    mock_saxo_client.get.return_value = {
        "Data": [
            {"OrderId": "999", "ExternalReference": "ref_1", "Status": "Working"}
        ]
    }

    client = OrderPlacementClient(mock_saxo_client)
    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "success"
    assert outcome.placement.status == PlacementStatus.TIMEOUT
    assert outcome.reconciliation.status == ReconciliationStatus.FOUND_WORKING
    assert outcome.order_id == "999"

def test_reconciliation_not_found(mock_saxo_client, order_intent, successful_precheck):
    """Test reconciliation fails to find order"""
    mock_saxo_client.post.side_effect = Timeout("Timeout")

    # Empty portfolio
    mock_saxo_client.get.return_value = {"Data": []}

    client = OrderPlacementClient(mock_saxo_client)
    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "failure"
    assert outcome.reconciliation.status == ReconciliationStatus.NOT_FOUND
