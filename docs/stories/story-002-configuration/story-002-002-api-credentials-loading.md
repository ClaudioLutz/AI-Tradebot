# Story 002-002: API Credentials Loading (OAuth + Manual Token)

## Story Overview
Implement API credentials loading with support for two authentication modes: OAuth (recommended for long-running bots) and Manual Token (testing). This ensures the bot can operate beyond 24 hours through automatic token refresh.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** support both OAuth and manual token authentication modes  
**So that** the bot can run continuously with automatic token refresh or use simple tokens for testing

## Acceptance Criteria
- [ ] OAuth mode implemented with app credentials (SAXO_APP_KEY, SAXO_APP_SECRET)
- [ ] Manual token mode supported (SAXO_ACCESS_TOKEN)
- [ ] Token provider abstraction with `get_access_token()` method
- [ ] Automatic token refresh using refresh_token
- [ ] Token expiration tracking and validation
- [ ] Clear error messages for missing credentials
- [ ] Environment type (SIM/LIVE) detected correctly
- [ ] No credentials hardcoded in code

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure created)
- `.env` file configured with Saxo credentials
- `python-dotenv` installed
- OAuth implementation available in `auth/saxo_oauth.py`

### Authentication Modes

#### Mode 1: OAuth (Recommended for Production)
Uses Authorization Code flow with refresh token support.

**Required Environment Variables:**
```bash
SAXO_APP_KEY=your_app_key
SAXO_APP_SECRET=your_app_secret
SAXO_REDIRECT_URI=http://localhost:8080/callback
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_ENV=SIM
```

**Token Storage:** `.secrets/saxo_tokens.json`

**Advantages:**
- Long-running operation (> 24 hours)
- Automatic token refresh
- Refresh tokens valid for days/weeks
- Access tokens ~20 minutes (auto-refreshed)

#### Mode 2: Manual Token (Testing Only)
Uses a manually obtained 24-hour access token.

**Required Environment Variables:**
```bash
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_ACCESS_TOKEN=eyJhbGc...your_24hour_token
SAXO_ENV=SIM
```

**Advantages:**
- Simple setup for testing
- No OAuth flow required
- Quick validation

**Disadvantages:**
- 24-hour limitation
- Must manually refresh
- Not suitable for production

### Implementation

Update `config/config.py`:

