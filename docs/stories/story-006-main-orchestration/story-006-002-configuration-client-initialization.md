# Story 006-002: Configuration and Client Initialization

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 5 Story Points  
**Priority:** High

## User Story
As a **trading bot**, I want **configuration loaded once at startup and Saxo client initialized** so that I can **have immutable settings throughout runtime and authenticated API access for all trading operations**.

## Acceptance Criteria
- [ ] Configuration loaded once at startup using `config.settings.Settings`
- [ ] Configuration remains immutable during runtime (no reloading mid-cycle)
- [ ] Saxo client initialized with OAuth or manual token from config
- [ ] Client initialization validates authentication before proceeding
- [ ] Startup logs display key configuration summary (watchlist size, account, mode)
- [ ] Graceful error handling for missing/invalid config
- [ ] Graceful error handling for authentication failures
- [ ] Client instance available throughout all trading cycles

## Technical Details

### Configuration Loading
```python
from config.settings import Settings

def load_configuration(logger):
    """Load configuration once at startup."""
    try:
        logger.info("Loading configuration from environment and settings")
        config = Settings()
        
        # Log configuration summary (without sensitive data)
        logger.info(f"Account Key: {config.SAXO_ACCOUNT_KEY}")
        logger.info(f"Watchlist Size: {len(config.WATCHLIST)} instruments")
        logger.info(f"Trading Hours Mode: {config.TRADING_HOURS_MODE}")
        logger.info(f"Cycle Interval: {config.CYCLE_INTERVAL_SECONDS} seconds")
        logger.info(f"Auth Mode: {config.SAXO_AUTH_MODE}")
        
        # Validate watchlist structure
        for idx, instrument in enumerate(config.WATCHLIST):
            required_keys = ["symbol", "uic", "asset_type"]
            if not all(key in instrument for key in required_keys):
                raise ValueError(
                    f"Invalid instrument at index {idx}: missing required keys. "
                    f"Required: {required_keys}, Got: {list(instrument.keys())}"
                )
        
        logger.info("Configuration loaded successfully")
        return config
    
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)
        raise
```

### Saxo Client Initialization
```python
from data.saxo_client import SaxoClient

def initialize_saxo_client(config, logger):
    """Initialize Saxo client with authentication."""
    try:
        logger.info("Initializing Saxo OpenAPI client")
        logger.info(f"Auth mode: {config.SAXO_AUTH_MODE}")
        
        saxo_client = SaxoClient(config)
        
        # Validate authentication by making a test API call
        logger.info("Validating authentication with test API call")
        
        # Test: Get user info or account info
        try:
            # This depends on SaxoClient implementation
            # Example: saxo_client.get_user_info()
            pass
        except Exception as auth_error:
            logger.error(f"Authentication validation failed: {auth_error}")
            raise
        
        logger.info("Saxo client initialized and authenticated successfully")
        return saxo_client
    
    except Exception as e:
        logger.error(f"Failed to initialize Saxo client: {e}", exc_info=True)
        raise
```

### Integration into Main
```python
def main():
    """Main trading bot execution."""
    args = parse_arguments()
    setup_logging()
    logger = logging.getLogger(__name__)
    log_startup_banner(args, logger)
    
    try:
        # 1. Load configuration (once at startup, immutable)
        config = load_configuration(logger)
        
        # 2. Initialize Saxo client
        saxo_client = initialize_saxo_client(config, logger)
        
        # 3. Run trading logic
        if args.single_cycle:
            run_cycle(config, saxo_client, dry_run=args.dry_run)
        else:
            while True:
                run_cycle(config, saxo_client, dry_run=args.dry_run)
                sleep_time = config.CYCLE_INTERVAL_SECONDS
                logger.info(f"Sleeping for {sleep_time} seconds until next cycle")
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
        return 1  # Exit with error code
    finally:
        logger.info("Trading bot shutting down")
    
    return 0  # Exit successfully
```

## Configuration Requirements

### Required Environment Variables
```bash
# Saxo Bank API Configuration
SAXO_APP_KEY=your_app_key_here
SAXO_APP_SECRET=your_app_secret_here
SAXO_ACCOUNT_KEY=your_account_key_here
SAXO_AUTH_MODE=oauth  # or "manual"

# OAuth Configuration (if using oauth mode)
SAXO_REDIRECT_URI=http://localhost:8080/callback
SAXO_AUTH_URL=https://sim.logonvalidation.net/authorize
SAXO_TOKEN_URL=https://sim.logonvalidation.net/token

# Manual Token (if using manual mode)
# SAXO_ACCESS_TOKEN=your_manual_token_here
# SAXO_TOKEN_EXPIRY=2024-12-31T23:59:59

# Trading Configuration
TRADING_HOURS_MODE=always  # or "fixed" or "instrument"
CYCLE_INTERVAL_SECONDS=300  # 5 minutes
```

### Watchlist Configuration in `config/settings.py`
```python
WATCHLIST = [
    {
        "symbol": "BTCUSD",
        "uic": 12345,
        "asset_type": "FxSpot"
    },
    {
        "symbol": "AAPL:xnas",
        "uic": 211,
        "asset_type": "Stock"
    }
]
```

