# Story 006-008: Developer Documentation

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 3 Story Points  
**Priority:** Medium

## User Story
As a **developer or operator**, I want **comprehensive documentation for the main orchestration script** so that I can **understand how to run, configure, and troubleshoot the trading bot**.

## Acceptance Criteria
- [ ] Main orchestration guide created (`docs/MAIN_ORCHESTRATION_GUIDE.md`)
- [ ] Documents command-line usage and examples
- [ ] Documents configuration requirements
- [ ] Documents trading hours modes
- [ ] Documents error scenarios and troubleshooting
- [ ] Documents deployment options
- [ ] Includes quickstart guide
- [ ] Includes FAQ section
- [ ] Code has comprehensive docstrings

## Technical Details

### Documentation Structure
```markdown
# Main Orchestration Guide

## Table of Contents
1. [Overview](#overview)
2. [Quickstart](#quickstart)
3. [Command-Line Usage](#command-line-usage)
4. [Configuration](#configuration)
5. [Trading Hours Modes](#trading-hours-modes)
6. [Operation Modes](#operation-modes)
7. [Monitoring and Logs](#monitoring-and-logs)
8. [Error Handling](#error-handling)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)
11. [FAQ](#faq)

## Overview
The main orchestration script (`main.py`) is the entry point for the trading bot...

## Quickstart
```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your credentials

# 2. Run in DRY_RUN mode (testing)
python main.py --dry-run --single-cycle

# 3. Run in continuous mode (production)
python main.py
```

## Command-Line Usage
### Synopsis
```bash
python main.py [--dry-run] [--single-cycle]
```

### Options
- `--dry-run`: Precheck only, no order placement
- `--single-cycle`: Run one cycle then exit
- `--help`: Display help message

### Examples
```bash
# Continuous loop in SIM mode (default)
python main.py

# Single cycle in DRY_RUN mode (testing)
python main.py --dry-run --single-cycle

# Continuous loop in DRY_RUN mode
python main.py --dry-run
```

## Configuration
### Required Environment Variables
```bash
# Saxo Bank API
SAXO_APP_KEY=your_app_key
SAXO_APP_SECRET=your_app_secret
SAXO_ACCOUNT_KEY=your_account_key
SAXO_AUTH_MODE=oauth

# Trading Configuration
TRADING_HOURS_MODE=always
CYCLE_INTERVAL_SECONDS=300
```

### Watchlist Configuration
Edit `config/settings.py`:
```python
WATCHLIST = [
    {
        "symbol": "BTCUSD",
        "uic": 12345,
        "asset_type": "FxSpot"
    }
]
```

## Trading Hours Modes
### Mode: `always` (24/7 Trading)
Best for: CryptoFX instruments
```bash
TRADING_HOURS_MODE=always
```

### Mode: `fixed` (Market Hours)
Best for: Equity instruments
```bash
TRADING_HOURS_MODE=fixed
TRADING_START=09:30
TRADING_END=16:00
TIMEZONE=America/New_York
```

## Operation Modes
### DRY_RUN Mode
- Prechecks all orders but doesn't place them
- Safe for testing strategies
- Use for development and validation

### SIM Mode (Default)
- Places orders in Saxo simulation environment
- Real order flow but paper trading
- Use for production testing

## Monitoring and Logs
### Log Locations
- Console: stdout (real-time)
- Files: `logs/` directory (if configured)

### Log Levels
- INFO: Normal operation
- WARNING: Non-critical issues
- ERROR: Recoverable errors
- CRITICAL: Fatal errors

### Example Log Output
```
2024-01-15 10:00:00 [INFO] main: Trading Bot Starting
2024-01-15 10:00:00 [INFO] main: Mode: SIM (Simulation Trading)
2024-01-15 10:00:00 [INFO] main: Loading configuration
2024-01-15 10:00:05 [INFO] main: Fetching market data for 5 instruments
2024-01-15 10:00:10 [INFO] main: Signals generated: 2 actionable
2024-01-15 10:00:15 [INFO] main: Successfully executed BUY for BTCUSD
```

## Error Handling
### Common Errors
#### Configuration Error
```
CRITICAL: Failed to load configuration: SAXO_APP_KEY not found
```
**Solution**: Check `.env` file has all required variables

#### Authentication Error
```
CRITICAL: Failed to initialize Saxo client: Token expired
```
**Solution**: Run `python scripts/saxo_login.py` to refresh token

#### Market Data Error
```
ERROR: Market data fetch failed: HTTP 500
```
**Action**: Bot will skip this cycle and retry next cycle

## Deployment
### Local Development
```bash
python main.py --dry-run
```

### Docker
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

### Systemd Service
```ini
[Unit]
Description=Trading Bot
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/opt/trading-bot
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Troubleshooting
### Bot exits immediately
**Check**: Configuration is valid (`python main.py --dry-run --single-cycle`)

### No signals generated
**Check**: Market data is being fetched, strategy parameters

### Orders not executing
**Check**: DRY_RUN flag, account permissions, instrument availability

### High error rate
**Check**: API rate limits, network connectivity, token expiry

## FAQ
### Q: How do I stop the bot?
A: Press Ctrl+C for graceful shutdown

