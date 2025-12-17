# Story 006-005: Main Loop and Continuous Operation

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 3 Story Points  
**Priority:** High

## User Story
As a **trading bot operator**, I want **continuous loop operation with configurable intervals** so that the bot can **run autonomously and execute trading cycles repeatedly without manual intervention**.

## Acceptance Criteria
- [ ] Main loop implemented with while True pattern
- [ ] Configurable cycle interval via `CYCLE_INTERVAL_SECONDS`
- [ ] Sleep between cycles with logged countdown
- [ ] Single-cycle mode exits after one iteration
- [ ] Continuous mode runs indefinitely until interrupted
- [ ] Loop respects graceful shutdown signals (Ctrl+C)
- [ ] Each cycle is independent (no state leakage)
- [ ] Cycle counter tracked and logged

## Technical Details

### Main Loop Implementation
```python
def main():
    """Main trading bot execution."""
    args = parse_arguments()
    setup_logging()
    logger = logging.getLogger(__name__)
    log_startup_banner(args, logger)
    
    try:
        # Load configuration and initialize client
        config = load_configuration(logger)
        saxo_client = initialize_saxo_client(config, logger)
        
        # Execution mode branching
        if args.single_cycle:
            logger.info("Single-cycle mode: Running one cycle then exiting")
            run_cycle(config, saxo_client, dry_run=args.dry_run)
            logger.info("Single cycle complete. Exiting.")
        else:
            logger.info("Continuous mode: Running indefinitely until interrupted")
            run_continuous_loop(config, saxo_client, dry_run=args.dry_run)
    
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Critical error in main: {e}", exc_info=True)
        return 1  # Exit with error code
    finally:
        logger.info("Trading bot shutting down")
    
    return 0  # Exit successfully


def run_continuous_loop(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """
    Run trading cycles continuously in a loop.
    
    Args:
        config: Settings instance
        saxo_client: Initialized Saxo client
        dry_run: If True, precheck only
    """
    logger = logging.getLogger(__name__)
    cycle_count = 0
    
    while True:
        cycle_count += 1
        logger.info(f"Starting cycle #{cycle_count}")
        
        try:
            run_cycle(config, saxo_client, dry_run=dry_run)
        except Exception as e:
            # Log error but don't crash - continue to next cycle
            logger.error(f"Cycle #{cycle_count} failed: {e}", exc_info=True)
            logger.info("Continuing to next cycle after error")
        
        # Sleep until next cycle
        sleep_time = config.CYCLE_INTERVAL_SECONDS
        logger.info(f"Cycle #{cycle_count} complete. Sleeping for {sleep_time} seconds.")
        logger.info(f"Next cycle will start at: {_get_next_cycle_time(sleep_time)}")
        
        time.sleep(sleep_time)


def _get_next_cycle_time(sleep_seconds: int) -> str:
    """
    Calculate and format the next cycle start time.
    
    Args:
        sleep_seconds: Seconds to sleep
        
    Returns:
        str: Formatted next cycle time
    """
    next_time = datetime.now() + timedelta(seconds=sleep_seconds)
    return next_time.strftime("%Y-%m-%d %H:%M:%S")
```

### Configuration
```python
# config/settings.py or .env
CYCLE_INTERVAL_SECONDS = 300  # 5 minutes

# Examples:
# 60 = 1 minute (for testing/high-frequency)
# 300 = 5 minutes (reasonable default)
# 900 = 15 minutes
# 1800 = 30 minutes
# 3600 = 1 hour
```

### Cycle Independence
```python
# Each cycle should be independent - no shared state between cycles
# Good: Config and client initialized once, reused across cycles
config = load_configuration(logger)  # Once at startup
saxo_client = initialize_saxo_client(config, logger)  # Once at startup

# Bad: Don't reload config or recreate client every cycle
while True:
    # Good: Just pass config and client to run_cycle
    run_cycle(config, saxo_client, dry_run=args.dry_run)
    
    # Bad: Don't do this
    # config = load_configuration(logger)  # Wasteful and error-prone
    # saxo_client = initialize_saxo_client(config, logger)  # Wasteful
```

## Enhanced Sleep with Progress Indicator (Optional)
```python
def sleep_with_progress(sleep_seconds: int, logger):
    """
    Sleep with periodic progress updates.
    
    Args:
        sleep_seconds: Total seconds to sleep
        logger: Logger instance
    """
    if sleep_seconds <= 60:
        # Short sleep - just wait
        time.sleep(sleep_seconds)
        return
    
    # For longer sleeps, log progress every minute
    elapsed = 0
    update_interval = 60  # Log every minute
    
    while elapsed < sleep_seconds:
        remaining = sleep_seconds - elapsed
        if remaining > update_interval:
            time.sleep(update_interval)
            elapsed += update_interval
            logger.debug(f"Sleeping... {remaining - update_interval} seconds remaining")
        else:
            time.sleep(remaining)
            elapsed = sleep_seconds


# Usage in continuous loop:
sleep_with_progress(config.CYCLE_INTERVAL_SECONDS, logger)
```

