# Story 002-004: Trading Settings Configuration

## Story Overview
Implement global trading settings including timeframes, operational modes, risk parameters, and asset-class-specific position sizing for Saxo Bank's multi-asset platform.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** trader  
**I want to** configure global trading settings with asset-class-specific parameters  
**So that** the bot handles stocks, ETFs, FX, and crypto appropriately

## Acceptance Criteria
- [ ] Default timeframe for market data configured
- [ ] Dry-run mode flag implemented
- [ ] Asset-class-specific position sizing (Stock/ETF vs FX/Crypto)
- [ ] Trading hours mode configuration (fixed/always/instrument)
- [ ] Risk management parameters defined
- [ ] All settings have sensible defaults
- [ ] Settings can be overridden via environment variables

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials with OAuth)
- Story 002-003 completed (structured watchlist)

### Key Saxo-Specific Changes

#### 1. Asset-Class-Specific Position Sizing

Saxo requires different sizing approaches for different asset classes:

- **Stocks/ETFs**: Specify quantity (shares). Convert USD value to shares.
- **FX/CryptoFX**: Specify notional amount (units of base currency).

#### 2. Trading Hours Modes

Support multiple trading hour strategies:

- **`fixed`**: Use configured hours (e.g., US market 9:30 AM - 4:00 PM EST)
- **`always`**: 24/7 operation (for crypto-focused bots)
- **`instrument`**: Per-instrument hours (crypto 24/5, stocks use fixed hours)

### Configuration Parameters

1. **Market Data Settings**
   - Default timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
   - Data lookback period

2. **Operational Modes**
   - Dry-run mode (simulation without real trades)
   - Live trading mode
   - Backtest mode

3. **Risk Management (Asset-Class-Specific)**
   - Maximum position value for Stock/ETF (USD converted to shares)
   - Maximum FX notional for FX/CryptoFX
   - Maximum portfolio exposure
   - Stop-loss percentage
   - Take-profit percentage

4. **Trading Parameters**
   - Minimum trade amount
   - Maximum trades per day
   - Trading hours mode (fixed/always/instrument)
   - Trading hours (for fixed mode)

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
    
    # API Credentials Configuration (Story 002-002)
    self._load_api_credentials()
    
    # Watchlist Configuration (Story 002-003)
    self._load_watchlist()
    
    # Trading Settings Configuration (Story 002-004)
    self._load_trading_settings()

def _load_trading_settings(self):
    """
    Load trading settings and operational parameters.
    
    Settings can be customized via environment variables or use defaults.
    Implements Saxo-specific asset-class-aware sizing.
    """
    # Market Data Settings
    self.default_timeframe = os.getenv("DEFAULT_TIMEFRAME", "1Min")
    self.data_lookback_days = int(os.getenv("DATA_LOOKBACK_DAYS", "30"))
    
    # Operational Mode
    self.dry_run = os.getenv("DRY_RUN", "True").lower() in ['true', '1', 'yes']
    self.backtest_mode = os.getenv("BACKTEST_MODE", "False").lower() in ['true', '1', 'yes']
    
    # Asset-Class-Specific Position Sizing (SAXO-SPECIFIC)
    # For Stock/ETF: USD value converted to shares at order time
    self.max_position_value_usd = float(os.getenv("MAX_POSITION_VALUE_USD", "1000.0"))
    
    # For FX/CryptoFX: Direct notional amount in units
    self.max_fx_notional = float(os.getenv("MAX_FX_NOTIONAL", "10000.0"))
    
    # Legacy parameter for backward compatibility
    self.max_position_size = self.max_position_value_usd
    
    # Portfolio-wide limits
    self.max_portfolio_exposure = float(os.getenv("MAX_PORTFOLIO_EXPOSURE", "10000.0"))
    
    # Risk Management Parameters
    self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "2.0"))
    self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "5.0"))
    
    # Trading Parameters
    self.min_trade_amount = float(os.getenv("MIN_TRADE_AMOUNT", "100.0"))
    self.max_trades_per_day = int(os.getenv("MAX_TRADES_PER_DAY", "10"))
    
    # Trading Hours Configuration (SAXO-SPECIFIC)
    # Modes: "fixed" (use configured hours), "always" (24/7), "instrument" (per-asset)
    self.trading_hours_mode = os.getenv("TRADING_HOURS_MODE", "fixed").lower()
    
    # Trading Hours (in UTC) - used when mode = "fixed"
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
    
    # Validate asset-class-specific sizing
    if self.max_position_value_usd <= 0:
        raise ConfigurationError(
            f"Invalid max_position_value_usd: {self.max_position_value_usd}. Must be positive."
        )
    
    if self.max_fx_notional <= 0:
        raise ConfigurationError(
            f"Invalid max_fx_notional: {self.max_fx_notional}. Must be positive."
        )
    
    if self.max_portfolio_exposure <= 0:
        raise ConfigurationError(
            f"Invalid max_portfolio_exposure: {self.max_portfolio_exposure}. Must be positive."
        )
    
    if self.min_trade_amount <= 0:
        raise ConfigurationError(
            f"Invalid min_trade_amount: {self.min_trade_amount}. Must be positive."
        )
    
    # Validate trading hours mode
    valid_modes = ["fixed", "always", "instrument"]
    if self.trading_hours_mode not in valid_modes:
        raise ConfigurationError(
            f"Invalid trading_hours_mode: {self.trading_hours_mode}. "
            f"Must be one of: {', '.join(valid_modes)}"
        )
    
    # Validate trading hours (if fixed mode)
    if self.trading_hours_mode == "fixed":
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

