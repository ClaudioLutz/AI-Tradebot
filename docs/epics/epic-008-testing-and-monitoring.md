# Epic 008: Testing and Monitoring System (Saxo SIM)

## Epic Overview
Establish comprehensive testing framework and monitoring capabilities using Saxo SIM environment to ensure bot reliability, verify correct behavior, and enable ongoing performance tracking. This epic focuses on validation, quality assurance, and operational health monitoring.

## Business Value
- Ensures bot behaves correctly before deployment
- Catches bugs early in development with safe SIM testing
- Provides confidence in strategy logic and execution flow
- Enables performance tracking over time
- Supports continuous improvement through metrics
- Validates Saxo integration (OAuth, precheck, order placement)

## Scope

### In Scope
- Unit tests for core modules (`config`, `data/market_data`, `strategies`, `execution`)
- **Integration tests with Saxo SIM** (precheck-only by default, opt-in for placement)
- Mock Saxo API responses for unit testing
- Validation scripts for configuration and setup
- Performance metrics tracking (OAuth refreshes, trades, precheck results, API errors)
- Health check mechanisms (API connectivity, token validity, data freshness)
- Test documentation and examples
- DRY_RUN testing procedures
- Saxo-specific test scenarios (instrument resolution, UIC/AssetType validation, precheck workflow)

### Out of Scope
- Historical backtesting engine
- Advanced statistical analysis (Sharpe ratio, max drawdown, etc.)
- Real-time monitoring dashboards (Grafana, Prometheus)
- Automated deployment pipelines (CI/CD)
- Load testing and stress testing
- Machine learning model evaluation
- Third-party monitoring services (DataDog, New Relic)

## Technical Considerations

### Test Framework
- Use `pytest` with `pytest-mock` for mocking
- Mock Saxo API with `unittest.mock` or `responses` library for unit tests
- Use actual Saxo SIM API for integration tests (safe, no real money)
- Test edge cases: missing data, API errors, invalid instruments, precheck failures
- Create test fixtures for sample market data with `instrument_id` keys

### Test Levels
1. **Unit Tests**: Mock all external dependencies (Saxo API, file I/O)
2. **Integration Tests**: Use Saxo SIM API (real HTTP calls, safe environment)
3. **End-to-End Tests**: Full bot cycle with DRY_RUN mode

### Saxo-Specific Testing
- Config validation: OAuth vs manual token, AccountKey presence, watchlist format
- Instrument resolution: Verify UIC/AssetType lookups work
- Market data: Test InfoPrice and OHLC fetching with real instruments
- Precheck workflow: Test order precheck with valid and invalid params
- Order placement: Test SIM order placement (behind explicit flag)
- OAuth refresh: Test token expiry and refresh logic

### Monitoring Metrics
- **OAuth Health**: Token refresh success rate, time until expiry
- **Data Freshness**: Timestamp of last successful data fetch per instrument
- **API Error Rate**: HTTP status distribution (200, 400, 429, 500)
- **Execution Success**: Precheck pass/fail rate, order placement success rate
- **Cycle Performance**: Cycle duration, instruments processed, signals generated

## Dependencies
- **Epic 001-2:** Saxo Bank Migration (SIM connectivity)
- **Epic 002:** Configuration Module (validation logic)
- **Epic 003:** Market Data Retrieval (data fetching)
- **Epic 004:** Trading Strategy System (signal generation)
- **Epic 005:** Trade Execution Module (precheck + placement)
- **Epic 006:** Main Orchestration Script (cycle execution)
- **Epic 007:** Logging and Scheduling (log analysis for monitoring)

## Success Criteria
- [ ] Test suite created with pytest
- [ ] Unit tests for config module (OAuth/manual, watchlist parsing)
- [ ] Unit tests for market data module (mock Saxo responses)
- [ ] Unit tests for strategy module (mock market data)
- [ ] Unit tests for execution module (mock precheck/placement)
- [ ] Integration test: OAuth token refresh
- [ ] Integration test: Instrument resolution (UIC lookup)
- [ ] Integration test: Market data fetch from SIM
- [ ] Integration test: Order precheck (valid and invalid)
- [ ] Integration test: Full cycle with DRY_RUN
- [ ] Configuration validation script
- [ ] Health check script (token, API, data)
- [ ] Performance metrics tracked and logged
- [ ] All tests pass successfully

