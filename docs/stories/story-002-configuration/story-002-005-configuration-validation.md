# Story 002-005: Configuration Validation and Error Handling

## Story Overview
Implement comprehensive validation logic for the complete configuration module, ensuring all settings are valid, consistent, and safe before the bot starts trading.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** validate the entire configuration on startup  
**So that** I can catch configuration errors before the bot starts trading

## Acceptance Criteria
- [ ] Comprehensive `is_valid()` method implemented
- [ ] All configuration sections validated
- [ ] Clear error messages for each validation failure
- [ ] Configuration health check method available
- [ ] Validation runs automatically on initialization
- [ ] Export configuration summary for debugging

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials)
- Story 002-003 completed (watchlist)
- Story 002-004 completed (trading settings)

### Validation Checks

1. **API Credentials Validation**
   - Base URL format and accessibility
   - Access token presence and format
   - Environment consistency

2. **Watchlist Validation**
   - At least one symbol present
   - Valid symbol formats
   - No duplicate symbols

3. **Trading Settings Validation**
   - Reasonable risk parameters
   - Valid timeframes
   - Logical trading hours
   - Positive amounts

4. **Cross-Setting Validation**
   - Min trade amount <= Max position size
   - Max position size <= Max portfolio exposure
   - Stop-loss < Take-profit (usually)

### Implementation

Update the `is_valid()` method:

