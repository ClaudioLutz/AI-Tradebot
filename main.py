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
import json
import os
from decimal import Decimal
from pathlib import Path
from datetime import datetime, time as time_obj
from zoneinfo import ZoneInfo
from typing import Optional, Dict, List, Any

# Import project modules
from config import settings
from config.config import Config
from config.runtime_config import RuntimeConfig
from data.saxo_client import SaxoClient
from data.market_data import get_latest_quotes
from strategies.base import BaseStrategy
from strategies.registry import get_strategy
from execution.trade_executor import SaxoTradeExecutor
from execution.models import OrderIntent, BuySell, AssetType, ExecutionStatus
from execution.intent_mapper import signal_to_intent
from state.trade_counter import TradeCounter

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


def setup_logging() -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


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

def initialize_saxo_client(env_settings) -> SaxoClient:
    """Initialize Saxo client with authentication."""
    try:
        logger.info("Initializing Saxo OpenAPI client")
        logger.info(f"Environment: {getattr(env_settings, 'SAXO_ENV', 'SIM')}")
        logger.info(f"Auth mode: {getattr(env_settings, 'SAXO_AUTH_MODE', 'manual')}")
        
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


def load_configuration(saxo_client: SaxoClient) -> RuntimeConfig:
    """
    Load and validate configuration once at startup.
    Resolves instruments using the shared Saxo client.

    Returns:
        RuntimeConfig: Immutable configuration object

    Raises:
        ValueError: If required configuration is missing or invalid
    """
    try:
        logger.info("Loading configuration from environment and settings")

        # Load from config.Config (which handles resolution)
        # We temporarily initialize Config to resolve instruments
        # Note: We must ensure Config uses our shared client

        # 1. Initialize standard config handler
        config_handler = Config()

        # 2. Resolve instruments using the shared client
        logger.info("Resolving instrument UICs...")
        config_handler.resolve_instruments(client=saxo_client)

        # 3. Construct RuntimeConfig from resolved values
        runtime_config = RuntimeConfig(
            saxo_env=config_handler.environment,
            saxo_auth_mode=config_handler.auth_mode,
            account_key=settings.SAXO_ACCOUNT_KEY,
            client_key=settings.SAXO_CLIENT_KEY,
            watchlist=config_handler.watchlist,
            cycle_interval_seconds=settings.CYCLE_INTERVAL_SECONDS,
            trading_hours_mode=settings.TRADING_HOURS_MODE,
            default_quantity=settings.DEFAULT_QUANTITY,
            max_positions=settings.MAX_POSITIONS,
            max_daily_trades=settings.MAX_DAILY_TRADES,
            max_position_size=settings.MAX_POSITION_SIZE,
            max_daily_loss=settings.MAX_DAILY_LOSS,
            stop_loss_percent=settings.STOP_LOSS_PERCENT,
            take_profit_percent=settings.TAKE_PROFIT_PERCENT,
            trading_start=settings.TRADING_START,
            trading_end=settings.TRADING_END,
            timezone=settings.TIMEZONE,
            log_level=settings.LOG_LEVEL
        )

        # Log configuration summary (mask sensitive data for security)
        logger.info(f"Account Key: {mask_sensitive_data(runtime_config.account_key)}")
        logger.info(f"Client Key: {mask_sensitive_data(runtime_config.client_key)}")
        logger.info(f"Watchlist Size: {len(runtime_config.watchlist)} instruments")
        logger.info(f"Trading Hours Mode: {runtime_config.trading_hours_mode}")
        logger.info(f"Cycle Interval: {runtime_config.cycle_interval_seconds} seconds")

        return runtime_config

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)
        raise


# =============================================================================
# Story 006-003: Trading Hours Logic
# =============================================================================

