# Story 002-006: Configuration Module Testing

## Story Overview
Create comprehensive unit tests for the configuration module to ensure all functionality works correctly and configuration validation is robust.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** have comprehensive tests for the configuration module  
**So that** I can ensure configuration works reliably and catch regressions early

## Acceptance Criteria
- [ ] Unit tests for all configuration methods
- [ ] Tests for valid and invalid configurations
- [ ] Tests for environment variable overrides
- [ ] Tests for validation logic
- [ ] Tests for helper methods
- [ ] 80%+ code coverage for config module
- [ ] All tests pass successfully

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials)
- Story 002-003 completed (watchlist)
- Story 002-004 completed (trading settings)
- Story 002-005 completed (validation)
- `pytest` installed

### Test Categories

1. **Initialization Tests**
   - Valid configuration loading
   - Missing credentials errors
   - Environment variable loading

2. **Credentials Tests**
   - Token masking
   - Environment detection
   - Base URL handling

3. **Watchlist Tests**
   - Default watchlist loading
   - Custom watchlist from environment
   - Symbol validation
   - Add/remove symbols
   - Stock/crypto filtering

4. **Trading Settings Tests**
   - Default settings loading
   - Environment overrides
   - Settings validation
   - Trading mode checks
   - Position sizing
   - Trading hours

5. **Validation Tests**
   - Valid configuration passes
   - Invalid configurations fail
   - Cross-validation checks
   - Health check functionality

6. **Export Tests**
   - Configuration export
   - Sensitive data masking
   - JSON export

### Implementation

Create or update `tests/test_config_module.py`:

