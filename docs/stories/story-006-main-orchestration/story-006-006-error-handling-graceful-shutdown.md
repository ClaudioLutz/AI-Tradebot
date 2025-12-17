# Story 006-006: Error Handling and Graceful Shutdown

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 5 Story Points  
**Priority:** High

## User Story
As a **trading bot operator**, I want **comprehensive error handling and graceful shutdown** so that the bot **recovers from transient errors, logs failures properly, and exits cleanly without data loss**.

## Acceptance Criteria
- [ ] Distinguishes between recoverable and non-recoverable errors
- [ ] Recoverable errors logged and skipped (cycle continues)
- [ ] Non-recoverable errors trigger clean shutdown
- [ ] Ctrl+C (SIGINT) handled gracefully
- [ ] SIGTERM handled gracefully (for Docker/systemd)
- [ ] All errors logged with full traceback
- [ ] Resource cleanup in finally block
- [ ] Exit codes indicate success (0) or failure (1)

## Technical Details

### Error Classification

#### Recoverable Errors (Continue Operation)
```python
class RecoverableError(Exception):
    """Errors that can be logged and skipped."""
    pass

# Examples:
# - Single instrument data fetch fails
# - Single order precheck fails
# - HTTP 429 (rate limit) - can retry
# - HTTP 500 (server error) - temporary
# - Network timeout - temporary
```

#### Non-Recoverable Errors (Exit)
```python
class FatalError(Exception):
    """Errors that require shutdown."""
    pass

# Examples:
# - Configuration file missing/invalid
# - Authentication failure (expired token, invalid credentials)
# - All instruments fail data fetch
# - Critical module import failure
```

### Comprehensive Error Handling
```python
def main():
    """Main trading bot execution with comprehensive error handling."""
    args = parse_arguments()
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        log_startup_banner(args, logger)
        
        # Critical initialization - any failure is fatal
        try:
            config = load_configuration(logger)
            saxo_client = initialize_saxo_client(config, logger)
        except Exception as e:
            logger.critical(
                f"Fatal initialization error: {e}. Cannot start trading bot.",
                exc_info=True
            )
            return 1  # Exit with error code
        
        # Run trading logic
        if args.single_cycle:
            run_cycle(config, saxo_client, dry_run=args.dry_run)
        else:
            run_continuous_loop(config, saxo_client, dry_run=args.dry_run)
    
    except KeyboardInterrupt:
        logger.info("=" * 60)
        logger.info("Shutdown initiated by user (Ctrl+C)")
        logger.info("=" * 60)
    
    except SystemExit as e:
        logger.info(f"System exit requested with code: {e.code}")
        return e.code if e.code else 0
    
    except Exception as e:
        logger.critical(
            f"Unexpected critical error in main: {e}",
            exc_info=True
        )
        return 1  # Exit with error code
    
    finally:
        # Resource cleanup
        cleanup_resources(logger)
    
    return 0  # Success


def cleanup_resources(logger):
    """Clean up resources before shutdown."""
    logger.info("Cleaning up resources...")
    
    try:
        # Close any open connections
        # Flush logs
        # Save any pending state
        pass
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    logger.info("=" * 60)
    logger.info("TRADING BOT SHUTDOWN COMPLETE")
    logger.info("=" * 60)
```

### Cycle-Level Error Handling
```python
def run_cycle(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """Execute a single trading cycle with error handling."""
    logger = logging.getLogger(__name__)
    
    try:
        # Trading hours check
        if not should_trade_now(config, logger):
            logger.info("Outside trading hours, skipping cycle")
            return
        
        # Fetch market data
        try:
            market_data = fetch_market_data(config.WATCHLIST, logger)
            if not market_data:
                logger.warning("No market data available, skipping cycle")
                return  # Recoverable - skip this cycle
        except Exception as e:
            logger.error(f"Market data fetch failed: {e}", exc_info=True)
            return  # Recoverable - skip this cycle
        
        # Generate signals
        try:
            signals = generate_trading_signals(market_data, config, logger)
        except Exception as e:
            logger.error(f"Signal generation failed: {e}", exc_info=True)
            return  # Recoverable - skip this cycle
        
        # Execute signals
        try:
            execute_trading_signals(signals, market_data, config, dry_run, logger)
        except Exception as e:
            logger.error(f"Signal execution failed: {e}", exc_info=True)
            # Continue - log failure but don't crash
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error in trading cycle: {e}", exc_info=True)
        # Don't propagate - log and continue to next cycle
```

