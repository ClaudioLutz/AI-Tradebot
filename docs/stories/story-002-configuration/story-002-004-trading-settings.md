# Story 002-004: Trading Settings Configuration

## Story Overview
Implement global trading settings including timeframes, operational modes, risk parameters, and other bot-wide configuration parameters.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** trader  
**I want to** configure global trading settings and parameters  
**So that** I can control how the bot operates and manages risk

## Acceptance Criteria
- [ ] Default timeframe for market data configured
- [ ] Dry-run mode flag implemented
- [ ] Risk management parameters defined
- [ ] Trading hours/schedule settings available
- [ ] Position sizing parameters configured
- [ ] All settings have sensible defaults
- [ ] Settings can be overridden via environment variables

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials)
- Story 002-003 completed (watchlist)

### Configuration Parameters

1. **Market Data Settings**
   - Default timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
   - Data lookback period

2. **Operational Modes**
   - Dry-run mode (simulation without real trades)
   - Live trading mode
   - Backtest mode

3. **Risk Management**
   - Maximum position size
   - Maximum portfolio exposure
   - Stop-loss percentage
   - Take-profit percentage

4. **Trading Parameters**
   - Minimum trade amount
   - Maximum trades per day
   - Trading hours (market open/close)

### Implementation

Add to the `Config.__init__()` method:

```python
def __init__(self):
    """
    Initialize configuration by loading from environment variables.
    
    Raises:
        ConfigurationError: If required credentials are missing
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # API Credentials Configuration
    self._load_api_credentials()
    
    # Watchlist Configuration
    self._load_watchlist()
    
    # Trading Settings Configuration
    self._load_trading_settings()

def _load_trading_settings(self):
    """
    Load trading settings and operational parameters.
    
    Settings can be customized via environment variables or use defaults.
    """
    # Market Data Settings
    self.default_timeframe = os.getenv("DEFAULT_TIMEFRAME", "1Min")
    self.data_lookback_days = int(os.getenv("DATA_LOOKBACK_DAYS", "30"))
    
    # Operational Mode
    self.dry_run = os.getenv("DRY_RUN", "True").lower() in ['true', '1', 'yes']
    self.backtest_mode = os.getenv("BACKTEST_MODE", "False").lower() in ['true', '1', 'yes']
    
    # Risk Management Parameters
    self.max_position_size = float(os.getenv("MAX_POSITION_SIZE", "1000.0"))
    self.max_portfolio_exposure = float(os.getenv("MAX_PORTFOLIO_EXPOSURE", "10000.0"))
    self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "2.0"))
    self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "5.0"))
    
    # Trading Parameters
    self.min_trade_amount = float(os.getenv("MIN_TRADE_AMOUNT", "100.0"))
    self.max_trades_per_day = int(os.getenv("MAX_TRADES_PER_DAY", "10"))
    
    # Trading Hours (in UTC)
    self.market_open_hour = int(os.getenv("MARKET_OPEN_HOUR", "14"))  # 9:30 AM EST = 14:30 UTC
    self.market_close_hour = int(os.getenv("MARKET_CLOSE_HOUR", "21"))  # 4:00 PM EST = 21:00 UTC
    
    # Logging and Monitoring
    self.log_level = os.getenv("LOG_LEVEL", "INFO")
    self.enable_notifications = os.getenv("ENABLE_NOTIFICATIONS", "False").lower() in ['true', '1', 'yes']
    
    # Validate settings
    self._validate_trading_settings()

def _validate_trading_settings(self):
    """
    Validate trading settings for correctness and safety.
    
    Raises:
        ConfigurationError: If settings are invalid or unsafe
    """
    # Validate timeframe
    valid_timeframes = ["1Min", "5Min", "15Min", "30Min", "1Hour", "4Hour", "1Day"]
    if self.default_timeframe not in valid_timeframes:
        raise ConfigurationError(
            f"Invalid timeframe: {self.default_timeframe}. "
            f"Must be one of: {', '.join(valid_timeframes)}"
        )
    
    # Validate risk parameters
    if self.stop_loss_pct <= 0 or self.stop_loss_pct > 100:
        raise ConfigurationError(
            f"Invalid stop_loss_pct: {self.stop_loss_pct}. Must be between 0 and 100."
        )
    
    if self.take_profit_pct <= 0 or self.take_profit_pct > 1000:
        raise ConfigurationError(
            f"Invalid take_profit_pct: {self.take_profit_pct}. Must be between 0 and 1000."
        )
    
    if self.max_position_size <= 0:
        raise ConfigurationError(
            f"Invalid max_position_size: {self.max_position_size}. Must be positive."
        )
    
    if self.max_portfolio_exposure <= 0:
        raise ConfigurationError(
            f"Invalid max_portfolio_exposure: {self.max_portfolio_exposure}. Must be positive."
        )
    
    if self.min_trade_amount <= 0:
        raise ConfigurationError(
            f"Invalid min_trade_amount: {self.min_trade_amount}. Must be positive."
        )
    
    # Validate trading hours
    if not (0 <= self.market_open_hour < 24):
        raise ConfigurationError(
            f"Invalid market_open_hour: {self.market_open_hour}. Must be 0-23."
        )
    
    if not (0 <= self.market_close_hour < 24):
        raise ConfigurationError(
            f"Invalid market_close_hour: {self.market_close_hour}. Must be 0-23."
        )
    
    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if self.log_level.upper() not in valid_log_levels:
        raise ConfigurationError(
            f"Invalid log_level: {self.log_level}. "
            f"Must be one of: {', '.join(valid_log_levels)}"
        )
    
    # Warn if dry_run is disabled
    if not self.dry_run and not self.is_simulation():
        import warnings
        warnings.warn(
            "⚠️  DRY_RUN is disabled in production environment! "
            "Real trades will be executed. Ensure this is intentional.",
            UserWarning
        )

def is_dry_run(self) -> bool:
    """
    Check if bot is running in dry-run mode (no real trades).
    
    Returns:
        True if dry-run mode enabled
    """
    return self.dry_run

def is_live_trading(self) -> bool:
    """
    Check if bot is in live trading mode (real trades executed).
    
    Returns:
        True if live trading (not dry-run and not backtest)
    """
    return not self.dry_run and not self.backtest_mode

def is_backtest_mode(self) -> bool:
    """
    Check if bot is in backtest mode.
    
    Returns:
        True if backtest mode enabled
    """
    return self.backtest_mode

def get_trading_mode(self) -> str:
    """
    Get current trading mode as string.
    
    Returns:
        Trading mode: "BACKTEST", "DRY_RUN", or "LIVE"
    """
    if self.backtest_mode:
        return "BACKTEST"
    elif self.dry_run:
        return "DRY_RUN"
    else:
        return "LIVE"

def calculate_position_size(self, price: float, risk_pct: float = 1.0) -> float:
    """
    Calculate position size based on risk parameters.
    
    Args:
        price: Current price of the instrument
        risk_pct: Percentage of max position to risk (default 1.0%)
    
    Returns:
        Recommended position size in dollars
    """
    position_size = self.max_position_size * (risk_pct / 100.0)
    return min(position_size, self.max_portfolio_exposure)

def is_within_trading_hours(self, current_hour: Optional[int] = None) -> bool:
    """
    Check if current time is within configured trading hours.
    
    Args:
        current_hour: Hour to check (0-23). If None, uses current UTC hour.
    
    Returns:
        True if within trading hours
    """
    if current_hour is None:
        from datetime import datetime
        current_hour = datetime.utcnow().hour
    
    if self.market_open_hour <= self.market_close_hour:
        # Normal case: e.g., 14-21
        return self.market_open_hour <= current_hour < self.market_close_hour
    else:
        # Wrap around midnight: e.g., 22-2
        return current_hour >= self.market_open_hour or current_hour < self.market_close_hour

def get_trading_settings_summary(self) -> Dict[str, Any]:
    """
    Get summary of trading settings.
    
    Returns:
        Dictionary with trading settings details
    """
    return {
        "trading_mode": self.get_trading_mode(),
        "default_timeframe": self.default_timeframe,
        "dry_run": self.dry_run,
        "backtest_mode": self.backtest_mode,
        "max_position_size": self.max_position_size,
        "max_portfolio_exposure": self.max_portfolio_exposure,
        "stop_loss_pct": self.stop_loss_pct,
        "take_profit_pct": self.take_profit_pct,
        "min_trade_amount": self.min_trade_amount,
        "max_trades_per_day": self.max_trades_per_day,
        "trading_hours": f"{self.market_open_hour:02d}:00-{self.market_close_hour:02d}:00 UTC",
        "log_level": self.log_level,
    }
```