```python
def is_valid(self) -> bool:
    """
    Validate that all required configuration is present and correct.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        self._validate_complete_configuration()
        return True
    except ConfigurationError:
        return False

def _validate_complete_configuration(self):
    """
    Perform comprehensive validation of entire configuration.
    
    Raises:
        ConfigurationError: If any validation check fails
    """
    # All individual validations are already called in their loaders
    # This method performs additional cross-validation
    
    # Validate position sizing logic
    if self.min_trade_amount > self.max_position_size:
        raise ConfigurationError(
            f"min_trade_amount (${self.min_trade_amount}) cannot exceed "
            f"max_position_size (${self.max_position_size})"
        )
    
    if self.max_position_size > self.max_portfolio_exposure:
        raise ConfigurationError(
            f"max_position_size (${self.max_position_size}) cannot exceed "
            f"max_portfolio_exposure (${self.max_portfolio_exposure})"
        )
    
    # Validate risk/reward ratio makes sense
    if self.stop_loss_pct >= self.take_profit_pct:
        import warnings
        warnings.warn(
            f"Stop-loss ({self.stop_loss_pct}%) >= Take-profit ({self.take_profit_pct}%). "
            "This may result in poor risk/reward ratio.",
            UserWarning
        )
    
    # Validate watchlist isn't empty
    if not self.watchlist:
        raise ConfigurationError("Watchlist cannot be empty")
    
    # Warn if production mode without dry-run
    if self.is_production() and not self.dry_run:
        import warnings
        warnings.warn(
            "⚠️  LIVE TRADING MODE: Bot is configured for real trading in production! "
            "Ensure this is intentional.",
            UserWarning
        )

def validate_symbol(self, symbol: str) -> bool:
    """
    Validate if a symbol format is acceptable.
    
    Args:
        symbol: Symbol to validate
    
    Returns:
        True if symbol format is valid
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    # Must contain only alphanumeric, /, -, .
    if not all(c.isalnum() or c in ['/', '-', '.'] for c in symbol):
        return False
    
    # Length check (reasonable bounds)
    if len(symbol) < 1 or len(symbol) > 20:
        return False
    
    return True

def get_configuration_health(self) -> Dict[str, Any]:
    """
    Get comprehensive health check of configuration.
    
    Returns:
        Dictionary with health status of each configuration section
    """
    health = {
        "overall_valid": self.is_valid(),
        "sections": {}
    }
    
    # Check API credentials
    try:
        health["sections"]["api_credentials"] = {
            "valid": bool(self.base_url and self.access_token),
            "base_url_set": bool(self.base_url),
            "token_set": bool(self.access_token),
            "environment": self.environment,
        }
    except Exception as e:
        health["sections"]["api_credentials"] = {
            "valid": False,
            "error": str(e)
        }
    
    # Check watchlist
    try:
        health["sections"]["watchlist"] = {
            "valid": len(self.watchlist) > 0,
            "symbol_count": len(self.watchlist),
            "stock_count": len(self.get_stock_symbols()),
            "crypto_count": len(self.get_crypto_symbols()),
        }
    except Exception as e:
        health["sections"]["watchlist"] = {
            "valid": False,
            "error": str(e)
        }
    
    # Check trading settings
    try:
        health["sections"]["trading_settings"] = {
            "valid": True,
            "trading_mode": self.get_trading_mode(),
            "dry_run": self.dry_run,
            "timeframe": self.default_timeframe,
            "risk_reward_ratio": round(self.take_profit_pct / self.stop_loss_pct, 2) if self.stop_loss_pct > 0 else 0,
        }
    except Exception as e:
        health["sections"]["trading_settings"] = {
            "valid": False,
            "error": str(e)
        }
    
    return health

def print_configuration_summary(self):
    """
    Print a formatted summary of the configuration for debugging.
    """
    print("=" * 60)
    print("🤖 Trading Bot Configuration Summary")
    print("=" * 60)
    
    # API Configuration
    print("\n📡 API Configuration:")
    print(f"  Environment:   {self.environment}")
    print(f"  Base URL:      {self.base_url}")
    print(f"  Token:         {self.get_masked_token()}")
    print(f"  Simulation:    {self.is_simulation()}")
    
    # Watchlist
    print("\n📊 Watchlist:")
    watchlist_summary = self.get_watchlist_summary()
    print(f"  Total Symbols: {watchlist_summary['total_symbols']}")
    print(f"  Stocks:        {watchlist_summary['stock_count']} - {', '.join(watchlist_summary['stocks'][:5])}")
    if watchlist_summary['stock_count'] > 5:
        print(f"                 ... and {watchlist_summary['stock_count'] - 5} more")
    print(f"  Crypto:        {watchlist_summary['crypto_count']} - {', '.join(watchlist_summary['crypto'])}")
    
    # Trading Settings
    print("\n⚙️  Trading Settings:")
    settings = self.get_trading_settings_summary()
    print(f"  Mode:          {settings['trading_mode']}")
    print(f"  Timeframe:     {settings['default_timeframe']}")
    print(f"  Dry Run:       {settings['dry_run']}")
    
    # Risk Management
    print("\n💰 Risk Management:")
    print(f"  Max Position:  ${settings['max_position_size']}")
    print(f"  Max Exposure:  ${settings['max_portfolio_exposure']}")
    print(f"  Stop Loss:     {settings['stop_loss_pct']}%")
    print(f"  Take Profit:   {settings['take_profit_pct']}%")
    print(f"  Risk/Reward:   1:{round(settings['take_profit_pct'] / settings['stop_loss_pct'], 1)}")
    
    # Trading Parameters
    print("\n📈 Trading Parameters:")
    print(f"  Min Trade:     ${settings['min_trade_amount']}")
    print(f"  Max Trades/Day:{settings['max_trades_per_day']}")
    print(f"  Trading Hours: {settings['trading_hours']}")
    
    # Logging
    print("\n📝 Logging:")
    print(f"  Log Level:     {settings['log_level']}")
    
    # Validation Status
    print("\n✅ Validation Status:")
    health = self.get_configuration_health()
    print(f"  Overall Valid: {'✓ Yes' if health['overall_valid'] else '✗ No'}")
    
    if not health['overall_valid']:
        print("\n⚠️  Configuration Issues Detected:")
        for section, status in health['sections'].items():
            if not status.get('valid', True):
                print(f"  - {section}: {status.get('error', 'Invalid')}")
    
    print("\n" + "=" * 60)

def export_configuration(self, include_sensitive: bool = False) -> Dict[str, Any]:
    """
    Export complete configuration as dictionary.
    
    Args:
        include_sensitive: If True, includes full tokens (DANGEROUS!)
    
    Returns:
        Dictionary with complete configuration
    """
    config_dict = {
        "api": {
            "base_url": self.base_url,
            "environment": self.environment,
            "token": self.access_token if include_sensitive else self.get_masked_token(),
            "is_simulation": self.is_simulation(),
        },
        "watchlist": {
            "symbols": self.watchlist,
            "stocks": self.get_stock_symbols(),
            "crypto": self.get_crypto_symbols(),
        },
        "trading_settings": {
            "timeframe": self.default_timeframe,
            "data_lookback_days": self.data_lookback_days,
            "trading_mode": self.get_trading_mode(),
            "dry_run": self.dry_run,
            "backtest_mode": self.backtest_mode,
        },
        "risk_management": {
            "max_position_size": self.max_position_size,
            "max_portfolio_exposure": self.max_portfolio_exposure,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "min_trade_amount": self.min_trade_amount,
        },
        "trading_parameters": {
            "max_trades_per_day": self.max_trades_per_day,
            "market_open_hour": self.market_open_hour,
            "market_close_hour": self.market_close_hour,
        },
        "logging": {
            "log_level": self.log_level,
            "enable_notifications": self.enable_notifications,
        }
    }
    
    return config_dict

def save_configuration_to_file(self, filepath: str, include_sensitive: bool = False):
    """
    Save configuration to JSON file for debugging.
    
    Args:
        filepath: Path to save configuration
        include_sensitive: If True, includes sensitive data (BE CAREFUL!)
    """
    import json
    
    config_dict = self.export_configuration(include_sensitive=include_sensitive)
    
    with open(filepath, 'w') as f:
        json.dump(config_dict, f, indent=2)
    
    print(f"Configuration saved to: {filepath}")
    if include_sensitive:
        print("⚠️  WARNING: File contains sensitive credentials!")
```