def should_trade_now(config: RuntimeConfig) -> bool:
    """
    Determine if trading should occur based on TRADING_HOURS_MODE.
    
    Args:
        config: Settings object with trading hours configuration
        
    Returns:
        bool: True if trading is allowed, False otherwise
    """
    mode = config.trading_hours_mode
    
    if mode == "always":
        # CryptoFX 24/7 trading - always allow
        logger.debug("Trading hours mode: always - Trading allowed")
        return True
    
    elif mode == "fixed":
        # Check fixed trading hours
        return _check_fixed_hours(config)
    
    elif mode == "instrument":
        # Per-instrument sessions are handled in run_cycle
        logger.debug("Trading hours mode: instrument - Checks delegated to instrument level")
        return True
    
    else:
        logger.error(f"Unknown TRADING_HOURS_MODE: {mode}. Defaulting to no trading.")
        return False


def _check_fixed_hours(config: RuntimeConfig) -> bool:
    """
    Check if current time is within fixed trading hours.
    
    Args:
        config: Settings with TRADING_START, TRADING_END, TIMEZONE
        
    Returns:
        bool: True if within trading hours, False otherwise
    """
    try:
        # Get current time in configured timezone
        timezone = ZoneInfo(config.timezone)
        current_time = datetime.now(timezone)
        
        # Parse trading hours (format: "HH:MM")
        start_time = time_obj.fromisoformat(config.trading_start)
        end_time = time_obj.fromisoformat(config.trading_end)
        
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
# Story 006-005: Risk Limits & State Management
# =============================================================================

# Logic moved to state/trade_counter.py

# =============================================================================
# Story 006-004: Single Trading Cycle
# =============================================================================