Update the `get_summary()` method:

```python
def get_summary(self) -> Dict[str, Any]:
    """
    Get a summary of current configuration (without sensitive data).
    
    Returns:
        Dictionary containing non-sensitive configuration details
    """
    return {
        "base_url": self.base_url,
        "environment": self.environment,
        "token_masked": self.get_masked_token(),
        "is_simulation": self.is_simulation(),
        "watchlist": self.get_watchlist_summary(),
        "trading_settings": self.get_trading_settings_summary(),
    }
```

### Environment Variables (Optional)

Add to `.env` file:

```bash
# Trading Settings (Optional - defaults provided)
DEFAULT_TIMEFRAME=1Min
DATA_LOOKBACK_DAYS=30
DRY_RUN=True
BACKTEST_MODE=False

# Risk Management
MAX_POSITION_SIZE=1000.0
MAX_PORTFOLIO_EXPOSURE=10000.0
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=5.0

# Trading Parameters
MIN_TRADE_AMOUNT=100.0
MAX_TRADES_PER_DAY=10

# Trading Hours (UTC)
MARKET_OPEN_HOUR=14
MARKET_CLOSE_HOUR=21

# Logging
LOG_LEVEL=INFO
ENABLE_NOTIFICATIONS=False
```

## Files to Modify
- `config/config.py` - Add trading settings
- `.env.example` - Add trading settings documentation

