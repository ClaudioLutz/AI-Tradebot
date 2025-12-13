# Story 002-007: Configuration Module Documentation

## Story Overview
Create comprehensive documentation for the configuration module including OAuth-first authentication, structured instruments, API reference, usage examples, configuration guide, and troubleshooting tips for Saxo Bank.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** have comprehensive documentation for the configuration module with Saxo-specific OAuth and structured instruments  
**So that** I can easily understand OAuth authentication, instrument resolution, and multi-asset configuration

## Acceptance Criteria
- [ ] README/guide for configuration module created
- [ ] OAuth authentication documentation (recommended approach)
- [ ] Structured instruments format documented
- [ ] Manual token mode documentation (testing only)
- [ ] API reference documentation complete
- [ ] Usage examples provided (OAuth-first)
- [ ] Configuration options documented
- [ ] Troubleshooting guide included (OAuth lifecycle, instrument resolution)
- [ ] Environment variable reference complete
- [ ] Best practices documented

## Technical Details

### Prerequisites
- Story 002-001 through 002-006 completed
- Configuration module fully implemented and tested

### Documentation Sections

1. **Configuration Guide** - Overview and quick start
2. **API Reference** - Detailed class/method documentation
3. **Usage Examples** - Common use cases
4. **Environment Variables** - Complete reference
5. **Troubleshooting** - Common issues and solutions
6. **Best Practices** - Recommended patterns

### Implementation

Create `docs/CONFIG_MODULE_GUIDE.md`:

```markdown
# Configuration Module Guide

## Overview

The configuration module (`config/config.py`) provides centralized management of all trading bot settings for Saxo Bank including:

- **OAuth Authentication:** Long-running operation via refresh tokens (recommended)
- **Manual Token Mode:** 24-hour tokens for quick testing
- **Structured Watchlist:** Instruments with AssetType + UIC for reliable order placement
- **Asset-Class-Specific Settings:** Different sizing for stocks vs FX/crypto
- **Trading Settings:** Risk parameters, timeframes, and operational modes
- **Validation:** Comprehensive Saxo-specific configuration checks

## Quick Start

### Basic Usage

```python
from config.config import Config

# Initialize configuration (auto-detects OAuth or manual mode)
config = Config()

# Access configuration
print(f"Auth Mode: {config.auth_mode}")  # "oauth" or "manual"
print(f"Environment: {config.environment}")
print(f"Trading Mode: {config.get_trading_mode()}")

# Get access token (works for both modes, auto-refreshes in OAuth)
token = config.get_access_token()

# Access structured watchlist
for inst in config.watchlist:
    print(f"{inst['symbol']}: {inst['asset_type']}, UIC: {inst['uic']}")
```

### Using Convenience Function

```python
from config.config import get_config

# Get validated configuration
config = get_config()
```

## Configuration Sections

### 1. Authentication

Saxo Bank API supports two authentication modes:

#### OAuth Mode (Recommended for Production)

OAuth provides long-running operation through automatic token refresh:

**Setup:**
1. Create app in [Saxo Developer Portal](https://www.developer.saxo/openapi/appmanagement)
2. Configure environment variables:
   ```bash
   SAXO_APP_KEY=your_app_key
   SAXO_APP_SECRET=your_app_secret
   SAXO_REDIRECT_URI=http://localhost:8080/callback
   ```
3. Authenticate once:
   ```bash
   python scripts/saxo_login.py
   ```
4. Tokens stored in `.secrets/saxo_tokens.json` (auto-refreshed)

**Token Lifecycle:**
- Access tokens: ~20 minutes (auto-refreshed)
- Refresh tokens: Days/weeks
- Bot runs continuously without manual intervention

**Example:**
```python
config = Config()  # Auto-detects OAuth mode
print(f"Auth mode: {config.auth_mode}")  # "oauth"