```python
"""
Comprehensive tests for config/config.py module.

Tests cover:
- Configuration initialization
- Credentials loading
- Watchlist management
- Trading settings
- Validation logic
- Export functionality
"""

import os
import pytest
import tempfile
from unittest.mock import patch
from config.config import Config, ConfigurationError, get_config


class TestConfigInitialization:
    """Test configuration initialization and loading."""
    
    def test_config_initialization_success(self):
        """Test successful configuration initialization."""
        config = Config()
        assert config is not None
        assert hasattr(config, 'base_url')
        assert hasattr(config, 'watchlist')
        assert hasattr(config, 'default_timeframe')
    
    def test_missing_base_url_raises_error(self):
        """Test that missing SAXO_REST_BASE raises error."""
        with patch.dict(os.environ, {'SAXO_REST_BASE': ''}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "SAXO_REST_BASE" in str(exc_info.value)
    
    def test_missing_access_token_raises_error(self):
        """Test that missing SAXO_ACCESS_TOKEN raises error."""
        with patch.dict(os.environ, {
            'SAXO_REST_BASE': 'https://gateway.saxobank.com/sim/openapi',
            'SAXO_ACCESS_TOKEN': ''
        }, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "SAXO_ACCESS_TOKEN" in str(exc_info.value)


class TestCredentials:
    """Test API credentials loading and handling."""
    
    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base URL."""
        with patch.dict(os.environ, {
            'SAXO_REST_BASE': 'https://gateway.saxobank.com/sim/openapi/',
            'SAXO_ACCESS_TOKEN': 'test_token_12345'
        }):
            config = Config()
            assert not config.base_url.endswith('/')
    
    def test_token_masking(self):
        """Test that tokens are properly masked."""
        config = Config()
        masked = config.get_masked_token()
        assert '...' in masked
        assert len(masked) < len(config.access_token)
    
    def test_environment_detection_sim(self):
        """Test SIM environment detection."""
        config = Config()
        assert config.is_simulation()
        assert not config.is_production()
    
    def test_environment_from_env_variable(self):
        """Test environment loaded from SAXO_ENV."""
        with patch.dict(os.environ, {'SAXO_ENV': 'LIVE'}):
            config = Config()
            assert config.environment == 'LIVE'


class TestWatchlist:
    """Test watchlist configuration and management."""
    
    def test_default_watchlist_loaded(self):
        """Test that default watchlist is loaded."""
        config = Config()
        assert len(config.watchlist) > 0
        assert 'AAPL' in config.watchlist
        assert 'BTC/USD' in config.watchlist or 'ETH/USD' in config.watchlist
    
    def test_custom_watchlist_from_environment(self):
        """Test loading custom watchlist from environment."""
        with patch.dict(os.environ, {'WATCHLIST': 'AAPL,MSFT,GOOGL'}):
            config = Config()
            assert config.watchlist == ['AAPL', 'MSFT', 'GOOGL']
    
    def test_stock_symbols_filtering(self):
        """Test filtering stock symbols from watchlist."""
        config = Config()
        stocks = config.get_stock_symbols()
        assert all('/' not in symbol for symbol in stocks)
    
    def test_crypto_symbols_filtering(self):
        """Test filtering crypto symbols from watchlist."""
        config = Config()
        crypto = config.get_crypto_symbols()
        assert all('/' in symbol for symbol in crypto)
    
    def test_add_symbol_success(self):
        """Test successfully adding a symbol."""
        config = Config()
        initial_count = len(config.watchlist)
        config.add_symbol('NVDA')
        assert len(config.watchlist) == initial_count + 1
        assert 'NVDA' in config.watchlist
    
    def test_add_duplicate_symbol_raises_error(self):
        """Test that adding duplicate symbol raises error."""
        config = Config()
        existing_symbol = config.watchlist[0]
        with pytest.raises(ConfigurationError) as exc_info:
            config.add_symbol(existing_symbol)
        assert "already in watchlist" in str(exc_info.value)
    
    def test_remove_symbol_success(self):
        """Test successfully removing a symbol."""
        config = Config()
        symbol_to_remove = config.watchlist[0]
        config.remove_symbol(symbol_to_remove)
        assert symbol_to_remove not in config.watchlist
    
    def test_remove_nonexistent_symbol_raises_error(self):
        """Test that removing non-existent symbol raises error."""
        config = Config()
        with pytest.raises(ConfigurationError) as exc_info:
            config.remove_symbol('NONEXISTENT')
        assert "not in watchlist" in str(exc_info.value)
    
    def test_watchlist_summary(self):
        """Test watchlist summary generation."""
        config = Config()
        summary = config.get_watchlist_summary()
        assert 'total_symbols' in summary
        assert 'stocks' in summary
        assert 'crypto' in summary
        assert summary['total_symbols'] == len(config.watchlist)


class TestTradingSettings:
    """Test trading settings configuration."""
    
    def test_default_settings_loaded(self):
        """Test that default settings are loaded correctly."""
        config = Config()
        assert config.default_timeframe == '1Min'
        assert config.dry_run is True
        assert config.max_position_size == 1000.0
        assert config.stop_loss_pct == 2.0
    
    def test_environment_override_timeframe(self):
        """Test timeframe can be overridden by environment."""
        with patch.dict(os.environ, {'DEFAULT_TIMEFRAME': '5Min'}):
            config = Config()
            assert config.default_timeframe == '5Min'
    
    def test_environment_override_dry_run(self):
        """Test dry_run can be overridden by environment."""
        with patch.dict(os.environ, {'DRY_RUN': 'False'}):
            config = Config()
            assert config.dry_run is False
    
    def test_invalid_timeframe_raises_error(self):
        """Test that invalid timeframe raises error."""
        with patch.dict(os.environ, {'DEFAULT_TIMEFRAME': 'InvalidFrame'}):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "Invalid timeframe" in str(exc_info.value)
    
    def test_trading_mode_detection(self):
        """Test trading mode detection."""
        config = Config()
        assert config.is_dry_run()
        assert not config.is_live_trading()
        assert config.get_trading_mode() == 'DRY_RUN'
    
    def test_position_size_calculation(self):
        """Test position size calculation."""
        config = Config()
        price = 150.0
        position_1pct = config.calculate_position_size(price, risk_pct=1.0)
        position_5pct = config.calculate_position_size(price, risk_pct=5.0)
        
        assert position_1pct < position_5pct
        assert position_1pct <= config.max_portfolio_exposure
    
    def test_trading_hours_check(self):
        """Test trading hours validation."""
        config = Config()
        # Within hours (14-21 UTC)
        assert config.is_within_trading_hours(15)
        assert config.is_within_trading_hours(20)
        # Outside hours
        assert not config.is_within_trading_hours(10)
        assert not config.is_within_trading_hours(22)
    
    def test_trading_settings_summary(self):
        """Test trading settings summary."""
        config = Config()
        summary = config.get_trading_settings_summary()
        assert 'trading_mode' in summary
        assert 'default_timeframe' in summary
        assert 'max_position_size' in summary


class TestValidation:
    """Test configuration validation logic."""
    
    def test_valid_configuration_passes(self):
        """Test that valid configuration passes validation."""
        config = Config()
        assert config.is_valid()
    
    def test_invalid_position_sizing_fails(self):
        """Test that invalid position sizing fails validation."""
        with patch.dict(os.environ, {
            'MIN_TRADE_AMOUNT': '2000.0',
            'MAX_POSITION_SIZE': '1000.0'
        }):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "min_trade_amount" in str(exc_info.value)
    
    def test_invalid_stop_loss_fails(self):
        """Test that invalid stop-loss fails validation."""
        with patch.dict(os.environ, {'STOP_LOSS_PCT': '-5.0'}):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "stop_loss_pct" in str(exc_info.value)
    
    def test_symbol_validation(self):
        """Test symbol validation."""
        config = Config()
        assert config.validate_symbol('AAPL')
        assert config.validate_symbol('BTC/USD')
        assert not config.validate_symbol('ABC@123')
        assert not config.validate_symbol('')
    
    def test_configuration_health_check(self):
        """Test configuration health check."""
        config = Config()
        health = config.get_configuration_health()
        assert 'overall_valid' in health
        assert 'sections' in health
        assert health['overall_valid'] is True


class TestExport:
    """Test configuration export functionality."""
    
    def test_export_configuration_masks_token(self):
        """Test that exported config masks sensitive data by default."""
        config = Config()
        exported = config.export_configuration(include_sensitive=False)
        assert '...' in exported['api']['token']
    
    def test_export_configuration_includes_sensitive(self):
        """Test export with sensitive data when requested."""
        config = Config()
        exported = config.export_configuration(include_sensitive=True)
        # Full token should be present (be careful with this!)
        assert exported['api']['token'] == config.access_token
    
    def test_export_has_all_sections(self):
        """Test that export includes all configuration sections."""
        config = Config()
        exported = config.export_configuration()
        assert 'api' in exported
        assert 'watchlist' in exported
        assert 'trading_settings' in exported
        assert 'risk_management' in exported
    
    def test_save_configuration_to_file(self):
        """Test saving configuration to file."""
        config = Config()
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filepath = f.name
        
        try:
            config.save_configuration_to_file(filepath, include_sensitive=False)
            assert os.path.exists(filepath)
            
            # Read and verify
            import json
            with open(filepath, 'r') as f:
                saved_config = json.load(f)
            assert 'api' in saved_config
            assert '...' in saved_config['api']['token']
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


class TestGetConfig:
    """Test convenience function for getting config."""
    
    def test_get_config_returns_valid_config(self):
        """Test that get_config returns valid configuration."""
        config = get_config()
        assert config is not None
        assert isinstance(config, Config)
        assert config.is_valid()
    
    def test_get_config_fails_with_invalid_config(self):
        """Test that get_config raises error with invalid config."""
        with patch.dict(os.environ, {'SAXO_REST_BASE': ''}, clear=True):
            with pytest.raises(ConfigurationError):
                get_config()


# Run tests with: python -m pytest tests/test_config_module.py -v
```

