# Story 002-005: Configuration Validation and Error Handling

## Story Overview
Implement comprehensive validation logic for the complete configuration module, ensuring all settings are valid, consistent, safe, and compliant with Saxo Bank requirements before the bot starts trading.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** validate the entire configuration with Saxo-specific checks on startup  
**So that** I catch configuration errors before the bot starts trading and ensure proper OAuth and instrument resolution

## Acceptance Criteria
- [ ] Comprehensive `is_valid()` method implemented
- [ ] All configuration sections validated
- [ ] Saxo-specific validations (OAuth, instrument resolution, crypto format)
- [ ] Clear error messages for each validation failure
- [ ] Configuration health check method available
- [ ] Validation runs automatically on initialization
- [ ] Export configuration summary for debugging

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials with OAuth)
- Story 002-003 completed (structured watchlist)
- Story 002-004 completed (trading settings)

### Validation Checks

1. **API Credentials Validation (Saxo-Specific)**
   - Base URL format and accessibility
   - Auth mode consistency (OAuth vs manual token)
   - OAuth: app credentials + token file existence
   - Manual: access token presence
   - Environment consistency

2. **Watchlist Validation (Saxo-Specific)**
   - At least one instrument present
   - Structured format: {symbol, asset_type, uic}
   - Instrument resolution (UIC presence for trading)
   - Crypto format validation (no slashes: BTCUSD not BTC/USD)
   - Crypto asset type compatibility (FxSpot vs FxCrypto)
   - No duplicate symbols