def run_cycle(config: RuntimeConfig, saxo_client: SaxoClient, dry_run: bool = False):
    """
    Execute a single trading cycle.
    
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
        
        # Initialize Trade Counter
        counter = TradeCounter(Path("state/trade_counter.json"))
        daily_counts = counter.load()
        today_count = counter.get_today(daily_counts)
        logger.info(f"Daily trade count: {today_count}/{config.max_daily_trades}")

        # Gate check: Daily Limit
        if today_count >= config.max_daily_trades:
            logger.warning("Blocked: max_daily_trades reached", extra={"today_count": today_count})
            return

        # 2. Fetch market data (Quotes)
        # Using shared saxo_client to respect rate limits
        logger.info(f"Fetching market data for {len(config.watchlist)} instruments")
        market_data = get_latest_quotes(
            config.watchlist,
            include_rate_limit_info=True,
            saxo_client=saxo_client
        )

        # 3. Gatekeeping & Bar Retrieval
        from data.market_data import get_ohlc_bars, should_trade_given_market_state
        from datetime import timezone

        valid_instruments = {}
        now_utc = datetime.now(timezone.utc)

        # Determine strategy requirements
        strategy = get_strategy("moving_average")
        bars_req = strategy.bar_requirements() if strategy.requires_bars() else None

        for instrument_id, container in market_data.items():
            symbol = container.get("symbol")

            # 3.1 Check errors
            if container.get("error"):
                logger.warning(f"Skipping {symbol}: Market data error - {container['error'].get('code')}")
                continue

            if not container.get("quote"):
                logger.warning(f"Skipping {symbol}: No quote available")
                continue

            # 3.2 Check freshness
            freshness = container.get("freshness", {})
            if freshness.get("is_stale"):
                logger.warning(f"Skipping {symbol}: Quote is stale (age={freshness.get('age_seconds')}s)")
                continue

            # 3.3 Check market state (if in instrument mode)
            if config.trading_hours_mode == "instrument":
                market_state = container["quote"].get("market_state")
                if not should_trade_given_market_state(market_state):
                    logger.info(f"Skipping {symbol}: Market closed (State: {market_state})")
                    continue

            # 3.4 Fetch bars if strategy needs them
            if bars_req:
                horizon, count = bars_req
                try:
                    bars_container = get_ohlc_bars(
                        container,
                        horizon_minutes=horizon,
                        count=count,
                        mode="UpTo",
                        time=now_utc.isoformat().replace("+00:00", "Z"),
                        saxo_client=saxo_client
                    )
                    container["bars"] = bars_container.get("bars", [])
                except Exception as e:
                    logger.error(f"Failed to fetch bars for {symbol}: {e}")
                    continue

            valid_instruments[instrument_id] = container

        logger.info(f"Market data ready for {len(valid_instruments)} instruments")
        
        if not valid_instruments:
            logger.info("No valid instruments to process. Cycle complete.")
            return

        # 4. Generate signals
        logger.info("Generating trading signals")
        signals = strategy.generate_signals(valid_instruments, now_utc)
        logger.info(f"Generated {len(signals)} signals")

        # 5. Execute trades
        logger.info("Executing trades")
        
        # Initialize executor
        executor = SaxoTradeExecutor(
            saxo_client=saxo_client,
            account_key=config.account_key,
            client_key=config.client_key,
            config={
                "duplicate_buy_policy": "block",
                "allow_short_covering": True
            }
        )

        trades_executed = 0

        for instrument_id, signal in signals.items():
            action = signal.action
            if action == "HOLD":
                continue

            logger.info(f"Processing signal for {instrument_id}: {action} ({signal.reason})")

            # Check Max Daily Trades (Early Exit within loop)
            if action == "BUY" and (today_count + trades_executed) >= config.max_daily_trades:
                 logger.warning("Skipping BUY: max_daily_trades limit hit during cycle")
                 continue

            # Map to Intent
            intent = signal_to_intent(
                signal,
                valid_instruments[instrument_id],
                config,
                executor.position_manager
            )

            if not intent:
                logger.warning(f"Could not map signal to intent for {instrument_id} (e.g. invalid position lookup)")
                continue

            # Execute
            result = executor.execute(intent, dry_run=dry_run)

            # Update counter on success
            if result.status in [ExecutionStatus.SUCCESS, ExecutionStatus.DRY_RUN]:
                # Increment for BUYs (and potentially SELLs if that's the policy)
                # Assuming simple trade count
                trades_executed += 1
                counter.increment_today(daily_counts, 1)

            logger.info(f"Execution result for {instrument_id}: {result.status.value} - {result.error_message or 'Success'}")

            # JSONL Logging
            log_execution_jsonl(instrument_id, signal, intent, result)

        # Persist counter updates
        if trades_executed > 0:
            counter.persist_atomic(daily_counts)
            logger.info(f"Persisted {trades_executed} new trades to counter")

        logger.info("Cycle complete")
        
    except Exception as e:
        logger.error(f"Error in trading cycle: {e}", exc_info=True)


def log_execution_jsonl(instrument_id: str, signal: Any, intent: OrderIntent, result: Any):
    """Log execution details to JSONL file for auditable history."""
    log_file = "logs/executions.jsonl"

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "instrument_id": instrument_id,
        "signal": {
            "action": signal.action,
            "reason": signal.reason,
            "decision_time": signal.decision_time
        },
        "intent": {
            "action": intent.buy_sell.value,
            "amount": float(intent.amount),
            "asset_type": intent.asset_type.value,
            "uic": intent.uic,
            "external_reference": intent.external_reference
        },
        "result": {
            "status": result.status.value,
            "order_id": result.order_id,
            "error_message": result.error_message,
            "request_id": result.request_id
        }
    }

    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write execution log: {e}")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main trading bot execution."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    setup_logging()
    
    # Log startup banner
    log_startup_banner(args)
    
    try:
        # 1. Initialize Saxo client (Early initialization for instrument resolution)
        saxo_client = initialize_saxo_client(settings)
        
        # 2. Load configuration (Resolves instruments using client)
        config = load_configuration(saxo_client)
        
        # 3. Run trading logic
        if args.single_cycle:
            logger.info("Running single cycle mode")
            run_cycle(config, saxo_client, dry_run=args.dry_run)
        else:
            logger.info("Running continuous loop mode")
            cycle_count = 0
            while True:
                cycle_count += 1
                logger.info(f"Cycle #{cycle_count}")
                run_cycle(config, saxo_client, dry_run=args.dry_run)
                
                # Wait before next cycle
                sleep_time = config.cycle_interval_seconds
                logger.info(f"Sleeping for {sleep_time} seconds until next cycle")
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
    
    return 0  # Exit successfully


if __name__ == "__main__":
    sys.exit(main())