### Q: Can I change config while bot is running?
A: No, restart the bot to load new configuration

### Q: How often does the bot trade?
A: Depends on `CYCLE_INTERVAL_SECONDS` and signals generated

### Q: What happens if network fails?
A: Bot logs error and continues to next cycle
```

### Code Docstrings
```python
"""
Trading Bot Main Orchestration Script.

This script serves as the entry point for the automated trading bot,
orchestrating the complete workflow from configuration loading to trade execution.

Usage:
    python main.py [--dry-run] [--single-cycle]

Options:
    --dry-run: Enable precheck-only mode (no order placement)
    --single-cycle: Run one trading cycle then exit

Environment Variables:
    SAXO_APP_KEY: Saxo Bank application key
    SAXO_APP_SECRET: Saxo Bank application secret
    SAXO_ACCOUNT_KEY: Trading account key
    SAXO_AUTH_MODE: Authentication mode (oauth or manual)
    TRADING_HOURS_MODE: Trading hours validation (always, fixed, instrument)
    CYCLE_INTERVAL_SECONDS: Seconds between trading cycles

Examples:
    # Run in DRY_RUN mode for testing
    $ python main.py --dry-run --single-cycle
    
    # Run in continuous SIM mode
    $ python main.py
    
    # Run one cycle in SIM mode
    $ python main.py --single-cycle

For more information, see docs/MAIN_ORCHESTRATION_GUIDE.md
"""

def main():
    """
    Main trading bot execution.
    
    This function coordinates the complete bot lifecycle:
    1. Parse command-line arguments
    2. Setup logging
    3. Load configuration
    4. Initialize Saxo client
    5. Run trading cycles (single or continuous)
    6. Handle shutdown signals
    7. Cleanup resources
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    pass


def run_cycle(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """
    Execute a single trading cycle.
    
    A trading cycle consists of the following phases:
    1. Check trading hours
    2. Fetch market data for all watchlist instruments
    3. Generate trading signals using configured strategy
    4. Execute signals (precheck + placement if not DRY_RUN)
    5. Log cycle summary
    
    Args:
        config: Immutable settings instance loaded at startup
        saxo_client: Initialized Saxo API client
        dry_run: If True, precheck only without order placement
    
    Raises:
        Does not raise - all errors are caught and logged
    
    Example:
        >>> config = Settings()
        >>> client = SaxoClient(config)
        >>> run_cycle(config, client, dry_run=True)
    """
    pass


def should_trade_now(config: Settings, logger) -> bool:
    """
    Determine if trading should occur based on trading hours configuration.
    
    Supports three modes:
    - always: Always returns True (for 24/7 CryptoFX)
    - fixed: Checks current time against configured hours
    - instrument: Per-instrument checks (not yet implemented)
    
    Args:
        config: Settings with TRADING_HOURS_MODE and related config
        logger: Logger instance for logging decisions
    
    Returns:
        bool: True if trading is allowed, False otherwise
    
    Example:
        >>> config = Settings()
        >>> config.TRADING_HOURS_MODE = "always"
        >>> should_trade_now(config, logger)
        True
    """
    pass
```

## Implementation Steps
1. Create `docs/MAIN_ORCHESTRATION_GUIDE.md`
2. Write overview and quickstart sections
3. Document command-line usage with examples
4. Document configuration requirements
5. Document trading hours modes
6. Document operation modes (DRY_RUN vs SIM)
7. Document monitoring and logging
8. Document error scenarios and troubleshooting
9. Document deployment options
10. Write FAQ section
11. Add comprehensive docstrings to `main.py`
12. Review and proofread documentation

## Dependencies
- Existing code implementation (main.py)
- Configuration module documentation
- Market data documentation
- Strategy documentation
- Execution documentation

## Validation Checklist
- [ ] Documentation is clear and comprehensive
- [ ] All command-line options documented
- [ ] Configuration examples provided
- [ ] Common errors and solutions documented
- [ ] Deployment options covered
- [ ] FAQ addresses common questions
- [ ] Code docstrings are complete
- [ ] Examples are tested and working
- [ ] Links to related documentation included

## Related Stories
- [Story 006-001: Command-Line Arguments and Initialization](./story-006-001-command-line-arguments-initialization.md)
- [Story 006-002: Configuration and Client Initialization](./story-006-002-configuration-client-initialization.md)
- [Story 006-003: Trading Hours Logic](./story-006-003-trading-hours-logic.md)
- [Story 006-004: Single Trading Cycle Implementation](./story-006-004-single-trading-cycle.md)

## Related Documentation
- [Configuration Module Guide](../../CONFIG_MODULE_GUIDE.md)
- [Market Data Guide](../../MARKET_DATA_GUIDE.md)
- [Strategy Development Guide](../../STRATEGY_DEVELOPMENT_GUIDE.md)
- [OAuth Setup Guide](../../OAUTH_SETUP_GUIDE.md)

## Notes
- Keep documentation up-to-date as code evolves
- Include real examples from actual usage
- Add screenshots or diagrams if helpful
- Consider video walkthrough for complex topics
- Encourage user feedback and questions
- Document known limitations and future enhancements
- Include performance benchmarks if available
- Add troubleshooting flowchart for common issues
- Link to API documentation where relevant
