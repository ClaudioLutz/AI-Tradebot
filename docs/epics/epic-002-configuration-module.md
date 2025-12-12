# Epic 002: Configuration Module Development (Saxo Bank)

## Epic Overview
Create a centralized configuration module (config/config.py) that manages all Saxo Bank API credentials, OAuth authentication, instrument definitions, and trading settings. This module serves as the single source of truth for bot configuration, specifically designed for Saxo Bank OpenAPI integration with long-running operation support.

## Business Value
- Centralizes all Saxo-specific configuration for easy maintenance
- Implements OAuth authentication flow with refresh token support for long-running operations
- Enforces security best practices for credential management
- Provides structured instrument definitions using Saxo's AssetType + UIC model
- Supports multiple asset classes (stocks, ETFs, FX, CryptoFX)
- Enables bot operation beyond 24 hours through token refresh

## Scope

### In Scope
- config/config.py module creation for Saxo Bank integration
- OAuth authentication support (Authorization Code + refresh_token flow)
- Manual token mode support (24-hour tokens for testing)
- Structured watchlist with AssetType + UIC resolution
- Instrument lookup and caching using `/ref/v1/instruments`
- Asset-class-specific trading parameters
- Trading hours configuration (multi-asset support: stocks, FX, crypto)
- Configuration validation logic aligned to Saxo requirements
- Default parameter definitions for Saxo SIM environment

### Out of Scope
- Database-backed configuration
- Multi-user configuration management
- Dynamic watchlist updates from external scanners
- User interface for configuration
- Multi-broker support (Saxo-only in this epic)

## Technical Considerations

### Authentication
- Support two authentication modes:
  1. **OAuth Mode (Recommended):** SAXO_APP_KEY + SAXO_APP_SECRET with token storage in `.secrets/saxo_tokens.json`
  2. **Manual Mode (Testing):** SAXO_ACCESS_TOKEN environment variable (24-hour limitation)
- Implement token refresh logic using `grant_type=refresh_token`
- Provide `get_access_token()` method that auto-refreshes when needed
- Store refresh tokens securely with appropriate expiration tracking

### Instrument Identity
- Use structured watchlist: `[{"symbol": "AAPL", "asset_type": "Stock", "uic": 211}, ...]`
- Implement instrument resolver using `/ref/v1/instruments?Keywords=...&AssetTypes=...`
- Cache resolved instruments to minimize API calls
- Validate uniqueness (same symbol can map to multiple instruments)
- Support Saxo CryptoFX format (e.g., "BTCUSD" as FxSpot/FxCrypto, not "BTC/USD")

### Asset-Class Considerations
- Different sizing models per asset type:
  - Stocks/ETFs: USD value converted to shares
  - FX/CryptoFX: Notional amounts in base currency units
- Trading hours vary by asset type:
  - US Equities: Fixed market hours
  - FX: Near 24/5 operation
  - CryptoFX: Often 24/7
- Support `TRADING_HOURS_MODE = "fixed" | "always" | "instrument"`

### Environment Configuration
- Default to Saxo SIM environment: https://gateway.saxobank.com/sim/openapi
- Load sensitive data from environment variables and secure token storage
- Include validation to ensure required OAuth settings or manual tokens are present
- Make configuration easily importable by other modules

## Dependencies
- Epic 001-2: Saxo Bank Migration (must be completed first)
- OAuth implementation from Story 001-2-011 (auth/saxo_oauth.py)

## Success Criteria
- [ ] config/config.py file created with Saxo-specific structure
- [ ] OAuth authentication mode implemented with token refresh
- [ ] Manual token mode supported for testing
- [ ] Structured watchlist with AssetType + UIC support
- [ ] Instrument resolver implemented using `/ref/v1/instruments`
- [ ] Asset-class-specific sizing parameters configured
- [ ] Trading hours support multiple asset classes
- [ ] Configuration validation enforces Saxo correctness
- [ ] Saxo SIM environment correctly configured
- [ ] Module is importable and testable

