# Story 006-007: Integration Testing

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 5 Story Points  
**Priority:** Medium

## User Story
As a **developer**, I want **comprehensive integration tests for the main orchestration script** so that I can **validate the end-to-end workflow and catch integration issues before production**.

## Acceptance Criteria
- [ ] Integration test suite created (`tests/test_main_integration.py`)
- [ ] Tests cover complete trading cycle workflow
- [ ] Tests validate configuration → data → signals → execution flow
- [ ] Tests use mocked Saxo API responses
- [ ] Tests verify DRY_RUN vs SIM mode behavior
- [ ] Tests validate single-cycle vs continuous mode
- [ ] Tests verify error handling and recovery
- [ ] Tests can run in CI/CD pipeline
- [ ] All tests pass successfully

## Technical Details

### Test Structure
```python
# tests/test_main_integration.py
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import (
    main,
    run_cycle,
    run_continuous_loop,
    should_trade_now,
    fetch_market_data,
    generate_trading_signals,
    execute_trading_signals
)
from config.settings import Settings


class TestMainIntegration(unittest.TestCase):
    """Integration tests for main orchestration script."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = self._create_mock_config()
        self.mock_saxo_client = Mock()
        self.mock_market_data = self._create_mock_market_data()
    
    def _create_mock_config(self):
        """Create mock configuration."""
        config = Mock(spec=Settings)
        config.WATCHLIST = [
            {
                "symbol": "BTCUSD",
                "uic": 12345,
                "asset_type": "FxSpot"
            }
        ]
        config.SAXO_ACCOUNT_KEY = "TEST_ACC"
        config.TRADING_HOURS_MODE = "always"
        config.CYCLE_INTERVAL_SECONDS = 300
        config.DEFAULT_QUANTITY = 100
        return config
    
    def _create_mock_market_data(self):
        """Create mock market data."""
        return {
            "FxSpot/12345": {
                "instrument_id": "FxSpot/12345",
                "symbol": "BTCUSD",
                "uic": 12345,
                "asset_type": "FxSpot",
                "bid": 50000.00,
                "ask": 50010.00,
                "timestamp": "2024-01-15T10:00:00Z"
            }
        }


class TestCompleteTradingCycle(TestMainIntegration):
    """Test complete trading cycle end-to-end."""
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    @patch('main.generate_trading_signals')
    @patch('main.execute_trading_signals')
    def test_successful_trading_cycle(
        self, mock_execute, mock_signals, mock_data, mock_hours
    ):
        """Test successful complete trading cycle."""
        # Setup mocks
        mock_hours.return_value = True
        mock_data.return_value = self.mock_market_data
        mock_signals.return_value = {"FxSpot/12345": "BUY"}
        mock_execute.return_value = {"success": 1, "failed": 0}
        
        # Run cycle
        run_cycle(self.mock_config, self.mock_saxo_client, dry_run=False)
        
        # Verify all phases executed
        mock_hours.assert_called_once()
        mock_data.assert_called_once_with(self.mock_config.WATCHLIST, unittest.mock.ANY)
        mock_signals.assert_called_once()
        mock_execute.assert_called_once()
    
    @patch('main.should_trade_now')
    def test_cycle_skips_outside_trading_hours(self, mock_hours):
        """Test cycle skips when outside trading hours."""
        mock_hours.return_value = False
        
        # Run cycle
        run_cycle(self.mock_config, self.mock_saxo_client, dry_run=False)
        
        # Only hours check should be called
        mock_hours.assert_called_once()
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    @patch('main.generate_trading_signals')
    @patch('main.execute_trading_signals')
    def test_dry_run_mode(
        self, mock_execute, mock_signals, mock_data, mock_hours
    ):
        """Test DRY_RUN mode prevents order placement."""
        # Setup mocks
        mock_hours.return_value = True
        mock_data.return_value = self.mock_market_data
        mock_signals.return_value = {"FxSpot/12345": "BUY"}
        mock_execute.return_value = {"success": 0, "failed": 0}
        
        # Run cycle in DRY_RUN mode
        run_cycle(self.mock_config, self.mock_saxo_client, dry_run=True)
        
        # Verify execution was called with dry_run=True
        self.assertTrue(mock_execute.call_args[1]['dry_run'])


class TestDataFetchingIntegration(TestMainIntegration):
    """Test market data fetching integration."""
    
    @patch('data.market_data.get_latest_quotes')
    def test_fetch_market_data_success(self, mock_get_quotes):
        """Test successful market data fetch."""
        mock_get_quotes.return_value = self.mock_market_data
        
        result = fetch_market_data(self.mock_config.WATCHLIST, Mock())
        
        self.assertEqual(result, self.mock_market_data)
        mock_get_quotes.assert_called_once_with(self.mock_config.WATCHLIST)
    
    @patch('data.market_data.get_latest_quotes')
    def test_fetch_market_data_partial_failure(self, mock_get_quotes):
        """Test market data fetch with missing instruments."""
        # Return data for only some instruments
        partial_data = {"FxSpot/12345": self.mock_market_data["FxSpot/12345"]}
        mock_get_quotes.return_value = partial_data
        
        result = fetch_market_data(
            self.mock_config.WATCHLIST + [{"symbol": "ETHUSD", "uic": 67890, "asset_type": "FxSpot"}],
            Mock()
        )
        
        # Should still return partial data
        self.assertEqual(len(result), 1)


class TestSignalGenerationIntegration(TestMainIntegration):
    """Test signal generation integration."""
    
    @patch('strategies.simple_strategy.generate_signals')
    def test_generate_signals_success(self, mock_generate):
        """Test successful signal generation."""
        expected_signals = {"FxSpot/12345": "BUY"}
        mock_generate.return_value = expected_signals
        
        result = generate_trading_signals(
            self.mock_market_data,
            self.mock_config,
            Mock()
        )
        
        self.assertEqual(result, expected_signals)
        mock_generate.assert_called_once_with(self.mock_market_data)
    
    @patch('strategies.simple_strategy.generate_signals')
    def test_generate_signals_all_hold(self, mock_generate):
        """Test signal generation with all HOLD signals."""
        mock_generate.return_value = {"FxSpot/12345": "HOLD"}
        
        result = generate_trading_signals(
            self.mock_market_data,
            self.mock_config,
            Mock()
        )
        
        self.assertEqual(result, {"FxSpot/12345": "HOLD"})


class TestSignalExecutionIntegration(TestMainIntegration):
    """Test signal execution integration."""
    
    @patch('execution.trade_executor.execute_signal')
    def test_execute_buy_signal(self, mock_execute):
        """Test BUY signal execution."""
        mock_execute.return_value = True
        
        signals = {"FxSpot/12345": "BUY"}
        result = execute_trading_signals(
            signals,
            self.mock_market_data,
            self.mock_config,
            dry_run=False,
            logger=Mock()
        )
        
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failed"], 0)
        mock_execute.assert_called_once()
    
    @patch('execution.trade_executor.execute_signal')
    def test_execute_multiple_signals(self, mock_execute):
        """Test execution of multiple signals."""
        mock_execute.return_value = True
        
        # Add second instrument
        multi_data = {
            **self.mock_market_data,
            "FxSpot/67890": {
                "instrument_id": "FxSpot/67890",
                "symbol": "ETHUSD",
                "uic": 67890,
                "asset_type": "FxSpot",
                "bid": 3000.00,
                "ask": 3001.00
            }
        }
        
        signals = {
            "FxSpot/12345": "BUY",
            "FxSpot/67890": "SELL"
        }
        
        result = execute_trading_signals(
            signals,
            multi_data,
            self.mock_config,
            dry_run=False,
            logger=Mock()
        )
        
        self.assertEqual(result["success"], 2)
        self.assertEqual(mock_execute.call_count, 2)


class TestErrorHandlingIntegration(TestMainIntegration):
    """Test error handling and recovery."""
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    def test_market_data_error_recovery(self, mock_data, mock_hours):
        """Test recovery from market data error."""
        mock_hours.return_value = True
        mock_data.side_effect = Exception("API Error")
        
        # Should not crash
        run_cycle(self.mock_config, self.mock_saxo_client, dry_run=False)
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    @patch('main.generate_trading_signals')
    def test_signal_generation_error_recovery(
        self, mock_signals, mock_data, mock_hours
    ):
        """Test recovery from signal generation error."""
        mock_hours.return_value = True
        mock_data.return_value = self.mock_market_data
        mock_signals.side_effect = Exception("Strategy Error")
        
        # Should not crash
        run_cycle(self.mock_config, self.mock_saxo_client, dry_run=False)
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    @patch('main.generate_trading_signals')
    @patch('main.execute_trading_signals')
    def test_execution_error_recovery(
        self, mock_execute, mock_signals, mock_data, mock_hours
    ):
        """Test recovery from execution error."""
        mock_hours.return_value = True
        mock_data.return_value = self.mock_market_data
        mock_signals.return_value = {"FxSpot/12345": "BUY"}
        mock_execute.side_effect = Exception("Execution Error")
        
        # Should not crash
        run_cycle(self.mock_config, self.mock_saxo_client, dry_run=False)


class TestContinuousLoopIntegration(TestMainIntegration):
    """Test continuous loop operation."""
    
    @patch('main.run_cycle')
    @patch('time.sleep')
    def test_continuous_loop_multiple_cycles(self, mock_sleep, mock_run_cycle):
        """Test continuous loop runs multiple cycles."""
        # Run 3 cycles then stop
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 3:
                raise KeyboardInterrupt()
        
        mock_run_cycle.side_effect = side_effect
        
        try:
            run_continuous_loop(
                self.mock_config,
                self.mock_saxo_client,
                dry_run=False
            )
        except KeyboardInterrupt:
            pass
        
        self.assertEqual(mock_run_cycle.call_count, 3)


if __name__ == '__main__':
    unittest.main()
```

