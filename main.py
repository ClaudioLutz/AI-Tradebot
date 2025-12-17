"""
AI Trading Bot - Main Orchestration Script

This is the main entry point for the trading bot that coordinates all modules:
- Configuration loading and validation
- Saxo client initialization and authentication
- Trading hours validation
- Market data retrieval
- Signal generation
- Trade execution

Epic 006: Main Orchestration (Multi-Asset)

Usage:
    # Continuous loop in SIM mode (default)
    python main.py

    # Single cycle in DRY_RUN mode (testing)
    python main.py --dry-run --single-cycle

    # Continuous loop in DRY_RUN mode
    python main.py --dry-run

Command-Line Arguments:
    --dry-run        Precheck only, no orders placed (for testing strategy logic)
    --single-cycle   Run one trading cycle then exit (useful for cron scheduling)
"""

import argparse
import logging
import time
import sys
import uuid
from datetime import datetime, time as time_obj
from zoneinfo import ZoneInfo
from typing import Optional, Dict, List, Any

# Import project modules
from config import settings
from data.saxo_client import SaxoClient
from data.market_data import get_latest_quotes
from strategies.base import BaseStrategy
from strategies.registry import get_strategy
from execution.trade_executor import SaxoTradeExecutor
from execution.models import OrderIntent, BuySell, AssetType
from logging_config import setup_logging
from common.log_context import TradingContextAdapter

# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Utility Functions
# =============================================================================

def mask_sensitive_data(value: Optional[str], show_chars: int = 8) -> str:
    """
    Mask sensitive data for secure logging.
    
    Args:
        value: The sensitive string to mask (or None)
        show_chars: Number of characters to show at start (default: 8)
        
    Returns:
        str: Masked string showing only first few and last 4 characters
        
    Example:
        mask_sensitive_data("1234567890abcdef") -> "12345678...cdef"
        mask_sensitive_data(None) -> "***"
    """
    if not value or len(value) <= show_chars:
        return "***"
    return f"{value[:show_chars]}...{value[-4:]}"


def validate_config_types(config) -> None:
    """
    Validate configuration value types and ranges.
    
    Args:
        config: Settings object with configuration
        
    Raises:
        ValueError: If configuration values are invalid
    """
    if config.CYCLE_INTERVAL_SECONDS < 1:
        raise ValueError("CYCLE_INTERVAL_SECONDS must be >= 1")
    
    if config.DEFAULT_QUANTITY <= 0:
        raise ValueError("DEFAULT_QUANTITY must be > 0")
    
    if config.MAX_POSITIONS < 1:
        raise ValueError("MAX_POSITIONS must be >= 1")
    
    if config.MAX_DAILY_TRADES < 1:
        raise ValueError("MAX_DAILY_TRADES must be >= 1")
    
    valid_modes = ["always", "fixed", "instrument"]
    if config.TRADING_HOURS_MODE not in valid_modes:
        raise ValueError(
            f"TRADING_HOURS_MODE must be one of {valid_modes}, "
            f"got: {config.TRADING_HOURS_MODE}"
        )


# =============================================================================
# Story 006-001: Command-Line Arguments and Initialization
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
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


# Replaced by logging_config.setup_logging