## Acceptance Criteria
1. Configuration module loads without errors
2. OAuth mode validates app credentials and token file existence
3. Manual token mode validates SAXO_ACCESS_TOKEN presence
4. Watchlist entries resolve to valid {AssetType, Uic} pairs
5. Instrument resolver queries Saxo API and caches results
6. Asset-class-specific parameters support stocks, FX, and crypto
7. Trading hours configuration supports multiple asset behaviors
8. Validation fails fast with actionable error messages
9. No hardcoded credentials present in code
10. Documentation covers OAuth setup and instrument resolution

## Related Documents
- docs/SAXO_MIGRATION_GUIDE.md
- docs/OAUTH_SETUP_GUIDE.md
- docs/Alpaca-to-Saxo-analysis.md
- auth/saxo_oauth.py
- config/config.py (to be created)
- [Saxo OAuth Documentation](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
- [Saxo Order Placement Guide](https://www.developer.saxo/openapi/learn/order-placement)
- [Saxo Instrument Search](https://openapi.help.saxo/hc/en-us/articles/6076270868637-Why-can-I-not-find-an-instrument)

## Example Configuration Elements
```python
# API Configuration - OAuth Mode (Recommended)
SAXO_APP_KEY = os.getenv("SAXO_APP_KEY")
SAXO_APP_SECRET = os.getenv("SAXO_APP_SECRET")
SAXO_REDIRECT_URI = os.getenv("SAXO_REDIRECT_URI")
TOKEN_FILE = ".secrets/saxo_tokens.json"

# API Configuration - Manual Mode (Testing)
SAXO_ACCESS_TOKEN = os.getenv("SAXO_ACCESS_TOKEN")  # 24h token
SAXO_REST_BASE = "https://gateway.saxobank.com/sim/openapi"

# Structured Watchlist (AssetType + UIC)
WATCHLIST = [
    {"symbol": "AAPL", "asset_type": "Stock", "uic": 211},
    {"symbol": "MSFT", "asset_type": "Stock", "uic": 23835},
    {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 12345},  # CryptoFX
]

# Asset-Class-Specific Settings
MAX_POSITION_VALUE_USD = 1000.0  # For stocks/ETFs (converted to shares)
MAX_FX_NOTIONAL = 10000.0  # For FX/CryptoFX (units)

# Trading Hours
TRADING_HOURS_MODE = "fixed"  # "fixed" | "always" | "instrument"
DEFAULT_TIMEFRAME = "1Min"
DRY_RUN = True
```

## Notes

### Authentication Strategy
- OAuth mode is recommended for long-running bots (> 24 hours)
- Manual token mode is acceptable for testing and short sessions
- Refresh tokens have longer expiration (typically days/weeks)
- Access tokens are short-lived (~20 minutes for Saxo)
- Token refresh should be transparent to calling code

### Instrument Resolution
- Saxo requires AssetType + UIC for all order placement
- Human-readable symbols (e.g., "AAPL") must be resolved to UIC
- Use `/ref/v1/instruments?Keywords=AAPL&AssetTypes=Stock`
- Cache results to minimize API calls
- Handle ambiguous matches (same symbol, multiple instruments)

### CryptoFX Handling
- Saxo uses "BTCUSD" format (no slash) for CryptoFX
- Currently traded as AssetType: FxSpot
- Planned migration to AssetType: FxCrypto (be prepared for both)
- Examples: BTCUSD, ETHUSD, LTCUSD

### Asset-Class-Specific Considerations
- Stock orders use share quantities (convert USD value to shares)
- FX orders use notional amounts in base currency
- Crypto orders use units (e.g., 0.5 BTC)
- Trading hours differ significantly across asset classes

### Configuration Immutability
- Avoid runtime mutation methods in config layer
- Keep config deterministic and predictable
- Load once, use throughout session
- For dynamic changes, reload configuration entirely
