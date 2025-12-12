# Story 002-007: Configuration Module Documentation

## Story Overview
Create comprehensive documentation for the configuration module including API reference, usage examples, configuration guide, and troubleshooting tips.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** have comprehensive documentation for the configuration module  
**So that** I can easily understand and use the configuration system

## Acceptance Criteria
- [ ] README/guide for configuration module created
- [ ] API reference documentation complete
- [ ] Usage examples provided
- [ ] Configuration options documented
- [ ] Troubleshooting guide included
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

The configuration module (`config/config.py`) provides centralized management of all trading bot settings including:

- **API Credentials:** Saxo Bank API connection details
- **Watchlist:** Instruments to monitor and trade
- **Trading Settings:** Risk parameters, timeframes, and operational modes
- **Validation:** Comprehensive configuration checks

## Quick Start

### Basic Usage

```python
from config.config import Config

# Initialize configuration
config = Config()

# Access configuration
print(f"Environment: {config.environment}")
print(f"Trading Mode: {config.get_trading_mode()}")
print(f"Watchlist: {config.watchlist}")
```

### Using Convenience Function

```python
from config.config import get_config

# Get validated configuration
config = get_config()
```

## Configuration Sections

### 1. API Credentials

Saxo Bank API authentication credentials.

**Required Environment Variables:**
- `SAXO_REST_BASE` - Saxo OpenAPI base URL
- `SAXO_ACCESS_TOKEN` - 24-hour access token
- `SAXO_ENV` - Environment (SIM or LIVE)

**Example:**
```python
config = Config()
print(f"Base URL: {config.base_url}")
print(f"Token (masked): {config.get_masked_token()}")
print(f"Is Simulation: {config.is_simulation()}")
```

### 2. Watchlist

List of instruments to monitor and trade.

**Configuration:**
```python
# Use default watchlist
config = Config()

# Or set via environment
# WATCHLIST=AAPL,MSFT,GOOGL,TSLA,BTC/USD,ETH/USD

# Access watchlist
all_symbols = config.watchlist
stocks = config.get_stock_symbols()
crypto = config.get_crypto_symbols()

# Dynamic management
config.add_symbol("NVDA")
config.remove_symbol("WMT")
```

### 3. Trading Settings

Operational parameters and risk management.

**Key Settings:**
- `default_timeframe` - Market data timeframe (1Min, 5Min, etc.)
- `dry_run` - Simulation mode flag
- `max_position_size` - Maximum position size ($)
- `stop_loss_pct` - Stop-loss percentage
- `take_profit_pct` - Take-profit percentage

**Example:**
```python
config = Config()

# Check trading mode
if config.is_dry_run():
    print("Running in simulation mode")

# Calculate position size
price = 150.0
size = config.calculate_position_size(price, risk_pct=1.0)

# Check trading hours
if config.is_within_trading_hours():
    print("Market is open")
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
| `WATCHLIST` | *(defaults)* | Comma-separated symbols |
| `DEFAULT_TIMEFRAME` | `1Min` | Market data timeframe |
| `DRY_RUN` | `True` | Enable simulation mode |
| `MAX_POSITION_SIZE` | `1000.0` | Max position size ($) |
| `MAX_PORTFOLIO_EXPOSURE` | `10000.0` | Max total exposure ($) |
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
Saxo Bank tokens expire after 24 hours. Generate new token:
1. Login to Saxo Developer Portal
2. Navigate to Applications
3. Generate new 24h token
4. Update `SAXO_ACCESS_TOKEN` in `.env`

### Issue: Invalid watchlist symbols

**Symptom:** Symbols not found or trading errors

**Solution:**
- Ensure crypto uses slash format: `BTC/USD` not `BTCUSD`
- Verify symbols are available on Saxo platform
- Check symbol spelling and case (uppercase)

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

❌ **Don't hardcode credentials:**
```python
# BAD
config.access_token = "my_token_here"
```

✅ **Use environment variables:**
```bash
# .env file
SAXO_ACCESS_TOKEN=your_token_here
```

### 2. Validate Configuration on Startup

```python
from config.config import Config

config = Config()
if not config.is_valid():
    print("Configuration invalid - fix errors before proceeding")
    exit(1)

config.print_configuration_summary()
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
2. **Rotate tokens regularly** - Saxo tokens expire in 24h
3. **Use SIM environment for development** - Avoid production risks
4. **Mask sensitive data in logs** - Use `get_masked_token()`
5. **Validate configuration** - Always check `is_valid()` before trading

## Related Documentation

- [Epic 002: Configuration Module](../../epics/epic-002-configuration-module.md)
- [Saxo Migration Guide](../SAXO_MIGRATION_GUIDE.md)
- [Saxo OpenAPI Documentation](https://developer.saxobank.com)

## Support

For issues or questions about configuration:
1. Check this documentation
2. Review `.env.example` for reference
3. Run configuration health check
4. Check Saxo Developer Portal for API status
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
**Estimate:** 2 points

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
2. API reference complete
3. All usage examples work
4. Troubleshooting guide helpful
5. Environment variables documented
6. Best practices clear
7. README updated
8. Documentation reviewed
