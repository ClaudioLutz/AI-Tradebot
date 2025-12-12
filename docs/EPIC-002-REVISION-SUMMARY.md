# Epic 002 Revision Summary - Saxo Bank Focus

## Overview

This document summarizes the comprehensive revisions made to Epic 002 and its stories based on executive feedback. The revisions transform the configuration module from Alpaca-focused to Saxo Bank-focused, addressing two critical requirements:

1. **OAuth Authentication** - Long-running bot operation (> 24 hours) via refresh tokens
2. **Instrument Identity** - Structured AssetType + UIC model for reliable order placement

## Documents Revised

### ✅ COMPLETED

1. **Epic 002 (epic-002-configuration-module.md)**
   - Removed all Alpaca references
   - Added OAuth authentication as primary mode
   - Defined structured watchlist with AssetType + UIC
   - Specified asset-class-specific considerations
   - Updated success criteria for Saxo requirements

2. **Story 002-002 (story-002-002-api-credentials-loading.md)**
   - Implemented dual authentication modes (OAuth + Manual Token)
   - Added token provider abstraction with `get_access_token()`
   - Automatic token refresh using refresh_token
   - Token expiration tracking and validation
   - Comprehensive OAuth lifecycle documentation

3. **Story 002-003 (story-002-003-watchlist-configuration.md)**
   - Structured watchlist format: `[{"symbol": "AAPL", "asset_type": "Stock", "uic": 211}, ...]`
   - Instrument resolver using `/ref/v1/instruments` API
   - Caching mechanism to minimize API calls
   - Ambiguous match handling with clear error messages
   - Saxo CryptoFX format support (BTCUSD not BTC/USD)
   - Support for FxSpot → FxCrypto transition

###  REMAINING UPDATES NEEDED

The following stories need key updates based on your feedback. Here are the critical changes required:

---

## Story 002-004: Trading Settings

### Key Changes Required

#### 1. Asset-Class-Specific Position Sizing

**Current (Generic USD):**
```python
MAX_POSITION_SIZE=1000.0  # Generic USD amount
```

**Revised (Asset-Class Specific):**
```python
# Stock/ETF Sizing
MAX_POSITION_VALUE_USD=1000.0  # Converted to shares later

# FX/CryptoFX Sizing  
MAX_FX_NOTIONAL=10000.0  # Direct notional units

# Implementation method:
def get_position_size_for_asset(self, instrument: dict, price: float) -> float:
    """Calculate position size based on asset type."""
    asset_type = instrument.get("asset_type")
    
    if asset_type in ["Stock", "Etf"]:
        # Convert USD value to shares
        value_usd = self.max_position_value_usd
        shares = int(value_usd / price)
        return shares
    
    elif asset_type in ["FxSpot", "FxCrypto"]:
        # Use notional amount directly
        return self.max_fx_notional / price  # Units of base currency
    
    else:
        raise ConfigurationError(f"Unsupported asset type: {asset_type}")
```

#### 2. Trading Hours Mode (Multi-Asset Support)

**Current (Fixed US Hours):**
```python
MARKET_OPEN_HOUR=14  # Fixed: 9:30 AM EST = 14:30 UTC
MARKET_CLOSE_HOUR=21  # Fixed: 4:00 PM EST = 21:00 UTC
```

**Revised (Multi-Asset Aware):**
```python
# Trading Hours Configuration
TRADING_HOURS_MODE=fixed  # Options: "fixed" | "always" | "instrument"

# Mode Implementations:
# - "fixed": Use configured hours (for US equities)
# - "always": 24/7 operation (for crypto)
# - "instrument": Per-instrument hours (future)

def is_trading_allowed(self, instrument: dict, current_hour: int = None) -> bool:
    """Check if trading allowed based on asset type and mode."""
    
    if self.trading_hours_mode == "always":
        return True
    
    elif self.trading_hours_mode == "fixed":
        # Use configured market hours
        return self.is_within_trading_hours(current_hour)
    
    elif self.trading_hours_mode == "instrument":
        # Check instrument-specific hours
        asset_type = instrument.get("asset_type")
        
        # Crypto/FX typically 24/5 or 24/7
        if asset_type in ["FxSpot", "FxCrypto"]:
            # Check for weekend (Saturday = 5, Sunday = 6)
            from datetime import datetime
            weekday = datetime.utcnow().weekday()
            return weekday < 5  # Monday-Friday (24/5)
        
        # Stocks use configured hours
        elif asset_type in ["Stock", "Etf"]:
            return self.is_within_trading_hours(current_hour)
        
        return False
    
    return False
```