## Files to Create/Modify
- `tests/test_config_module.py` - Comprehensive config tests

## Definition of Done
- [ ] All test classes implemented
- [ ] Tests cover happy paths and error cases
- [ ] Environment variable mocking working
- [ ] All tests pass
- [ ] 80%+ code coverage achieved
- [ ] Tests documented with docstrings

## Running Tests

### Run All Config Tests
```bash
python -m pytest tests/test_config_module.py -v
```

### Run Specific Test Class
```bash
python -m pytest tests/test_config_module.py::TestWatchlist -v
```

### Run with Coverage
```bash
python -m pytest tests/test_config_module.py --cov=config.config --cov-report=html
```

### Run Specific Test
```bash
python -m pytest tests/test_config_module.py::TestValidation::test_valid_configuration_passes -v
```

## Story Points
**Estimate:** 3 points

## Dependencies
- Story 002-001 through 002-005 completed
- `pytest` installed
- `pytest-cov` installed (for coverage)

## Blocks
- Story 002-007 (documentation needs complete and tested module)

## Testing Best Practices
1. **Isolation:** Each test is independent
2. **Clear Names:** Test names describe what is being tested
3. **Arrange-Act-Assert:** Clear test structure
4. **Mock External Dependencies:** Use environment mocking
5. **Coverage:** Aim for 80%+ coverage

## Common Testing Patterns

### Environment Variable Mocking
```python
with patch.dict(os.environ, {'VAR_NAME': 'value'}):
    # Test code here
```

### Exception Testing
```python
with pytest.raises(ConfigurationError) as exc_info:
    # Code that should raise
assert "expected message" in str(exc_info.value)
```

### Temporary File Testing
```python
with tempfile.NamedTemporaryFile() as f:
    # Test file operations
```

## Coverage Goals
- **Overall Coverage:** 80%+
- **Critical Paths:** 100% (validation, credentials)
- **Helper Methods:** 80%+
- **Export Functions:** 70%+

## Test Execution Order
1. Initialization tests (foundation)
2. Credentials tests (authentication)
3. Watchlist tests (configuration)
4. Trading settings tests (parameters)
5. Validation tests (safety)
6. Export tests (debugging)

## Continuous Integration
These tests should be run:
- On every commit
- Before merging to main branch
- As part of CI/CD pipeline
- Before releases

## Architecture Notes
- **Test Isolation:** Use mocking to avoid dependencies
- **Comprehensive Coverage:** Test both success and failure cases
- **Documentation:** Each test has clear docstring
- **Maintainability:** Easy to add new tests

## Future Enhancements (Not in this story)
- Integration tests with real API
- Performance tests
- Load tests for configuration loading
- Mutation testing
- Property-based testing

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- [Pytest Documentation](https://docs.pytest.org/)
- [Python Testing Best Practices](https://realpython.com/pytest-python-testing/)

## Success Criteria
✅ Story is complete when:
1. All test classes implemented
2. All tests pass successfully
3. 80%+ code coverage achieved
4. Tests are well-documented
5. Can run tests independently
6. Coverage report generated
7. No test failures or warnings