## Acceptance Criteria
1. Can run full test suite with `pytest tests/`
2. Tests cover normal operation and error cases (happy path + edge cases)
3. Mock API prevents actual calls in unit tests
4. Integration tests use SIM environment exclusively (no Live)
5. Order placement tests require explicit flag `--allow-sim-orders`
6. Config validation catches errors before bot runs
7. Health check validates: OAuth token, API connectivity, data freshness
8. Performance metrics logged for analysis
9. Test documentation explains how to run and add tests
10. All modules have >70% code coverage (unit tests)

## Related Documents
- `tests/` directory
- `test_integration_saxo.py` (existing integration tests)
- [Epic 005: Trade Execution Module](./epic-005-trade-execution-module.md) (precheck workflow)
- README.md (testing section to be added)

## Test Structure
```
trading_bot/
├── tests/
│   ├── __init__.py
│   ├── test_config.py              # Config validation, parsing
│   ├── test_market_data.py         # Data fetching (mocked)
│   ├── test_strategy.py            # Signal generation
│   ├── test_execution.py           # Order precheck/placement (mocked)
│   ├── test_integration_saxo.py    # SIM integration tests
│   ├── test_oauth.py               # OAuth refresh logic
│   └── fixtures/
│       ├── sample_instruments.py   # Instrument fixtures
│       ├── sample_market_data.py   # Market data fixtures
│       └── sample_responses.py     # Mock Saxo API responses
```

## Example Unit Tests

### Test Config Module
```python
import pytest
from config.settings import Settings

def test_config_loads_watchlist():
    """Test watchlist parsing from config."""
    config = Settings()
    
    assert len(config.WATCHLIST) > 0
    for instrument in config.WATCHLIST:
        assert 'asset_type' in instrument
        assert 'uic' in instrument
        assert 'symbol' in instrument


def test_config_validates_auth_mode():
    """Test authentication mode validation."""
    config = Settings()
    
    assert config.AUTH_MODE in ['oauth', 'manual']
    
    if config.AUTH_MODE == 'oauth':
        assert config.SAXO_APP_KEY is not None
        assert config.SAXO_APP_SECRET is not None
    else:
        assert config.SAXO_ACCESS_TOKEN is not None


def test_config_instrument_id_generation():
    """Test instrument_id construction."""
    instrument = {'asset_type': 'Stock', 'uic': 211, 'symbol': 'AAPL'}
    instrument_id = f"{instrument['asset_type']}:{instrument['uic']}"
    
    assert instrument_id == "Stock:211"
```

### Test Market Data Module (Mocked)
```python
import pytest
from unittest.mock import Mock, patch
from data.market_data import get_latest_quotes

def test_get_latest_quotes_success():
    """Test successful quote fetching (mocked)."""
    instruments = [
        {'asset_type': 'Stock', 'uic': 211, 'symbol': 'AAPL'}
    ]
    
    mock_response = {
        'Data': [{
            'Uic': 211,
            'AssetType': 'Stock',
            'Quote': {
                'Bid': 150.25,
                'Ask': 150.30,
                'Mid': 150.275,
                'DelayedByMinutes': 0
            }
        }]
    }
    
    with patch('data.saxo_client.SaxoClient.get') as mock_get:
        mock_get.return_value = mock_response
        
        result = get_latest_quotes(instruments)
        
        assert 'Stock:211' in result
        assert result['Stock:211']['quote']['bid'] == 150.25
        assert result['Stock:211']['symbol'] == 'AAPL'


def test_get_latest_quotes_http_error():
    """Test handling of HTTP errors."""
    instruments = [{'asset_type': 'Stock', 'uic': 211, 'symbol': 'AAPL'}]
    
    with patch('data.saxo_client.SaxoClient.get') as mock_get:
        mock_get.side_effect = Exception("HTTP 500")
        
        result = get_latest_quotes(instruments)
        
        # Should return empty or partial results, not crash
        assert isinstance(result, dict)
```