## Test Execution
```bash
# Run all integration tests
python -m pytest tests/test_main_integration.py -v

# Run specific test class
python -m pytest tests/test_main_integration.py::TestCompleteTradingCycle -v

# Run with coverage
python -m pytest tests/test_main_integration.py --cov=main --cov-report=html
```

## CI/CD Integration
```yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run integration tests
      run: |
        python -m pytest tests/test_main_integration.py -v --cov=main
```

## Implementation Steps
1. Create `tests/test_main_integration.py` file
2. Implement test fixtures (mock config, market data, etc.)
3. Write tests for complete trading cycle
4. Write tests for each phase (data, signals, execution)
5. Write tests for error handling
6. Write tests for DRY_RUN vs SIM mode
7. Write tests for single-cycle vs continuous mode
8. Add CI/CD workflow configuration
9. Run tests and fix any failures
10. Document test coverage and gaps

## Dependencies
- `unittest` (built-in)
- `pytest` (optional, but recommended)
- `pytest-cov` for coverage reports
- All project modules (main, config, data, strategies, execution)

## Validation Checklist
- [ ] All integration tests pass
- [ ] Test coverage > 80% for main.py
- [ ] Tests can run in isolated environment
- [ ] Tests run successfully in CI/CD
- [ ] Tests validate happy path (successful cycle)
- [ ] Tests validate error cases (API failures, etc.)
- [ ] Tests validate both DRY_RUN and SIM modes
- [ ] Tests validate graceful shutdown
- [ ] Test execution time < 30 seconds

## Related Stories
- [Story 006-001: Command-Line Arguments and Initialization](./story-006-001-command-line-arguments-initialization.md)
- [Story 006-004: Single Trading Cycle Implementation](./story-006-004-single-trading-cycle.md)
- [Story 006-005: Main Loop and Continuous Operation](./story-006-005-main-loop-continuous-operation.md)
- [Story 006-006: Error Handling and Graceful Shutdown](./story-006-006-error-handling-graceful-shutdown.md)

## Notes
- Use mocks extensively to avoid hitting real Saxo API
- Test isolation is critical - each test should be independent
- Integration tests are slower than unit tests - keep them focused
- Consider adding end-to-end tests with real (simulated) API later
- Document any known test gaps or limitations
- Add performance benchmarks for cycle execution time
- Consider adding smoke tests for quick validation
- Future: Add load testing for continuous operation
- Future: Add chaos testing (random failures, timeouts)