def get_position_size_for_asset(self, instrument: Dict[str, Any], price: float, risk_pct: float = 1.0) -> float:
    """
    Calculate position size based on asset type (Saxo-specific).
    
    - Stock/ETF: Returns USD value (to be converted to shares at order time)
    - FX/CryptoFX: Returns notional amount in base currency units
    
    Args:
        instrument: Instrument dict with 'asset_type' key
        price: Current price of the instrument
        risk_pct: Percentage of max position to risk (default 1.0%)
    
    Returns:
        Position size (USD value for stocks, notional for FX)
    
    Raises:
        ConfigurationError: If asset type unsupported
    """
    asset_type = instrument.get("asset_type")
    
    if asset_type in ["Stock", "Etf"]:
        # For stocks/ETFs: calculate USD value
        # (will be converted to shares: shares = value_usd / price)
        value_usd = self.max_position_value_usd * (risk_pct / 100.0)
        return min(value_usd, self.max_portfolio_exposure)
    
    elif asset_type in ["FxSpot", "FxCrypto"]:
        # For FX/Crypto: use notional amount
        notional = self.max_fx_notional * (risk_pct / 100.0)
        return min(notional, self.max_portfolio_exposure)
    
    else:
        raise ConfigurationError(
            f"Unsupported asset type: {asset_type}. "
            f"Supported: Stock, Etf, FxSpot, FxCrypto"
        )

def calculate_shares_for_stock(self, price: float, risk_pct: float = 1.0) -> int:
    """
    Calculate number of shares for stock/ETF orders.
    
    Args:
        price: Current stock price
        risk_pct: Percentage of max position to risk (default 1.0%)
    
    Returns:
        Number of shares (integer)
    """
    value_usd = self.max_position_value_usd * (risk_pct / 100.0)
    value_usd = min(value_usd, self.max_portfolio_exposure)
    shares = int(value_usd / price)
    return max(shares, 1)  # Minimum 1 share

def is_trading_allowed(self, instrument: Dict[str, Any], current_hour: Optional[int] = None) -> bool:
    """
    Check if trading is allowed based on trading hours mode and asset type.
    
    Args:
        instrument: Instrument dict with 'asset_type' key
        current_hour: Hour to check (0-23). If None, uses current UTC hour.
    
    Returns:
        True if trading is allowed
    """
    if current_hour is None:
        from datetime import datetime
        current_hour = datetime.utcnow().hour
    
    # Mode: Always (24/7 operation)
    if self.trading_hours_mode == "always":
        return True
    
    # Mode: Fixed hours (use configured market hours)
    elif self.trading_hours_mode == "fixed":
        return self.is_within_trading_hours(current_hour)
    
    # Mode: Instrument-specific (check by asset type)
    elif self.trading_hours_mode == "instrument":
        asset_type = instrument.get("asset_type")
        
        # Crypto/FX: 24/5 (Monday-Friday)
        if asset_type in ["FxSpot", "FxCrypto"]:
            from datetime import datetime
            weekday = datetime.utcnow().weekday()
            return weekday < 5  # Monday(0) - Friday(4)
        
        # Stocks/ETFs: Use configured hours
        elif asset_type in ["Stock", "Etf"]:
            return self.is_within_trading_hours(current_hour)
        
        return False
    
    return False

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
        "max_position_value_usd": self.max_position_value_usd,
        "max_fx_notional": self.max_fx_notional,
        "max_portfolio_exposure": self.max_portfolio_exposure,
        "stop_loss_pct": self.stop_loss_pct,
        "take_profit_pct": self.take_profit_pct,
        "min_trade_amount": self.min_trade_amount,
        "max_trades_per_day": self.max_trades_per_day,
        "trading_hours_mode": self.trading_hours_mode,
        "trading_hours": f"{self.market_open_hour:02d}:00-{self.market_close_hour:02d}:00 UTC" if self.trading_hours_mode == "fixed" else self.trading_hours_mode,
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
        "auth_mode": self.auth_mode,
        "environment": self.environment,
        "token_masked": self.get_masked_token(),
        "is_simulation": self.is_simulation(),
        "watchlist": self.get_watchlist_summary(),
        "trading_settings": self.get_trading_settings_summary(),
    }
