import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout
from decimal import Decimal
from execution.placement import (
    OrderPlacementClient, PlacementConfig, PlacementStatus,
    ExecutionOutcome
)
from execution.models import OrderIntent, AssetType, BuySell, PrecheckResult

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
        amount=Decimal(100),
        external_reference="ref_1"
    )

@pytest.fixture
def successful_precheck():
    return PrecheckResult(success=True)

def test_dry_run_skips_placement(mock_saxo_client, order_intent, successful_precheck):
    """Test DRY_RUN mode"""
    config = PlacementConfig(dry_run=True)
    client = OrderPlacementClient(mock_saxo_client, config)

    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "success"
    assert outcome.order_id == "DRY_RUN_ID"
    assert mock_saxo_client.post.call_count == 0

def test_failed_precheck_skips_placement(mock_saxo_client, order_intent):
    """Test failed precheck blocks placement"""
    failed_precheck = PrecheckResult(success=False)
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

def test_trade_not_completed_triggers_reconciliation(mock_saxo_client, order_intent, successful_precheck):
    """Test TradeNotCompleted (or missing OrderId) triggers reconciliation"""
    # Placement returns no OrderId
    mock_saxo_client.post.return_value = {
        "ErrorInfo": {"ErrorCode": "TradeNotCompleted"}
    }

    # Reconciliation finds the order
    mock_saxo_client.get.return_value = {
        "Data": [{"OrderId": "12345", "Status": "Filled", "ExternalReference": "ref_1"}]
    }

    client = OrderPlacementClient(mock_saxo_client)
    outcome = client.place_order(order_intent, successful_precheck)

    assert outcome.final_status == "success"
    assert outcome.order_id == "12345"
    assert outcome.reconciliation is not None
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
    assert outcome.order_id == "999"
    assert outcome.reconciliation is not None