# Get token (auto-refreshes if needed)
token = config.get_access_token()
```

#### Manual Token Mode (Testing Only)

Manual mode uses 24-hour tokens for quick testing:

**Setup:**
1. Get token from [Saxo Token Generator](https://www.developer.saxo/openapi/token)
2. Set environment variable:
   ```bash
   SAXO_ACCESS_TOKEN=your_24hour_token
   ```

⚠️ **Limitations:**
- Expires after 24 hours
- Requires manual renewal
- Not suitable for long-running bots

**Example:**
```python
config = Config()  # Auto-detects manual mode
print(f"Auth mode: {config.auth_mode}")  # "manual"
```

**Environment Variables:**
- `SAXO_REST_BASE` - Saxo OpenAPI base URL
- `SAXO_ENV` - Environment (SIM or LIVE, default: SIM)

**For OAuth:**
- `SAXO_APP_KEY`
- `SAXO_APP_SECRET`
- `SAXO_REDIRECT_URI`

**For Manual:**
- `SAXO_ACCESS_TOKEN`

### 2. Structured Watchlist

Saxo requires **AssetType + UIC** for order placement. The config module uses a structured format:

**Structured Format:**
```python
watchlist = [
    {
        "symbol": "AAPL",          # Human-readable symbol
        "asset_type": "Stock",     # Required: Stock, Etf, FxSpot, FxCrypto
        "uic": 211,                # Required: Universal Instrument Code
        "exchange": "NASDAQ"       # Optional: Exchange metadata
    },
    {
        "symbol": "BTCUSD",        # Crypto (NO SLASH!)
        "asset_type": "FxSpot",    # Currently FxSpot, transitioning to FxCrypto
        "uic": 24680               # Resolved from Saxo API
    }
]
```

**Instrument Resolution:**
Convert human-readable symbols to Saxo UICs:

```python
config = Config()

# Watchlist loaded with UICs = None
print(config.watchlist[0])
# {"symbol": "AAPL", "asset_type": "Stock", "uic": None}

# Resolve via Saxo API
config.resolve_instruments()

# Now has UIC
print(config.watchlist[0])
# {"symbol": "AAPL", "asset_type": "Stock", "uic": 211, "description": "Apple Inc.", "exchange": "NASDAQ"}
```

**CryptoFX Format:**
⚠️ **Critical:** Saxo uses **no slash** for crypto symbols:

- ✅ Correct: `"BTCUSD"`, `"ETHUSD"`, `"LTCUSD"`
- ❌ Wrong: `"BTC/USD"`, `"ETH/USD"`

Currently traded as `AssetType: FxSpot`. Saxo is planning migration to `FxCrypto`.

**Configuration accepts both** for forward compatibility:
```python
{"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}     # Current
{"symbol": "BTCUSD", "asset_type": "FxCrypto", "uic": 24680}  # Future
```

### 3. Trading Settings (Asset-Class-Specific)

Operational parameters with Saxo multi-asset support.

**Key Settings:**
- `default_timeframe` - Market data timeframe (1Min, 5Min, etc.)
- `dry_run` - Simulation mode flag
- `max_position_value_usd` - Max position for Stock/ETF (converted to shares)
- `max_fx_notional` - Max notional for FX/CryptoFX
- `trading_hours_mode` - Trading hours strategy (fixed/always/instrument)
- `stop_loss_pct` - Stop-loss percentage
- `take_profit_pct` - Take-profit percentage

**Asset-Class-Specific Position Sizing:**
```python
config = Config()

# Stock order (USD value → shares)
stock_inst = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
price = 175.0
value_usd = config.get_position_size_for_asset(stock_inst, price, risk_pct=1.0)
shares = config.calculate_shares_for_stock(price, risk_pct=1.0)
print(f"Buy {shares} shares of AAPL (${value_usd:.2f})")

# FX/Crypto order (notional amount)
crypto_inst = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}
price = 43000.0
notional = config.get_position_size_for_asset(crypto_inst, price, risk_pct=1.0)
btc_units = notional / price
print(f"Buy {btc_units:.6f} BTC (notional: ${notional:.2f})")
```

**Trading Hours Modes:**
```python
config = Config()