## Error Handling

### Configuration Errors
```python
# Missing environment variable
ConfigurationError: SAXO_APP_KEY not found in environment variables

# Invalid watchlist
ValueError: Invalid instrument at index 1: missing required keys. 
Required: ['symbol', 'uic', 'asset_type'], Got: ['symbol', 'uic']

# Invalid trading hours mode
ValueError: TRADING_HOURS_MODE must be one of: always, fixed, instrument. 
Got: invalid_mode
```

### Authentication Errors
```python
# OAuth token expired
AuthenticationError: OAuth token expired. Please run: python scripts/saxo_login.py

# Invalid credentials
AuthenticationError: Invalid APP_KEY or APP_SECRET

# Network error
ConnectionError: Unable to connect to Saxo API. Check network connection.
```

## Implementation Steps
1. Create `load_configuration()` function to load Settings
2. Add configuration validation logic (watchlist structure, required fields)
3. Log configuration summary (without sensitive data)
4. Create `initialize_saxo_client()` function
5. Add authentication validation (test API call)
6. Handle authentication errors gracefully (log and exit)
7. Integrate into main() function
8. Test with valid configuration
9. Test with missing configuration (should exit cleanly)
10. Test with expired token (should provide clear error message)

## Dependencies
- Epic 002: Configuration Module (`config.settings.Settings`)
- Epic 001-2: Saxo Bank Migration (`data.saxo_client.SaxoClient`)
- Environment variables must be set in `.env` file

## Testing Strategy
```python
# tests/test_main_config_init.py
import unittest
from unittest.mock import Mock, patch, MagicMock

class TestConfigurationLoading(unittest.TestCase):
    """Test configuration loading."""
    
    @patch('config.settings.Settings')
    def test_valid_configuration(self, mock_settings):
        """Test loading valid configuration."""
        mock_config = Mock()
        mock_config.WATCHLIST = [
            {"symbol": "BTCUSD", "uic": 12345, "asset_type": "FxSpot"}
        ]
        mock_config.SAXO_ACCOUNT_KEY = "ACC123"
        mock_config.TRADING_HOURS_MODE = "always"
        mock_settings.return_value = mock_config
        
        logger = Mock()
        config = load_configuration(logger)
        
        self.assertIsNotNone(config)
        logger.info.assert_called()
    
    @patch('config.settings.Settings')
    def test_invalid_watchlist_instrument(self, mock_settings):
        """Test invalid instrument in watchlist."""
        mock_config = Mock()
        mock_config.WATCHLIST = [
            {"symbol": "BTCUSD"}  # Missing uic and asset_type
        ]
        mock_settings.return_value = mock_config
        
        logger = Mock()
        
        with self.assertRaises(ValueError) as context:
            load_configuration(logger)
        
        self.assertIn("missing required keys", str(context.exception))


class TestSaxoClientInitialization(unittest.TestCase):
    """Test Saxo client initialization."""
    
    @patch('data.saxo_client.SaxoClient')
    def test_successful_initialization(self, mock_client_class):
        """Test successful client initialization."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_config = Mock()
        mock_config.SAXO_AUTH_MODE = "oauth"
        
        logger = Mock()
        client = initialize_saxo_client(mock_config, logger)
        
        self.assertIsNotNone(client)
        logger.info.assert_called()
    
    @patch('data.saxo_client.SaxoClient')
    def test_authentication_failure(self, mock_client_class):
        """Test authentication failure."""
        mock_client_class.side_effect = Exception("Authentication failed")
        
        mock_config = Mock()
        logger = Mock()
        
        with self.assertRaises(Exception) as context:
            initialize_saxo_client(mock_config, logger)
        
        self.assertIn("Authentication failed", str(context.exception))
        logger.error.assert_called()
```

## Validation Checklist
- [ ] Configuration loaded successfully with valid `.env` file
- [ ] Watchlist validated (all required keys present)
- [ ] Saxo client initialized and authenticated
- [ ] Startup logs show configuration summary
- [ ] Missing environment variable causes clear error message and exit
- [ ] Invalid watchlist structure causes clear error message and exit
- [ ] Expired token causes clear error message with instructions
- [ ] Configuration remains immutable during runtime (not reloaded)

## Related Stories
- [Story 006-001: Command-Line Arguments and Initialization](./story-006-001-command-line-arguments-initialization.md)
- [Story 006-004: Single Trading Cycle Implementation](./story-006-004-single-trading-cycle.md)
- [Story 006-006: Error Handling and Graceful Shutdown](./story-006-006-error-handling-graceful-shutdown.md)
- [Story 002-001: Create Config Module Structure](../story-002-configuration/story-002-001-create-config-module-structure.md)

## Notes
- Configuration is loaded ONCE at startup and remains immutable
- Do NOT reload configuration during cycles (introduces race conditions)
- Sensitive data (tokens, secrets) should NOT be logged
- Clear error messages are critical for operators to debug issues
- Consider adding `--validate-config` flag in future for config testing without running bot
- Authentication validation is critical before entering trading loop