3. **Trading Settings Validation**
   - Reasonable risk parameters
   - Valid timeframes
   - Logical trading hours
   - Positive amounts
   - Asset-class-specific sizing parameters

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
    
    Includes Saxo-specific validations for auth, instruments, and asset types.
    
    Raises:
        ConfigurationError: If any validation check fails
    """
    # Saxo-specific validations
    self._validate_auth_mode()
    self._validate_instrument_resolution()
    self._validate_crypto_asset_types()
    self._validate_crypto_symbol_format()
    
    # Cross-validation for position sizing logic
    if self.min_trade_amount > self.max_position_value_usd:
        raise ConfigurationError(
            f"min_trade_amount (${self.min_trade_amount}) cannot exceed "
            f"max_position_value_usd (${self.max_position_value_usd})"
        )
    
    if self.max_position_value_usd > self.max_portfolio_exposure:
        raise ConfigurationError(
            f"max_position_value_usd (${self.max_position_value_usd}) cannot exceed "
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
    
    # Warn if production with manual token mode
    if self.is_production() and self.auth_mode == "manual":
        import warnings
        warnings.warn(
            "⚠️  Using manual token mode in LIVE environment!\n"
            "   Manual tokens expire after 24 hours.\n"
            "   Consider switching to OAuth mode for production.",
            UserWarning
        )

def _validate_auth_mode(self):
    """
    Validate that authentication mode is properly configured.
    
    Ensures either:
    - OAuth mode: app credentials + token file exists
    - Manual mode: access token present
    
    Raises:
        ConfigurationError: If auth configuration is invalid
    """
    if self.auth_mode == "oauth":
        # OAuth mode validation
        if not self.app_key or not self.app_secret:
            raise ConfigurationError(
                "OAuth mode detected but app credentials incomplete. "
                "Required: SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI"
            )
        
        if not os.path.exists(self.token_file):
            raise ConfigurationError(
                f"OAuth mode configured but token file not found: {self.token_file}\n"
                f"Please authenticate first:\n"
                f"  python scripts/saxo_login.py"
            )
        
        print(f"✓ OAuth authentication mode validated")
    
    elif self.auth_mode == "manual":
        # Manual token mode validation
        if not self.manual_access_token:
            raise ConfigurationError(
                "Manual token mode detected but SAXO_ACCESS_TOKEN not set."
            )
        
        print(f"⚠️  Manual token mode (24-hour limitation)")
        print(f"   For production use, switch to OAuth mode")
    
    else:
        raise ConfigurationError(f"Unknown auth mode: {self.auth_mode}")

def _validate_instrument_resolution(self, strict: bool = None):
    """
    Validate that all watchlist instruments can be resolved to {AssetType, Uic}.
    
    This is critical for Saxo order placement which requires both.
    Validation strictness depends on runtime mode:
    - LIVE trading: Strict (raises error if unresolved)
    - DRY_RUN mode: Warning only (allows development/testing without UICs)
    - Market data only: Warning only (UICs not required for quotes)
    
    Args:
        strict: Override strictness. If None, auto-detect from trading mode.
                True = error on unresolved, False = warning only.
    
    Raises:
        ConfigurationError: If strict mode and instruments lack UICs
    """
    unresolved = [
        inst for inst in self.watchlist 
        if inst.get("uic") is None
    ]
    
    if not unresolved:
        print(f"✓ All {len(self.watchlist)} instruments resolved with UICs")
        return
    
    # Determine strictness
    if strict is None:
        # Auto-detect: strict only for LIVE trading mode
        strict = self.is_live_trading()
    
    symbols = [inst.get("symbol") for inst in unresolved]
    message = (
        f"Unresolved instruments found: {', '.join(symbols)}\n"
        f"Run config.resolve_instruments() to query Saxo API for UICs.\n"
        f"Or manually specify UICs in watchlist configuration."
    )
    
    if strict:
        # LIVE mode: require all UICs for order placement
        raise ConfigurationError(message)
    else:
        # DRY_RUN or development: warn but allow
        import warnings
        warnings.warn(
            f"⚠️  {len(unresolved)} unresolved instrument(s): {', '.join(symbols)}\n"
            "   UICs required for order placement. In DRY_RUN mode, this is a warning.\n"
            "   For LIVE trading, all instruments must be resolved.",
            UserWarning
        )
        print(f"⚠️  {len(unresolved)} of {len(self.watchlist)} instruments unresolved (warning in DRY_RUN mode)")

def _validate_crypto_asset_types(self):
    """
    Validate CryptoFX asset types (FxSpot vs FxCrypto).
    
    Saxo is transitioning from FxSpot to FxCrypto for crypto instruments.
    Accept both during transition period.
    
    Raises:
        ConfigurationError: If crypto has invalid asset type
    """
    crypto_instruments = [
        inst for inst in self.watchlist
        if inst.get("symbol", "").upper().startswith(("BTC", "ETH", "LTC", "XRP", "ADA"))
    ]
    
    for inst in crypto_instruments:
        asset_type = inst.get("asset_type")
        
        # Accept both FxSpot and FxCrypto for crypto
        if asset_type not in ["FxSpot", "FxCrypto"]:
            symbol = inst.get("symbol")
            raise ConfigurationError(
                f"Crypto instrument {symbol} has invalid asset type: {asset_type}\n"
                f"Expected 'FxSpot' or 'FxCrypto'. "
                f"Note: Saxo is transitioning crypto from FxSpot to FxCrypto."
            )
    
    if crypto_instruments:
        print(f"✓ CryptoFX validation passed for {len(crypto_instruments)} instruments")

def _validate_crypto_symbol_format(self):
    """
    Validate that crypto symbols use Saxo format (no slashes).
    
    Saxo requires: BTCUSD, ETHUSD (not BTC/USD, ETH/USD)
    
    Raises:
        ConfigurationError: If crypto symbols contain slashes
    """
    crypto_with_slashes = [
        inst.get("symbol") for inst in self.watchlist
        if inst.get("asset_type") in ["FxSpot", "FxCrypto"] and "/" in inst.get("symbol", "")
    ]
    
    if crypto_with_slashes:
        raise ConfigurationError(
            f"Crypto symbols contain slashes (invalid for Saxo): {', '.join(crypto_with_slashes)}\n"
            f"Saxo CryptoFX format: BTCUSD, ETHUSD (no slashes)\n"
            f"Please update watchlist to remove slashes."
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
    
    # Must contain only alphanumeric, -, .
    # Note: Slashes are NOT allowed for Saxo crypto
    if not all(c.isalnum() or c in ['-', '.'] for c in symbol):
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
            "valid": bool(self.base_url and self.get_access_token()),
            "base_url_set": bool(self.base_url),
            "auth_mode": self.auth_mode,
            "token_set": bool(self.get_access_token()),
            "environment": self.environment,
        }
    except Exception as e:
        health["sections"]["api_credentials"] = {
            "valid": False,
            "error": str(e)
        }
    
    # Check watchlist
    try:
        unresolved = sum(1 for inst in self.watchlist if inst.get("uic") is None)
        health["sections"]["watchlist"] = {
            "valid": len(self.watchlist) > 0 and unresolved == 0,
            "instrument_count": len(self.watchlist),
            "resolved_count": len(self.watchlist) - unresolved,
            "unresolved_count": unresolved,
            "has_crypto": any(inst.get("asset_type") in ["FxSpot", "FxCrypto"] for inst in self.watchlist),
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
            "trading_hours_mode": self.trading_hours_mode,
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
    print(f"  Auth Mode:     {self.auth_mode}")
    print(f"  Base URL:      {self.base_url}")
    print(f"  Token:         {self.get_masked_token()}")
    print(f"  Simulation:    {self.is_simulation()}")
    
    # Watchlist
    print("\n📊 Watchlist:")
    watchlist_summary = self.get_watchlist_summary()
    print(f"  Total Instruments: {watchlist_summary['total_instruments']}")
    
    # Group by asset type
    asset_types = {}
    for inst in self.watchlist:
        asset_type = inst.get("asset_type", "Unknown")
        if asset_type not in asset_types:
            asset_types[asset_type] = []
        asset_types[asset_type].append(inst.get("symbol"))
    
    for asset_type, symbols in asset_types.items():
        print(f"  {asset_type}: {len(symbols)} - {', '.join(symbols[:5])}")
        if len(symbols) > 5:
            print(f"    ... and {len(symbols) - 5} more")
    
    # Trading Settings
    print("\n⚙️  Trading Settings:")
    settings = self.get_trading_settings_summary()
    print(f"  Mode:          {settings['trading_mode']}")
    print(f"  Timeframe:     {settings['default_timeframe']}")
    print(f"  Dry Run:       {settings['dry_run']}")
    print(f"  Hours Mode:    {settings['trading_hours_mode']}")
    
    # Risk Management
    print("\n💰 Risk Management:")
    print(f"  Stock Position:${settings['max_position_value_usd']}")
    print(f"  FX Notional:   ${settings['max_fx_notional']}")
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
            "auth_mode": self.auth_mode,
            "environment": self.environment,
            "token": self.get_access_token() if include_sensitive else self.get_masked_token(),
            "is_simulation": self.is_simulation(),
        },
        "watchlist": {
            "instruments": self.watchlist,
            "count": len(self.watchlist),
        },
        "trading_settings": {
            "timeframe": self.default_timeframe,
            "data_lookback_days": self.data_lookback_days,
            "trading_mode": self.get_trading_mode(),
            "dry_run": self.dry_run,
            "backtest_mode": self.backtest_mode,
            "trading_hours_mode": self.trading_hours_mode,
        },
        "risk_management": {
            "max_position_value_usd": self.max_position_value_usd,
            "max_fx_notional": self.max_fx_notional,
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
- `config/config.py` - Add Saxo-specific validation and health check methods

## Definition of Done
- [ ] Comprehensive validation implemented
- [ ] Saxo-specific validations added (OAuth, instruments, crypto)
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

### Test 2: OAuth Mode Validation
```python
from config.config import Config

config = Config()  # Should auto-detect OAuth if configured
print(f"Auth mode: {config.auth_mode}")
print(f"Token file exists: {os.path.exists(config.token_file)}")
```

Expected:
```
Auth mode: oauth
Token file exists: True
✓ OAuth authentication mode validated
```

### Test 3: Instrument Resolution Validation
```python
from config.config import Config

config = Config()
# If instruments unresolved, should raise error
try:
    config._validate_instrument_resolution()
except ConfigurationError as e:
    print(f"Expected error: {e}")
```

Expected (if unresolved): "Expected error: Unresolved instruments found: AAPL, MSFT..."

### Test 4: Crypto Format Validation
```python
from config.config import Config

# Test with invalid crypto format (slash)
config = Config()
config.watchlist = [
    {"symbol": "BTC/USD", "asset_type": "FxSpot", "uic": 24680}
]

try:
    config._validate_crypto_symbol_format()
except ConfigurationError as e:
    print(f"Expected error: {e}")
```

Expected: "Expected error: Crypto symbols contain slashes..."

### Test 5: Configuration Health Check
```python
from config.config import Config

config = Config()
health = config.get_configuration_health()

print(f"Overall valid: {health['overall_valid']}")
print(f"Auth mode: {health['sections']['api_credentials']['auth_mode']}")
print(f"Instruments: {health['sections']['watchlist']['instrument_count']}")
print(f"Resolved: {health['sections']['watchlist']['resolved_count']}")
```

Expected:
```
Overall valid: True
Auth mode: oauth
Instruments: 5
Resolved: 5
```

### Test 6: Print Configuration Summary
```python
from config.config import Config

config = Config()
config.print_configuration_summary()
```

Expected: Formatted configuration summary with all sections

### Test 7: Symbol Validation (No Slashes)
```python
from config.config import Config

config = Config()
print(f"Valid 'AAPL': {config.validate_symbol('AAPL')}")
print(f"Valid 'BTCUSD': {config.validate_symbol('BTCUSD')}")
print(f"Valid 'BTC/USD': {config.validate_symbol('BTC/USD')}")  # Should be False
print(f"Valid 'ABC@123': {config.validate_symbol('ABC@123')}")  # Should be False
```

Expected:
```
Valid 'AAPL': True
Valid 'BTCUSD': True
Valid 'BTC/USD': False
Valid 'ABC@123': False
```

## Story Points
**Estimate:** 5 points (Saxo-specific validations add complexity)

## Dependencies
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials with OAuth)
- Story 002-003 completed (structured watchlist)
- Story 002-004 completed (trading settings)

## Blocks
- Story 002-006 (testing needs validation)
- Story 002-007 (documentation needs complete module)

## Saxo-Specific Validation Rationale

### OAuth Mode Validation
- **Ensures long-running capability**: OAuth with refresh tokens enables >24h operation
- **Prevents production failures**: Catches missing token files before trading
- **Clear guidance**: Error messages tell users how to authenticate

### Instrument Resolution Validation
- **Trading requirement**: Saxo orders require AssetType + UIC
- **Prevents order failures**: Catches unresolved instruments before trading
- **Resolution guidance**: Error message instructs how to resolve UICs

### Crypto Format Validation
- **Saxo-specific requirement**: CryptoFX uses BTCUSD not BTC/USD
- **Prevents lookup failures**: Slash format won't match Saxo instruments
- **Clear migration path**: Error message explains correct format

### Crypto Asset Type Validation
- **Transition support**: Accepts both FxSpot and FxCrypto during Saxo migration
- **Future-proof**: Ready for Saxo's FxSpot → FxCrypto transition
- **Explicit validation**: Rejects invalid asset types for crypto

## Common Validation Errors

### Auth Mode Errors
- **OAuth without token file**: Run `python scripts/saxo_login.py`
- **Missing app credentials**: Set SAXO_APP_KEY, SAXO_APP_SECRET
- **Manual without token**: Set SAXO_ACCESS_TOKEN

### Instrument Resolution Errors
- **Unresolved UICs**: Run `config.resolve_instruments()`
- **Ambiguous matches**: Manually specify UIC
- **Invalid symbols**: Check Saxo instrument availability

### Crypto Format Errors
- **Slashes in symbols**: Remove slashes (BTC/USD → BTCUSD)
- **Wrong asset type**: Use FxSpot or FxCrypto
- **Invalid crypto pairs**: Check Saxo CryptoFX availability

## Architecture Notes
- **Defensive Programming:** Validate early and often
- **Saxo-Specific:** Checks aligned with Saxo requirements
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
- EPIC-002 Revision Summary: `docs/EPIC-002-REVISION-SUMMARY.md`
- [Saxo OAuth Documentation](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
- [Saxo Order Placement](https://www.developer.saxo/openapi/learn/order-placement)

## Success Criteria
✅ Story is complete when:
1. Comprehensive validation implemented
2. Saxo-specific validations working (OAuth, instruments, crypto)
3. Health check functional
4. Summary printing working
5. Export functionality complete
6. Cross-validation checks in place
7. All verification tests pass
8. Clear error messages for all failures
9. Documentation complete