```python
from typing import Optional, Callable
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

class ConfigurationError(Exception):
    """Custom exception for configuration errors."""
    pass


class Config:
    """
    Centralized configuration management for Saxo trading bot.
    Supports OAuth and manual token authentication modes.
    """
    
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
        
        # Determine and initialize authentication mode
        self._initialize_authentication()
    
    def _load_api_credentials(self):
        """
        Load API credentials from environment variables.
        
        Raises:
            ConfigurationError: If required credentials are missing
        """
        # Saxo Bank REST API base URL
        self.base_url = os.getenv("SAXO_REST_BASE")
        if not self.base_url:
            raise ConfigurationError(
                "SAXO_REST_BASE not found in environment variables. "
                "Please configure your .env file with Saxo Bank API base URL."
            )
        
        # Environment type (SIM or LIVE)
        self.environment = os.getenv("SAXO_ENV", "SIM")
        
        # Normalize base URL (remove trailing slash)
        self.base_url = self.base_url.rstrip('/')
        
        # Validate environment type
        if self.environment not in ["SIM", "LIVE"]:
            raise ConfigurationError(
                f"Invalid SAXO_ENV value: {self.environment}. "
                "Must be 'SIM' or 'LIVE'."
            )
        
        # OAuth credentials (optional - for OAuth mode)
        self.app_key = os.getenv("SAXO_APP_KEY")
        self.app_secret = os.getenv("SAXO_APP_SECRET")
        self.redirect_uri = os.getenv("SAXO_REDIRECT_URI")
        
        # Manual token (optional - for manual mode)
        self.manual_access_token = os.getenv("SAXO_ACCESS_TOKEN")
        
        # Token storage path
        self.token_file = os.getenv("SAXO_TOKEN_FILE", ".secrets/saxo_tokens.json")
    
    def _initialize_authentication(self):
        """
        Initialize authentication based on available credentials.
        
        Determines auth mode and sets up token provider.
        
        Raises:
            ConfigurationError: If neither auth mode is properly configured
        """
        # Check for OAuth mode first (recommended)
        if self.app_key and self.app_secret:
            self.auth_mode = "oauth"
            self._setup_oauth_provider()
        
        # Fall back to manual token mode
        elif self.manual_access_token:
            self.auth_mode = "manual"
            self._setup_manual_provider()
        
        # No valid credentials found
        else:
            raise ConfigurationError(
                "No valid authentication credentials found. Please configure either:\n"
                "  OAuth Mode (Recommended): SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI\n"
                "  Manual Mode (Testing): SAXO_ACCESS_TOKEN\n"
                "See docs/OAUTH_SETUP_GUIDE.md for details."
            )
    
    def _setup_oauth_provider(self):
        """
        Setup OAuth token provider with automatic refresh.
        """
        from auth.saxo_oauth import SaxoOAuth
        
        try:
            self.oauth_client = SaxoOAuth(
                app_key=self.app_key,
                app_secret=self.app_secret,
                redirect_uri=self.redirect_uri,
                base_url=self.base_url
            )
            
            # Check if tokens exist
            if not os.path.exists(self.token_file):
                raise ConfigurationError(
                    f"OAuth mode configured but token file not found: {self.token_file}\n"
                    "Please run: python scripts/saxo_login.py"
                )
            
            # Load tokens
            self.oauth_client.load_tokens(self.token_file)
            
            # Verify tokens are valid
            if not self.oauth_client.has_valid_tokens():
                print("⚠️  Warning: Stored tokens may be expired. Attempting refresh...")
                if not self.oauth_client.refresh_access_token():
                    raise ConfigurationError(
                        "Failed to refresh expired tokens. Please re-authenticate:\n"
                        "  python scripts/saxo_login.py"
                    )
            
            print(f"✓ OAuth authentication initialized (mode: {self.auth_mode})")
            
        except ImportError:
            raise ConfigurationError(
                "OAuth mode requires auth/saxo_oauth.py. "
                "Please ensure OAuth implementation exists."
            )
        except Exception as e:
            raise ConfigurationError(f"OAuth setup failed: {e}")
    
    def _setup_manual_provider(self):
        """
        Setup manual token provider (no automatic refresh).
        """
        print(f"⚠️  Manual token mode (24-hour limitation)")
        print(f"   For long-running bots, use OAuth mode instead")
    
    def get_access_token(self) -> str:
        """
        Get current access token (auto-refreshes if needed in OAuth mode).
        
        This is the primary method for obtaining tokens. It handles
        automatic refresh in OAuth mode and returns static token in manual mode.
        
        Returns:
            Valid access token
        
        Raises:
            ConfigurationError: If token unavailable or refresh fails
        """
        if self.auth_mode == "oauth":
            # OAuth mode: auto-refresh if needed
            try:
                # Check if refresh needed
                if not self.oauth_client.has_valid_tokens():
                    print("🔄 Token expired, refreshing...")
                    if not self.oauth_client.refresh_access_token():
                        raise ConfigurationError(
                            "Token refresh failed. Please re-authenticate:\n"
                            "  python scripts/saxo_login.py"
                        )
                    # Save refreshed tokens
                    self.oauth_client.save_tokens(self.token_file)
                    print("✓ Token refreshed successfully")
                
                return self.oauth_client.get_access_token()
            
            except Exception as e:
                raise ConfigurationError(f"Failed to get OAuth token: {e}")
        
        elif self.auth_mode == "manual":
            # Manual mode: return static token
            if not self.manual_access_token:
                raise ConfigurationError("Manual access token not available")
            return self.manual_access_token
        
        else:
            raise ConfigurationError(f"Unknown auth mode: {self.auth_mode}")
    
    def get_masked_token(self) -> str:
        """
        Get a masked version of the access token for safe logging.
        
        Returns:
            Masked token showing only first and last 4 characters
        """
        try:
            token = self.get_access_token()
            if not token or len(token) < 12:
                return "****"
            return f"{token[:4]}...{token[-4:]}"
        except:
            return "****"
    
    def is_simulation(self) -> bool:
        """
        Check if running in simulation environment.
        
        Returns:
            True if using SIM environment
        """
        return self.environment == "SIM" or "/sim/" in self.base_url.lower()
    
    def is_production(self) -> bool:
        """
        Check if running in production (LIVE) environment.
        
        Returns:
            True if using LIVE environment
        """
        return not self.is_simulation()
    
    def is_oauth_mode(self) -> bool:
        """
        Check if using OAuth authentication mode.
        
        Returns:
            True if OAuth mode
        """
        return self.auth_mode == "oauth"
    
    def is_manual_mode(self) -> bool:
        """
        Check if using manual token authentication mode.
        
        Returns:
            True if manual mode
        """
        return self.auth_mode == "manual"
    
    def get_auth_summary(self) -> dict:
        """
        Get authentication configuration summary.
        
        Returns:
            Dictionary with auth details (no sensitive data)
        """
        summary = {
            "auth_mode": self.auth_mode,
            "base_url": self.base_url,
            "environment": self.environment,
            "is_simulation": self.is_simulation(),
            "token_masked": self.get_masked_token(),
        }
        
        if self.auth_mode == "oauth":
            summary["token_file"] = self.token_file
            summary["token_file_exists"] = os.path.exists(self.token_file)
            summary["supports_refresh"] = True
        else:
            summary["supports_refresh"] = False
            summary["expiry_warning"] = "24-hour token limitation"
        
        return summary
```

