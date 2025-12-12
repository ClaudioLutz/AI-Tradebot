# Epic 008: Testing and Monitoring System

## Epic Overview
Establish comprehensive testing framework and monitoring capabilities to ensure bot reliability, verify correct behavior, and enable ongoing performance tracking. This epic focuses on validation, quality assurance, and operational visibility.

## Business Value
- Ensures bot behaves correctly before live deployment
- Catches bugs early in development
- Provides confidence in strategy logic
- Enables performance tracking over time
- Supports continuous improvement through metrics

## Scope

### In Scope
- Unit tests for core modules (data_fetcher, strategy, trader)
- Integration tests for complete workflow
- Mock API responses for testing without live calls
- Validation scripts for configuration and setup
- Performance metrics tracking (trades, P&L, win rate)
- Dashboard or reporting basics (daily summaries)
- Health check mechanisms
- Test documentation and examples
- Dry-run testing procedures

### Out of Scope
- Historical backtesting engine
- Advanced statistical analysis
- Real-time monitoring dashboards (Grafana, etc.)
- Automated deployment pipelines (CI/CD)
- Load testing and stress testing
- Machine learning model evaluation
- Third-party monitoring services

## Technical Considerations
- Use pytest or unittest framework
- Mock Alpaca API with unittest.mock or responses library
- Test edge cases (missing data, API errors, invalid signals)
- Create test fixtures for sample market data
- Validate configuration on startup
- Track key metrics: number of trades, success rate, position values
- Generate daily/weekly summary reports
- Implement health checks (API connectivity, data freshness)
- Use test data that doesn't affect paper trading account

## Dependencies
- Epic 001: Initial Setup and Environment Configuration
- Epic 002: Configuration Module Development
- Epic 003: Market Data Retrieval Module
- Epic 004: Trading Strategy System
- Epic 005: Trade Execution Module
- Epic 006: Main Orchestration Script
- Epic 007: Logging and Scheduling System

## Success Criteria
- [ ] Test suite created with pytest/unittest
- [ ] Unit tests for data_fetcher module
- [ ] Unit tests for strategy module
- [ ] Unit tests for trader module
- [ ] Integration test for complete cycle
- [ ] Mock API responses working
- [ ] Configuration validation script
- [ ] Performance metrics tracked and logged
- [ ] Daily summary report generated
- [ ] Health check script created
- [ ] All tests pass successfully

## Acceptance Criteria
1. Can run full test suite with single command
2. Tests cover normal operation and error cases
3. Mock API prevents actual API calls during testing
4. Configuration errors caught before bot runs
5. Performance metrics recorded for each trading day
6. Daily summary includes trades executed and P&L
7. Health check validates API connectivity and data availability
8. Test documentation explains how to add new tests
9. All modules have >70% code coverage (aspirational)

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- tests/ (directory to be created)
- README.md (testing section to be added)

## Test Structure
```
trading_bot/
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_data_fetcher.py
│   ├── test_strategy.py
│   ├── test_trader.py
│   ├── test_integration.py
│   └── fixtures/
│       └── sample_data.py
```

## Example Unit Tests

### Test Data Fetcher
```python
import pytest
from unittest.mock import Mock, patch
import data_fetcher

def test_get_latest_data_success():
    """Test successful data retrieval."""
    with patch('data_fetcher.api') as mock_api:
        # Mock API response
        mock_api.get_bars.return_value = {
            'AAPL': {'close': 150.0, 'volume': 1000000}
        }
        
        result = data_fetcher.get_latest_data(['AAPL'])
        
        assert 'AAPL' in result
        assert result['AAPL']['close'] == 150.0

def test_get_latest_data_api_error():
    """Test handling of API errors."""
    with patch('data_fetcher.api') as mock_api:
        mock_api.get_bars.side_effect = Exception("API Error")
        
        result = data_fetcher.get_latest_data(['AAPL'])
        
        assert result == {}  # Should return empty dict on error
```

### Test Strategy
```python
from strategies import example_strategy

def test_generate_signals_buy():
    """Test BUY signal generation."""
    market_data = {
        'AAPL': {
            'prices': [100, 101, 102, 103, 104],  # Uptrend
            'short_ma': 103,
            'long_ma': 101
        }
    }
    
    signals = example_strategy.generate_signals(market_data)
    
    assert signals['AAPL'] == 'BUY'

def test_generate_signals_hold():
    """Test HOLD signal when no clear trend."""
    market_data = {
        'AAPL': {
            'prices': [100, 100, 100, 100, 100],
            'short_ma': 100,
            'long_ma': 100
        }
    }
    
    signals = example_strategy.generate_signals(market_data)
    
    assert signals['AAPL'] == 'HOLD'
```