#### 3. Additional Environment Variables

Add to `.env.example`:
```bash
# Asset-Class-Specific Position Sizing
MAX_POSITION_VALUE_USD=1000.0  # For Stock/ETF (converted to shares)
MAX_FX_NOTIONAL=10000.0        # For FX/CryptoFX (notional units)

# Trading Hours Configuration
TRADING_HOURS_MODE=fixed  # Options: fixed | always | instrument
MARKET_OPEN_HOUR=14       # If mode=fixed (UTC)
MARKET_CLOSE_HOUR=21      # If mode=fixed (UTC)
```

---

## Story 002-005: Configuration Validation

### Key Saxo-Specific Validations to Add

#### 1. Instrument Resolution Validation

```python
def _validate_instrument_resolution(self):
    """
    Validate that all watchlist instruments can be resolved to {AssetType, Uic}.
    
    This is critical for Saxo order placement which requires both.
    """
    unresolved = [
        inst for inst in self.watchlist 
        if inst.get("uic") is None
    ]
    
    if unresolved:
        symbols = [inst.get("symbol") for inst in unresolved]
        raise ConfigurationError(
            f"Unresolved instruments found: {', '.join(symbols)}\n"
            f"Run config.resolve_instruments() to query Saxo API for UICs.\n"
            f"Or manually specify UICs in watchlist configuration."
        )
    
    print(f"✓ All {len(self.watchlist)} instruments resolved with UICs")
```

#### 2. CryptoFX Asset Type Compatibility

```python
def _validate_crypto_asset_types(self):
    """
    Validate CryptoFX asset types (FxSpot vs FxCrypto).
    
    Saxo is transitioning from FxSpot to FxCrypto for crypto instruments.
    Accept both during transition period.
    """
    crypto_instruments = [
        inst for inst in self.watchlist
        if inst.get("symbol", "").upper().startswith(("BTC", "ETH", "LTC", "XRP", "ADA"))
    ]
    
    for inst in crypto_instruments:
        asset_type = inst.get("asset_type")
        
        # Accept both FxSpot and FxCrypto for crypto
        if asset_type not in ["FxSpot", "FxCrypto"]:
            symbol = inst.get("symbol")
            raise ConfigurationError(
                f"Crypto instrument {symbol} has invalid asset type: {asset_type}\n"
                f"Expected 'FxSpot' or 'FxCrypto'. "
                f"Note: Saxo is transitioning crypto from FxSpot to FxCrypto."
            )
    
    if crypto_instruments:
        print(f"✓ CryptoFX validation passed for {len(crypto_instruments)} instruments")
```

#### 3. Auth Mode Consistency Validation

```python
def _validate_auth_mode(self):
    """
    Validate that authentication mode is properly configured.
    
    Ensures either:
    - OAuth mode: app credentials + token file exists
    - Manual mode: access token present
    """
    if self.auth_mode == "oauth":
        # OAuth mode validation
        if not self.app_key or not self.app_secret:
            raise ConfigurationError(
                "OAuth mode detected but app credentials incomplete. "
                "Required: SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI"
            )
        
        if not os.path.exists(self.token_file):
            raise ConfigurationError(
                f"OAuth mode configured but token file not found: {self.token_file}\n"
                f"Please authenticate first:\n"
                f"  python scripts/saxo_login.py"
            )
        
        print(f"✓ OAuth authentication mode validated")
    
    elif self.auth_mode == "manual":
        # Manual token mode validation
        if not self.manual_access_token:
            raise ConfigurationError(
                "Manual token mode detected but SAXO_ACCESS_TOKEN not set."
            )
        
        print(f"⚠️  Manual token mode (24-hour limitation)")
        print(f"   For production use, switch to OAuth mode")
    
    else:
        raise ConfigurationError(f"Unknown auth mode: {self.auth_mode}")
```

#### 4. Enhanced `_validate_complete_configuration()` Method