### Update `.env.example`

```bash
# Saxo Bank API Configuration
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_ENV=SIM

# === AUTHENTICATION MODE 1: OAuth (Recommended for Production) ===
# For long-running bots with automatic token refresh
# Get these from: https://www.developer.saxo/openapi/appmanagement
SAXO_APP_KEY=your_app_key_here
SAXO_APP_SECRET=your_app_secret_here
SAXO_REDIRECT_URI=http://localhost:8080/callback

# Token storage path (auto-managed)
SAXO_TOKEN_FILE=.secrets/saxo_tokens.json

# === AUTHENTICATION MODE 2: Manual Token (Testing Only) ===
# For short testing sessions (24-hour limit)
# Get from: https://www.developer.saxo/openapi/token
# SAXO_ACCESS_TOKEN=your_24hour_token_here

# NOTE: Configure EITHER OAuth credentials OR manual token, not both
# OAuth mode is preferred for production use
```

## Files to Modify
- `config/config.py` - Add OAuth + manual token authentication
- `.env.example` - Document both auth modes

## Definition of Done
- [ ] OAuth authentication mode implemented
- [ ] Manual token mode implemented
- [ ] Token provider abstraction with auto-refresh
- [ ] Missing credentials raise ConfigurationError
- [ ] Token masking for safe logging
- [ ] Environment detection working
- [ ] Auth mode detection and validation
- [ ] All tests pass
- [ ] No hardcoded credentials present

## Testing

### Test 1: OAuth Mode Configuration
```python
import os
os.environ['SAXO_APP_KEY'] = 'test_key'
os.environ['SAXO_APP_SECRET'] = 'test_secret'
os.environ['SAXO_REDIRECT_URI'] = 'http://localhost:8080/callback'

from config.config import Config

# Note: This will fail without actual tokens
# Run scripts/saxo_login.py first in real testing
try:
    config = Config()
    print(f"Auth Mode: {config.auth_mode}")
    print(f"Is OAuth: {config.is_oauth_mode()}")
    auth_summary = config.get_auth_summary()
    print(f"Summary: {auth_summary}")
except Exception as e:
    print(f"Expected (need tokens): {e}")
```

### Test 2: Manual Token Mode
```python
import os
os.environ['SAXO_ACCESS_TOKEN'] = 'test_token_12345'
os.environ['SAXO_REST_BASE'] = 'https://gateway.saxobank.com/sim/openapi'

from config.config import Config

config = Config()
print(f"Auth Mode: {config.auth_mode}")
print(f"Is Manual: {config.is_manual_mode()}")
print(f"Token (masked): {config.get_masked_token()}")
```

Expected:
```
⚠️  Manual token mode (24-hour limitation)
   For long-running bots, use OAuth mode instead
Auth Mode: manual
Is Manual: True
Token (masked): test...2345
```

### Test 3: Get Access Token (Manual Mode)
```python
from config.config import Config

config = Config()
token = config.get_access_token()
print(f"Token length: {len(token)}")
print(f"Token masked: {config.get_masked_token()}")
```

### Test 4: No Credentials Error
```python
import os
# Clear all auth variables
for key in ['SAXO_APP_KEY', 'SAXO_ACCESS_TOKEN']:
    if key in os.environ:
        del os.environ[key]

from config.config import Config, ConfigurationError

try:
    config = Config()
except ConfigurationError as e:
    print(f"Expected error caught:")
    print(e)
```

Expected: Error message with both auth options listed

