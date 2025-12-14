import pytest
from unittest.mock import Mock, patch
from execution.disclaimers import (
    DisclaimerService, DisclaimerConfig, DisclaimerPolicy,
    DisclaimerDetails, DisclaimerResolutionOutcome
)
from execution.models import OrderIntent, AssetType, BuySell
from execution.precheck import PrecheckOutcome, PreTradeDisclaimers
from datetime import datetime

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

def test_no_disclaimers_allows_trading(mock_saxo_client, order_intent):
    service = DisclaimerService(mock_saxo_client)
    precheck_outcome = PrecheckOutcome(ok=True, pre_trade_disclaimers=None)

    outcome = service.evaluate_disclaimers(precheck_outcome, order_intent)

    assert outcome.allow_trading
    assert not outcome.blocking_disclaimers
    assert not outcome.normal_disclaimers

def test_blocking_disclaimer_blocks_trading(mock_saxo_client, order_intent):
    """Test that blocking disclaimers always block trading"""
    service = DisclaimerService(mock_saxo_client)

    precheck_outcome = PrecheckOutcome(
        ok=True,
        pre_trade_disclaimers=PreTradeDisclaimers(
            disclaimer_context="ctx",
            disclaimer_tokens=["BLOCKING_TOKEN"]
        )
    )

    # Mock DM response: IsBlocking=True
    mock_saxo_client.get.return_value = {
        "Data": [{
            "DisclaimerToken": "BLOCKING_TOKEN",
            "IsBlocking": True,
            "Title": "Blocking Warning",
            "Body": "Risk..."
        }]
    }

    outcome = service.evaluate_disclaimers(precheck_outcome, order_intent)

    assert not outcome.allow_trading
    assert len(outcome.blocking_disclaimers) == 1
    assert outcome.blocking_disclaimers[0].token == "BLOCKING_TOKEN"

def test_normal_disclaimer_blocks_by_default(mock_saxo_client, order_intent):
    """Test BLOCK_ALL policy blocks even normal disclaimers"""
    config = DisclaimerConfig(policy=DisclaimerPolicy.BLOCK_ALL)
    service = DisclaimerService(mock_saxo_client, config)

    precheck_outcome = PrecheckOutcome(
        ok=True,
        pre_trade_disclaimers=PreTradeDisclaimers(
            disclaimer_context="ctx",
            disclaimer_tokens=["NORMAL_TOKEN"]
        )
    )

    # Mock DM response: IsBlocking=False
    mock_saxo_client.get.return_value = {
        "Data": [{
            "DisclaimerToken": "NORMAL_TOKEN",
            "IsBlocking": False,
            "Title": "Normal Warning",
            "Body": "Info..."
        }]
    }

    outcome = service.evaluate_disclaimers(precheck_outcome, order_intent)

    assert not outcome.allow_trading
    assert len(outcome.normal_disclaimers) == 1

def test_auto_accept_normal_disclaimers(mock_saxo_client, order_intent):
    """Test AUTO_ACCEPT_NORMAL policy accepts normal disclaimers"""
    config = DisclaimerConfig(policy=DisclaimerPolicy.AUTO_ACCEPT_NORMAL)
    service = DisclaimerService(mock_saxo_client, config)

    precheck_outcome = PrecheckOutcome(
        ok=True,
        pre_trade_disclaimers=PreTradeDisclaimers(
            disclaimer_context="ctx",
            disclaimer_tokens=["NORMAL_TOKEN"]
        )
    )

    # Mock DM response: IsBlocking=False
    mock_saxo_client.get.return_value = {
        "Data": [{
            "DisclaimerToken": "NORMAL_TOKEN",
            "IsBlocking": False,
            "Title": "Normal Warning",
            "Body": "Info..."
        }]
    }

    outcome = service.evaluate_disclaimers(precheck_outcome, order_intent)

    assert outcome.allow_trading
    assert len(outcome.auto_accepted) == 1
    assert outcome.auto_accepted[0] == "NORMAL_TOKEN"
    assert mock_saxo_client.post.called

def test_auto_accept_refuses_blocking(mock_saxo_client, order_intent):
    """Test AUTO_ACCEPT_NORMAL never accepts blocking disclaimers"""
    config = DisclaimerConfig(policy=DisclaimerPolicy.AUTO_ACCEPT_NORMAL)
    service = DisclaimerService(mock_saxo_client, config)

    precheck_outcome = PrecheckOutcome(
        ok=True,
        pre_trade_disclaimers=PreTradeDisclaimers(
            disclaimer_context="ctx",
            disclaimer_tokens=["BLOCKING_TOKEN"]
        )
    )

    # Mock DM response: IsBlocking=True
    mock_saxo_client.get.return_value = {
        "Data": [{
            "DisclaimerToken": "BLOCKING_TOKEN",
            "IsBlocking": True,
            "Title": "Blocking Warning",
            "Body": "Risk..."
        }]
    }

    outcome = service.evaluate_disclaimers(precheck_outcome, order_intent)

    # Should still block
    assert not outcome.allow_trading
    assert len(outcome.blocking_disclaimers) == 1
    assert len(outcome.auto_accepted) == 0
    # Should NOT have called post to accept
    assert not mock_saxo_client.post.called

def test_cache_behavior(mock_saxo_client, order_intent):
    """Test disclaimer details caching"""
    service = DisclaimerService(mock_saxo_client)

    mock_saxo_client.get.return_value = {
        "Data": [{
            "DisclaimerToken": "TOKEN",
            "IsBlocking": False
        }]
    }

    # First call
    service._get_disclaimer_details("TOKEN")
    assert mock_saxo_client.get.call_count == 1

    # Second call (cached)
    service._get_disclaimer_details("TOKEN")
    assert mock_saxo_client.get.call_count == 1