## Graceful Shutdown Handling
```python
import signal
import sys

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    
    # Set a global flag to stop loop
    global shutdown_requested
    shutdown_requested = True


def run_continuous_loop(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """Run with graceful shutdown support."""
    global shutdown_requested
    shutdown_requested = False
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger = logging.getLogger(__name__)
    cycle_count = 0
    
    while not shutdown_requested:
        cycle_count += 1
        
        try:
            run_cycle(config, saxo_client, dry_run=dry_run)
        except Exception as e:
            logger.error(f"Cycle #{cycle_count} failed: {e}", exc_info=True)
        
        if shutdown_requested:
            logger.info("Shutdown requested during cycle. Exiting loop.")
            break
        
        # Sleep with periodic checks for shutdown
        sleep_time = config.CYCLE_INTERVAL_SECONDS
        logger.info(f"Sleeping for {sleep_time} seconds.")
        
        # Break sleep into 10-second chunks to check shutdown flag
        for _ in range(0, sleep_time, 10):
            if shutdown_requested:
                logger.info("Shutdown requested during sleep. Exiting loop.")
                break
            time.sleep(min(10, sleep_time))
```

## Error Recovery Strategy

### Cycle-Level Errors (Continue Loop)
```python
# Errors in individual cycles should not crash the bot
try:
    run_cycle(config, saxo_client, dry_run=dry_run)
except Exception as e:
    logger.error(f"Cycle failed: {e}", exc_info=True)
    logger.info("Continuing to next cycle after error")
    # Continue loop - don't crash
```

### Critical Errors (Exit Loop)
```python
# Only exit loop on critical errors
try:
    config = load_configuration(logger)
    saxo_client = initialize_saxo_client(config, logger)
except Exception as e:
    logger.critical(f"Critical initialization error: {e}", exc_info=True)
    return 1  # Exit - can't continue without config/client
```

## Implementation Steps
1. Create `run_continuous_loop()` function with while True
2. Add cycle counter and logging
3. Integrate `run_cycle()` call inside try/except
4. Add sleep with configurable interval
5. Add next cycle time calculation and logging
6. Implement single-cycle vs continuous branching in main()
7. Test single-cycle mode (runs once, exits)
8. Test continuous mode (runs indefinitely)
9. Test Ctrl+C graceful shutdown
10. Test error recovery (cycle errors don't crash loop)

## Dependencies
- Story 006-001: Command-Line Arguments
- Story 006-002: Configuration Loading
- Story 006-004: Single Trading Cycle

## Testing Strategy
```python
# tests/test_main_loop.py
import unittest
from unittest.mock import Mock, patch, call
import time

class TestMainLoop(unittest.TestCase):
    """Test main loop and continuous operation."""
    
    @patch('main.run_cycle')
    @patch('time.sleep')
    def test_continuous_loop_runs_multiple_cycles(self, mock_sleep, mock_run_cycle):
        """Test continuous loop runs multiple cycles."""
        config = Mock()
        config.CYCLE_INTERVAL_SECONDS = 60
        saxo_client = Mock()
        
        # Run 3 cycles then stop
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 3:
                raise KeyboardInterrupt()  # Simulate Ctrl+C
        
        mock_run_cycle.side_effect = side_effect
        
        try:
            run_continuous_loop(config, saxo_client, dry_run=False)
        except KeyboardInterrupt:
            pass
        
        # Verify run_cycle was called 3 times
        self.assertEqual(mock_run_cycle.call_count, 3)
        
        # Verify sleep was called with correct interval
        mock_sleep.assert_called_with(60)
    
    @patch('main.run_cycle')
    @patch('time.sleep')
    def test_continuous_loop_recovers_from_cycle_errors(self, mock_sleep, mock_run_cycle):
        """Test loop continues after cycle errors."""
        config = Mock()
        config.CYCLE_INTERVAL_SECONDS = 60
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
        
        try:
            run_continuous_loop(config, saxo_client, dry_run=False)
        except KeyboardInterrupt:
            pass
        
        # Verify run_cycle was called twice (error + success)
        self.assertEqual(mock_run_cycle.call_count, 2)
    
    @patch('main.run_cycle')
    def test_single_cycle_mode(self, mock_run_cycle):
        """Test single-cycle mode runs once and exits."""
        args = Mock()
        args.single_cycle = True
        args.dry_run = False
        
        config = Mock()
        saxo_client = Mock()
        
        # In actual main(), this would call run_cycle once
        run_cycle(config, saxo_client, dry_run=False)
        
        # Verify run_cycle was called once
        mock_run_cycle.assert_called_once()
```

## Validation Checklist
- [ ] Single-cycle mode runs once and exits
- [ ] Continuous mode runs indefinitely until interrupted
- [ ] Cycle interval is configurable via `CYCLE_INTERVAL_SECONDS`
- [ ] Sleep duration is logged between cycles
- [ ] Next cycle time is calculated and logged
- [ ] Cycle counter increments correctly
- [ ] Ctrl+C triggers graceful shutdown
- [ ] Cycle errors don't crash the loop
- [ ] Critical initialization errors exit cleanly
- [ ] Each cycle is independent (no state leakage)

## Related Stories
- [Story 006-001: Command-Line Arguments and Initialization](./story-006-001-command-line-arguments-initialization.md)
- [Story 006-004: Single Trading Cycle Implementation](./story-006-004-single-trading-cycle.md)
- [Story 006-006: Error Handling and Graceful Shutdown](./story-006-006-error-handling-graceful-shutdown.md)

## Notes
- Keep loop simple - avoid complex state management
- Each cycle should be independent (immutable config, reused client)
- Don't reload configuration during loop (error-prone, wasteful)
- Log next cycle time for operator convenience
- Consider adding sleep progress indicator for long intervals (>5 minutes)
- Graceful shutdown is critical for clean exit
- Cycle errors should be logged but not crash the bot
- Future: Add health check endpoint that reports last successful cycle time
- Future: Add metrics export (cycle duration, success rate, etc.)