def log_startup_banner(args: argparse.Namespace) -> None:
    """
    Log startup information for audit trail.
    
    Args:
        args: Parsed command-line arguments
    """
    logger.info("=" * 60)
    logger.info("TRADING BOT STARTING")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY_RUN (Precheck Only)' if args.dry_run else 'SIM (Simulation Trading)'}")
    logger.info(f"Execution: {'Single Cycle' if args.single_cycle else 'Continuous Loop'}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)


# =============================================================================
# Story 006-002: Configuration and Client Initialization
# =============================================================================

def load_configuration():
    """
    Load and validate configuration once at startup.
    
    Returns:
        settings: Validated configuration settings object
        
    Raises:
        ValueError: If required configuration is missing or invalid
    """
    try:
        logger.info("Loading configuration from environment and settings")
        
        # Validate required environment variables
        required_vars = ["SAXO_ACCOUNT_KEY", "SAXO_CLIENT_KEY"]
        missing_vars = [var for var in required_vars if not getattr(settings, var, None)]
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please set them in your .env file."
            )
        
        # Log configuration summary (mask sensitive data for security)
        logger.info(f"Account Key: {mask_sensitive_data(settings.SAXO_ACCOUNT_KEY)}")
        logger.info(f"Client Key: {mask_sensitive_data(settings.SAXO_CLIENT_KEY)}")
        logger.info(f"Watchlist Size: {len(settings.WATCHLIST)} instruments")
        logger.info(f"Trading Hours Mode: {settings.TRADING_HOURS_MODE}")
        logger.info(f"Cycle Interval: {settings.CYCLE_INTERVAL_SECONDS} seconds")
        logger.info(f"Auth Mode: {settings.SAXO_AUTH_MODE}")
        
        # Validate configuration types and ranges
        validate_config_types(settings)
        
        # Normalize watchlist: create immutable copy with consistent 'symbol' field
        # This prevents mutation of the original configuration
        normalized_watchlist = []
        for idx, instrument in enumerate(settings.WATCHLIST):
            # Required keys: either 'name' or 'symbol', plus 'asset_type'
            has_identifier = "symbol" in instrument or "name" in instrument
            has_asset_type = "asset_type" in instrument
            
            if not has_identifier or not has_asset_type:
                raise ValueError(
                    f"Invalid instrument at index {idx}: missing required keys. "
                    f"Required: ['symbol' or 'name', 'asset_type'], Got: {list(instrument.keys())}"
                )
            
            # Create normalized copy with 'symbol' field
            normalized_instrument = instrument.copy()
            if "symbol" not in normalized_instrument and "name" in normalized_instrument:
                normalized_instrument["symbol"] = normalized_instrument["name"]
            
            normalized_watchlist.append(normalized_instrument)
        
        # Replace watchlist with normalized version (immutable after this point)
        settings.WATCHLIST = normalized_watchlist
        
        logger.info("Configuration loaded and validated successfully")
        return settings
    
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)
        raise


def initialize_saxo_client(config):
    """Initialize Saxo client with authentication."""
    try:
        logger.info("Initializing Saxo OpenAPI client")
        logger.info(f"Environment: {config.SAXO_ENV}")
        logger.info(f"Auth mode: {config.SAXO_AUTH_MODE}")
        
        saxo_client = SaxoClient()
        
        # Validate authentication by making a test API call
        logger.info("Validating authentication with test API call")
        
        try:
            # Test: Get user info
            response = saxo_client.get("/port/v1/users/me")
            if isinstance(response, dict):
                user_id = response.get("UserId", "Unknown")
                logger.info(f"Authentication successful. User ID: {user_id}")
            else:
                logger.info("Authentication successful")
        except Exception as auth_error:
            logger.error(f"Authentication validation failed: {auth_error}")
            logger.error(
                "Please verify your token is valid and not expired. "
                "Run 'python scripts/saxo_login.py' to refresh your OAuth token."
            )
            raise
        
        logger.info("Saxo client initialized and authenticated successfully")
        return saxo_client
    
    except Exception as e:
        logger.error(f"Failed to initialize Saxo client: {e}", exc_info=True)
        raise


# =============================================================================
# Story 006-003: Trading Hours Logic
# =============================================================================