# Mode: fixed (use configured hours, e.g., US market 14:00-21:00 UTC)
# Mode: always (24/7 for crypto-only bots)
# Mode: instrument (per-asset: stocks use fixed, crypto 24/5)

stock = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
crypto = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}

# Check trading allowed
if config.is_trading_allowed(stock):
    print("Can trade stocks now")

if config.is_trading_allowed(crypto):
    print("Can trade crypto now")
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SAXO_REST_BASE` | Saxo API base URL | `https://gateway.saxobank.com/sim/openapi` |
| `SAXO_ACCESS_TOKEN` | Saxo API access token | `eyJhbGc...xyz` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SAXO_ENV` | `SIM` | Environment (SIM or LIVE) |
| `WATCHLIST` | *(structured)* | JSON array of instruments |
| `DEFAULT_TIMEFRAME` | `1Min` | Market data timeframe |
| `DRY_RUN` | `True` | Enable simulation mode |
| `MAX_POSITION_VALUE_USD` | `1000.0` | Max position for Stock/ETF ($) |
| `MAX_FX_NOTIONAL` | `10000.0` | Max notional for FX/Crypto |
| `MAX_PORTFOLIO_EXPOSURE` | `10000.0` | Max total exposure ($) |
| `TRADING_HOURS_MODE` | `fixed` | Trading hours mode (fixed/always/instrument) |
| `STOP_LOSS_PCT` | `2.0` | Stop-loss percentage |
| `TAKE_PROFIT_PCT` | `5.0` | Take-profit percentage |
| `MIN_TRADE_AMOUNT` | `100.0` | Minimum trade amount ($) |
| `MAX_TRADES_PER_DAY` | `10` | Max trades per day |
| `MARKET_OPEN_HOUR` | `14` | Market open hour (UTC) |
| `MARKET_CLOSE_HOUR` | `21` | Market close hour (UTC) |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Reference

### Config Class

Main configuration class.

#### Methods

##### `__init__()`
Initialize configuration by loading from environment variables.

**Raises:**
- `ConfigurationError` - If required credentials missing

**Example:**
```python
config = Config()
```

##### `is_valid() -> bool`
Validate complete configuration.

**Returns:** `True` if valid

##### `get_masked_token() -> str`
Get masked access token for safe logging.

**Returns:** Masked token (e.g., "eyJh...xyz9")

##### `is_simulation() -> bool`
Check if using SIM environment.

**Returns:** `True` if simulation

##### `is_production() -> bool`
Check if using LIVE environment.

**Returns:** `True` if production

##### `get_stock_symbols() -> List[str]`
Get only stock symbols from watchlist.

**Returns:** List of stock symbols

##### `get_crypto_symbols() -> List[str]`
Get only crypto symbols from watchlist.

**Returns:** List of crypto symbols

##### `add_symbol(symbol: str) -> None`
Add symbol to watchlist.

**Parameters:**
- `symbol` - Symbol to add

**Raises:**
- `ConfigurationError` - If symbol invalid or duplicate

##### `remove_symbol(symbol: str) -> None`
Remove symbol from watchlist.

**Parameters:**
- `symbol` - Symbol to remove

**Raises:**
- `ConfigurationError` - If symbol not in watchlist

##### `is_dry_run() -> bool`
Check if dry-run mode enabled.

**Returns:** `True` if dry-run mode

##### `is_live_trading() -> bool`
Check if live trading mode.

**Returns:** `True` if live trading

##### `get_trading_mode() -> str`
Get current trading mode.

**Returns:** "BACKTEST", "DRY_RUN", or "LIVE"

##### `calculate_position_size(price: float, risk_pct: float = 1.0) -> float`
Calculate position size based on risk parameters.

**Parameters:**
- `price` - Current price
- `risk_pct` - Risk percentage (default 1.0%)

**Returns:** Position size in dollars

##### `is_within_trading_hours(current_hour: Optional[int] = None) -> bool`
Check if within trading hours.

**Parameters:**
- `current_hour` - Hour to check (0-23), None for current

**Returns:** `True` if within trading hours

##### `get_configuration_health() -> Dict[str, Any]`
Get comprehensive health check.

**Returns:** Dictionary with health status

##### `print_configuration_summary()`
Print formatted configuration summary.

##### `export_configuration(include_sensitive: bool = False) -> Dict[str, Any]`
Export configuration as dictionary.

**Parameters:**
- `include_sensitive` - Include sensitive data (dangerous!)

**Returns:** Configuration dictionary

##### `save_configuration_to_file(filepath: str, include_sensitive: bool = False)`
Save configuration to JSON file.

**Parameters:**
- `filepath` - Path to save
- `include_sensitive` - Include sensitive data

### ConfigurationError

Custom exception for configuration errors.

### get_config() -> Config

Convenience function to get validated config.

**Returns:** Validated Config instance

**Raises:**
- `ConfigurationError` - If configuration invalid

## Usage Examples

### Example 1: Basic Configuration

```python
from config.config import Config

