from decimal import Decimal
from unittest.mock import Mock
from execution.intent_mapper import signal_to_intent
from execution.models import OrderIntent, BuySell, AssetType
from config.runtime_config import RuntimeConfig
from execution.position import Position

def test_signal_to_intent_buy():
    signal = Mock()
    signal.action = "BUY"
    signal.strategy_id = "test_strat"

    instrument = {"asset_type": "Stock", "uic": 123}

    cfg = Mock(spec=RuntimeConfig)
    cfg.default_quantity = Decimal("10")
    cfg.account_key = "acc"
    cfg.client_key = "cli"

    pm = Mock()

    intent = signal_to_intent(signal, instrument, cfg, pm)

    assert intent.buy_sell == BuySell.BUY
    assert intent.amount == Decimal("10")
    assert intent.uic == 123
    assert intent.asset_type == AssetType.STOCK

def test_signal_to_intent_sell_no_position():
    signal = Mock()
    signal.action = "SELL"

    instrument = {"asset_type": "Stock", "uic": 123}
    cfg = Mock(spec=RuntimeConfig)
    pm = Mock()
    pm.get_position.return_value = None

    intent = signal_to_intent(signal, instrument, cfg, pm)
    assert intent is None

def test_signal_to_intent_sell_with_position():
    signal = Mock()
    signal.action = "SELL"
    signal.strategy_id = "test_strat"

    instrument = {"asset_type": "Stock", "uic": 123}
    cfg = Mock(spec=RuntimeConfig)
    cfg.account_key = "acc"
    cfg.client_key = "cli"

    pm = Mock()
    pos = Mock(spec=Position)
    pos.net_quantity = Decimal("50")
    pm.get_position.return_value = pos

    intent = signal_to_intent(signal, instrument, cfg, pm)

    assert intent.buy_sell == BuySell.SELL
    assert intent.amount == Decimal("50")
    assert intent.uic == 123
