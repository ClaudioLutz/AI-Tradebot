# Story 002-006: Configuration Module Testing

## Story Overview
Create comprehensive unit tests for the configuration module to ensure all functionality works correctly, including Saxo-specific OAuth authentication, structured watchlists, and multi-asset support.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** have comprehensive tests for the configuration module with OAuth and Saxo-specific features  
**So that** I can ensure configuration works reliably with both auth modes and catch regressions early

## Acceptance Criteria
- [ ] Unit tests for all configuration methods
- [ ] Tests for OAuth and manual token auth modes
- [ ] Tests for structured watchlist (AssetType + UIC)
- [ ] Tests for valid and invalid configurations
- [ ] Tests for environment variable overrides
- [ ] Tests for Saxo-specific validation logic
- [ ] Tests for asset-class-specific sizing
- [ ] Tests for trading hours modes
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

3. **Watchlist Tests (Saxo-Specific)**
   - Structured watchlist loading ({symbol, asset_type, uic})
   - Custom watchlist from environment
   - Instrument resolution
   - Crypto symbol format validation (no slashes)
   - Crypto asset type validation (FxSpot/FxCrypto)
   - Symbol validation

4. **Trading Settings Tests (Saxo-Specific)**
   - Default settings loading
   - Environment overrides
   - Settings validation
   - Trading mode checks
   - Asset-class-specific position sizing (Stock vs FX)
   - Trading hours modes (fixed/always/instrument)

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
from unittest.mock import patch, mock_open
from config.config import Config, ConfigurationError, get_config


# ==============================================================================
# BASE ENVIRONMENT FIXTURES
# ==============================================================================
# These fixtures ensure tests are deterministic and don't rely on local .env

@pytest.fixture
def base_manual_env():
    """
    Base environment for manual token mode tests.
    Always use with patch.dict(..., clear=True) for deterministic tests.
    """
    return {
        'SAXO_REST_BASE': 'https://gateway.saxobank.com/sim/openapi',
        'SAXO_ACCESS_TOKEN': 'test_manual_token_12345678901234567890',
        'SAXO_ENV': 'SIM',
        'DRY_RUN': 'True',
    }

@pytest.fixture
def base_oauth_env():
    """
    Base environment for OAuth mode tests.
    OAuth mode also requires mocking token file existence.
    """
    return {
        'SAXO_REST_BASE': 'https://gateway.saxobank.com/sim/openapi',
        'SAXO_APP_KEY': 'test_app_key',
        'SAXO_APP_SECRET': 'test_app_secret',
        'SAXO_REDIRECT_URI': 'http://localhost:8080/callback',
        'SAXO_ENV': 'SIM',
        'DRY_RUN': 'True',
    }