### Test Strategy Module
```python
from strategies.simple_strategy import generate_signals

def test_generate_signals_buy():
    """Test BUY signal generation."""
    market_data = {
        'Stock:211': {
            'instrument_id': 'Stock:211',
            'asset_type': 'Stock',
            'uic': 211,
            'symbol': 'AAPL',
            'bars': [
                {'close': 100}, {'close': 101}, {'close': 102},
                {'close': 103}, {'close': 104}, {'close': 105}
            ]
        }
    }
    
    signals = generate_signals(market_data)
    
    assert 'Stock:211' in signals
    assert signals['Stock:211'] in ['BUY', 'SELL', 'HOLD']


def test_generate_signals_insufficient_data():
    """Test HOLD signal when insufficient data."""
    market_data = {
        'Stock:211': {
            'instrument_id': 'Stock:211',
            'bars': []  # No data
        }
    }
    
    signals = generate_signals(market_data)
    
    assert signals['Stock:211'] == 'HOLD'
```

### Test Execution Module (Mocked)
```python
from unittest.mock import patch
from execution.trade_executor import precheck_order, execute_signal

def test_precheck_order_success():
    """Test successful order precheck (mocked)."""
    mock_response = {
        'PreCheckResult': {
            'IsValid': True,
            'EstimatedCosts': {'TotalCost': 1500.25}
        }
    }
    
    with patch('data.saxo_client.SaxoClient.post') as mock_post:
        mock_post.return_value = mock_response
        
        result = precheck_order(
            account_key='test_account',
            asset_type='Stock',
            uic=211,
            buy_sell='Buy',
            amount=10,
            symbol='AAPL'
        )
        
        assert result['success'] == True
        assert result['estimated_cost'] == 1500.25


def test_precheck_order_failure():
    """Test precheck failure (insufficient funds)."""
    mock_response = {
        'PreCheckResult': {
            'IsValid': False,
            'ErrorCode': 'InsufficientFunds',
            'ErrorMessage': 'Not enough funds'
        }
    }
    
    with patch('data.saxo_client.SaxoClient.post') as mock_post:
        mock_post.return_value = mock_response
        
        result = precheck_order(
            account_key='test_account',
            asset_type='Stock',
            uic=211,
            buy_sell='Buy',
            amount=1000,
            symbol='AAPL'
        )
        
        assert result['success'] == False
        assert 'InsufficientFunds' in result['error_code']


def test_execute_signal_dry_run():
    """Test signal execution in DRY_RUN mode."""
    instrument = {
        'instrument_id': 'Stock:211',
        'asset_type': 'Stock',
        'uic': 211,
        'symbol': 'AAPL'
    }
    
    with patch('execution.trade_executor.precheck_order') as mock_precheck:
        mock_precheck.return_value = {'success': True, 'estimated_cost': 1500}
        
        result = execute_signal(
            instrument=instrument,
            signal='BUY',
            account_key='test_account',
            amount=10,
            dry_run=True  # DRY_RUN mode
        )
        
        assert result == True
        mock_precheck.assert_called_once()  # Precheck called
        # Placement should NOT be called in DRY_RUN
```

## Integration Tests (Saxo SIM)

### Test OAuth Token Refresh
```python
import pytest
from auth.saxo_oauth import SaxoOAuth

@pytest.mark.integration
def test_oauth_token_refresh():
    """Test OAuth token refresh with real SIM API."""
    oauth = SaxoOAuth()
    
    # Load existing token
    token = oauth.load_token()
    assert token is not None
    
    # Attempt refresh
    new_token = oauth.refresh_token()
    
    assert new_token is not None
    assert new_token['access_token'] != token['access_token']
```

### Test Market Data Fetch (SIM)
```python
import pytest
from data.market_data import get_latest_quotes

@pytest.mark.integration
def test_fetch_real_quote_from_sim():
    """Test fetching real quote from Saxo SIM."""
    instruments = [
        {'asset_type': 'Stock', 'uic': 211, 'symbol': 'AAPL'}
    ]
    
    result = get_latest_quotes(instruments)
    
    assert 'Stock:211' in result
    assert 'quote' in result['Stock:211']
    assert 'bid' in result['Stock:211']['quote']
```

