# Story 002-002: API Credentials Loading

## Story Overview
Implement API credentials loading from environment variables in the Config class, ensuring secure handling of sensitive Saxo Bank API credentials.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** load API credentials from environment variables  
**So that** sensitive credentials are never hardcoded and remain secure

## Acceptance Criteria
- [ ] Saxo Bank API credentials loaded from environment variables
- [ ] Missing credentials raise clear error messages
- [ ] Access token is properly masked in logs
- [ ] Environment type (SIM/LIVE) detected correctly
- [ ] No credentials hardcoded in code

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure created)
- `.env` file configured with Saxo credentials
- `python-dotenv` installed

### Environment Variables Required
```bash
# Saxo Bank API Configuration
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_ACCESS_TOKEN=your_24hour_token_here
SAXO_ENV=SIM
```

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
            "Please configure your .env file with Saxo Bank API credentials."
        )
    
    # Saxo Bank access token
    self.access_token = os.getenv("SAXO_ACCESS_TOKEN")
    if not self.access_token:
        raise ConfigurationError(
            "SAXO_ACCESS_TOKEN not found in environment variables. "
            "Please configure your .env file with Saxo Bank API token. "
            "Note: Tokens expire after 24 hours."
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

def get_masked_token(self) -> str:
    """
    Get a masked version of the access token for safe logging.
    
    Returns:
        Masked token showing only first and last 4 characters
    """
    if not self.access_token or len(self.access_token) < 12:
        return "****"
    return f"{self.access_token[:4]}...{self.access_token[-4:]}"

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
    }
```

## Files to Modify
- `config/config.py` - Add credential loading logic

## Definition of Done
- [ ] Credentials loaded from environment variables
- [ ] Missing credentials raise ConfigurationError
- [ ] Token masking implemented for safe logging
- [ ] Environment detection working
- [ ] All tests pass
- [ ] No hardcoded credentials present

## Testing

### Test 1: Load Valid Credentials
```python
from config.config import Config

config = Config()
print(f"Base URL: {config.base_url}")
print(f"Environment: {config.environment}")
print(f"Token (masked): {config.get_masked_token()}")
print(f"Is Simulation: {config.is_simulation()}")
```

Expected output:
```
Base URL: https://gateway.saxobank.com/sim/openapi
Environment: SIM
Token (masked): eyJh...xyz9
Is Simulation: True
```

### Test 2: Missing Credentials Error
```python
import os
from config.config import Config, ConfigurationError

# Temporarily remove token
token_backup = os.environ.get('SAXO_ACCESS_TOKEN')
if 'SAXO_ACCESS_TOKEN' in os.environ:
    del os.environ['SAXO_ACCESS_TOKEN']

try:
    config = Config()
except ConfigurationError as e:
    print(f"Expected error caught: {e}")
finally:
    if token_backup:
        os.environ['SAXO_ACCESS_TOKEN'] = token_backup
```

Expected: "Expected error caught: SAXO_ACCESS_TOKEN not found..."

### Test 3: Environment Detection
```python
from config.config import Config

config = Config()
print(f"Is SIM: {config.is_simulation()}")
print(f"Is LIVE: {config.is_production()}")
```

Expected:
```
Is SIM: True
Is LIVE: False
```

### Test 4: Configuration Summary
```python
from config.config import Config

config = Config()
summary = config.get_summary()
print(f"Summary keys: {list(summary.keys())}")
print(f"Token contains '...': {'...' in summary['token_masked']}")
```

Expected:
```
Summary keys: ['base_url', 'environment', 'token_masked', 'is_simulation']
Token contains '...': True
```

## Story Points
**Estimate:** 2 points

## Dependencies
- Story 002-001 completed (module structure)
- Epic 001-2 completed (Saxo migration with .env configured)

## Blocks
- Story 002-003 (needs credentials for endpoint configuration)
- Story 002-006 (validation needs credentials)

## Security Considerations
- **Never log full tokens** - Always use `get_masked_token()`
- **Fail fast** - Raise errors immediately if credentials missing
- **Clear error messages** - Help developers fix configuration issues
- **Token expiry warning** - Remind users that tokens expire in 24h
- **No defaults** - Never provide default credentials

## Common Issues and Solutions

### Issue: ConfigurationError on initialization
**Solution:** Ensure `.env` file exists with required variables

### Issue: Token shows as "****"
**Solution:** Token may be too short or missing

### Issue: Wrong environment detected
**Solution:** Check SAXO_ENV value and base URL format

### Issue: Token expired error
**Solution:** Generate new token from Saxo Developer Portal (24h expiry)

## Best Practices
1. Always use environment variables for credentials
2. Mask sensitive data in logs and displays
3. Provide helpful error messages with solutions
4. Validate credentials format and presence
5. Document token expiry limitations

## Token Management Notes
- Saxo Bank tokens expire after **24 hours**
- Tokens must be refreshed from Developer Portal
- Always use SIM environment for development
- Store tokens securely, never commit to git

## Architecture Notes
- **Separation of Concerns:** Credentials loading isolated in private method
- **Fail-Fast Pattern:** Errors raised during initialization
- **Security First:** Masking and validation built-in
- **Environment Awareness:** Clear distinction between SIM and LIVE

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- Saxo Migration Guide: `docs/SAXO_MIGRATION_GUIDE.md`
- [Saxo OpenAPI Authentication](https://www.developer.saxo/openapi/learn/oauth-authorization-code-grant)

## Success Criteria
✅ Story is complete when:
1. Credentials loaded from environment variables
2. Missing credentials raise clear errors
3. Token masking works correctly
4. Environment detection accurate
5. All verification tests pass
6. No credentials in code
7. Documentation updated
