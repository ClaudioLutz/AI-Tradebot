# Epic 007: Logging and Scheduling System

## Epic Overview
Implement comprehensive logging infrastructure and establish scheduling mechanisms for automated bot execution. This epic ensures visibility into bot operations and provides reliable, fail-safe execution patterns.

## Business Value
- Creates audit trail for all trading decisions and actions
- Enables debugging and performance analysis
- Provides reliable automated execution via OS schedulers
- Prevents silent failures through persistent logging
- Supports compliance and review requirements

## Scope

### In Scope
- Python logging module configuration
- Structured log file creation (logs/ directory)
- Log rotation and retention policies
- Comprehensive event logging (data, signals, trades, errors)
- Scheduling documentation (cron/Task Scheduler)
- Market hours scheduling logic
- Random delay/jitter to avoid API bursts
- Log analysis utilities (optional)
- Error notification basics

### Out of Scope
- Centralized logging systems (ELK, Splunk)
- Real-time monitoring dashboards
- Cloud-based scheduling
- Advanced alerting systems (PagerDuty, etc.)
- Log analytics and visualization tools
- Database logging

## Technical Considerations
- Use Python logging module with FileHandler and ConsoleHandler
- Log format: timestamp, level, module, message
- Log levels: DEBUG (detailed), INFO (key events), ERROR (failures)
- Create logs/ directory for log files
- Implement log rotation (daily or size-based)
- Use external scheduler (cron/Task Scheduler) over internal loops
- Add random delays (0-10 seconds) to distribute API calls
- Document scheduling setup for different operating systems
- Consider separate crypto vs stock market schedules

## Dependencies
- Epic 001: Initial Setup and Environment Configuration
- Epic 006: Main Orchestration Script

## Success Criteria
- [ ] Logging configuration module/function created
- [ ] Logs written to logs/bot.log with timestamps
- [ ] All major events logged (startup, data fetch, signals, trades, errors)
- [ ] Log rotation implemented (prevents huge log files)
- [ ] Console and file logging both work
- [ ] Scheduling documentation complete for Windows/Linux/Mac
- [ ] Example cron job provided
- [ ] Market hours awareness integrated
- [ ] Random delay mechanism implemented

## Acceptance Criteria
1. Each bot cycle writes structured logs to file
2. Log files include timestamps, levels, and clear messages
3. Old log files are rotated automatically
4. Documentation explains how to set up cron/Task Scheduler
5. Example schedule runs bot every minute during market hours
6. Logs capture all trade decisions with rationale
7. Errors include stack traces for debugging
8. Can review historical bot behavior from logs

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- logs/bot.log (to be created)
- README.md (scheduling section to be added)

## Logging Configuration Example
```python
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """Configure logging for the trading bot."""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

## What to Log
1. **Startup Events**
   - Bot initialization
   - Configuration loaded
   - API connection established
   - Watchlist loaded

2. **Data Retrieval**
   - Symbols fetched
   - Current prices
   - API response times
   - Failed data requests

3. **Signal Generation**
   - Strategy applied
   - Signals per symbol (BUY/SELL/HOLD)
   - Indicator values used

4. **Trade Execution**
   - Order placed (symbol, side, quantity)
   - Order confirmation (order ID, fill price)
   - Position changes
   - Failed orders with reason

5. **Errors and Warnings**
   - API errors
   - Network timeouts
   - Invalid data
   - Exception stack traces

6. **Cycle Summary**
   - Cycle completion
   - Next cycle scheduled time
   - Performance metrics

## Scheduling Options

### Option 1: Cron (Linux/Mac)
```bash
# Edit crontab
crontab -e

# Run every minute during market hours (9:30 AM - 4:00 PM ET, weekdays)
# Adjust timezone as needed
*/1 9-16 * * 1-5 cd /path/to/trading_bot && /path/to/venv/bin/python main.py >> logs/cron.log 2>&1
```

### Option 2: Windows Task Scheduler
- Open Task Scheduler
- Create Basic Task
- Trigger: Daily at 9:30 AM
- Action: Start a program
- Program: python.exe
- Arguments: main.py
- Start in: C:\path\to\trading_bot
- Set to repeat every 1 minute for 6.5 hours

### Option 3: Python schedule Library
```python
import schedule
import time

def job():
    """Run bot cycle."""
    # Check if market is open, then run cycle
    pass

# Schedule for market hours
schedule.every(1).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
```

## Random Delay Implementation
```python
import random
import time

# Add jitter to avoid exact-minute API bursts
jitter = random.randint(0, 10)
time.sleep(jitter)
```

## Market Hours Logic
```python
def is_market_hours():
    """Check if within stock market trading hours."""
    import datetime
    now = datetime.datetime.now()
    
    # Check weekday
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Check time (9:30 AM - 4:00 PM ET)
    market_open = datetime.time(9, 30)
    market_close = datetime.time(16, 0)
    current_time = now.time()
    
    return market_open <= current_time <= market_close
```

## Notes
- External schedulers more reliable than internal loops
- Each run is independent (prevents memory leaks)
- Crypto trades 24/7, consider separate schedule
- Log retention: keep last 30 days minimum
- Review logs regularly to tune strategy
- Add email alerts for critical errors (future enhancement)
- Consider using Alpaca's get_clock() instead of local time
