# Epic 002: Configuration Module Development

## Epic Overview
Create a centralized configuration module (config/config.py) that manages all API credentials, settings, and watchlist definitions. This module serves as the single source of truth for bot configuration.

## Business Value
- Centralizes all configuration for easy maintenance
- Enforces security best practices for credential management
- Provides flexibility to adjust settings without code changes
- Supports multiple asset types (stocks and crypto)

## Scope

### In Scope
- config/config.py module creation
- API key loading from environment variables
- Alpaca API endpoint configuration (paper trading)
- Watchlist definition (5-20 stocks plus BTC/ETH)
- Global settings (timeframe, mode flags)
- Configuration validation logic
- Default parameter definitions

### Out of Scope
- Database-backed configuration
- Multi-environment configuration (dev/staging/prod)
- Dynamic watchlist updates from external sources
- User interface for configuration

## Technical Considerations
- Load sensitive data from environment variables (os.getenv())
- Support both stock symbols (e.g., "AAPL", "MSFT") and crypto pairs (e.g., "BTC/USD", "ETH/USD")
- Default to paper trading endpoint: https://paper-api.alpaca.markets
- Include validation to ensure required environment variables are set
- Make configuration easily importable by other modules

## Dependencies
- Epic 001: Initial Setup and Environment Configuration (must be completed first)

## Success Criteria
- [ ] config/config.py file created with proper structure
- [ ] API credentials loaded from environment variables
- [ ] Watchlist supports 5-20 stocks plus BTC/ETH
- [ ] Paper trading endpoint correctly configured
- [ ] Configuration validation prevents missing credentials
- [ ] Default timeframe and mode flags defined
- [ ] Module is importable and testable

## Acceptance Criteria
1. Configuration module loads without errors
2. Missing environment variables raise clear error messages
3. Watchlist contains valid Alpaca-supported symbols
4. Other modules can import and use configuration values
5. No hardcoded API keys present in code
6. Documentation exists for all configuration options

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- config/config.py (to be created)

## Example Configuration Elements
```python
# API Configuration (from environment)
API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

# Watchlist
WATCHLIST = ["AAPL", "MSFT", "GOOGL", "TSLA", "BTC/USD", "ETH/USD"]

# Trading Settings
DEFAULT_TIMEFRAME = "1Min"
DRY_RUN = True
```

## Notes
- Keep watchlist flexible for easy additions/removals
- Document each configuration parameter with comments
- Consider adding a config validation function
- Ensure crypto symbols use slash format (BTC/USD, not BTCUSD)