config = Config()
config.print_configuration_summary()
```

### Example 2: Check Configuration Health

```python
from config.config import Config

config = Config()
health = config.get_configuration_health()

if health['overall_valid']:
    print("✓ Configuration is valid")
else:
    print("✗ Configuration has issues:")
    for section, status in health['sections'].items():
        if not status.get('valid', True):
            print(f"  - {section}: {status.get('error')}")
```

### Example 3: Dynamic Watchlist Management

```python
from config.config import Config

config = Config()

# View current watchlist
print(f"Current symbols: {config.watchlist}")

# Add a symbol
config.add_symbol("NVDA")
print(f"Added NVDA: {config.watchlist}")

# Filter by type
stocks = config.get_stock_symbols()
crypto = config.get_crypto_symbols()
print(f"Stocks: {stocks}")
print(f"Crypto: {crypto}")
```

### Example 4: Position Sizing

```python
from config.config import Config

config = Config()

# Calculate position sizes for different stocks
symbols_prices = {
    "AAPL": 175.0,
    "MSFT": 380.0,
    "GOOGL": 140.0
}

for symbol, price in symbols_prices.items():
    size = config.calculate_position_size(price, risk_pct=1.0)
    shares = int(size / price)
    print(f"{symbol}: ${size:.2f} ({shares} shares)")
```

### Example 5: Trading Hours Check

```python
from config.config import Config
from datetime import datetime

config = Config()

# Check if we should trade now
current_hour = datetime.utcnow().hour

if config.is_within_trading_hours(current_hour):
    print("✓ Within trading hours - proceed with trading")
else:
    print("✗ Outside trading hours - wait for market open")
```

### Example 6: Export Configuration for Debugging

```python
from config.config import Config

config = Config()

# Export without sensitive data
config.save_configuration_to_file(
    "config_snapshot.json",
    include_sensitive=False
)
print("Configuration saved to config_snapshot.json")
```

## Troubleshooting

### Issue: ConfigurationError on initialization

**Symptom:** `ConfigurationError: SAXO_REST_BASE not found`

**Solution:**
1. Ensure `.env` file exists in project root
2. Verify `SAXO_REST_BASE` is set in `.env`
3. Check that `python-dotenv` is installed

```bash
# Verify .env file
cat .env | grep SAXO_REST_BASE