### Instrument-Level Error Handling
```python
def execute_trading_signals(signals, market_data, config, dry_run, logger):
    """Execute signals with per-instrument error handling."""
    for instrument_id, signal in signals.items():
        if signal == "HOLD":
            continue
        
        try:
            # Execute this signal
            instrument_data = market_data.get(instrument_id)
            if not instrument_data:
                logger.warning(f"No data for {instrument_id}, skipping")
                continue  # Skip this instrument, continue with others
            
            success = execute_signal(
                instrument=build_instrument_dict(instrument_data),
                signal=signal,
                account_key=config.SAXO_ACCOUNT_KEY,
                amount=config.DEFAULT_QUANTITY,
                dry_run=dry_run
            )
            
            if not success:
                logger.error(f"Failed to execute {signal} for {instrument_id}")
        
        except Exception as e:
            # Log error but continue with other instruments
            logger.error(
                f"Error executing {signal} for {instrument_id}: {e}",
                exc_info=True
            )
            continue  # Don't let one instrument crash the whole cycle
```

### Signal Handling (Graceful Shutdown)
```python
import signal
import sys

# Global shutdown flag
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger = logging.getLogger(__name__)
    
    signal_names = {
        signal.SIGINT: "SIGINT (Ctrl+C)",
        signal.SIGTERM: "SIGTERM (Kill)"
    }
    
    signal_name = signal_names.get(signum, f"Signal {signum}")
    logger.info(f"Received {signal_name}. Initiating graceful shutdown...")
    
    shutdown_requested = True


def setup_signal_handlers():
    """Register signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def run_continuous_loop(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """Run continuous loop with graceful shutdown support."""
    global shutdown_requested
    shutdown_requested = False
    
    setup_signal_handlers()
    
    logger = logging.getLogger(__name__)
    cycle_count = 0
    
    while not shutdown_requested:
        cycle_count += 1
        
        try:
            run_cycle(config, saxo_client, dry_run=dry_run)
        except Exception as e:
            logger.error(f"Cycle #{cycle_count} failed: {e}", exc_info=True)
        
        if shutdown_requested:
            logger.info("Shutdown requested. Exiting main loop.")
            break
        
        # Sleep with periodic shutdown checks
        sleep_time = config.CYCLE_INTERVAL_SECONDS
        for _ in range(0, sleep_time, 10):
            if shutdown_requested:
                break
            time.sleep(min(10, sleep_time - (_ * 10)))
```

## Error Logging Best Practices

### Structured Error Logging
```python
def log_error_structured(logger, error_type, phase, instrument_id=None, details=None):
    """Log errors in structured format for analysis."""
    log_data = {
        "error_type": error_type,
        "phase": phase,
        "timestamp": datetime.now().isoformat(),
    }
    
    if instrument_id:
        log_data["instrument_id"] = instrument_id
    
    if details:
        log_data["details"] = details
    
    logger.error(f"Structured error: {log_data}", exc_info=True)


# Usage:
try:
    result = risky_operation()
except Exception as e:
    log_error_structured(
        logger,
        error_type="API_ERROR",
        phase="market_data_fetch",
        instrument_id="FxSpot/12345",
        details=str(e)
    )
```

### Error Metrics (Optional)
```python
# Track error counts for monitoring
error_counts = {
    "market_data_errors": 0,
    "signal_generation_errors": 0,
    "execution_errors": 0,
    "critical_errors": 0
}

def increment_error_count(error_type):
    """Increment error counter for metrics."""
    if error_type in error_counts:
        error_counts[error_type] += 1


# Log error summary periodically
def log_error_summary(logger):
    """Log error summary for monitoring."""
    logger.info(f"Error Summary: {error_counts}")
```