```

### Environment Variables

Add to `.env.example`:

```bash
# Trading Settings (Optional - defaults provided)
DEFAULT_TIMEFRAME=1Min
DATA_LOOKBACK_DAYS=30
DRY_RUN=True
BACKTEST_MODE=False

# Asset-Class-Specific Position Sizing (SAXO-SPECIFIC)
MAX_POSITION_VALUE_USD=1000.0  # For Stock/ETF (converted to shares)
MAX_FX_NOTIONAL=10000.0        # For FX/CryptoFX (notional units)
MAX_PORTFOLIO_EXPOSURE=10000.0

# Risk Management
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=5.0

# Trading Parameters
MIN_TRADE_AMOUNT=100.0
MAX_TRADES_PER_DAY=10

# Trading Hours Configuration (SAXO-SPECIFIC)
TRADING_HOURS_MODE=fixed  # Options: fixed | always | instrument
MARKET_OPEN_HOUR=14       # If mode=fixed (UTC)
MARKET_CLOSE_HOUR=21      # If mode=fixed (UTC)

# Logging
LOG_LEVEL=INFO
ENABLE_NOTIFICATIONS=False
```

## Files to Modify
- `config/config.py` - Add trading settings with Saxo-specific features
- `.env.example` - Add trading settings documentation

## Definition of Done
- [ ] All trading settings loaded with defaults
- [ ] Environment variable overrides working
- [ ] Asset-class-specific sizing implemented
- [ ] Trading hours mode supports fixed/always/instrument
- [ ] Settings validation implemented
- [ ] Helper methods for mode checks
- [ ] Position sizing works for stocks and FX
- [ ] Trading hours check functional
- [ ] All tests pass

## Testing

### Test 1: Asset-Class-Specific Position Sizing (Stock)
```python
from config.config import Config

config = Config()
stock_instrument = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
price = 175.0

# Get position size in USD
position_value = config.get_position_size_for_asset(stock_instrument, price, risk_pct=1.0)
print(f"Position value: ${position_value}")

# Calculate shares
shares = config.calculate_shares_for_stock(price, risk_pct=1.0)
print(f"Shares to buy: {shares}")
```

Expected:
```
Position value: $10.0
Shares to buy: 5
```

### Test 2: Asset-Class-Specific Position Sizing (Crypto)
```python
from config.config import Config

config = Config()
crypto_instrument = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}
price = 43000.0

# Get notional amount
notional = config.get_position_size_for_asset(crypto_instrument, price, risk_pct=1.0)
print(f"Notional amount: {notional}")

# Calculate units of BTC
btc_units = notional / price
print(f"BTC units: {btc_units:.6f}")
```

Expected:
```
Notional amount: 100.0
BTC units: 0.002326
```

### Test 3: Trading Hours Mode - Fixed
```python
from config.config import Config

config = Config()  # Default: mode=fixed
stock = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}

print(f"Trading allowed at 15:00 UTC: {config.is_trading_allowed(stock, 15)}")
print(f"Trading allowed at 22:00 UTC: {config.is_trading_allowed(stock, 22)}")
```

Expected:
```
Trading allowed at 15:00 UTC: True
Trading allowed at 22:00 UTC: False
```

### Test 4: Trading Hours Mode - Always
```python
import os
os.environ['TRADING_HOURS_MODE'] = 'always'