# Install python-dotenv if missing
pip install python-dotenv
```

### Issue: Token expired error

**Symptom:** 401 authentication errors when using config

**Solution:**

**If using OAuth mode (recommended):**
- Tokens auto-refresh automatically
- If refresh fails, re-authenticate:
  ```bash
  python scripts/saxo_login.py
  ```

**If using manual mode:**
- Tokens expire after 24 hours
- Generate new token from [Saxo Developer Portal](https://www.developer.saxo/openapi/token)
- Update `SAXO_ACCESS_TOKEN` in `.env`
- **Recommendation:** Switch to OAuth mode for production

### Issue: Invalid watchlist symbols

**Symptom:** Symbols not found or trading errors

**Solution:**
- ⚠️ **Crypto must use NO-SLASH format:** `BTCUSD` not `BTC/USD` (Saxo-specific)
- Verify symbols are available on Saxo platform
- Check symbol spelling and case (uppercase)
- Ensure instruments have UICs resolved: `config.resolve_instruments()`

### Issue: Unresolved instruments

**Symptom:** `ConfigurationError: Unresolved instruments found`

**Solution:**
Instruments need UICs for trading:
```python
config = Config()
config.resolve_instruments()  # Queries Saxo API for UICs
```

Or manually specify UICs in watchlist configuration.

### Issue: Configuration validation warnings

**Symptom:** Warnings about stop-loss/take-profit ratio

**Solution:**
This is informational - ensure risk/reward ratio is intentional:
```python
# Ensure stop-loss < take-profit for positive risk/reward
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=5.0  # 2.5:1 risk/reward ratio
```

### Issue: Dry-run mode not working

**Symptom:** Bot executing real trades despite DRY_RUN=True

**Solution:**
1. Verify `.env` has `DRY_RUN=True`
2. Restart application to reload environment
3. Check config: `print(config.is_dry_run())`

## Best Practices

### 1. Always Use Environment Variables

❌ **Don't hardcode credentials or bypass token provider:**
```python
# BAD
config.access_token = "my_token_here"
config.manual_access_token = "hardcoded"
```

✅ **Use OAuth mode with environment variables:**
```bash
# .env file - OAuth (recommended)
SAXO_APP_KEY=your_app_key
SAXO_APP_SECRET=your_app_secret
SAXO_REDIRECT_URI=http://localhost:8080/callback

# Or manual mode for testing
SAXO_ACCESS_TOKEN=your_24h_token
```

### 2. Validate Configuration on Startup

```python
from config.config import Config

config = Config()

# Check auth mode
print(f"Using {config.auth_mode} authentication")

# Validate configuration
if not config.is_valid():
    print("Configuration invalid - fix errors before proceeding")
    exit(1)

# Review configuration
config.print_configuration_summary()

# Ensure instruments resolved
if any(inst.get('uic') is None for inst in config.watchlist):
    print("Resolving instruments...")
    config.resolve_instruments()
```

### 3. Start with Dry-Run Mode

Always test with `DRY_RUN=True` before live trading:

```bash
# .env
DRY_RUN=True  # Safe mode for testing
```

### 4. Use Configuration Summary for Debugging

```python
config = Config()
config.print_configuration_summary()
# Review output before starting bot
```

### 5. Never Log Full Tokens

```python
# BAD
print(f"Token: {config.access_token}")

# GOOD
print(f"Token: {config.get_masked_token()}")
```

### 6. Regularly Review Risk Parameters

```python
config = Config()
settings = config.get_trading_settings_summary()

