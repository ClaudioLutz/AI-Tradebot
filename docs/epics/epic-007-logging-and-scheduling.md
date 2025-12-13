# Epic 007: Logging and Scheduling System (Saxo-aware)

## Epic Overview
Implement comprehensive logging infrastructure with Saxo-specific fields and establish scheduling mechanisms for automated bot execution. This epic ensures visibility into bot operations with support for flexible trading hours modes.

## Business Value
- Creates audit trail for all trading decisions and API interactions
- Enables debugging and performance analysis with Saxo-critical context
- Provides reliable automated execution via OS schedulers
- Supports compliance and review requirements
- Facilitates operational health monitoring

## Scope

### In Scope
- Python logging module configuration with structured format
- **Saxo-critical fields**: `client_id`, `account_key`, `instrument_id`, `uic`, `asset_type`, `order_id`, HTTP status
- Log file creation with rotation (`logs/` directory)
- Log retention policies (30 days minimum)
- Comprehensive event logging:
  - OAuth token refresh events
  - Data retrieval with instrument context
  - Signal generation with instrument_id keys
  - Order execution (precheck + placement) with Saxo OrderIds
  - HTTP errors with status codes and response bodies
- Scheduling documentation (cron/Task Scheduler)
- **Trading hours scheduling** based on `TRADING_HOURS_MODE` from config
- Random delay/jitter to avoid API bursts
- Log analysis utilities (optional)

### Out of Scope
- Centralized logging systems (ELK, Splunk, CloudWatch)
- Real-time monitoring dashboards (Grafana, etc.)
- Cloud-based scheduling (AWS EventBridge, GCP Scheduler)
- Advanced alerting systems (PagerDuty, OpsGenie)
- Log analytics and visualization tools
- Database logging (PostgreSQL, MongoDB)
- Structured logging formats (JSON, protobuf)

## Technical Considerations

### Logging Configuration
- Use Python `logging` module with `RotatingFileHandler` and `StreamHandler`
- **Log format:** `timestamp | level | module | message | context_fields`
- **Log levels:**
  - `DEBUG`: Detailed diagnostics (HTTP requests/responses)
  - `INFO`: Key events (cycle start, signals, orders placed)
  - `WARNING`: Recoverable issues (stale data, precheck warnings)
  - `ERROR`: Failures (API errors, order rejections)
  - `CRITICAL`: System failures (auth failure, config missing)
- **Log rotation:** Daily or size-based (10MB files, keep 5 backups)
- **Masked sensitive data:** Mask `account_key`, `client_id` in logs (last 4 chars only)

### Saxo-Specific Logging Fields
Every log entry related to instruments or orders should include:
- `instrument_id`: `"{asset_type}:{uic}"` (e.g., `"Stock:211"`)
- `asset_type`: `"Stock"`, `"FxSpot"`, etc.
- `uic`: Saxo UIC (e.g., `211`)
- `symbol`: Human-readable label (e.g., `"AAPL"`)
- `account_key`: Masked (e.g., `"****5678"`)
- `order_id`: Saxo OrderId (if applicable)
- `http_status`: HTTP status code for API calls (e.g., `200`, `400`, `429`)
- `error_code`: Saxo error code (if applicable)
- `error_message`: Saxo error message (if applicable)

### Scheduling Considerations
- Use external scheduler (cron/Task Scheduler) for reliability
- Schedule based on `TRADING_HOURS_MODE` from config:
  - `always`: Run every N minutes (e.g., for CryptoFX)
  - `fixed`: Run only during configured hours (e.g., 09:30-16:00 ET)
  - `instrument`: (Future) per-instrument session-aware scheduling
- Add random jitter (0-10 seconds) to distribute API load
- Each run is independent (prevents memory leaks, easier recovery)

## Dependencies
- **Epic 001-2:** Saxo Bank Migration (OAuth refresh logging)
- **Epic 002:** Configuration Module (`TRADING_HOURS_MODE`)
- **Epic 006:** Main Orchestration Script (cycle logging)

## Success Criteria
- [ ] Logging configuration module/function created
- [ ] Logs written to `logs/bot.log` with structured format
- [ ] All major events logged with Saxo-critical fields
- [ ] OAuth refresh events logged (success/failure)
- [ ] Log rotation implemented (prevents huge log files)
- [ ] Console and file logging both work
- [ ] Scheduling documentation complete for Windows/Linux/Mac
- [ ] Example cron/Task Scheduler configurations provided
- [ ] Trading hours scheduling aligned with `TRADING_HOURS_MODE`
- [ ] Random delay mechanism implemented

