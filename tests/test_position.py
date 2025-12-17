import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from execution.position import (
    PositionManager, PositionAwareGuards, ExecutionConfig,
    Position, PositionGuardResult
)
from datetime import datetime

@pytest.fixture
def mock_saxo_client():
    return Mock()

@pytest.fixture
def position_manager(mock_saxo_client):
    return PositionManager(mock_saxo_client, "client_123")

@pytest.fixture
def guards(position_manager):
    config = ExecutionConfig()
    return PositionAwareGuards(position_manager, config)

def test_fetch_positions_success(mock_saxo_client, position_manager):
    """Test successful fetching and caching of positions"""
    mock_saxo_client.get.return_value = {
        "Data": [
            {
                "NetPositionId": "pos1",
                "NetPositionBase": {
                    "AssetType": "Stock",
                    "Uic": 211,
                    "Amount": 100,
                    "AccountKey": "acc1",
                    "Currency": "USD",
                    "CanBeClosed": True
                },
                "NetPositionView": {
                    "AverageOpenPrice": 150.0,
                    "MarketValue": 15000.0,
                    "ProfitLossOnTrade": 500.0
                }
            }
        ]
    }

    positions = position_manager.get_positions()

    assert len(positions) == 1
    pos = positions[("Stock", 211)]
    assert pos.net_quantity == Decimal("100")
    assert pos.average_price == Decimal("150.0")
    assert pos.uic == 211

    # Test Caching
    mock_saxo_client.get.reset_mock()
    positions_cached = position_manager.get_positions()
    assert positions_cached == positions
    assert mock_saxo_client.get.call_count == 0

def test_guard_buy_no_position(guards, position_manager):
    """Test buy allowed when no position exists"""
    with patch.object(position_manager, 'get_positions', return_value={}):
        result = guards.evaluate_buy_intent("Stock", 211, Decimal("100"))

    assert result.allowed
    assert result.reason == "no_existing_position"

def test_guard_buy_duplicate_blocked(guards, position_manager):
    """Test buy blocked when position already exists"""
    pos = Position(
        asset_type="Stock", uic=211, account_key="acc1", position_id="p1",
        net_quantity=Decimal("100"), average_price=Decimal("10"),
        market_value=Decimal("1000"), unrealized_pnl=Decimal("0"), currency="USD"
    )

    with patch.object(position_manager, 'get_positions', return_value={("Stock", 211): pos}):
        result = guards.evaluate_buy_intent("Stock", 211, Decimal("100"))

    assert not result.allowed
    assert result.reason == "duplicate_buy_prevented"

def test_guard_sell_no_position(guards, position_manager):
    """Test sell blocked when no position exists"""
    with patch.object(position_manager, 'get_positions', return_value={}):
        result = guards.evaluate_sell_intent("Stock", 211, Decimal("100"))

    assert not result.allowed
    assert result.reason == "no_position_to_sell"

def test_guard_sell_valid_position(guards, position_manager):
    """Test sell allowed when position exists"""
    pos = Position(
        asset_type="Stock", uic=211, account_key="acc1", position_id="p1",
        net_quantity=Decimal("100"), average_price=Decimal("10"),
        market_value=Decimal("1000"), unrealized_pnl=Decimal("0"), currency="USD"
    )

    with patch.object(position_manager, 'get_positions', return_value={("Stock", 211): pos}):
        # Partial sell
        result = guards.evaluate_sell_intent("Stock", 211, Decimal("50"))
        assert result.allowed
        assert result.position_quantity == Decimal("50")

        # Full sell (None quantity)
        result_full = guards.evaluate_sell_intent("Stock", 211, None)
        assert result_full.allowed
        assert result_full.position_quantity == Decimal("100")

def test_guard_sell_short_blocked(guards, position_manager):
    """Test selling a short position is blocked (requires Buy to close)"""
    pos = Position(
        asset_type="Stock", uic=211, account_key="acc1", position_id="p1",
        net_quantity=Decimal("-100"), average_price=Decimal("10"),
        market_value=Decimal("-1000"), unrealized_pnl=Decimal("0"), currency="USD"
    )

    with patch.object(position_manager, 'get_positions', return_value={("Stock", 211): pos}):
        result = guards.evaluate_sell_intent("Stock", 211, Decimal("100"))

    assert not result.allowed
    assert result.reason == "position_is_short"

def test_guard_buy_cover_short(guards, position_manager):
    """Test buy to cover short (disabled by default)"""
    pos = Position(
        asset_type="Stock", uic=211, account_key="acc1", position_id="p1",
        net_quantity=Decimal("-100"), average_price=Decimal("10"),
        market_value=Decimal("-1000"), unrealized_pnl=Decimal("0"), currency="USD"
    )

    with patch.object(position_manager, 'get_positions', return_value={("Stock", 211): pos}):
        # Default config: allow_short_covering = False
        result = guards.evaluate_buy_intent("Stock", 211, Decimal("100"))
        assert not result.allowed
        assert result.reason == "short_covering_not_configured"

        # Enable short covering
        guards.config.allow_short_covering = True
        result_enabled = guards.evaluate_buy_intent("Stock", 211, Decimal("100"))
        assert result_enabled.allowed
        assert result_enabled.reason == "reducing_short_position"
