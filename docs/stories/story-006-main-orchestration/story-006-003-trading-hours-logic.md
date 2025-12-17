# Story 006-003: Trading Hours Logic

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 5 Story Points  
**Priority:** High

## User Story
As a **trading bot**, I want **intelligent trading hours validation** so that I can **avoid placing orders outside market hours for equity instruments while supporting 24/7 trading for CryptoFX**.

## Acceptance Criteria
- [ ] `should_trade_now()` function implemented with three modes: `always`, `fixed`, `instrument`
- [ ] Mode `always`: Always returns True (for 24/7 CryptoFX trading)
- [ ] Mode `fixed`: Checks current time against configured hours (for equity market hours)
- [ ] Mode `instrument`: Raises NotImplementedError (reserved for future per-instrument checks)
- [ ] Trading hours mode configured via `TRADING_HOURS_MODE` in config
- [ ] Fixed hours use timezone-aware datetime comparisons
- [ ] Logs reason when trading is skipped due to hours
- [ ] Handles timezone conversions correctly (e.g., UTC to ET for US markets)

## Technical Details

### Trading Hours Function
```python
from datetime import datetime, time
from zoneinfo import ZoneInfo

def should_trade_now(config, logger) -> bool:
    """
    Determine if trading should occur based on TRADING_HOURS_MODE.
    
    Args:
        config: Settings object with trading hours configuration
        logger: Logger instance
        
    Returns:
        bool: True if trading is allowed, False otherwise
    """
    mode = config.TRADING_HOURS_MODE
    
    if mode == "always":
        # CryptoFX 24/7 trading - always allow
        logger.debug("Trading hours mode: always - Trading allowed")
        return True
    
    elif mode == "fixed":
        # Check fixed trading hours
        return _check_fixed_hours(config, logger)
    
    elif mode == "instrument":
        # Future: per-instrument trading sessions
        logger.error("TRADING_HOURS_MODE='instrument' not yet implemented")
        raise NotImplementedError("Per-instrument hours not yet implemented")
    
    else:
        logger.error(f"Unknown TRADING_HOURS_MODE: {mode}. Defaulting to no trading.")
        return False


def _check_fixed_hours(config, logger) -> bool:
    """
    Check if current time is within fixed trading hours.
    
    Args:
        config: Settings with TRADING_START, TRADING_END, TIMEZONE
        logger: Logger instance
        
    Returns:
        bool: True if within trading hours, False otherwise
    """
    try:
        # Get current time in configured timezone
        timezone = ZoneInfo(config.TIMEZONE)
        current_time = datetime.now(timezone)
        
        # Parse trading hours (format: "HH:MM")
        start_time = time.fromisoformat(config.TRADING_START)
        end_time = time.fromisoformat(config.TRADING_END)
        
        current_time_only = current_time.time()
        
        # Check if current time is within trading window
        if start_time <= current_time_only <= end_time:
            logger.debug(
                f"Within trading hours: {current_time_only} "
                f"(allowed: {start_time} - {end_time})"
            )
            return True
        else:
            logger.info(
                f"Outside trading hours: {current_time_only} "
                f"(allowed: {start_time} - {end_time}). Skipping cycle."
            )
            return False
    
    except Exception as e:
        logger.error(f"Error checking trading hours: {e}", exc_info=True)
        # On error, default to not trading (safe behavior)
        return False


def _is_weekend(current_time: datetime) -> bool:
    """
    Check if current time is on weekend (Saturday=5, Sunday=6).
    
    Args:
        current_time: Timezone-aware datetime
        
    Returns:
        bool: True if weekend, False otherwise
    """
    return current_time.weekday() in (5, 6)
```

### Configuration Options

#### Mode: `always` (CryptoFX 24/7)
```python
# config/settings.py or .env
TRADING_HOURS_MODE = "always"
# No additional configuration needed
```

#### Mode: `fixed` (Equity Market Hours)
```python
# config/settings.py or .env
TRADING_HOURS_MODE = "fixed"
TRADING_START = "09:30"  # Market open time
TRADING_END = "16:00"    # Market close time
TIMEZONE = "America/New_York"  # Market timezone

# Example for European markets:
# TRADING_START = "09:00"
# TRADING_END = "17:30"
# TIMEZONE = "Europe/London"
```

#### Mode: `instrument` (Future Enhancement)
```python
# Future implementation will check per-instrument trading sessions
TRADING_HOURS_MODE = "instrument"
# Will query Saxo API for each instrument's TradingSessions
```

### Integration into Trading Cycle
```python
def run_cycle(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """Execute a single trading cycle."""
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Starting trading cycle")
    logger.info(f"Mode: {'DRY_RUN' if dry_run else 'SIM'}")
    
    try:
        # 1. Check trading hours FIRST
        if not should_trade_now(config, logger):
            logger.info("Outside trading hours, skipping cycle")
            return
        
        # 2. Rest of cycle logic (data fetch, signals, execution)
        # ... (implemented in other stories)
        
    except Exception as e:
        logger.error(f"Error in trading cycle: {e}", exc_info=True)
```

## Weekend Handling (Optional Enhancement)
```python
def should_trade_now(config, logger) -> bool:
    """Enhanced version with weekend checking."""
    mode = config.TRADING_HOURS_MODE
    
    # Check weekends for equity markets
    if mode == "fixed" and hasattr(config, 'SKIP_WEEKENDS') and config.SKIP_WEEKENDS:
        timezone = ZoneInfo(config.TIMEZONE)
        current_time = datetime.now(timezone)
        
        if _is_weekend(current_time):
            logger.info(f"Weekend detected ({current_time.strftime('%A')}). Skipping cycle.")
            return False
    
    # Rest of logic...
```