def should_trade_now(config) -> bool:
    """
    Determine if trading should occur based on TRADING_HOURS_MODE.
    
    Args:
        config: Settings object with trading hours configuration
        
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
        return _check_fixed_hours(config)
    
    elif mode == "instrument":
        # Future: per-instrument trading sessions
        logger.error("TRADING_HOURS_MODE='instrument' not yet implemented")
        raise NotImplementedError("Per-instrument hours not yet implemented")
    
    else:
        logger.error(f"Unknown TRADING_HOURS_MODE: {mode}. Defaulting to no trading.")
        return False


def _check_fixed_hours(config) -> bool:
    """
    Check if current time is within fixed trading hours.
    
    Args:
        config: Settings with TRADING_START, TRADING_END, TIMEZONE
        
    Returns:
        bool: True if within trading hours, False otherwise
    """
    try:
        # Get current time in configured timezone
        timezone = ZoneInfo(config.TIMEZONE)
        current_time = datetime.now(timezone)
        
        # Parse trading hours (format: "HH:MM")
        start_time = time_obj.fromisoformat(config.TRADING_START)
        end_time = time_obj.fromisoformat(config.TRADING_END)
        
        current_time_only = current_time.time()
        
        # Check if current time is within trading window
        # Handle overnight trading (e.g., 22:00 - 02:00)
        if start_time > end_time:
            # Overnight trading window
            is_within_hours = (current_time_only >= start_time or 
                             current_time_only <= end_time)
        else:
            # Normal same-day window
            is_within_hours = (start_time <= current_time_only <= end_time)
        
        if is_within_hours:
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


# =============================================================================
# Story 006-004: Single Trading Cycle (Placeholder - Phase 2)
# =============================================================================

def run_cycle(config, saxo_client: SaxoClient, dry_run: bool = False):
    """
    Execute a single trading cycle.
    
    This is a placeholder implementation. Full implementation coming in Story 006-004.
    
    Args:
        config: Settings object with configuration
        saxo_client: Authenticated Saxo client
        dry_run: If True, precheck only (no order placement)
    """
    logger.info("=" * 60)
    logger.info("Starting trading cycle")
    logger.info(f"Mode: {'DRY_RUN' if dry_run else 'SIM'}")
    
    try:
        # 1. Check trading hours FIRST
        if not should_trade_now(config):
            logger.info("Outside trading hours, skipping cycle")
            return
        
        # 2. Fetch market data (placeholder)
        logger.info(f"Fetching market data for {len(config.WATCHLIST)} instruments")
        # TODO: Implement in Story 006-004
        # market_data = get_latest_quotes(config.WATCHLIST)
        
        # 3. Generate signals (placeholder)
        logger.info("Generating trading signals")
        # TODO: Implement in Story 006-004
        # strategy = get_strategy("moving_average")
        # signals = strategy.generate_signals(market_data, datetime.now(timezone.utc))
        
        # 4. Execute trades (placeholder)
        logger.info("Executing trades")
        # TODO: Implement in Story 006-004
        
        logger.info("Cycle complete (placeholder - full implementation in Story 006-004)")
        
    except Exception as e:
        logger.error(f"Error in trading cycle: {e}", exc_info=True)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main trading bot execution."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging (non-blocking, redacted)
    log_listener = setup_logging(log_level="DEBUG" if args.dry_run else "INFO")

    # Generate Run ID
    run_id = str(uuid.uuid4())

    # Initialize context logger for main startup
    # We use a global variable or pass it down?
    # Better to re-bind logger to the adapter locally
    main_logger = TradingContextAdapter(logger, {'run_id': run_id, 'cycle_id': 'INIT'})
    
    # Log startup banner
    main_logger.info("=" * 60)
    main_logger.info("TRADING BOT STARTING")
    main_logger.info("=" * 60)
    main_logger.log_event("startup_begin",
        mode='DRY_RUN' if args.dry_run else 'SIM',
        execution='Single Cycle' if args.single_cycle else 'Continuous Loop',
        timestamp=datetime.now().isoformat()
    )
    main_logger.info("=" * 60)
    
    try:
        # 1. Load configuration (once at startup, immutable)
        config = load_configuration()
        main_logger.log_event("startup_config_loaded")
        
        # 2. Initialize Saxo client
        saxo_client = initialize_saxo_client(config)
        
        # 3. Run trading logic
        if args.single_cycle:
            cycle_id = str(uuid.uuid4())
            cycle_logger = TradingContextAdapter(logger, {'run_id': run_id, 'cycle_id': cycle_id})
            cycle_logger.info("Running single cycle mode")

            run_cycle(config, saxo_client, dry_run=args.dry_run)
        else:
            main_logger.info("Running continuous loop mode")
            cycle_count = 0
            while True:
                cycle_count += 1
                cycle_id = str(uuid.uuid4())
                cycle_logger = TradingContextAdapter(logger, {'run_id': run_id, 'cycle_id': cycle_id})

                cycle_logger.log_event("cycle_begin", count=cycle_count)
                run_cycle(config, saxo_client, dry_run=args.dry_run)
                cycle_logger.log_event("cycle_end")
                
                # Wait before next cycle
                sleep_time = config.CYCLE_INTERVAL_SECONDS
                cycle_logger.info(f"Sleeping for {sleep_time} seconds until next cycle")
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user (Ctrl+C)")
    
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
        return 1  # Exit with error code
    
    finally:
        logger.info("=" * 60)
        logger.info("TRADING BOT SHUTDOWN COMPLETE")
        logger.info("=" * 60)
        log_listener.stop()
    
    return 0  # Exit successfully


if __name__ == "__main__":
    sys.exit(main())
