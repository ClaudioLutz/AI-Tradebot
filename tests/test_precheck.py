import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from execution.precheck import PrecheckClient, PrecheckOutcome, ErrorInfo, RetryConfig
from execution.models import OrderIntent, AssetType, BuySell

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
        amount=100,
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

    assert outcome.ok
    assert outcome.estimated_cost.amount == Decimal("10.5")
    assert outcome.estimated_cost.currency == "USD"
    assert outcome.margin_impact_buy_sell.amount == Decimal("500")

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

    assert not outcome.ok
    assert outcome.error_info.error_code == "InsufficientFunds"
    assert outcome.error_info.message == "Not enough money"

def test_precheck_legacy_margin(mock_saxo_client, order_intent):
    """Test fallback for legacy MarginImpact field"""
    client = PrecheckClient(mock_saxo_client)

    mock_saxo_client.post.return_value = {
        "PreCheckResult": "Ok",
        "MarginImpact": {"Amount": 100, "Currency": "EUR"}
    }

    outcome = client.execute_precheck(order_intent)

    assert outcome.ok
    assert outcome.margin_impact_buy_sell.amount == Decimal("100")

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

    assert outcome.ok
    assert outcome.pre_trade_disclaimers.disclaimer_context == "ctx123"
    assert outcome.pre_trade_disclaimers.disclaimer_tokens == ["RISK_WARN"]

def test_http_exception_handling(mock_saxo_client, order_intent):
    """Test handling of HTTP exceptions from saxo client"""
    client = PrecheckClient(mock_saxo_client)

    # Simulate an exception that has a status_code attribute
    class SaxoError(Exception):
        status_code = 400

    mock_saxo_client.post.side_effect = SaxoError("Bad Request")

    outcome = client.execute_precheck(order_intent)

    assert not outcome.ok
    assert outcome.http_status == 400
    assert outcome.error_info.error_code == "HTTP_ERROR"

def test_retry_logic(mock_saxo_client, order_intent):
    """Test that retry happens on transient errors"""
    client = PrecheckClient(mock_saxo_client)

    # Configure retry to be fast
    client.retry_config = RetryConfig(max_retries=1, backoff_base_seconds=0.01)

    class SaxoTransientError(Exception):
        status_code = 503

    # First call fails with 503, second succeeds
    mock_saxo_client.post.side_effect = [
        SaxoTransientError("Service Unavailable"),
        {"PreCheckResult": "Ok"}
    ]

    outcome = client.execute_precheck(order_intent)

    assert outcome.ok
    assert mock_saxo_client.post.call_count == 2

def test_retry_exhaustion(mock_saxo_client, order_intent):
    """Test that retry gives up after max retries"""
    client = PrecheckClient(mock_saxo_client)
    client.retry_config = RetryConfig(max_retries=1, backoff_base_seconds=0.01)

    class SaxoTransientError(Exception):
        status_code = 503

    mock_saxo_client.post.side_effect = SaxoTransientError("Service Unavailable")

    outcome = client.execute_precheck(order_intent)

    assert not outcome.ok
    assert outcome.http_status == 503
    assert mock_saxo_client.post.call_count == 2  # Initial + 1 retry