Update the existing method to include Saxo-specific checks:

```python
def _validate_complete_configuration(self):
    """
    Perform comprehensive validation of entire configuration.
    
    Includes Saxo-specific validations for auth, instruments, and asset types.
    """
    # Existing cross-validation checks...
    # (position sizing, risk/reward ratio, etc.)
    
    # NEW: Saxo-specific validations
    self._validate_auth_mode()
    self._validate_instrument_resolution()
    self._validate_crypto_asset_types()
    
    # Asset-class-specific sizing validation
    if self.max_position_value_usd <= 0:
        raise ConfigurationError(
            f"Invalid max_position_value_usd: {self.max_position_value_usd}. "
            "Must be positive."
        )
    
    if self.max_fx_notional <= 0:
        raise ConfigurationError(
            f"Invalid max_fx_notional: {self.max_fx_notional}. "
            "Must be positive."
        )
    
    # Warn if production without OAuth
    if self.is_production() and self.auth_mode == "manual":
        import warnings
        warnings.warn(
            "⚠️  Using manual token mode in LIVE environment!\n"
            "   Manual tokens expire after 24 hours.\n"
            "   Consider switching to OAuth mode for production.",
            UserWarning
        )
```

---

## Story 002-007: Configuration Documentation

### Key OAuth Documentation Additions

The documentation story needs to be updated to reflect OAuth as the **recommended** authentication method. Key sections to add/revise:

#### 1. Authentication Section (Expanded)

```markdown
## Authentication

### OAuth Mode (Recommended for Production)

OAuth mode provides long-running operation through automatic token refresh:

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
from config.config import Config

config = Config()  # Auto-detects OAuth mode
print(f"Auth mode: {config.auth_mode}")  # "oauth"

# Get token (auto-refreshes if needed)
token = config.get_access_token()
```

### Manual Token Mode (Testing Only)

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

### Token Refresh Behavior

In OAuth mode, token refresh is completely transparent:

```python
config = Config()

# First call - uses existing token
token1 = config.get_access_token()

# ... 25 minutes later (token expired)

# Second call - automatically refreshes
token2 = config.get_access_token()  # Prints: "🔄 Token expired, refreshing..."
                                     # Prints: "✓ Token refreshed successfully"

# Returns fresh token without error
```

### Token Invalidation

**Important:** Saxo cannot revoke individual access tokens. To revoke access:

1. Remove app access from Saxo Developer Portal
2. This invalidates the refresh token
3. Bot will fail on next refresh attempt
4. User must re-authenticate: `python scripts/saxo_login.py`