### Test Order Precheck (SIM)
```python
import pytest
from execution.trade_executor import precheck_order

@pytest.mark.integration
def test_precheck_valid_order_sim():
    """Test precheck with valid order in SIM."""
    result = precheck_order(
        account_key=config.SAXO_ACCOUNT_KEY,
        asset_type='Stock',
        uic=211,
        buy_sell='Buy',
        amount=1,
        symbol='AAPL'
    )
    
    assert 'success' in result
    if result['success']:
        assert 'estimated_cost' in result


@pytest.mark.integration
@pytest.mark.sim_orders  # Explicit flag required
def test_place_order_sim():
    """Test actual order placement in SIM (use with caution)."""
    # This test requires --allow-sim-orders flag
    pytest.skip("Requires explicit --allow-sim-orders flag")
```

## Configuration Validation Script

```python
def validate_config():
    """Validate configuration before bot starts."""
    from config.settings import Settings
    
    errors = []
    warnings = []
    
    try:
        config = Settings()
    except Exception as e:
        errors.append(f"Config loading failed: {e}")
        return False, errors, warnings
    
    # 1. Check authentication
    if config.AUTH_MODE == 'oauth':
        if not config.SAXO_APP_KEY or not config.SAXO_APP_SECRET:
            errors.append("OAuth mode selected but APP_KEY/APP_SECRET missing")
    elif config.AUTH_MODE == 'manual':
        if not config.SAXO_ACCESS_TOKEN:
            errors.append("Manual mode selected but ACCESS_TOKEN missing")
    else:
        errors.append(f"Invalid AUTH_MODE: {config.AUTH_MODE}")
    
    # 2. Check AccountKey
    if not config.SAXO_ACCOUNT_KEY:
        errors.append("SAXO_ACCOUNT_KEY not set")
    
    # 3. Check watchlist
    if not config.WATCHLIST or len(config.WATCHLIST) == 0:
        errors.append("WATCHLIST is empty")
    
    # Validate watchlist format
    for idx, instrument in enumerate(config.WATCHLIST):
        if 'asset_type' not in instrument:
            errors.append(f"Watchlist item {idx}: missing 'asset_type'")
        if 'uic' not in instrument:
            errors.append(f"Watchlist item {idx}: missing 'uic'")
        if 'symbol' not in instrument:
            warnings.append(f"Watchlist item {idx}: missing 'symbol' (optional)")
    
    # 4. Check environment
    if 'live' in config.SAXO_BASE_URL.lower():
        warnings.append("WARNING: Using LIVE environment (not SIM)!")
    
    # 5. Check trading hours mode
    if config.TRADING_HOURS_MODE not in ['always', 'fixed', 'instrument']:
        errors.append(f"Invalid TRADING_HOURS_MODE: {config.TRADING_HOURS_MODE}")
    
    # Print results
    if errors:
        print("\n❌ Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("\n⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors:
        print("\n✅ Configuration valid")
        return True, [], warnings
    
    return False, errors, warnings
```

## Health Check Script

```python
def health_check():
    """Verify bot is healthy and ready to trade."""
    from config.settings import Settings
    from auth.saxo_oauth import SaxoOAuth
    from data.saxo_client import SaxoClient
    from data.market_data import get_latest_quotes
    
    checks = []
    
    # 1. Config validation
    try:
        config = Settings()
        checks.append(("Config Loading", True, f"{len(config.WATCHLIST)} instruments"))
    except Exception as e:
        checks.append(("Config Loading", False, str(e)))
        return False
    
    # 2. OAuth token validity
    if config.AUTH_MODE == 'oauth':
        try:
            oauth = SaxoOAuth()
            token = oauth.load_token()
            expires_at = token.get('expires_at', 0)
            time_remaining = expires_at - time.time()
            
            if time_remaining > 0:
                checks.append(("OAuth Token", True, f"Valid for {int(time_remaining/60)} minutes"))
            else:
                checks.append(("OAuth Token", False, "Token expired"))
        except Exception as e:
            checks.append(("OAuth Token", False, str(e)))
    else:
        checks.append(("OAuth Token", True, "Manual token mode"))
    
    # 3. Saxo API connectivity
    try:
        client = SaxoClient(config)
        # Simple API call to verify connectivity
        response = client.get('/port/v1/users/me')
        checks.append(("API Connection", True, f"ClientId: {response.get('ClientId', 'N/A')}"))
    except Exception as e:
        checks.append(("API Connection", False, str(e)))
    
    # 4. Market data fetch
    try:
        if config.WATCHLIST:
            test_instrument = config.WATCHLIST[0]
            data = get_latest_quotes([test_instrument])
            instrument_id = f"{test_instrument['asset_type']}:{test_instrument['uic']}"
            
            if instrument_id in data:
                checks.append(("Data Fetch", True, f"Got quote for {test_instrument['symbol']}"))
            else:
                checks.append(("Data Fetch", False, "No data returned"))
        else:
            checks.append(("Data Fetch", False, "No instruments to test"))
    except Exception as e:
        checks.append(("Data Fetch", False, str(e)))
    
    # Print results
    print("\n=== Health Check Results ===")
    all_passed = True
    for name, passed, details in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {name}: {details}")
        if not passed:
            all_passed = False
    
    return all_passed
```

