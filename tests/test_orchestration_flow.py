
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import json
import os
from decimal import Decimal

from main import run_cycle, log_execution_jsonl
from config.runtime_config import RuntimeConfig
from execution.models import ExecutionStatus, OrderIntent, ExecutionResult, AssetType, BuySell
from strategies.base import Signal

class TestOrchestrationFlow(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_config = RuntimeConfig(
            saxo_env="SIM",
            saxo_auth_mode="manual",
            account_key="acc_123",
            client_key="cli_123",
            watchlist=[
                {"symbol": "AAPL", "asset_type": "Stock", "uic": 211},
            ],
            cycle_interval_seconds=60,
            trading_hours_mode="always",
            default_quantity=Decimal("10"),
            max_positions=5,
            max_daily_trades=10,
            max_position_size=1000,
            max_daily_loss=100,
            stop_loss_percent=1.0,
            take_profit_percent=2.0
        )

        # Reset state file
        if os.path.exists("state/trade_counter.json"):
            os.remove("state/trade_counter.json")

    @patch("main.get_latest_quotes")
    @patch("main.get_strategy")
    @patch("main.SaxoTradeExecutor")
    @patch("data.market_data.get_ohlc_bars")
    @patch("data.market_data.should_trade_given_market_state")
    def test_run_cycle_full_flow(self, mock_should_trade, mock_get_bars, mock_executor_cls, mock_get_strategy, mock_get_quotes):
        # 1. Setup Market Data Mock
        mock_get_quotes.return_value = {
            "Stock:211": {
                "instrument_id": "Stock:211",
                "symbol": "AAPL",
                "uic": 211,
                "asset_type": "Stock",
                "quote": {"market_state": "Open", "bid": 150.0, "ask": 151.0},
                "freshness": {"is_stale": False}
            }
        }
        mock_should_trade.return_value = True
        mock_get_bars.return_value = {"bars": [{"time": "2023-01-01T00:00:00Z", "close": 150}]}

        # 2. Setup Strategy Mock
        mock_strategy = MagicMock()
        mock_get_strategy.return_value = mock_strategy
        mock_strategy.requires_bars.return_value = True
        mock_strategy.bar_requirements.return_value = (60, 60)

        now = datetime.now(timezone.utc)
        signal = Signal(
            action="BUY",
            reason="TEST_SIGNAL",
            timestamp=now.isoformat(),
            decision_time=now.isoformat()
        )
        mock_strategy.generate_signals.return_value = {"Stock:211": signal}

        # 3. Setup Executor Mock
        mock_executor = mock_executor_cls.return_value
        mock_executor.position_manager.get_positions.return_value = {} # No existing positions

        mock_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            order_intent=None, # Will be filled by actual logic, but here result is return value
            order_id="ord_123",
            request_id="req_123",
            error_message=None
        )
        mock_executor.execute.return_value = mock_result

        # 4. Run Cycle
        run_cycle(self.mock_config, self.mock_client, dry_run=True)

        # 5. Assertions

        # Check quotes fetched
        mock_get_quotes.assert_called_once()

        # Check strategy called
        mock_strategy.generate_signals.assert_called_once()

        # Check executor initialized and called
        mock_executor_cls.assert_called_once()
        mock_executor.execute.assert_called_once()

        # Check Intent details
        call_args = mock_executor.execute.call_args
        intent = call_args[0][0]
        self.assertEqual(intent.buy_sell, BuySell.BUY)
        self.assertEqual(intent.asset_type, AssetType.STOCK)
        self.assertEqual(intent.uic, 211)
        self.assertEqual(intent.amount, Decimal("10")) # Default quantity

    @patch("main.get_latest_quotes")
    @patch("main.get_strategy")
    @patch("main.SaxoTradeExecutor")
    def test_risk_limit_max_daily_trades(self, mock_executor_cls, mock_get_strategy, mock_get_quotes):
        # Pre-fill trade counter
        os.makedirs("state", exist_ok=True)
        with open("state/trade_counter.json", "w") as f:
            # Use current UTC date
            today = datetime.now(timezone.utc).date().isoformat()
            json.dump({"date": today, "count": 10}, f)

        mock_get_quotes.return_value = {
            "Stock:211": {
                "instrument_id": "Stock:211",
                "symbol": "AAPL", "uic": 211, "asset_type": "Stock",
                "quote": {"market_state": "Open"}, "freshness": {"is_stale": False}
            }
        }

        mock_strategy = MagicMock()
        mock_get_strategy.return_value = mock_strategy
        signal = Signal(action="BUY", reason="TEST", timestamp="2023-01-01", decision_time="2023-01-01")
        mock_strategy.generate_signals.return_value = {"Stock:211": signal}

        mock_executor = mock_executor_cls.return_value
        mock_executor.position_manager.get_positions.return_value = {}

        # Run
        run_cycle(self.mock_config, self.mock_client, dry_run=True)

        # Executor should NOT be called because max daily trades reached (10 >= 10)
        # Wait, run_cycle checks daily trades at start now.
        # But also checks inside the loop.
        # If it returns early, execute is not called.
        mock_executor.execute.assert_not_called()

if __name__ == '__main__':
    unittest.main()