See: [Saxo OAuth Documentation](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
```

#### 2. Instrument Configuration Section

```markdown
## Instrument Configuration

### Structured Watchlist Format

Saxo requires **AssetType + UIC** for order placement. The config module uses a structured format:

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

### Instrument Resolution

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

Resolution process:
1. Queries `/ref/v1/instruments?Keywords=AAPL&AssetTypes=Stock`
2. Handles multiple matches (exact symbol match preferred)
3. Caches results in `.cache/instruments.json`
4. Updates watchlist with UICs

### CryptoFX Format

⚠️ **Critical:** Saxo uses **no slash** for crypto symbols:

- ✅ Correct: `"BTCUSD"`, `"ETHUSD"`, `"LTCUSD"`
- ❌ Wrong: `"BTC/USD"`, `"ETH/USD"`

Currently traded as `AssetType: FxSpot`. Saxo is planning migration to `FxCrypto`.

**Configuration accepts both** for forward compatibility:
```python
{"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 24680}     # Current
{"symbol": "BTCUSD", "asset_type": "FxCrypto", "uic": 24680}  # Future
```

See: [Saxo CryptoFX Guide](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)
```

---

## Implementation Priority

Based on your feedback, implement in this order:

1. ✅ **Epic 002 Update** - Saxo-focused scope (COMPLETED)
2. ✅ **Story 002-002** - OAuth + Manual auth modes (COMPLETED)
3. ✅ **Story 002-003** - Structured watchlist + UIC resolution (COMPLETED)
4. **Story 002-004** - Asset-class sizing + trading hours mode
5. **Story 002-005** - Saxo-specific validation (instrument resolution, crypto types, auth mode)
6. **Story 002-007** - OAuth documentation update

Stories 002-001 and 002-006 (module structure and testing) require minimal changes as they're implementation-focused.

---

## Testing Checklist

After implementing all revisions:

### OAuth Authentication
- [ ] OAuth mode auto-detects with app credentials
- [ ] Manual mode auto-detects with access token
- [ ] Token refresh works automatically
- [ ] Expired refresh token raises clear error
- [ ] Token masking prevents sensitive data leaks

### Instrument Resolution
- [ ] Watchlist validates structured format
- [ ] Resolver queries `/ref/v1/instruments` correctly
- [ ] Cache mechanism reduces API calls
- [ ] Ambiguous matches show clear error with options
- [ ] CryptoFX format (no slash) enforced
- [ ] Both FxSpot and FxCrypto accepted for crypto

### Asset-Class Configuration
- [ ] Stock/ETF sizing converts USD to shares
- [ ] FX/Crypto sizing uses notional amounts
- [ ] Trading hours mode supports fixed/always/instrument
- [ ] Asset-specific trading hours validation works

### Validation
- [ ] Unresolved instruments detected and reported
- [ ] CryptoFX asset type compatibility checked
- [ ] Auth mode consistency validated
- [ ] Production + manual token raises warning
- [ ] All cross-validation checks pass

---

## Migration Guide for Existing Code

If you have existing Alpaca-style configuration code:

### Before (Alpaca):
```python
# Simple string watchlist
WATCHLIST = ["AAPL", "MSFT", "BTC/USD"]

# Generic position size
MAX_POSITION_SIZE = 1000.0

# 24-hour token
ALPACA_API_KEY = "..."
```

### After (Saxo):
```python
# Structured watchlist
WATCHLIST = [
    {"symbol": "AAPL", "asset_type": "Stock", "uic": None},
    {"symbol": "MSFT", "asset_type": "Stock", "uic": None},
    {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": None}  # NO SLASH!
]

# Asset-class-specific sizing
MAX_POSITION_VALUE_USD = 1000.0  # For stocks
MAX_FX_NOTIONAL = 10000.0        # For FX/crypto

# OAuth credentials (long-running)
SAXO_APP_KEY = "..."
SAXO_APP_SECRET = "..."
SAXO_REDIRECT_URI = "http://localhost:8080/callback"
```

Then resolve instruments:
```python
config = Config()
config.resolve_instruments()  # Queries Saxo API for UICs
```

---

## Questions for Clarification

Before finalizing Stories 002-004 and 002-005, please confirm:

1. **Asset-Class Sizing:** Should there be separate limits for different stock categories (e.g., large-cap vs small-cap)?
   
2. **Trading Hours:** For `instrument` mode, should the config query Saxo's trading schedule API, or use hardcoded schedules per asset type?

3. **Validation Timing:** Should instrument resolution happen automatically in `__init__()`, or remain a separate explicit call (`config.resolve_instruments()`)?

4. **Cache Invalidation:** How long should instrument cache remain valid? (Suggest: 7 days, or until force_refresh=True)

---

## References

- [Saxo OAuth Authorization Code Grant](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
- [Saxo Order Placement Guide](https://www.developer.saxo/openapi/learn/order-placement)
- [Saxo Instrument Search](https://openapi.help.saxo/hc/en-us/articles/6076270868637-Why-can-I-not-find-an-instrument)
- [Saxo CryptoFX in OpenAPI](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)
- [Saxo Release Notes](https://www.developer.saxo/openapi/releasenotes/completed-planned-changes)

---

## Summary

The Epic 002 revisions transform the configuration module into a Saxo-optimized system that:

1. ✅ **Supports long-running operation** via OAuth refresh tokens (> 24 hours)
2. ✅ **Uses Saxo's AssetType + UIC model** for reliable order placement
3. ✅ **Handles CryptoFX correctly** (no-slash format, FxSpot/FxCrypto transition)
4. **Asset-class-aware sizing** (stocks vs FX/crypto)
5. **Multi-asset trading hours** (fixed/always/instrument modes)
6. **Comprehensive validation** (instrument resolution, auth mode, crypto types)

These changes address the two biggest blockers identified in your review and set a solid foundation for reliable Saxo trading bot operation.