### Test Trader
```python
from unittest.mock import patch
import trader
from config.config import DRY_RUN

def test_execute_buy_dry_run():
    """Test buy execution in dry-run mode."""
    with patch('config.config.DRY_RUN', True):
        result = trader.execute_buy('AAPL', 1)
        
        assert result == True  # Should succeed without API call

def test_execute_buy_paper_trading():
    """Test buy execution in paper trading mode."""
    with patch('trader.api') as mock_api:
        mock_api.submit_order.return_value = {'id': '123', 'status': 'filled'}
        
        result = trader.execute_buy('AAPL', 1)
        
        assert result == True
        mock_api.submit_order.assert_called_once()
```

## Integration Test
```python
def test_full_trading_cycle():
    """Test complete data -> signal -> trade workflow."""
    with patch('data_fetcher.get_latest_data') as mock_data, \
         patch('trader.execute_signal') as mock_trade:
        
        # Mock data
        mock_data.return_value = {
            'AAPL': {'close': 150, 'volume': 1000000}
        }
        
        # Run cycle
        from main import run_single_cycle
        run_single_cycle()
        
        # Verify trades executed
        assert mock_trade.called
```

## Configuration Validation
```python
def validate_config():
    """Validate configuration before bot starts."""
    errors = []
    
    # Check API keys
    if not os.getenv('APCA_API_KEY_ID'):
        errors.append("APCA_API_KEY_ID not set")
    
    if not os.getenv('APCA_API_SECRET_KEY'):
        errors.append("APCA_API_SECRET_KEY not set")
    
    # Check watchlist
    if not WATCHLIST or len(WATCHLIST) == 0:
        errors.append("WATCHLIST is empty")
    
    # Check base URL
    if "paper" not in BASE_URL:
        errors.append("WARNING: Not using paper trading endpoint!")
    
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("Configuration valid ✓")
    return True
```

## Performance Metrics
```python
class PerformanceTracker:
    """Track bot performance metrics."""
    
    def __init__(self):
        self.metrics = {
            'trades_executed': 0,
            'buys': 0,
            'sells': 0,
            'errors': 0,
            'api_calls': 0,
            'start_time': None,
            'end_time': None
        }
    
    def record_trade(self, side):
        """Record a trade execution."""
        self.metrics['trades_executed'] += 1
        if side == 'buy':
            self.metrics['buys'] += 1
        elif side == 'sell':
            self.metrics['sells'] += 1
    
    def record_error(self):
        """Record an error occurrence."""
        self.metrics['errors'] += 1
    
    def generate_report(self):
        """Generate daily summary report."""
        report = f"""
        === Trading Bot Daily Summary ===
        Date: {datetime.now().strftime('%Y-%m-%d')}
        
        Trades Executed: {self.metrics['trades_executed']}
        - Buys: {self.metrics['buys']}
        - Sells: {self.metrics['sells']}
        
        Errors: {self.metrics['errors']}
        API Calls: {self.metrics['api_calls']}
        
        Runtime: {self.metrics.get('runtime', 'N/A')}
        """
        return report
```

## Health Check Script
```python
def health_check():
    """Verify bot is healthy and ready to trade."""
    checks = []
    
    # 1. API Connectivity
    try:
        api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL)
        clock = api.get_clock()
        checks.append(("API Connection", True, "Connected"))
    except Exception as e:
        checks.append(("API Connection", False, str(e)))
    
    # 2. Data Retrieval
    try:
        data = data_fetcher.get_latest_data(['AAPL'])
        checks.append(("Data Fetch", len(data) > 0, f"Got {len(data)} symbols"))
    except Exception as e:
        checks.append(("Data Fetch", False, str(e)))
    
    # 3. Strategy Execution
    try:
        signals = example_strategy.generate_signals({})
        checks.append(("Strategy", True, "Working"))
    except Exception as e:
        checks.append(("Strategy", False, str(e)))
    
    # Print results
    print("\n=== Health Check Results ===")
    all_passed = True
    for name, passed, details in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {name}: {details}")
        if not passed:
            all_passed = False
    
    return all_passed
```

## Running Tests
```bash
# Install pytest
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=. tests/

# Run specific test file
pytest tests/test_strategy.py

# Run in verbose mode
pytest -v tests/
```

## Notes
- Write tests as you develop each module
- Mock external dependencies (Alpaca API) in tests
- Use test fixtures for consistent test data
- Run tests before committing code changes
- Aim for meaningful coverage, not just high percentage
- Include both positive and negative test cases
- Document expected behavior in test docstrings
- Consider adding performance benchmarks later
