# AI Trading Bot

An automated trading bot using the Alpaca API for paper trading. This bot implements configurable trading strategies and provides a foundation for algorithmic trading experimentation.

## Features

- 📈 Paper trading with Alpaca Markets API
- 🔧 Configurable trading strategies
- 📊 Real-time market data access
- 📝 Comprehensive logging
- ⏰ Scheduled trading execution
- 🧪 Safe paper trading mode (no real money at risk)

## Prerequisites

Before you begin, ensure you have the following:

- **Python 3.8+** installed ([Download Python](https://www.python.org/downloads/))
- **Alpaca Account** with paper trading enabled ([Sign up](https://alpaca.markets))
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

2. Edit `.env` with your Alpaca API credentials:
   ```env
   APCA_API_KEY_ID=your_api_key_here
   APCA_API_SECRET_KEY=your_secret_key_here
   APCA_API_BASE_URL=https://paper-api.alpaca.markets
   ```

3. Get your API keys from [Alpaca Dashboard](https://app.alpaca.markets/paper/dashboard/overview)
   - Sign in to your Alpaca account
   - Navigate to the Paper Trading section
   - Go to "Your API Keys"
   - Generate new keys or use existing ones

### 5. Verify Setup

```bash
python test_connection.py
```

You should see "ALL TESTS PASSED" if everything is configured correctly.

### 6. Run the Bot

```bash
python main.py
```

## Project Structure

```
AI Trader/
├── config/              # Configuration settings
│   ├── __init__.py
│   └── settings.py      # Trading parameters and API config
├── data/                # Market data retrieval
│   ├── __init__.py
│   └── market_data.py   # Market data fetching functions
├── strategies/          # Trading strategies
│   ├── __init__.py
│   └── simple_strategy.py  # Strategy implementation
├── execution/           # Trade execution
│   ├── __init__.py
│   └── trade_executor.py   # Order placement logic
├── logs/                # Log files (generated at runtime)
├── tests/               # Test files
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_market_data.py
│   ├── test_strategy.py
│   └── test_execution.py
├── docs/                # Documentation
│   ├── epics/          # Epic specifications
│   └── stories/        # User stories
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

Configure trading behavior in `config/settings.py`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| SYMBOL | Stock symbol to trade | AAPL |
| QUANTITY | Number of shares per trade | 1 |
| CHECK_INTERVAL | Time between checks (minutes) | 15 |

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| APCA_API_KEY_ID | Alpaca API Key | Yes |
| APCA_API_SECRET_KEY | Alpaca API Secret | Yes |
| APCA_API_BASE_URL | API endpoint URL | Yes |

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

### Testing

```bash
# Run all tests (when implemented in Epic 008)
python -m pytest tests/

# Run specific test
python -m pytest tests/test_strategy.py
```

## Development Roadmap

The project is structured into epics following an agile development approach:

- ✅ **Epic 001**: Initial Setup and Environment (COMPLETE)
- ⏳ **Epic 002**: Configuration Module
- ⏳ **Epic 003**: Market Data Retrieval
- ⏳ **Epic 004**: Trading Strategy System
- ⏳ **Epic 005**: Trade Execution Module
- ⏳ **Epic 006**: Main Orchestration
- ⏳ **Epic 007**: Logging and Scheduling
- ⏳ **Epic 008**: Testing and Monitoring

See `docs/epics/` for detailed epic specifications.

## Saxo Configuration Module

- Guide: [`docs/CONFIG_MODULE_GUIDE.md`](docs/CONFIG_MODULE_GUIDE.md)
- Implementation: `config/config.py`

## Important Notes

⚠️ **Paper Trading Only**: This bot is configured for paper trading. Never use it with a live trading account without thorough testing and understanding of the risks.

🔒 **Security**: 
- Never commit your `.env` file or share your API keys
- Always use environment variables for sensitive data
- Regenerate keys immediately if accidentally exposed
- The `.env` file is already in `.gitignore`

📊 **Market Hours**: 
- The US stock market is open Monday-Friday, 9:30 AM - 4:00 PM Eastern Time
- The bot will only execute trades during market hours
- Check market calendar for holidays

💰 **Paper Trading**:
- Paper trading accounts start with $100,000 in virtual cash
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

**"Forbidden" or "Unauthorized" API error**
- Check your API keys in `.env` are correct
- Ensure you're using paper trading URL
- Verify keys are for paper trading (not live)
- Try regenerating keys in Alpaca dashboard

**"Market is closed" message**
- The bot only trades during market hours
- Check if it's a holiday or weekend
- View market calendar at [Alpaca Markets](https://alpaca.markets/support/calendar/)

**Environment variables not loading**
- Ensure `.env` file exists in project root
- Check file is named exactly `.env` (not `.env.txt`)
- Verify no spaces around `=` in `.env` file
- Run `python verify_env.py` to check

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

- [Alpaca Markets Documentation](https://alpaca.markets/docs/)
- [Alpaca Python SDK](https://github.com/alpacahq/alpaca-trade-api-python)
- [Paper Trading Dashboard](https://app.alpaca.markets/paper/dashboard/overview)

## Acknowledgments

Built with:
- [Alpaca Trade API](https://alpaca.markets/) - Commission-free trading API
- [pandas](https://pandas.pydata.org/) - Data analysis library
- [schedule](https://schedule.readthedocs.io/) - Job scheduling library
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management