## Edge Cases and Special Considerations

### Overnight Trading
```python
# If trading hours span midnight (e.g., 22:00 - 02:00)
# Need to handle wraparound:
if start_time > end_time:
    # Overnight trading window
    is_within_hours = (current_time_only >= start_time or 
                       current_time_only <= end_time)
else:
    # Normal same-day window
    is_within_hours = (start_time <= current_time_only <= end_time)
```

### Market Holidays
```python
# Future enhancement: check market calendar
from pandas.tseries.holiday import USFederalHolidayCalendar

def _is_market_holiday(current_time: datetime, market: str = "US") -> bool:
    """Check if current date is a market holiday."""
    if market == "US":
        cal = USFederalHolidayCalendar()
        holidays = cal.holidays(start=current_time, end=current_time)
        return len(holidays) > 0
    return False
```

## Implementation Steps
1. Create `should_trade_now()` function with mode branching
2. Implement `_check_fixed_hours()` helper function
3. Add timezone-aware datetime handling using `zoneinfo`
4. Implement time parsing and comparison logic
5. Add comprehensive logging (debug for allowed, info for denied)
6. Add error handling for invalid config values
7. Integrate into `run_cycle()` as first check
8. Test with different timezones and hours configurations
9. Test edge cases (midnight wraparound, invalid times)
10. Document configuration options in main docstring

## Dependencies
- Python `datetime` and `zoneinfo` modules (built-in)
- Configuration module with trading hours settings

## Testing Strategy
```python
# tests/test_trading_hours.py
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time
from zoneinfo import ZoneInfo

class TestTradingHours(unittest.TestCase):
    """Test trading hours validation logic."""
    
    def test_mode_always(self):
        """Test 'always' mode always returns True."""
        config = Mock()
        config.TRADING_HOURS_MODE = "always"
        logger = Mock()
        
        result = should_trade_now(config, logger)
        
        self.assertTrue(result)
    
    @patch('main.datetime')
    def test_mode_fixed_within_hours(self, mock_datetime):
        """Test 'fixed' mode within trading hours."""
        # Mock current time: 10:00 AM ET
        mock_now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        mock_datetime.now.return_value = mock_now
        
        config = Mock()
        config.TRADING_HOURS_MODE = "fixed"
        config.TRADING_START = "09:30"
        config.TRADING_END = "16:00"
        config.TIMEZONE = "America/New_York"
        logger = Mock()
        
        result = should_trade_now(config, logger)
        
        self.assertTrue(result)
    
    @patch('main.datetime')
    def test_mode_fixed_outside_hours(self, mock_datetime):
        """Test 'fixed' mode outside trading hours."""
        # Mock current time: 8:00 AM ET (before market open)
        mock_now = datetime(2024, 1, 15, 8, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        mock_datetime.now.return_value = mock_now
        
        config = Mock()
        config.TRADING_HOURS_MODE = "fixed"
        config.TRADING_START = "09:30"
        config.TRADING_END = "16:00"
        config.TIMEZONE = "America/New_York"
        logger = Mock()
        
        result = should_trade_now(config, logger)
        
        self.assertFalse(result)
    
    def test_mode_instrument_not_implemented(self):
        """Test 'instrument' mode raises NotImplementedError."""
        config = Mock()
        config.TRADING_HOURS_MODE = "instrument"
        logger = Mock()
        
        with self.assertRaises(NotImplementedError):
            should_trade_now(config, logger)
    
    def test_invalid_mode(self):
        """Test unknown mode returns False."""
        config = Mock()
        config.TRADING_HOURS_MODE = "invalid_mode"
        logger = Mock()
        
        result = should_trade_now(config, logger)
        
        self.assertFalse(result)
    
    @patch('main.datetime')
    def test_weekend_check(self, mock_datetime):
        """Test weekend detection (optional enhancement)."""
        # Mock Saturday
        mock_now = datetime(2024, 1, 13, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        mock_datetime.now.return_value = mock_now
        
        result = _is_weekend(mock_now)
        
        self.assertTrue(result)
```

## Validation Checklist
- [ ] Mode `always` always returns True
- [ ] Mode `fixed` correctly checks time ranges
- [ ] Mode `instrument` raises NotImplementedError
- [ ] Invalid mode returns False and logs error
- [ ] Timezone conversions work correctly (UTC, ET, London, etc.)
- [ ] Time parsing handles "HH:MM" format correctly
- [ ] Logs are clear about why trading was skipped
- [ ] Error handling prevents crashes on invalid config
- [ ] Edge case: midnight wraparound (future enhancement)
- [ ] Edge case: weekend detection (future enhancement)

## Related Stories
- [Story 006-002: Configuration and Client Initialization](./story-006-002-configuration-client-initialization.md)
- [Story 006-004: Single Trading Cycle Implementation](./story-006-004-single-trading-cycle.md)
- [Story 002-004: Trading Settings](../story-002-configuration/story-002-004-trading-settings.md)

## Notes
- Start with simple time-of-day checks; add weekends/holidays later
- Always use timezone-aware datetimes to avoid DST issues
- Log at INFO level when skipping (for audit trail)
- Default to NOT trading on errors (safe behavior)
- Consider adding market calendar support in future (NYSE, NASDAQ holidays)
- For mixed portfolios (crypto + equities), consider per-instrument mode
- CryptoFX trading 24/7 requires `mode="always"`
- Document timezone requirements clearly in configuration guide
