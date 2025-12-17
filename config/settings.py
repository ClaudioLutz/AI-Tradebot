"""
Configuration Settings - Saxo Bank Integration
Central configuration for trading bot parameters.
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Module logger
logger = logging.getLogger(__name__)

# Saxo API Configuration
SAXO_ENV = os.getenv("SAXO_ENV", "SIM")
SAXO_REST_BASE = os.getenv("SAXO_REST_BASE")
SAXO_ACCESS_TOKEN = os.getenv("SAXO_ACCESS_TOKEN")
SAXO_ACCOUNT_KEY = os.getenv("SAXO_ACCOUNT_KEY")
SAXO_CLIENT_KEY = os.getenv("SAXO_CLIENT_KEY")
SAXO_AUTH_MODE = os.getenv("SAXO_AUTH_MODE", "manual")  # "oauth" or "manual"

# Trading Configuration
WATCHLIST = [
    # Stocks - Major US Tech Companies
    {"name": "AAPL", "asset_type": "Stock", "uic": 211},
    {"name": "MSFT", "asset_type": "Stock"},
    {"name": "GOOGL", "asset_type": "Stock"},
    {"name": "TSLA", "asset_type": "Stock"},
    {"name": "AMZN", "asset_type": "Stock"},
    
    # Crypto - Major Pairs (FxSpot or FxCrypto)
    # Note: Saxo is transitioning crypto from FxSpot to FxCrypto
    # UICs remain the same, but AssetType may change
    {"name": "BTCUSD", "asset_type": "FxSpot", "uic": 21700189},
    {"name": "ETHUSD", "asset_type": "FxSpot", "uic": 21750301},
    
    # Note: If UIC is not provided, it will be discovered at runtime
    # using the market data module's find_instrument_uic() function
]

# Watchlist Format Documentation:
# Each watchlist entry is a dictionary with:
#   - name (required): Instrument keyword/symbol for search
#   - asset_type (required): Saxo asset type (Stock, FxSpot, FxCrypto, etc.)
#   - uic (optional): Universal Instrument Code - if known, include for faster lookup
#
# Common Asset Types:
#   - Stock: Equities
#   - FxSpot: Forex pairs (and legacy crypto)
#   - FxCrypto: Crypto pairs (new designation)
#   - CfdOnIndex: Index CFDs
#   - Bond: Bonds
#
# Example Discovery (if UIC not provided):
#   from data.market_data import find_instrument_uic
#   uic = find_instrument_uic("AAPL", "Stock")

# Trading Parameters
TRADE_AMOUNT = 1  # Default trade amount (shares for stocks, units for FX)
MAX_POSITIONS = 5  # Maximum number of open positions
STOP_LOSS_PERCENT = 0.02  # 2% stop loss
TAKE_PROFIT_PERCENT = 0.05  # 5% take profit

# Risk Management
MAX_POSITION_SIZE = 1000  # Maximum dollar amount per position
MAX_DAILY_LOSS = 500  # Maximum loss per day before stopping
MAX_DAILY_TRADES = 10  # Maximum number of trades per day

# Trading Hours Configuration (Epic 006)
TRADING_HOURS_MODE = os.getenv("TRADING_HOURS_MODE", "always")  # "always", "fixed", or "instrument"
TRADING_START = os.getenv("TRADING_START", "09:30")  # Market open time (HH:MM format)
TRADING_END = os.getenv("TRADING_END", "16:00")  # Market close time (HH:MM format)
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")  # Market timezone

# Cycle Configuration
CYCLE_INTERVAL_SECONDS = int(os.getenv("CYCLE_INTERVAL_SECONDS", "300"))  # 5 minutes default
DEFAULT_QUANTITY = float(os.getenv("DEFAULT_QUANTITY", "1.0"))  # Default trade quantity

# Scheduling (if using scheduler)
TRADING_SCHEDULE = "09:30"  # Time to run trading logic (format: "HH:MM")
CHECK_INTERVAL_MINUTES = 15  # How often to check positions/signals

# Logging Configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "logs/trading_bot.log"

# Module information
__version__ = "2.0.0"
__api__ = "Saxo OpenAPI"

# Log configuration load (will only appear when logging is configured)
logger.debug(f"Configuration loaded: {len(WATCHLIST)} instruments in watchlist ({SAXO_ENV} environment)")