class TestConfigInitialization:
    """Test configuration initialization and loading."""
    
    def test_config_initialization_success(self, base_manual_env):
        """Test successful configuration initialization with manual token."""
        with patch.dict(os.environ, base_manual_env, clear=True):
            config = Config()
            assert config is not None
            assert hasattr(config, 'base_url')
            assert hasattr(config, 'watchlist')
            assert hasattr(config, 'default_timeframe')
    
    def test_missing_base_url_raises_error(self):
        """Test that missing SAXO_REST_BASE raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "SAXO_REST_BASE" in str(exc_info.value)
    
    def test_oauth_mode_missing_token_file_raises_error(self, base_oauth_env):
        """Test that OAuth mode without token file raises error."""
        with patch.dict(os.environ, base_oauth_env, clear=True):
            # Don't mock token file existence - it should fail
            with patch('os.path.exists', return_value=False):
                with pytest.raises(ConfigurationError) as exc_info:
                    Config()
                assert "token file not found" in str(exc_info.value).lower()
    
    def test_manual_mode_missing_token_raises_error(self):
        """Test that manual mode without SAXO_ACCESS_TOKEN raises error."""
        with patch.dict(os.environ, {
            'SAXO_REST_BASE': 'https://gateway.saxobank.com/sim/openapi',
        }, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "access" in str(exc_info.value).lower() or "token" in str(exc_info.value).lower()


class TestAuthentication:
    """Test API authentication (OAuth and manual token modes)."""
    
    def test_oauth_mode_detection(self, base_oauth_env):
        """Test OAuth mode is detected when app credentials present."""
        with patch.dict(os.environ, base_oauth_env, clear=True):
            # Mock token file existence and content
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data='{"access_token": "oauth_test_token"}')):
                    config = Config()
                    assert config.auth_mode == "oauth"
    
    def test_manual_mode_detection(self, base_manual_env):
        """Test manual mode is detected when only access token present."""
        with patch.dict(os.environ, base_manual_env, clear=True):
            config = Config()
            assert config.auth_mode == "manual"
    
    def test_get_access_token_oauth_mode(self, base_oauth_env):
        """Test get_access_token() in OAuth mode."""
        with patch.dict(os.environ, base_oauth_env, clear=True):
            # Mock OAuth token retrieval
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data='{"access_token": "oauth_token_from_file"}')):
                    config = Config()
                    if config.auth_mode == "oauth":
                        token = config.get_access_token()
                        assert token is not None
                        assert len(token) > 0
    
    def test_get_access_token_manual_mode(self, base_manual_env):
        """Test get_access_token() in manual mode."""
        with patch.dict(os.environ, base_manual_env, clear=True):
            config = Config()
            if config.auth_mode == "manual":
                token = config.get_access_token()
                assert token == base_manual_env['SAXO_ACCESS_TOKEN']


class TestCredentials:
    """Test API credentials loading and handling."""
    
    def test_base_url_trailing_slash_removed(self, base_manual_env):
        """Test that trailing slash is removed from base URL."""
        env = base_manual_env.copy()
        env['SAXO_REST_BASE'] = 'https://gateway.saxobank.com/sim/openapi/'
        with patch.dict(os.environ, env, clear=True):
            config = Config()
            assert not config.base_url.endswith('/')
    
    def test_token_masking(self, base_manual_env):
        """Test that tokens are properly masked."""
        with patch.dict(os.environ, base_manual_env, clear=True):
            config = Config()
            masked = config.get_masked_token()
            token = config.get_access_token()  # Use method, not attribute
            assert '...' in masked
            assert len(masked) < len(token)
    
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
    
    def test_auth_mode_in_summary(self):
        """Test auth mode included in configuration summary."""
        config = Config()
        summary = config.get_summary()
        assert 'auth_mode' in summary
        assert summary['auth_mode'] in ['oauth', 'manual']


class TestWatchlist:
    """Test structured watchlist configuration (Saxo-specific)."""
    
    def test_structured_watchlist_format(self):
        """Test that watchlist uses structured format."""
        config = Config()
        assert len(config.watchlist) > 0
        
        # Check first instrument has required fields
        first_inst = config.watchlist[0]
        assert 'symbol' in first_inst
        assert 'asset_type' in first_inst
        # UIC may be None if not yet resolved
    
    def test_instrument_with_uic(self):
        """Test instrument with resolved UIC."""
        config = Config()
        # Find an instrument with UIC
        resolved = [inst for inst in config.watchlist if inst.get('uic') is not None]
        if resolved:
            inst = resolved[0]
            assert isinstance(inst['uic'], int)
            assert inst['uic'] > 0
    
    def test_crypto_no_slash_format(self):
        """Test that crypto symbols use no-slash format (BTCUSD not BTC/USD)."""
        config = Config()
        crypto_instruments = [
            inst for inst in config.watchlist 
            if inst.get('asset_type') in ['FxSpot', 'FxCrypto']
        ]
        
        for inst in crypto_instruments:
            symbol = inst.get('symbol', '')
            assert '/' not in symbol, f"Crypto symbol {symbol} should not contain slash"
    
    def test_crypto_asset_type_validation(self):
        """Test that crypto uses FxSpot or FxCrypto asset type."""
        config = Config()
        crypto_symbols = ['BTC', 'ETH', 'LTC', 'XRP', 'ADA']
        
        for inst in config.watchlist:
            symbol = inst.get('symbol', '')
            if any(symbol.startswith(crypto) for crypto in crypto_symbols):
                assert inst.get('asset_type') in ['FxSpot', 'FxCrypto'], \
                    f"Crypto {symbol} should have FxSpot or FxCrypto asset type"
    
    def test_watchlist_by_asset_type(self):
        """Test filtering watchlist by asset type."""
        config = Config()
        
        stocks = [inst for inst in config.watchlist if inst.get('asset_type') == 'Stock']
        fx = [inst for inst in config.watchlist if inst.get('asset_type') in ['FxSpot', 'FxCrypto']]
        
        # Should have some instruments
        assert len(stocks) + len(fx) > 0
    
    def test_watchlist_summary_structure(self):
        """Test watchlist summary includes Saxo-specific info with stable schema."""
        config = Config()
        summary = config.get_watchlist_summary()
        
        # Required keys per stable schema
        assert 'total_instruments' in summary
        assert 'resolved' in summary  # Count of resolved instruments
        assert 'unresolved' in summary  # Count of unresolved instruments
        assert 'by_asset_type' in summary  # Breakdown by asset type
        
        # Verify counts are consistent
        assert summary['resolved'] + summary['unresolved'] == summary['total_instruments']


class TestTradingSettings:
    """Test trading settings configuration (Saxo asset-class-specific)."""
    
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
    
    def test_asset_specific_position_sizing_stock(self):
        """Test position sizing for stocks (USD value)."""
        config = Config()
        stock_inst = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
        price = 175.0
        
        position_value = config.get_position_size_for_asset(stock_inst, price, risk_pct=1.0)
        assert position_value > 0
        assert position_value <= config.max_portfolio_exposure
    
    def test_asset_specific_position_sizing_fx(self):
        """Test position sizing for FX/Crypto (notional amount)."""
        config = Config()
        crypto_inst = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}
        price = 43000.0
        
        notional = config.get_position_size_for_asset(crypto_inst, price, risk_pct=1.0)
        assert notional > 0
        assert notional <= config.max_portfolio_exposure
    
    def test_calculate_shares_for_stock(self):
        """Test calculating shares for stock orders."""
        config = Config()
        price = 150.0
        
        shares = config.calculate_shares_for_stock(price, risk_pct=1.0)
        assert isinstance(shares, int)
        assert shares >= 1  # Minimum 1 share
    
    def test_trading_hours_fixed_mode(self):
        """Test trading hours in fixed mode."""
        with patch.dict(os.environ, {'TRADING_HOURS_MODE': 'fixed'}):
            config = Config()
            stock = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
            
            # Within hours (14-21 UTC default)
            assert config.is_trading_allowed(stock, 15)
            # Outside hours
            assert not config.is_trading_allowed(stock, 22)
    
    def test_trading_hours_always_mode(self):
        """Test trading hours in always mode (24/7)."""
        with patch.dict(os.environ, {'TRADING_HOURS_MODE': 'always'}):
            config = Config()
            crypto = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}
            
            # Should allow trading at any hour
            assert config.is_trading_allowed(crypto, 3)
            assert config.is_trading_allowed(crypto, 15)
            assert config.is_trading_allowed(crypto, 22)
    
    def test_trading_hours_instrument_mode(self):
        """Test trading hours in instrument mode (per-asset) using injectable time."""
        with patch.dict(os.environ, {'TRADING_HOURS_MODE': 'instrument'}):
            config = Config()
            stock = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
            crypto = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}
            
            # Stock uses fixed hours (inject hour for deterministic testing)
            assert config.is_trading_allowed(stock, current_hour=15, current_minute=0)
            assert not config.is_trading_allowed(stock, current_hour=22, current_minute=0)
            
            # Crypto uses 24/5 - use injectable current_weekday parameter
            # Weekday 2 = Wednesday (trading allowed)
            assert config.is_trading_allowed(crypto, current_hour=3, current_weekday=2)
            # Weekday 6 = Sunday (trading NOT allowed)
            assert not config.is_trading_allowed(crypto, current_hour=3, current_weekday=6)
    
    def test_trading_settings_summary(self):
        """Test trading settings summary (Saxo-specific)."""
        config = Config()
        summary = config.get_trading_settings_summary()
        assert 'trading_mode' in summary
        assert 'default_timeframe' in summary
        assert 'max_position_value_usd' in summary
        assert 'max_fx_notional' in summary
        assert 'trading_hours_mode' in summary


class TestValidation:
    """Test configuration validation logic (Saxo-specific)."""
    
    def test_valid_configuration_passes(self):
        """Test that valid configuration passes validation."""
        config = Config()
        assert config.is_valid()
    
    def test_invalid_position_sizing_fails(self, base_manual_env):
        """Test that invalid position sizing fails validation."""
        env = base_manual_env.copy()
        env['MIN_TRADE_AMOUNT'] = '2000.0'
        env['MAX_POSITION_VALUE_USD'] = '1000.0'  # Use correct env var name
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "min_trade_amount" in str(exc_info.value)
    
    def test_invalid_stop_loss_fails(self):
        """Test that invalid stop-loss fails validation."""
        with patch.dict(os.environ, {'STOP_LOSS_PCT': '-5.0'}):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "stop_loss_pct" in str(exc_info.value)
    
    def test_symbol_validation_no_slashes(self):
        """Test symbol validation rejects slashes (Saxo crypto format)."""
        config = Config()
        assert config.validate_symbol('AAPL')
        assert config.validate_symbol('BTCUSD')  # No slash - correct
        assert not config.validate_symbol('BTC/USD')  # Slash - invalid for Saxo
        assert not config.validate_symbol('ABC@123')
        assert not config.validate_symbol('')
    
    def test_crypto_format_validation(self):
        """Test that crypto symbols without slashes pass validation."""
        config = Config()
        config.watchlist = [
            {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680},
            {"symbol": "ETHUSD", "asset_type": "FxSpot", "uic": 24681}
        ]
        
        # Should not raise error
        config._validate_crypto_symbol_format()
    
    def test_crypto_format_validation_rejects_slashes(self):
        """Test that crypto symbols with slashes fail validation."""
        config = Config()
        config.watchlist = [
            {"symbol": "BTC/USD", "asset_type": "FxSpot", "uic": 24680}
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            config._validate_crypto_symbol_format()
        assert "slash" in str(exc_info.value).lower()
    
    def test_instrument_resolution_validation(self):
        """Test instrument resolution validation."""
        config = Config()
        # Create watchlist with unresolved instrument
        config.watchlist = [
            {"symbol": "AAPL", "asset_type": "Stock", "uic": None}
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            config._validate_instrument_resolution()
        assert "unresolved" in str(exc_info.value).lower()
    
    def test_auth_mode_validation_oauth(self):
        """Test OAuth mode validation."""
        with patch.dict(os.environ, {
            'SAXO_APP_KEY': 'test_key',
            'SAXO_APP_SECRET': 'test_secret'
        }):
            with patch('os.path.exists', return_value=True):
                config = Config()
                # Should not raise if token file exists
                config._validate_auth_mode()
    
    def test_auth_mode_validation_manual(self):
        """Test manual token mode validation."""
        with patch.dict(os.environ, {
            'SAXO_ACCESS_TOKEN': 'test_token'
        }):
            config = Config()
            # Should not raise if token set
            config._validate_auth_mode()
    
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
        token = config.get_access_token()
        assert exported['api']['token'] == token
    
    def test_export_includes_auth_mode(self):
        """Test that export includes auth mode."""
        config = Config()
        exported = config.export_configuration()
        assert 'auth_mode' in exported['api']
        assert exported['api']['auth_mode'] in ['oauth', 'manual']
    
    def test_export_has_all_sections(self):
        """Test that export includes all configuration sections (Saxo-specific)."""
        config = Config()
        exported = config.export_configuration()
        assert 'api' in exported
        assert 'watchlist' in exported
        assert 'trading_settings' in exported
        assert 'risk_management' in exported
        
        # Check Saxo-specific fields
        assert 'auth_mode' in exported['api']
        assert 'instruments' in exported['watchlist'] or 'watchlist' in exported
        assert 'max_fx_notional' in exported['risk_management']
    
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

## Test Environment Setup

### OAuth Mode Testing
For OAuth mode tests, you may need to:
1. Mock token file existence: `patch('os.path.exists', return_value=True)`
2. Mock token file content: `patch('builtins.open', mock_open(read_data='{"access_token": "test"}'))`
3. Mock token refresh: `patch.object(SaxoOAuth, 'refresh_access_token')`

### Manual Mode Testing
For manual mode tests:
1. Set `SAXO_ACCESS_TOKEN` in patched environment
2. Clear OAuth credentials to force manual mode

### Structured Watchlist Testing
Use test fixtures with proper structure:
```python
@pytest.fixture
def sample_watchlist():
    return [
        {"symbol": "AAPL", "asset_type": "Stock", "uic": 211},
        {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}
    ]
```

## Continuous Integration
These tests should be run:
- On every commit
- Before merging to main branch
- As part of CI/CD pipeline
- Before releases

### CI Test Matrix
Test against both auth modes:
- OAuth mode (with mocked token file)
- Manual token mode (with environment variable)

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
- EPIC-002 Revision Summary: `docs/EPIC-002-REVISION-SUMMARY.md`
- [Pytest Documentation](https://docs.pytest.org/)
- [Python Testing Best Practices](https://realpython.com/pytest-python-testing/)
- [Saxo OAuth Documentation](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)

## Success Criteria
✅ Story is complete when:
1. All test classes implemented (including OAuth and Saxo-specific tests)
2. All tests pass successfully
3. Tests cover both OAuth and manual auth modes
4. Tests validate structured watchlist format
5. Tests validate Saxo-specific features (crypto format, asset-class sizing)
6. 80%+ code coverage achieved
7. Tests are well-documented
8. Can run tests independently
9. Coverage report generated
10. No test failures or warnings