## Acceptance Criteria
1. Each bot cycle writes structured logs with timestamps and context
2. Saxo-critical fields included in relevant log entries
3. OAuth token refresh events logged with expiry times
4. Order execution logs include: instrument_id, order_id, precheck result, placement status
5. HTTP errors logged with status code, error body, and retry count
6. Old log files rotated automatically (daily or size-based)
7. Sensitive data masked (account_key, client_id)
8. Documentation explains how to set up scheduling for different trading hours modes
9. Can review historical bot behavior and trace orders from logs
10. Log analysis can identify trends (API errors, successful trades, token refreshes)

## Related Documents
- `logs/bot.log` (to be created)
- `README.md` (scheduling section to be added)
- [Epic 002: Configuration Module](./epic-002-configuration-module.md) (`TRADING_HOURS_MODE`)

## Logging Configuration Example

```python
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(log_level: str = "INFO"):
    """Configure logging for the trading bot with Saxo-specific context."""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Create formatter with additional context
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (10MB files, keep 5 backups)
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all, handlers filter
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive data, showing only last N characters."""
    if not value or len(value) <= visible_chars:
        return "****"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
```

## What to Log (Saxo-Specific)

### 1. Startup Events
```python
logger.info("Trading Bot Starting")
logger.info(f"Config loaded: {len(watchlist)} instruments, mode={trading_hours_mode}")
logger.info(f"Auth mode: {'OAuth' if oauth_enabled else 'Manual Token'}")
logger.info(f"Environment: {'SIM' if is_sim else 'LIVE'}")
logger.info(f"AccountKey: {mask_sensitive(account_key)}")
```

### 2. OAuth Token Management
```python
logger.info(f"OAuth token refreshed successfully, expires_at={expires_at}")
logger.error(f"OAuth token refresh failed: {error_message}")
logger.warning(f"Token expires in {minutes_remaining} minutes")
```

### 3. Data Retrieval
```python
logger.info(f"Fetching market data for {len(instruments)} instruments")
logger.info(
    f"Quote fetched: instrument_id={instrument_id}, asset_type={asset_type}, "
    f"uic={uic}, symbol={symbol}, bid={bid}, ask={ask}, timestamp={timestamp}"
)
logger.error(
    f"Data fetch failed: instrument_id={instrument_id}, http_status={status}, "
    f"error={error_message}"
)
```

### 4. Signal Generation
```python
logger.info(f"Signals generated: {signal_count} BUY, {sell_count} SELL, {hold_count} HOLD")
logger.info(
    f"Signal: instrument_id={instrument_id}, symbol={symbol}, signal={signal}, "
    f"reason={reason}"
)
```

### 5. Order Execution (Precheck + Placement)
```python
# Precheck
logger.info(
    f"Precheck: instrument_id={instrument_id}, asset_type={asset_type}, uic={uic}, "
    f"symbol={symbol}, buy_sell={buy_sell}, amount={amount}, "
    f"estimated_cost={cost}, is_valid={is_valid}"
)
logger.error(
    f"Precheck failed: instrument_id={instrument_id}, symbol={symbol}, "
    f"http_status={status}, error_code={error_code}, error_message={message}"
)

# Placement
logger.info(
    f"Order placed: instrument_id={instrument_id}, symbol={symbol}, "
    f"order_id={order_id}, buy_sell={buy_sell}, amount={amount}, "
    f"status={status}, account_key={mask_sensitive(account_key)}"
)
logger.error(
    f"Order placement failed: instrument_id={instrument_id}, symbol={symbol}, "
    f"http_status={status}, error={error_message}"
)
```

### 6. HTTP Errors
```python
logger.error(
    f"HTTP error: method={method}, url={url}, status={status_code}, "
    f"body={response_body}, retry_count={retry}"
)
```

### 7. Cycle Summary
```python
logger.info(
    f"Cycle complete: duration={duration_seconds}s, signals={signal_count}, "
    f"orders_placed={order_count}, errors={error_count}"
)
```

## Scheduling Based on TRADING_HOURS_MODE

### Mode: `always` (CryptoFX 24/7)
Run bot every N minutes continuously:

**Linux/Mac (cron):**
```bash
# Run every 5 minutes, 24/7
*/5 * * * * cd /path/to/trading_bot && /path/to/venv/bin/python main.py --single-cycle >> logs/cron.log 2>&1
```

**Windows (Task Scheduler):**
- Trigger: Daily at 00:00
- Repeat every: 5 minutes
- Duration: 24 hours
- Expire: Never

### Mode: `fixed` (Equity Market Hours)
Run bot only during configured hours:

**Example: US Market Hours (09:30-16:00 ET, weekdays)**