## Definition of Done
- [ ] All trading settings loaded with defaults
- [ ] Environment variable overrides working
- [ ] Settings validation implemented
- [ ] Helper methods for mode checks
- [ ] Position sizing calculator working
- [ ] Trading hours check functional
- [ ] All tests pass

## Testing

### Test 1: Load Default Settings
```python
from config.config import Config

config = Config()
settings = config.get_trading_settings_summary()

print(f"Trading Mode: {settings['trading_mode']}")
print(f"Timeframe: {settings['default_timeframe']}")
print(f"Dry Run: {settings['dry_run']}")
print(f"Max Position: ${settings['max_position_size']}")
```

Expected:
```
Trading Mode: DRY_RUN
Timeframe: 1Min
Dry Run: True
Max Position: $1000.0
```

### Test 2: Check Trading Mode
```python
from config.config import Config

config = Config()
print(f"Is Dry Run: {config.is_dry_run()}")
print(f"Is Live Trading: {config.is_live_trading()}")
print(f"Is Backtest: {config.is_backtest_mode()}")
print(f"Mode: {config.get_trading_mode()}")
```

Expected:
```
Is Dry Run: True
Is Live Trading: False
Is Backtest: False
Mode: DRY_RUN
```

### Test 3: Position Size Calculation
```python
from config.config import Config

config = Config()
price = 150.0  # Stock at $150

position_1pct = config.calculate_position_size(price, risk_pct=1.0)
position_5pct = config.calculate_position_size(price, risk_pct=5.0)

print(f"Position (1% risk): ${position_1pct}")
print(f"Position (5% risk): ${position_5pct}")
```

Expected:
```
Position (1% risk): $10.0
Position (5% risk): $50.0
```

### Test 4: Trading Hours Check
```python
from config.config import Config

config = Config()
print(f"Trading at 15:00 UTC: {config.is_within_trading_hours(15)}")
print(f"Trading at 22:00 UTC: {config.is_within_trading_hours(22)}")
print(f"Trading at 10:00 UTC: {config.is_within_trading_hours(10)}")
```

Expected:
```
Trading at 15:00 UTC: True
Trading at 22:00 UTC: False
Trading at 10:00 UTC: False
```

### Test 5: Invalid Settings Error
```python
import os
os.environ['STOP_LOSS_PCT'] = '-5.0'  # Invalid

from config.config import Config, ConfigurationError
try:
    config = Config()
except ConfigurationError as e:
    print(f"Expected error: {e}")
```

Expected: "Expected error: Invalid stop_loss_pct: -5.0..."

### Test 6: Environment Override
```python
import os
os.environ['DEFAULT_TIMEFRAME'] = '5Min'
os.environ['MAX_POSITION_SIZE'] = '2000.0'

from config.config import Config
config = Config()

print(f"Timeframe: {config.default_timeframe}")
print(f"Max Position: ${config.max_position_size}")
```

Expected:
```
Timeframe: 5Min
Max Position: $2000.0
```

## Story Points
**Estimate:** 3 points

## Dependencies
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials)
- Story 002-003 completed (watchlist)

## Blocks
- Story 002-005 (validation needs all settings)
- Story 002-006 (testing needs all settings)

## Default Settings Rationale
- **1Min timeframe:** High-frequency trading capability
- **Dry-run enabled:** Safety first, no accidental real trades
- **2% stop-loss:** Conservative risk management
- **5% take-profit:** Reasonable profit target
- **$1000 max position:** Manageable risk per trade
- **14-21 UTC hours:** US market hours (9:30 AM - 4:00 PM EST)

## Risk Management Best Practices
1. **Always start with dry-run enabled**
2. **Set stop-losses on all positions**
3. **Limit position sizes to manage risk**
4. **Don't exceed portfolio exposure limits**
5. **Monitor and adjust based on performance**

## Common Issues and Solutions

### Issue: Invalid timeframe error
**Solution:** Use valid timeframe: 1Min, 5Min, 15Min, 30Min, 1Hour, 4Hour, 1Day

### Issue: Negative risk parameters
**Solution:** All risk values must be positive

### Issue: Trading outside hours
**Solution:** Check `is_within_trading_hours()` before trading

### Issue: Dry-run warning
**Solution:** Intentional when testing, disable for live trading

## Architecture Notes
- **Safety First:** Dry-run enabled by default
- **Flexibility:** All settings overridable via environment
- **Validation:** Comprehensive checks prevent invalid configs
- **Helpers:** Convenience methods for common checks

## Future Enhancements (Not in this story)
- Dynamic position sizing based on volatility
- Adaptive stop-loss/take-profit
- Multiple timeframe support
- Custom trading schedules per symbol
- Risk-reward ratio calculations

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- Risk Management Guide: [Investopedia - Risk Management](https://www.investopedia.com/terms/r/riskmanagement.asp)

## Success Criteria
✅ Story is complete when:
1. All trading settings loaded with defaults
2. Environment overrides working
3. Validation comprehensive and working
4. Helper methods implemented
5. Position sizing working
6. Trading hours check functional
7. All verification tests pass
8. Documentation complete
