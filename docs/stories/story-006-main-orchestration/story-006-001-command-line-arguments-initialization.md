# Story 006-001: Command-Line Arguments and Initialization

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 3 Story Points  
**Priority:** High

## User Story
As a **trading bot operator**, I want **command-line arguments and proper initialization** so that I can **control bot behavior (dry-run, single-cycle) and have structured logging from startup**.

## Acceptance Criteria
- [ ] `main.py` has proper `if __name__ == "__main__"` entry point
- [ ] Command-line argument parser implemented using `argparse`
- [ ] Supports `--dry-run` flag (precheck only, no order placement)
- [ ] Supports `--single-cycle` flag (run once then exit)
- [ ] Logging configured with structured format including timestamps, levels, and module names
- [ ] Startup banner logs script mode (DRY_RUN vs SIM, Single vs Continuous)
- [ ] Script has proper docstring with usage examples
- [ ] Help text is clear and comprehensive (`python main.py --help`)

## Technical Details

### Command-Line Arguments
```python
import argparse

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Trading Bot - Main Orchestration Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Continuous loop in SIM mode (default)
  python main.py

  # Single cycle in DRY_RUN mode (testing)
  python main.py --dry-run --single-cycle

  # Continuous loop in DRY_RUN mode
  python main.py --dry-run
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Precheck only, no orders placed (for testing strategy logic)"
    )
    
    parser.add_argument(
        "--single-cycle",
        action="store_true",
        help="Run one trading cycle then exit (useful for cron scheduling)"
    )
    
    return parser.parse_args()
```

### Logging Configuration
```python
import logging

def setup_logging():
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Optionally reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
```

### Startup Banner
```python
def log_startup_banner(args, logger):
    """Log startup information for audit trail."""
    logger.info("=" * 60)
    logger.info("TRADING BOT STARTING")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY_RUN (Precheck Only)' if args.dry_run else 'SIM (Simulation Trading)'}")
    logger.info(f"Execution: {'Single Cycle' if args.single_cycle else 'Continuous Loop'}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)
```

### Main Entry Point
```python
def main():
    """Main trading bot execution."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Log startup banner
    log_startup_banner(args, logger)
    
    try:
        # TODO: Rest of main logic
        pass
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
    finally:
        logger.info("Trading bot shutting down")


if __name__ == "__main__":
    main()
```

## Implementation Steps
1. Create argument parser with `--dry-run` and `--single-cycle` flags
2. Add comprehensive help text and usage examples
3. Implement logging configuration with structured format
4. Create startup banner logging function
5. Implement main entry point with try/except/finally blocks
6. Add script docstring with usage instructions
7. Test command-line argument parsing:
   ```bash
   python main.py --help
   python main.py --dry-run
   python main.py --single-cycle
   python main.py --dry-run --single-cycle
   ```

## Dependencies
- Python `argparse` module (built-in)
- Python `logging` module (built-in)

## Testing Strategy
```python
# tests/test_main_initialization.py
import unittest
from unittest.mock import patch
import sys

class TestCommandLineArguments(unittest.TestCase):
    """Test command-line argument parsing."""
    
    def test_no_arguments(self):
        """Test default behavior (no flags)."""
        with patch.object(sys, 'argv', ['main.py']):
            args = parse_arguments()
            self.assertFalse(args.dry_run)
            self.assertFalse(args.single_cycle)
    
    def test_dry_run_flag(self):
        """Test --dry-run flag."""
        with patch.object(sys, 'argv', ['main.py', '--dry-run']):
            args = parse_arguments()
            self.assertTrue(args.dry_run)
            self.assertFalse(args.single_cycle)
    
    def test_single_cycle_flag(self):
        """Test --single-cycle flag."""
        with patch.object(sys, 'argv', ['main.py', '--single-cycle']):
            args = parse_arguments()
            self.assertFalse(args.dry_run)
            self.assertTrue(args.single_cycle)
    
    def test_both_flags(self):
        """Test both flags together."""
        with patch.object(sys, 'argv', ['main.py', '--dry-run', '--single-cycle']):
            args = parse_arguments()
            self.assertTrue(args.dry_run)
            self.assertTrue(args.single_cycle)
    
    def test_help_text(self):
        """Test that help text is displayed."""
        with patch.object(sys, 'argv', ['main.py', '--help']):
            with self.assertRaises(SystemExit):
                parse_arguments()
```

## Validation Checklist
- [ ] Script runs without errors: `python main.py`
- [ ] Help text is clear and comprehensive: `python main.py --help`
- [ ] Flags are parsed correctly: `python main.py --dry-run --single-cycle`
- [ ] Logging format includes timestamp, level, and module name
- [ ] Startup banner logs mode and execution type
- [ ] Ctrl+C triggers graceful shutdown message
- [ ] Critical errors are logged with full traceback

## Related Stories
- [Story 006-002: Configuration and Client Initialization](./story-006-002-configuration-client-initialization.md)
- [Story 006-005: Main Loop and Continuous Operation](./story-006-005-main-loop-continuous-operation.md)
- [Story 006-006: Error Handling and Graceful Shutdown](./story-006-006-error-handling-graceful-shutdown.md)

## Notes
- Keep argument parsing simple; avoid over-engineering with subcommands
- Logging format should be consistent with existing modules (config, data, strategies, execution)
- Consider adding `--version` flag in future iteration
- Consider adding `--config-file` flag for custom config paths in future
- Startup banner should be informative but not excessively verbose
