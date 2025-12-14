import pytest
from unittest.mock import Mock
from decimal import Decimal
from execution.precheck import PrecheckClient, RetryConfig
from execution.models import OrderIntent, AssetType, BuySell, PrecheckResult

@pytest.fixture
def mock_saxo_client():
    client = Mock()
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

def test_precheck_success(mock_saxo_client, order_intent):
    """Test successful precheck response parsing"""
    client = PrecheckClient(mock_saxo_client)

    mock_saxo_client.post.return_value = {
        "PreCheckResult": "Ok",
        "EstimatedCost": {"Amount": 10.5, "Currency": "USD"},
        "MarginImpactBuySell": {"Amount": 500, "Currency": "USD"}
    }

    outcome = client.execute_precheck(order_intent)

    assert outcome.success
    assert outcome.estimated_cost == 10.5
    assert outcome.estimated_currency == "USD"
    assert outcome.margin_impact == 500.0

def test_precheck_validation_failure(mock_saxo_client, order_intent):
    """Test precheck validation failure (HTTP 200 with ErrorInfo)"""
    client = PrecheckClient(mock_saxo_client)

    mock_saxo_client.post.return_value = {
        "PreCheckResult": "Error",
        "ErrorInfo": {
            "ErrorCode": "InsufficientFunds",
            "Message": "Not enough money"
        }
    }

    outcome = client.execute_precheck(order_intent)

    assert not outcome.success
    assert outcome.error_code == "InsufficientFunds"
    assert outcome.error_message == "Not enough money"

def test_precheck_legacy_margin(mock_saxo_client, order_intent):
    """Test fallback for legacy MarginImpact field"""
    client = PrecheckClient(mock_saxo_client)

    mock_saxo_client.post.return_value = {
        "PreCheckResult": "Ok",
        "MarginImpact": {"Amount": 100, "Currency": "EUR"}
    }

    outcome = client.execute_precheck(order_intent)

    assert outcome.success
    assert outcome.margin_impact == 100.0

def test_precheck_disclaimers(mock_saxo_client, order_intent):
    """Test parsing of PreTradeDisclaimers"""
    client = PrecheckClient(mock_saxo_client)

    mock_saxo_client.post.return_value = {
        "PreCheckResult": "Ok",
        "PreTradeDisclaimers": {
            "DisclaimerContext": "ctx123",
            "DisclaimerTokens": ["RISK_WARN"]
        }
    }

    outcome = client.execute_precheck(order_intent)

    assert outcome.success
    assert outcome.disclaimer_context == "ctx123"
    assert outcome.disclaimer_tokens == ["RISK_WARN"]

def test_http_exception_handling(mock_saxo_client, order_intent):
    """Test handling of HTTP exceptions from saxo client"""
    client = PrecheckClient(mock_saxo_client)

    class SaxoError(Exception):
        status_code = 400

    mock_saxo_client.post.side_effect = SaxoError("Bad Request")

    outcome = client.execute_precheck(order_intent)

    assert not outcome.success
    assert outcome.error_code == "HTTP_400"
    assert "Bad Request" in outcome.error_message
