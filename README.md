# AI Trading Bot

An automated trading bot using the Saxo Bank OpenAPI for paper trading. This bot implements configurable trading strategies and provides a foundation for algorithmic trading experimentation.

## Features

- 📈 Paper trading with Saxo Bank OpenAPI (SIM environment)
- 🔧 Configurable trading strategies  
- 📊 Real-time market data access (stocks, ETFs, FX, crypto)
- 🔐 OAuth 2.0 authentication with automatic token refresh
- 📝 Comprehensive configuration and logging
- ⏰ Scheduled trading execution
- 🧪 Safe paper trading mode (no real money at risk)

## Prerequisites

Before you begin, ensure you have the following:

- **Python 3.8+** installed ([Download Python](https://www.python.org/downloads/))
- **Saxo Developer Account** with OpenAPI access ([Sign up](https://www.developer.saxo))
- **Git** for version control (optional but recommended)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "AI Trader"
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.\venv\Scripts\activate.bat

# Activate (Linux/Mac)
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Saxo OpenAPI credentials:
   ```env
   SAXO_ENV=SIM
   SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
   SAXO_AUTH_BASE=https://sim.logonvalidation.net

   # OAuth Mode (Recommended)
   SAXO_APP_KEY=your_app_key_here
   SAXO_APP_SECRET=your_app_secret_here
   SAXO_REDIRECT_URI=http://localhost:8765/callback
   ```

3. Get your API credentials from [Saxo Developer Portal](https://www.developer.saxo):
   - Sign in to your Saxo developer account
   - Create or select an application
   - Copy your App Key and App Secret
   - Configure redirect URI: `http://localhost:8765/callback`

4. Authenticate using OAuth:
   ```bash
   python scripts/saxo_login.py
   ```

### 5. Verify Setup

```bash
python verify_env.py
```

You should see configuration validation pass if everything is configured correctly.

### 6. Run the Bot

```bash
python main.py
```

## Project Structure

```
AI Trader/
├── config/              # Configuration management
│   ├── __init__.py
│   └── config.py        # Centralized config (Saxo OpenAPI)
├── data/                # Market data retrieval
│   ├── __init__.py
│   ├── saxo_client.py   # Saxo REST API client
│   └── market_data.py   # Market data functions
├── strategies/          # Trading strategies
│   ├── __init__.py
│   └── simple_strategy.py  # Strategy implementation
├── execution/           # Trade execution
│   ├── __init__.py
│   └── trade_executor.py   # Order placement logic
├── auth/                # Authentication
│   ├── __init__.py
│   └── saxo_oauth.py    # OAuth 2.0 implementation
├── scripts/             # Utility scripts
│   ├── README.md
│   └── saxo_login.py    # OAuth login helper
├── logs/                # Log files (generated at runtime)
├── tests/               # Test files
│   ├── __init__.py
│   ├── test_config_module.py
│   ├── test_market_data.py
│   ├── test_strategy.py
│   └── test_execution.py
├── docs/                # Documentation
│   ├── epics/          # Epic specifications
│   ├── stories/        # User stories
│   ├── CONFIG_MODULE_GUIDE.md
│   ├── OAUTH_SETUP_GUIDE.md
│   └── SAXO_MIGRATION_GUIDE.md
├── .env                 # Environment variables (not in git)
├── .env.example         # Environment template
├── .gitignore           # Git ignore rules
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── main.py              # Main entry point
├── test_connection.py   # API connection test
└── verify_env.py        # Environment verification
```

## Configuration

### Trading Parameters

Configure trading behavior in `.env`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| DEFAULT_TIMEFRAME | Bar timeframe (1Min, 5Min, etc.) | 1Min |
| DATA_LOOKBACK_DAYS | Historical data period | 30 |
| DRY_RUN | Enable dry run mode | True |
| MAX_POSITION_VALUE_USD | Max position size for stocks/ETFs | 1000.0 |
| MAX_FX_NOTIONAL | Max notional for FX/crypto | 10000.0 |
| STOP_LOSS_PCT | Stop loss percentage | 2.0 |
| TAKE_PROFIT_PCT | Take profit percentage | 5.0 |

See `docs/CONFIG_MODULE_GUIDE.md` for complete configuration reference.

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| SAXO_REST_BASE | Saxo OpenAPI base URL | Yes |
| SAXO_ENV | Environment (SIM or LIVE) | Yes |
| SAXO_APP_KEY | OAuth app key | Yes (OAuth) |
| SAXO_APP_SECRET | OAuth app secret | Yes (OAuth) |
| SAXO_REDIRECT_URI | OAuth redirect URI | Yes (OAuth) |
| SAXO_ACCESS_TOKEN | Manual 24h token | Yes (Manual mode) |

**Note**: Choose ONE authentication mode (OAuth recommended for production, manual token for quick testing).

## Usage

### Basic Usage

```bash
# Activate environment
.\venv\Scripts\Activate.ps1

# Run the bot
python main.py
```

### Verify Environment

```bash
# Check environment variables are set
python verify_env.py

# Test API connection
python test_connection.py
```

### OAuth Authentication

```bash
# Initial authentication (opens browser)
python scripts/saxo_login.py

# Tokens are automatically refreshed by the bot
```

### Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_config_module.py

# Run with verbose output
python -m pytest tests/ -v
```

## Development Roadmap

The project is structured into epics following an agile development approach:

- ✅ **Epic 001-1**: Initial Setup and Environment (COMPLETE)
- ✅ **Epic 001-2**: Saxo Bank Migration (COMPLETE)
- ✅ **Epic 002**: Configuration Module (COMPLETE)
- ✅ **Epic 003**: Market Data Retrieval (COMPLETE)
- ⏳ **Epic 004**: Trading Strategy System
- ⏳ **Epic 005**: Trade Execution Module
- ⏳ **Epic 006**: Main Orchestration
- ⏳ **Epic 007**: Logging and Scheduling
- ⏳ **Epic 008**: Testing and Monitoring

See `docs/epics/` for detailed epic specifications.

## Important Notes

⚠️ **Paper Trading Only**: This bot is configured for paper trading in Saxo's SIM environment. Never use it with a live trading account without thorough testing and understanding of the risks.

🔒 **Security**: 
- Never commit your `.env` file or share your API credentials
- Always use environment variables for sensitive data
- Regenerate credentials immediately if accidentally exposed
- The `.env` file is already in `.gitignore`
- OAuth tokens are stored in `.secrets/` (also in `.gitignore`)

📊 **Market Hours**: 
- Different markets have different trading hours
- Stocks: typically 9:30 AM - 4:00 PM ET (US markets)
- FX/Crypto: nearly 24/5 (closed weekends)
- The bot respects `TRADING_HOURS_MODE` configuration

💰 **Paper Trading**:
- Saxo SIM accounts provide virtual cash for testing
- All trades are simulated - no real money is used
- Perfect for testing strategies without risk

## Troubleshooting

### Common Issues

**"Module not found" error**
```bash
# Make sure virtual environment is activated
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

**"SAXO_REST_BASE not found" error**
- Check your `.env` file exists in project root
- Verify the file is named exactly `.env` (not `.env.txt`)
- Run `python verify_env.py` to check configuration

**OAuth authentication fails**
- Ensure redirect URI matches exactly: `http://localhost:8765/callback`
- Check app credentials in Saxo Developer Portal
- Try clearing `.secrets/saxo_tokens.json` and re-authenticating
- See `docs/OAUTH_SETUP_GUIDE.md` for detailed troubleshooting

**"Authentication conflict detected" error**
- You have both OAuth and manual token configured
- Choose ONE mode: unset either `SAXO_ACCESS_TOKEN` or OAuth credentials
- See `.env.example` for proper configuration

**401 Unauthorized / Token expired**
- Manual tokens expire after 24 hours
- OAuth tokens refresh automatically (recommended)
- Re-run `python scripts/saxo_login.py` if OAuth refresh fails

**Instrument resolution fails**
- Verify symbols are correct (use Saxo format: "BTCUSD" not "BTC/USD")
- Check asset types match (Stock, Etf, FxSpot, FxCrypto)
- UICs can be pre-configured in `WATCHLIST_JSON` to skip resolution

## Contributing

1. Create a new branch for your feature
2. Follow the existing code style
3. Write tests for new functionality
4. Update documentation as needed
5. Submit a pull request

## License

This project is provided as-is for educational purposes.

## Disclaimer

This software is for educational purposes only. Trading involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software. Always test thoroughly with paper trading before considering any real trading activities.

**USE AT YOUR OWN RISK.**

## Support

For issues and questions:
- Check the [documentation](docs/)
- Review the [epic specifications](docs/epics/)
- Review the [user stories](docs/stories/)
- Create a new issue with detailed information

## Resources

- [Saxo Developer Portal](https://www.developer.saxo)
- [Saxo OpenAPI Documentation](https://www.developer.saxo/openapi/learn)
- [OAuth Setup Guide](docs/OAUTH_SETUP_GUIDE.md)
- [Configuration Guide](docs/CONFIG_MODULE_GUIDE.md)
- [Market Data Guide](docs/MARKET_DATA_GUIDE.md)
- [Saxo Migration Guide](docs/SAXO_MIGRATION_GUIDE.md)

## Acknowledgments

Built with:
- [Saxo Bank OpenAPI](https://www.developer.saxo) - Professional trading API
- [requests](https://requests.readthedocs.io/) - HTTP library
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management
- [pytest](https://pytest.org/) - Testing framework