## Performance Monitoring

```python
class PerformanceMonitor:
    """Track bot performance metrics."""
    
    def __init__(self):
        self.metrics = {
            'cycle_count': 0,
            'signals_generated': 0,
            'orders_prechecked': 0,
            'orders_placed': 0,
            'precheck_failures': 0,
            'placement_failures': 0,
            'api_errors': {},  # {status_code: count}
            'oauth_refreshes': 0,
            'data_fetch_errors': 0,
            'cycle_durations': []
        }
    
    def record_cycle(self, duration_seconds):
        self.metrics['cycle_count'] += 1
        self.metrics['cycle_durations'].append(duration_seconds)
    
    def record_signal(self):
        self.metrics['signals_generated'] += 1
    
    def record_precheck(self, success):
        self.metrics['orders_prechecked'] += 1
        if not success:
            self.metrics['precheck_failures'] += 1
    
    def record_placement(self, success):
        self.metrics['orders_placed'] += 1
        if not success:
            self.metrics['placement_failures'] += 1
    
    def record_api_error(self, status_code):
        self.metrics['api_errors'][status_code] = \
            self.metrics['api_errors'].get(status_code, 0) + 1
    
    def record_oauth_refresh(self):
        self.metrics['oauth_refreshes'] += 1
    
    def get_summary(self):
        avg_duration = sum(self.metrics['cycle_durations']) / len(self.metrics['cycle_durations']) \
            if self.metrics['cycle_durations'] else 0
        
        return {
            'total_cycles': self.metrics['cycle_count'],
            'avg_cycle_duration': round(avg_duration, 2),
            'signals_generated': self.metrics['signals_generated'],
            'orders_prechecked': self.metrics['orders_prechecked'],
            'precheck_success_rate': self._success_rate(
                self.metrics['orders_prechecked'], 
                self.metrics['precheck_failures']
            ),
            'orders_placed': self.metrics['orders_placed'],
            'placement_success_rate': self._success_rate(
                self.metrics['orders_placed'],
                self.metrics['placement_failures']
            ),
            'oauth_refreshes': self.metrics['oauth_refreshes'],
            'api_errors': self.metrics['api_errors']
        }
    
    def _success_rate(self, total, failures):
        if total == 0:
            return 0.0
        return round((total - failures) / total * 100, 2)
```

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest --cov=. --cov-report=html tests/

# Run only unit tests (skip integration)
pytest tests/ -v -m "not integration"

# Run integration tests (with SIM API)
pytest tests/ -v -m integration

# Run specific test file
pytest tests/test_config.py -v

# Run tests matching pattern
pytest tests/ -k "test_precheck" -v
```

## CI/CD Safety

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests only
        run: pytest tests/ -v -m "not integration"
        # Integration tests require secrets, run manually
```

## Notes
- Unit tests should NOT make real API calls (use mocks)
- Integration tests use SIM environment (safe, but still hits real API)
- Order placement tests require explicit opt-in flag
- Validate config before every bot run (catch errors early)
- Monitor OAuth token expiry to avoid mid-cycle auth failures
- Track API error rates to detect Saxo API issues
- Log all test failures for investigation
- Run health check daily (cron job or manual)
- Review metrics weekly to identify trends

## Future Enhancements
- Automated backtesting framework
- Performance dashboard (Grafana + Prometheus)
- Real-time alerts (PagerDuty, Slack)
- A/B testing for strategy variants
- Automated regression testing
- Load testing for high-frequency strategies