## Files to Modify
- `config/config.py` - Add validation and health check methods

## Definition of Done
- [ ] Comprehensive validation implemented
- [ ] Health check method working
- [ ] Configuration summary printing
- [ ] Export functionality implemented
- [ ] Cross-validation checks in place
- [ ] Clear error messages
- [ ] All tests pass

## Testing

### Test 1: Valid Configuration
```python
from config.config import Config

config = Config()
print(f"Configuration valid: {config.is_valid()}")
```

Expected: "Configuration valid: True"

### Test 2: Configuration Health Check
```python
from config.config import Config

config = Config()
health = config.get_configuration_health()

print(f"Overall valid: {health['overall_valid']}")
print(f"Sections: {list(health['sections'].keys())}")
print(f"Watchlist valid: {health['sections']['watchlist']['valid']}")
```

Expected:
```
Overall valid: True
Sections: ['api_credentials', 'watchlist', 'trading_settings']
Watchlist valid: True
```

### Test 3: Print Configuration Summary
```python
from config.config import Config

config = Config()
config.print_configuration_summary()
```

Expected: Formatted configuration summary output

### Test 4: Invalid Position Size
```python
import os
os.environ['MIN_TRADE_AMOUNT'] = '2000.0'
os.environ['MAX_POSITION_SIZE'] = '1000.0'

from config.config import Config, ConfigurationError
try:
    config = Config()
except ConfigurationError as e:
    print(f"Expected error: {e}")
```

Expected: "Expected error: min_trade_amount ($2000.0) cannot exceed max_position_size..."

### Test 5: Export Configuration
```python
from config.config import Config

config = Config()
config_dict = config.export_configuration(include_sensitive=False)

print(f"Keys: {list(config_dict.keys())}")
print(f"Has API: {'api' in config_dict}")
print(f"Has Watchlist: {'watchlist' in config_dict}")
print(f"Token masked: {'...' in config_dict['api']['token']}")
```

Expected:
```
Keys: ['api', 'watchlist', 'trading_settings', 'risk_management', 'trading_parameters', 'logging']
Has API: True
Has Watchlist: True
Token masked: True
```

### Test 6: Symbol Validation
```python
from config.config import Config

config = Config()
print(f"Valid 'AAPL': {config.validate_symbol('AAPL')}")
print(f"Valid 'BTC/USD': {config.validate_symbol('BTC/USD')}")
print(f"Valid 'ABC@123': {config.validate_symbol('ABC@123')}")  # Invalid
print(f"Valid '': {config.validate_symbol('')}")  # Invalid
```

Expected:
```
Valid 'AAPL': True
Valid 'BTC/USD': True
Valid 'ABC@123': False
Valid '': False
```

## Story Points
**Estimate:** 3 points

## Dependencies
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials)
- Story 002-003 completed (watchlist)
- Story 002-004 completed (trading settings)

## Blocks
- Story 002-006 (testing needs validation)
- Story 002-007 (documentation needs complete module)

## Validation Best Practices
1. **Fail Fast:** Catch errors during initialization
2. **Clear Messages:** Help users fix problems
3. **Cross-Validation:** Check relationships between settings
4. **Health Checks:** Provide diagnostic information
5. **Safe Defaults:** Prefer conservative settings

## Common Validation Errors

### Invalid Position Sizing
- Min trade > Max position
- Max position > Max exposure

### Invalid Risk Parameters
- Stop-loss = 0
- Negative percentages
- Stop-loss > Take-profit (warning)

### Invalid Watchlist
- Empty watchlist
- Invalid symbol format
- Duplicate symbols

### Invalid Trading Hours
- Hours outside 0-23 range
- Negative lookback days

## Architecture Notes
- **Defensive Programming:** Validate early and often
- **User-Friendly:** Clear error messages with solutions
- **Debuggable:** Export and summary methods aid troubleshooting
- **Secure:** Never log sensitive data by default

## Future Enhancements (Not in this story)
- Real-time configuration reloading
- Configuration versioning
- Configuration diff tool
- Automated configuration testing
- Configuration presets/templates

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- [Python Validation Best Practices](https://realpython.com/python-data-validation/)

## Success Criteria
✅ Story is complete when:
1. Comprehensive validation implemented
2. Health check functional
3. Summary printing working
4. Export functionality complete
5. Cross-validation checks in place
6. All verification tests pass
7. Clear error messages for all failures
8. Documentation complete