**Linux/Mac (cron):**
```bash
# Run every minute from 09:30-16:00 ET, Monday-Friday
*/1 9-16 * * 1-5 cd /path/to/trading_bot && /path/to/venv/bin/python main.py --single-cycle >> logs/cron.log 2>&1

# Or with specific timezone handling
*/1 * * * * TZ=America/New_York [ $(date +\%H) -ge 9 ] && [ $(date +\%H) -lt 16 ] && cd /path/to/trading_bot && /path/to/venv/bin/python main.py --single-cycle
```

**Windows (Task Scheduler):**
- Trigger: Daily at 09:30 AM
- Repeat every: 1 minute
- Duration: 6 hours 30 minutes (until 16:00)
- Days: Monday, Tuesday, Wednesday, Thursday, Friday

**Example: European Market Hours (08:00-16:30 CET, weekdays)**
```bash
# Run every minute from 08:00-16:30 CET, Monday-Friday
*/1 8-16 * * 1-5 cd /path/to/trading_bot && /path/to/venv/bin/python main.py --single-cycle >> logs/cron.log 2>&1
```

### Mode: `instrument` (Future - Per-Instrument Sessions)
Future enhancement: Query Saxo for trading sessions, schedule accordingly.

## Random Delay Implementation

```python
import random
import time

def add_jitter(max_seconds: int = 10):
    """Add random delay to avoid exact-minute API bursts."""
    jitter = random.randint(0, max_seconds)
    logger.debug(f"Adding jitter: {jitter} seconds")
    time.sleep(jitter)

# Use at start of each cycle
add_jitter()
```

## Log Analysis Utilities

### Example: Count Orders by Status
```bash
# Count successful order placements
grep "Order placed" logs/bot.log | wc -l

# Count precheck failures
grep "Precheck failed" logs/bot.log | wc -l

# Show HTTP errors with status codes
grep "HTTP error" logs/bot.log | grep -oP 'status=\d+' | sort | uniq -c
```

### Example: Extract Order IDs
```bash
# Extract all Saxo OrderIds
grep "order_id=" logs/bot.log | grep -oP 'order_id=\d+' | sort | uniq
```

### Example: Monitor Token Refresh
```bash
# Show OAuth refresh events
grep "OAuth token refresh" logs/bot.log | tail -20
```

## Log Retention Policy

### Retention Duration
- **Minimum:** 30 days of logs
- **Recommended:** 90 days for production systems
- **Compliance:** Check regulatory requirements (may require longer)

### Rotation Strategy
```python
# Option 1: Size-based (10MB files, keep 5 backups = 50MB total)
RotatingFileHandler('logs/bot.log', maxBytes=10*1024*1024, backupCount=5)

# Option 2: Time-based (daily rotation, keep 30 days)
from logging.handlers import TimedRotatingFileHandler
TimedRotatingFileHandler('logs/bot.log', when='midnight', interval=1, backupCount=30)
```

### Archival
```bash
# Compress old logs monthly
gzip logs/bot.log.2024-11-*

# Move to archive directory
mv logs/bot.log.*.gz logs/archive/
```

## Error Notification (Optional)

### Email Alerts for Critical Errors
```python
from logging.handlers import SMTPHandler

# Add SMTP handler for CRITICAL errors
smtp_handler = SMTPHandler(
    mailhost=('smtp.gmail.com', 587),
    fromaddr='bot@example.com',
    toaddrs=['admin@example.com'],
    subject='Trading Bot CRITICAL Error',
    credentials=('user', 'password'),
    secure=()
)
smtp_handler.setLevel(logging.CRITICAL)
logger.addHandler(smtp_handler)
```

## Notes
- External schedulers (cron/Task Scheduler) more reliable than internal loops
- Each run is independent (prevents memory leaks, easier failure recovery)
- Always use `--single-cycle` flag with schedulers (avoids infinite loops)
- Log review is essential: check daily for errors and anomalies
- Trading hours logic in orchestration (Epic 006) is primary; scheduling is secondary enforcement
- For CryptoFX 24/7, consider alerting on unusual activity (e.g., no trades for 24h)
- Mask sensitive data in logs, but keep full data in secure audit trail if needed
- Consider log forwarding to centralized system for production deployments

## Future Enhancements
- Structured logging (JSON format) for machine parsing
- Real-time log streaming to monitoring dashboard
- Automated log analysis (detect patterns, anomalies)
- Performance metrics logging (API latency, cycle duration)
- Integration with monitoring systems (Prometheus, Datadog)
- Log-based alerts (e.g., >10 failed orders in 1 hour → alert)
