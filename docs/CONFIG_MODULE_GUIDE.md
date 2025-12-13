# Configuration Module Guide (Saxo Bank)

## Overview

The configuration module (`config/config.py`) provides centralized management of all bot settings for Saxo Bank:

- OAuth-first authentication (refreshable tokens for long-running bots)
- Manual token mode for quick testing (24-hour token)
- Structured watchlist with `AssetType + UIC`
- Trading settings (timeframes, risk, hours) with multi-asset support
- Validation + health checks + safe summaries (no secrets)

## Quick Start

```python
from config.config import Config, get_config

config = get_config()  # validated Config
print(config.get_summary())

# Token access works for both modes
token = config.get_access_token()
print(config.get_masked_token())
```

## Authentication

### OAuth Mode (Recommended)

**Environment variables:**

```bash
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_ENV=SIM

SAXO_APP_KEY=your_app_key
SAXO_APP_SECRET=your_app_secret
SAXO_REDIRECT_URI=http://localhost:8765/callback
SAXO_TOKEN_FILE=.secrets/saxo_tokens.json
```

**One-time login:**

```bash
python scripts/saxo_login.py
```

After this, the bot uses refresh tokens automatically via `auth/saxo_oauth.py`.

### Manual Token Mode (Testing Only)

```bash
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_ENV=SIM
SAXO_ACCESS_TOKEN=your_24h_token
```

## Watchlist

Saxo order placement requires `AssetType + UIC`.

### Structured format

```json
[
  {"symbol": "AAPL", "asset_type": "Stock", "uic": 211},
  {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 21700189}
]
```

### Configure via environment

```bash
WATCHLIST_JSON=[{"symbol":"AAPL","asset_type":"Stock","uic":211}]
```

### Resolve missing UICs

If `uic` is `null`, you can resolve it by querying Saxo:

```python
config = Config()
config.resolve_instruments()
print(config.get_watchlist_summary())
```

**Crypto format note:** use `BTCUSD` not `BTC/USD`.

## Trading Settings

Key environment variables (defaults shown):

```bash
DEFAULT_TIMEFRAME=1Min
DATA_LOOKBACK_DAYS=30
DRY_RUN=True
BACKTEST_MODE=False

MAX_POSITION_VALUE_USD=1000.0
MAX_FX_NOTIONAL=10000.0
MAX_PORTFOLIO_EXPOSURE=10000.0

STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=5.0

MIN_TRADE_AMOUNT=100.0
MAX_TRADES_PER_DAY=10

TRADING_HOURS_MODE=fixed   # fixed | always | instrument
MARKET_OPEN_TIME=14:30
MARKET_CLOSE_TIME=21:00

LOG_LEVEL=INFO
ENABLE_NOTIFICATIONS=False
```

### Asset-class sizing helper

```python
stock = {"symbol": "AAPL", "asset_type": "Stock", "uic": 211}
crypto = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 21700189}

value_usd = config.get_position_size_for_asset(stock, price=175.0, risk_pct=1.0)
notional = config.get_position_size_for_asset(crypto, price=43000.0, risk_pct=1.0)
```

## Validation and Health Checks

```python
config = Config()
print(config.is_valid())
print(config.get_configuration_health())
config.print_configuration_summary()
```

## Running tests

```bash
python -m pytest -q
# or
python -m pytest tests/test_config_module.py -v
```