## Exit Codes
```python
# Standard exit codes
EXIT_SUCCESS = 0
EXIT_CONFIGURATION_ERROR = 1
EXIT_AUTHENTICATION_ERROR = 2
EXIT_CRITICAL_ERROR = 3

def main():
    """Main with proper exit codes."""
    try:
        config = load_configuration(logger)
    except Exception as e:
        logger.critical(f"Configuration error: {e}")
        return EXIT_CONFIGURATION_ERROR
    
    try:
        saxo_client = initialize_saxo_client(config, logger)
    except Exception as e:
        logger.critical(f"Authentication error: {e}")
        return EXIT_AUTHENTICATION_ERROR
    
    # ... rest of logic
    
    return EXIT_SUCCESS
```

## Implementation Steps
1. Create error classification (Recoverable vs Fatal)
2. Add comprehensive try/except blocks in main()
3. Implement signal handlers (SIGINT, SIGTERM)
4. Add resource cleanup in finally block
5. Implement cycle-level error handling (log and continue)
6. Implement instrument-level error handling (skip failed instruments)
7. Add structured error logging
8. Implement proper exit codes
9. Test error scenarios:
   - Configuration missing
   - Authentication failure
   - Single instrument fails
   - API rate limit
   - Network timeout
   - Ctrl+C during cycle
   - Ctrl+C during sleep

## Dependencies
- Python `signal` module (built-in)
- Python `sys` module (built-in)

## Testing Strategy
```python
# tests/test_error_handling.py
import unittest
from unittest.mock import Mock, patch

class TestErrorHandling(unittest.TestCase):
    """Test error handling and recovery."""
    
    @patch('main.load_configuration')
    def test_configuration_error_exits_cleanly(self, mock_config):
        """Test configuration error causes clean exit."""
        mock_config.side_effect = Exception("Config not found")
        
        exit_code = main()
        
        self.assertEqual(exit_code, 1)
    
    @patch('main.run_cycle')
    def test_cycle_error_continues_loop(self, mock_run_cycle):
        """Test cycle error doesn't crash loop."""
        config = Mock()
        config.CYCLE_INTERVAL_SECONDS = 1
        saxo_client = Mock()
        
        # First cycle fails, second succeeds, then stop
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Cycle error")
            elif call_count[0] >= 2:
                raise KeyboardInterrupt()
        
        mock_run_cycle.side_effect = side_effect
        
        # Should not crash - loop should continue after error
        try:
            run_continuous_loop(config, saxo_client, dry_run=False)
        except KeyboardInterrupt:
            pass
        
        self.assertEqual(mock_run_cycle.call_count, 2)
    
    def test_signal_handler_sets_shutdown_flag(self):
        """Test signal handler sets shutdown flag."""
        global shutdown_requested
        shutdown_requested = False
        
        signal_handler(signal.SIGINT, None)
        
        self.assertTrue(shutdown_requested)
```

## Validation Checklist
- [ ] Configuration errors cause clean exit with error code
- [ ] Authentication errors cause clean exit with error code
- [ ] Cycle errors are logged but don't crash loop
- [ ] Instrument errors are logged but don't crash cycle
- [ ] Ctrl+C triggers graceful shutdown
- [ ] SIGTERM triggers graceful shutdown
- [ ] All errors logged with full traceback
- [ ] Resources cleaned up in finally block
- [ ] Exit codes indicate success/failure correctly
- [ ] Shutdown during sleep exits cleanly
- [ ] Shutdown during cycle completes current cycle

## Related Stories
- [Story 006-001: Command-Line Arguments and Initialization](./story-006-001-command-line-arguments-initialization.md)
- [Story 006-004: Single Trading Cycle Implementation](./story-006-004-single-trading-cycle.md)
- [Story 006-005: Main Loop and Continuous Operation](./story-006-005-main-loop-continuous-operation.md)

## Notes
- Fail fast for configuration/authentication (can't run without them)
- Fail gracefully for transient errors (network, API, single instrument)
- Always log full tracebacks for debugging
- Signal handling is critical for Docker/systemd deployments
- Resource cleanup prevents memory leaks and connection issues
- Exit codes enable monitoring scripts to detect failures
- Consider adding error alerting (email, Slack) for critical errors
- Consider adding error rate limiting (halt if too many errors per hour)
- Future: Add error metrics export (Prometheus, CloudWatch)
