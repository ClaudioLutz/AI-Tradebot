# Story 002-001: Create Configuration Module Structure

## Story Overview
Create the basic structure for the centralized configuration module (config/config.py) that will serve as the single source of truth for all bot configuration settings.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** developer  
**I want to** create a centralized configuration module  
**So that** all bot settings are managed in one place with consistent structure

## Acceptance Criteria
- [ ] `config/config.py` file created in config directory
- [ ] Basic module docstring present
- [ ] Module structure follows Python best practices
- [ ] File can be imported without errors
- [ ] Module includes necessary import statements

## Technical Details

### Prerequisites
- Epic 001 completed (environment setup)
- Python virtual environment activated
- `python-dotenv` installed

### Module Location
`config/config.py`

### Initial Structure

```python
"""
Configuration Module for AI Trading Bot

This module serves as the centralized configuration for the trading bot,
managing API credentials, trading settings, watchlists, and operational parameters.

All sensitive credentials are loaded from environment variables using python-dotenv.
The module follows security best practices by never hardcoding credentials.

Usage:
    from config.config import Config
    
    config = Config()
    print(config.base_url)
    print(config.watchlist)
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is invalid or incomplete."""
    pass


class Config:
    """
    Centralized configuration class for the trading bot.
    
    Loads all settings from environment variables and provides
    a clean interface for accessing configuration throughout the application.
    
    Attributes:
        base_url: Saxo OpenAPI base URL
        access_token: Saxo API access token
        environment: Trading environment (SIM or LIVE)
        watchlist: List of instruments to monitor
        default_timeframe: Default timeframe for market data
        dry_run: Whether to run in simulation mode
    
    Example:
        config = Config()
        if config.is_valid():
            print(f"Environment: {config.environment}")
    """
    
    def __init__(self):
        """
        Initialize configuration by loading from environment variables.
        """
        # Load environment variables from .env file
        load_dotenv()
        
        # Placeholder for configuration sections
        # These will be implemented in subsequent stories
        pass
    
    def is_valid(self) -> bool:
        """
        Validate that all required configuration is present and correct.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        # Validation logic will be implemented in subsequent stories
        return True
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current configuration (without sensitive data).
        
        Returns:
            Dictionary containing non-sensitive configuration details
        """
        # Summary logic will be implemented in subsequent stories
        return {}


# Convenience function for quick config access
def get_config() -> Config:
    """
    Get a configured Config instance.
    
    Returns:
        Configured Config object
    
    Raises:
        ConfigurationError: If configuration is invalid
    """
    config = Config()
    if not config.is_valid():
        raise ConfigurationError("Configuration validation failed")
    return config


# Module-level convenience variables
# These will be populated in subsequent stories
__all__ = ['Config', 'ConfigurationError', 'get_config']
```

## Files to Create
- `config/config.py` - New configuration module with basic structure

## Definition of Done
- [ ] File created in correct location (`config/config.py`)
- [ ] No syntax errors
- [ ] Module can be imported successfully
- [ ] Basic class structure present
- [ ] Docstrings complete
- [ ] Follows PEP 8 style guidelines

## Testing

### Test 1: Import Module
```python
# Test basic import
from config.config import Config

print("Config imported successfully")
```

Expected: "Config imported successfully"

### Test 2: Instantiate Config
```python
from config.config import Config

config = Config()
print(f"Config instance created: {type(config).__name__}")
```

Expected: "Config instance created: Config"

### Test 3: Check Methods Exist
```python
from config.config import Config

config = Config()
print(f"has is_valid: {hasattr(config, 'is_valid')}")
print(f"has get_summary: {hasattr(config, 'get_summary')}")
```

Expected:
```
has is_valid: True
has get_summary: True
```

### Test 4: Use Convenience Function
```python
from config.config import get_config

config = get_config()
print("Config obtained via convenience function")
```

Expected: "Config obtained via convenience function"

## Story Points
**Estimate:** 1 point (basic structure setup)

## Dependencies
- Epic 001-2 completed (Saxo Bank migration)
- `python-dotenv` installed

## Blocks
- Story 002-002 (API credentials loading)
- Story 002-003 (API endpoint configuration)
- Story 002-004 (Watchlist definition)

## Architecture Notes
- **Design Pattern:** Singleton-like behavior through module-level access
- **Security:** No credentials in code, only in environment
- **Extensibility:** Easy to add new configuration sections
- **Validation:** Built-in validation framework for config integrity

## Best Practices
1. Use type hints for all methods
2. Comprehensive docstrings for all classes and methods
3. Raise custom exceptions with clear messages
4. Separate concerns (loading, validation, access)
5. Keep configuration immutable after initialization

## Common Issues and Solutions

### Issue: Import errors
**Solution:** Ensure `config/__init__.py` exists

### Issue: ModuleNotFoundError for dotenv
**Solution:** Install python-dotenv: `pip install python-dotenv`

### Issue: Config class not found
**Solution:** Verify file is named `config.py` in `config/` directory

## Security Considerations
- Never log sensitive configuration values
- Load all credentials from environment only
- Validate configuration before use
- Fail fast with clear errors for missing credentials

## Future Enhancements (Not in this story)
- Configuration file support (YAML/JSON)
- Dynamic configuration reloading
- Configuration versioning
- Remote configuration management
- Environment-specific overrides

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- Saxo Migration Guide: `docs/SAXO_MIGRATION_GUIDE.md`
- [Python-dotenv Documentation](https://pypi.org/project/python-dotenv/)

## Success Criteria
✅ Story is complete when:
1. `config/config.py` file exists
2. Module imports without errors
3. Config class can be instantiated
4. All verification tests pass
5. Code follows project structure
6. Documentation is complete