### Test 5: Auth Summary
```python
from config.config import Config

config = Config()
summary = config.get_auth_summary()

print(f"Auth mode: {summary['auth_mode']}")
print(f"Environment: {summary['environment']}")
print(f"Supports refresh: {summary['supports_refresh']}")
print(f"Is simulation: {summary['is_simulation']}")
```

## Story Points
**Estimate:** 3 points

## Dependencies
- Story 002-001 completed (module structure)
- Epic 001-2 completed (Saxo migration with OAuth implementation)

## Blocks
- Story 002-003 (needs credentials for API calls)
- Story 002-005 (validation needs auth mode checks)

## Security Considerations
- **Never log full tokens** - Always use `get_masked_token()`
- **Fail fast** - Raise errors immediately if credentials missing
- **Clear error messages** - Help developers fix configuration issues
- **Token storage** - OAuth tokens in `.secrets/` (gitignored)
- **No defaults** - Never provide default credentials
- **Rotation** - OAuth mode handles automatic token refresh
- **Expiry tracking** - Validate token expiration before use

## Token Lifecycle

### OAuth Mode
1. User runs `scripts/saxo_login.py` (one-time)
2. Tokens stored in `.secrets/saxo_tokens.json`
3. Access token (~20 min) auto-refreshed when needed
4. Refresh token (days/weeks) used for renewal
5. If refresh fails, user re-authenticates

### Manual Mode
1. User obtains 24h token from Saxo Developer Portal
2. Sets `SAXO_ACCESS_TOKEN` in `.env`
3. Token valid for 24 hours
4. After expiry, user manually obtains new token
5. Not suitable for long-running bots

## Common Issues and Solutions

### Issue: "OAuth mode configured but token file not found"
**Solution:** Run OAuth login flow first:
```bash
python scripts/saxo_login.py
```

### Issue: "Token refresh failed"
**Solution:** Refresh token expired, re-authenticate:
```bash
python scripts/saxo_login.py
```

### Issue: "No valid authentication credentials found"
**Solution:** Configure one of the auth modes in `.env`:
- OAuth: SAXO_APP_KEY + SAXO_APP_SECRET + SAXO_REDIRECT_URI
- Manual: SAXO_ACCESS_TOKEN

### Issue: Manual token expired (24h)
**Solution:** 
- Get new token from Saxo Developer Portal
- Update `SAXO_ACCESS_TOKEN` in `.env`
- Or switch to OAuth mode for automatic refresh

### Issue: Token shows as "****"
**Solution:** Token may be unavailable or refresh failed

## Best Practices
1. **Use OAuth mode for production** - Automatic token refresh
2. **Use manual mode for testing** - Quick validation only
3. **Never commit tokens** - Keep `.secrets/` in `.gitignore`
4. **Monitor token expiry** - OAuth handles this automatically
5. **Validate credentials on startup** - Fail fast if misconfigured
6. **Mask sensitive data in logs** - Use `get_masked_token()`

## Architecture Notes
- **Abstraction:** `get_access_token()` hides mode-specific logic
- **Separation of Concerns:** Auth mode detection isolated
- **Fail-Fast Pattern:** Errors raised during initialization
- **Security First:** Masking and validation built-in
- **Future-Proof:** Easy to add more auth modes if needed

## Migration from 24h Tokens
If currently using manual tokens, migrate to OAuth:

1. Create app in Saxo Developer Portal
2. Add OAuth credentials to `.env`:
   ```bash
   SAXO_APP_KEY=your_key
   SAXO_APP_SECRET=your_secret
   SAXO_REDIRECT_URI=http://localhost:8080/callback
   ```
3. Run login script:
   ```bash
   python scripts/saxo_login.py
   ```
4. Remove `SAXO_ACCESS_TOKEN` from `.env`
5. Restart bot - will auto-detect OAuth mode

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- [Saxo OAuth Documentation](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
- [OAuth Setup Guide](../../OAUTH_SETUP_GUIDE.md)
- OAuth Implementation: `auth/saxo_oauth.py`

## Success Criteria
✅ Story is complete when:
1. OAuth mode implemented with auto-refresh
2. Manual mode supported for testing
3. Token provider abstraction working
4. Missing credentials raise clear errors
5. Token masking works correctly
6. Environment detection accurate
7. Auth mode properly detected and validated
8. All verification tests pass
9. No credentials in code
10. Documentation updated with both modes