from config.config import Config

config = Config()
crypto = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}

print(f"Mode: {config.trading_hours_mode}")
print(f"Trading allowed at 03:00 UTC: {config.is_trading_allowed(crypto, 3)}")
```

Expected:
```
Mode: always
Trading allowed at 03:00 UTC: True
```

### Test 5: Trading Hours Mode - Instrument
```python
import os
os.environ['TRADING_HOURS_MODE'] = 'instrument'

from config.config import Config

config = Config()
stock = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
crypto = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}

# Crypto: 24/5 (weekdays only)
print(f"Crypto trading (weekday): {config.is_trading_allowed(crypto, 3)}")

# Stock: Uses fixed hours
print(f"Stock trading at 15:00: {config.is_trading_allowed(stock, 15)}")
print(f"Stock trading at 22:00: {config.is_trading_allowed(stock, 22)}")
```

Expected (on weekday):
```
Crypto trading (weekday): True
Stock trading at 15:00: True
Stock trading at 22:00: False
```

### Test 6: Trading Settings Summary
```python
from config.config import Config

config = Config()
summary = config.get_trading_settings_summary()

print(f"Trading Mode: {summary['trading_mode']}")
print(f"Max Position (Stock): ${summary['max_position_value_usd']}")
print(f"Max Notional (FX): ${summary['max_fx_notional']}")
print(f"Trading Hours Mode: {summary['trading_hours_mode']}")
```

Expected:
```
Trading Mode: DRY_RUN
Max Position (Stock): $1000.0
Max Notional (FX): $10000.0
Trading Hours Mode: fixed
```

## Story Points
**Estimate:** 5 points (Saxo-specific complexity)

## Dependencies
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials with OAuth)
- Story 002-003 completed (structured watchlist)

## Blocks
- Story 002-005 (validation needs all settings)
- Story 002-006 (testing needs all settings)

## Saxo-Specific Design Rationale

### Asset-Class-Specific Sizing
- **Stocks/ETFs**: Saxo orders require quantity (shares). We store USD value and calculate shares at order time.
- **FX/CryptoFX**: Saxo orders use notional amount. We store notional directly.

### Trading Hours Modes
- **`fixed`**: For US equities-focused bots (9:30 AM - 4:00 PM EST)
- **`always`**: For crypto-only bots (24/7 operation)
- **`instrument`**: For multi-asset bots (crypto 24/5, stocks use fixed hours)

### Default Settings Rationale
- **1Min timeframe:** High-frequency capability
- **Dry-run enabled:** Safety first
- **2% stop-loss:** Conservative risk
- **5% take-profit:** 2.5:1 risk/reward ratio
- **$1000 max position (stocks):** Manageable per-trade risk
- **$10000 max notional (FX):** Larger size for FX/crypto
- **14-21 UTC hours:** US market hours (9:30 AM - 4:00 PM EST)

## Common Issues and Solutions

### Issue: Wrong sizing for FX orders
**Solution:** Use `get_position_size_for_asset()` which handles asset type automatically

### Issue: Crypto trading outside hours in fixed mode
**Solution:** Use `trading_hours_mode=always` or `trading_hours_mode=instrument`

### Issue: Position size too large
**Solution:** Adjust `MAX_POSITION_VALUE_USD` or `MAX_FX_NOTIONAL` in `.env`

## Architecture Notes
- **Asset-Class Aware:** Different sizing for stocks vs FX
- **Flexible Hours:** Three modes support different strategies
- **Safety First:** Dry-run enabled by default
- **Validation:** Comprehensive checks prevent invalid configs

## Future Enhancements (Not in this story)
- Per-instrument position limits
- Dynamic sizing based on volatility
- Adaptive stop-loss/take-profit
- Multiple timeframe support
- Custom trading schedules per symbol

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- EPIC-002 Revision Summary: `docs/EPIC-002-REVISION-SUMMARY.md`
- [Saxo Order Placement Guide](https://www.developer.saxo/openapi/learn/order-placement)

## Success Criteria
✅ Story is complete when:
1. Asset-class-specific sizing implemented
2. Trading hours mode supports fixed/always/instrument
3. Environment overrides working
4. Validation comprehensive
5. Helper methods implemented
6. All verification tests pass
7. Documentation complete