# Review before trading
print(f"Stop Loss: {settings['stop_loss_pct']}%")
print(f"Take Profit: {settings['take_profit_pct']}%")
print(f"Max Position: ${settings['max_position_size']}")
```

## Security Considerations

1. **Never commit `.env` file** - Add to `.gitignore`
2. **Use OAuth for production** - Automatic token refresh, secure storage
3. **Protect token file** - `.secrets/saxo_tokens.json` contains refresh token
4. **Manual tokens expire in 24h** - Not suitable for long-running bots
5. **Use SIM environment for development** - Avoid production risks
6. **Mask sensitive data in logs** - Use `get_masked_token()`
7. **Validate configuration** - Always check `is_valid()` before trading
8. **Never commit structured watchlist with real UICs to public repos** - May expose trading strategy

## Related Documentation

- [Epic 002: Configuration Module](../../epics/epic-002-configuration-module.md)
- [EPIC-002 Revision Summary](../EPIC-002-REVISION-SUMMARY.md)
- [OAuth Setup Guide](../OAUTH_SETUP_GUIDE.md)
- [Saxo Migration Guide](../SAXO_MIGRATION_GUIDE.md)
- [Saxo OAuth Documentation](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
- [Saxo Order Placement Guide](https://www.developer.saxo/openapi/learn/order-placement)
- [Saxo CryptoFX in OpenAPI](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)

## Support

For issues or questions about configuration:
1. Check this documentation
2. Review `.env.example` for reference
3. Run configuration health check: `config.print_configuration_summary()`
4. For OAuth issues, see `docs/OAUTH_SETUP_GUIDE.md`
5. For instrument resolution, run `config.resolve_instruments()`
6. Check Saxo Developer Portal for API status

## Migration from Alpaca/Other Platforms

If migrating from other platforms:

**Key Differences:**
1. **Auth:** OAuth refresh tokens (not static API keys)
2. **Watchlist:** Structured format with AssetType + UIC
3. **Crypto symbols:** No slashes (BTCUSD not BTC/USD)
4. **Position sizing:** Asset-class-specific (stocks vs FX)
5. **Trading hours:** Multiple modes (fixed/always/instrument)

See `docs/SAXO_MIGRATION_GUIDE.md` for detailed migration steps.
```

## Files to Create
- `docs/CONFIG_MODULE_GUIDE.md` - Comprehensive configuration guide

## Files to Update
- `README.md` - Add link to configuration guide
- `.env.example` - Ensure all variables documented

## Definition of Done
- [ ] Configuration guide created
- [ ] API reference complete
- [ ] Usage examples provided
- [ ] Troubleshooting section complete
- [ ] Environment variables documented
- [ ] Best practices included
- [ ] README updated with link

## Story Points
**Estimate:** 3 points (OAuth and structured instruments complexity)

## Dependencies
- Story 002-001 through 002-006 completed
- Configuration module fully implemented

## Blocks
- None (final story in epic)

## Documentation Best Practices
1. **Clear Structure:** Logical organization
2. **Practical Examples:** Real-world use cases
3. **Searchable:** Easy to find information
4. **Complete:** Cover all functionality
5. **Maintained:** Keep up-to-date with code

## Review Checklist

### Completeness
- [ ] All public methods documented
- [ ] All environment variables listed
- [ ] Common use cases covered
- [ ] Error scenarios explained

### Accuracy
- [ ] Code examples work correctly
- [ ] Variable names match actual code
- [ ] Examples tested and verified

### Usability
- [ ] Quick start guide present
- [ ] Examples are practical
- [ ] Troubleshooting helpful
- [ ] Easy to navigate

## Architecture Notes
- **Single Source of Truth:** One comprehensive guide
- **Example-Driven:** Learn by doing
- **Troubleshooting Focus:** Help users solve problems
- **Security Conscious:** Emphasize safe practices

## Future Enhancements (Not in this story)
- Video tutorials
- Interactive examples
- FAQ section
- Configuration wizard
- Migration guides from other platforms

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- [Writing Great Documentation](https://www.writethedocs.org/guide/)

## Success Criteria
✅ Story is complete when:
1. CONFIG_MODULE_GUIDE.md created
2. OAuth authentication documented as recommended approach
3. Structured instruments format explained with examples
4. Manual token mode documented with limitations
5. Token lifecycle explained (refresh behavior)
6. CryptoFX format (no slashes) clearly documented
7. Asset-class-specific sizing examples provided
8. API reference complete
9. All usage examples work
10. Troubleshooting guide covers OAuth and instrument resolution
11. Environment variables documented
12. Best practices clear
13. README updated
14. Documentation reviewed
