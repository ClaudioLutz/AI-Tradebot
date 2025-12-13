# Epic 006: Main Orchestration Script (Multi-Asset)

## Epic Overview
Create the `main.py` orchestrator script that ties together all modules into a cohesive trading bot workflow with support for multi-asset trading hours. This script serves as the entry point and coordinates the full cycle: configuration → data retrieval → signal generation → risk checks → trade execution.

## Business Value
- Provides single entry point to run the trading bot
- Orchestrates complete trading workflow end-to-end
- Supports multi-asset trading (equities + CryptoFX with different hours)
- Enables automated trading cycles with config-driven hours logic
- Simplifies bot operation for users
- Creates foundation for scheduled/continuous operation

## Scope

### In Scope
- `main.py` script creation
- Configuration loading and initialization (load once, immutable)
- Saxo client initialization with OAuth/manual token
- Module integration (`config`, `data/market_data`, `strategies`, `execution`)
- Complete trading cycle implementation:
  1. Load config
  2. Init Saxo client
  3. Fetch market data
  4. Run strategy
  5. Risk checks + precheck
  6. Place/skip orders
  7. Persist cycle summary
- **Trading hours logic** (`TRADING_HOURS_MODE` from config):
  - `always`: No market hours check (e.g., CryptoFX 24/7)
  - `fixed`: Check fixed hours (e.g., 09:30-16:00 for US equities)
  - `instrument`: Per-instrument trading sessions (future enhancement)
- Graceful error handling and recovery
- Startup and shutdown procedures
- Command-line argument support (`--dry-run`, `--single-cycle`)

### Out of Scope
- Advanced scheduling logic (covered in Epic 007)
- Complex workflow orchestration (e.g., DAG execution)
- Multi-strategy parallel execution
- Distributed computing
- Web interface or GUI
- Real-time event-driven architecture

## Technical Considerations

### Configuration-Driven Design
- Load config once at startup (immutable during runtime)
- Config provides: watchlist (with {asset_type, uic, symbol}), AccountKey, auth mode, trading hours mode, DRY_RUN flag

### Trading Hours Logic
```python
def should_trade_now(config) -> bool:
    """Determine if trading should occur based on TRADING_HOURS_MODE."""
    mode = config.TRADING_HOURS_MODE
    
    if mode == "always":
        return True  # CryptoFX, always tradeable
    
    elif mode == "fixed":
        # Check fixed hours (e.g., US market 09:30-16:00 ET)
        current_time = datetime.now(config.TIMEZONE)
        start = config.TRADING_START  # e.g., "09:30"
        end = config.TRADING_END      # e.g., "16:00"
        # Parse and compare times
        return is_within_hours(current_time, start, end)
    
    elif mode == "instrument":
        # Future: check per-instrument trading sessions
        # For now, fall back to "always" or raise NotImplementedError
        raise NotImplementedError("Per-instrument hours not yet implemented")
    
    else:
        logger.error(f"Unknown TRADING_HOURS_MODE: {mode}")
        return False
```

### Cycle Phases
1. **Config Load** (once at startup)
2. **Client Init** (Saxo client with OAuth or manual token)
3. **Market Data Fetch** (normalized by instrument_id)
4. **Strategy Execution** (pure function over market data)
5. **Risk Checks** (optional: position limits, exposure checks)
6. **Precheck Orders** (Saxo precheck for cost estimation)
7. **Order Placement** (if not DRY_RUN and precheck passes)
8. **Cycle Summary** (log results, sleep until next cycle)

## Dependencies
- **Epic 001-2:** Saxo Bank Migration (client initialization)
- **Epic 002:** Configuration Module (config loading, watchlist)
- **Epic 003:** Market Data Retrieval (normalized data feed)
- **Epic 004:** Trading Strategy System (signal generation)
- **Epic 005:** Trade Execution Module (precheck + placement)

## Success Criteria
- [ ] `main.py` script created and executable
- [ ] All modules properly imported and initialized
- [ ] Config loaded once at startup (immutable)
- [ ] Saxo client initialized with OAuth or manual token
- [ ] Complete trading cycle runs successfully
- [ ] Data fetching → signal generation → execution flow works
- [ ] Trading hours logic implemented (always/fixed modes)
- [ ] Exceptions are caught and logged without crashing
- [ ] Graceful shutdown on Ctrl+C
- [ ] Supports `--dry-run` and `--single-cycle` command-line args

## Acceptance Criteria
1. Script runs without errors when executed via `python main.py`
2. Fetches data for all instruments in watchlist (keyed by instrument_id)
3. Generates signals using configured strategy
4. Respects DRY_RUN flag (precheck only, no placement)
5. Executes trades based on signals (if not DRY_RUN)
6. Logs all major steps and outcomes with Saxo-specific fields
7. Respects trading hours based on `TRADING_HOURS_MODE`
8. Handles API errors without crashing (retries or skips cycle)
9. Cleans up resources on exit (close connections, flush logs)
10. Supports both single-cycle and continuous loop operation

## Related Documents
- `main.py` (to be enhanced)
- [Epic 002: Configuration Module](./epic-002-configuration-module.md)
- [Epic 005: Trade Execution Module](./epic-005-trade-execution-module.md)

## Main Script Structure

```python
import time
import logging
import argparse
from datetime import datetime
from config.settings import Settings
from data.saxo_client import SaxoClient
from data.market_data import get_latest_quotes, get_ohlc_bars
from strategies.simple_strategy import generate_signals
from execution.trade_executor import execute_signal, get_positions

logger = logging.getLogger(__name__)


def should_trade_now(config: Settings) -> bool:
    """Check if trading is allowed based on TRADING_HOURS_MODE."""
    mode = config.TRADING_HOURS_MODE
    
    if mode == "always":
        return True
    elif mode == "fixed":
        # Check fixed trading hours
        return is_within_trading_hours(config)
    else:
        logger.warning(f"Unknown TRADING_HOURS_MODE: {mode}, defaulting to False")
        return False


def run_cycle(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """Execute a single trading cycle."""
    logger.info("=" * 60)
    logger.info("Starting trading cycle")
    logger.info(f"Mode: {'DRY_RUN' if dry_run else 'SIM'}")
    
    try:
        # 1. Check trading hours
        if not should_trade_now(config):
            logger.info("Outside trading hours, skipping cycle")
            return
        
        # 2. Fetch market data
        logger.info(f"Fetching market data for {len(config.WATCHLIST)} instruments")
        market_data = get_latest_quotes(config.WATCHLIST)
        logger.info(f"Fetched data for {len(market_data)} instruments")
        
        # Optional: Fetch OHLC bars if strategy needs them
        # for instrument in config.WATCHLIST:
        #     bars = get_ohlc_bars(instrument, horizon=60, interval="1m")
        #     market_data[bars["instrument_id"]]["bars"] = bars["bars"]
        
        # 3. Generate signals
        logger.info("Generating trading signals")
        signals = generate_signals(market_data)
        logger.info(f"Signals: {signals}")
        
        # 4. Execute signals
        account_key = config.SAXO_ACCOUNT_KEY
        for instrument_id, signal in signals.items():
            if signal == "HOLD":
                continue
            
            # Find instrument data
            instrument_data = market_data.get(instrument_id)
            if not instrument_data:
                logger.warning(f"No data for {instrument_id}, skipping")
                continue
            
            # Execute signal
            instrument = {
                "instrument_id": instrument_data["instrument_id"],
                "asset_type": instrument_data["asset_type"],
                "uic": instrument_data["uic"],
                "symbol": instrument_data["symbol"]
            }
            
            success = execute_signal(
                instrument=instrument,
                signal=signal,
                account_key=account_key,
                amount=config.DEFAULT_QUANTITY,
                dry_run=dry_run
            )
            
            if success:
                logger.info(f"Successfully executed {signal} for {instrument_id}")
            else:
                logger.error(f"Failed to execute {signal} for {instrument_id}")
        
        logger.info("Cycle complete")
    
    except Exception as e:
        logger.error(f"Error in trading cycle: {e}", exc_info=True)


def main():
    """Main trading bot execution."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Trading Bot")
    parser.add_argument("--dry-run", action="store_true", help="Precheck only, no orders placed")
    parser.add_argument("--single-cycle", action="store_true", help="Run once then exit")
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    logger.info("Trading Bot Starting")
    logger.info(f"Mode: {'DRY_RUN' if args.dry_run else 'SIM'}")
    logger.info(f"Execution: {'Single Cycle' if args.single_cycle else 'Continuous Loop'}")
    
    try:
        # 1. Load configuration (once at startup, immutable)
        logger.info("Loading configuration")
        config = Settings()
        logger.info(f"Loaded {len(config.WATCHLIST)} instruments in watchlist")
        logger.info(f"Trading hours mode: {config.TRADING_HOURS_MODE}")
        
        # 2. Initialize Saxo client
        logger.info("Initializing Saxo client")
        saxo_client = SaxoClient(config)
        logger.info("Saxo client initialized")
        
        # 3. Run trading loop
        if args.single_cycle:
            run_cycle(config, saxo_client, dry_run=args.dry_run)
        else:
            while True:
                run_cycle(config, saxo_client, dry_run=args.dry_run)
                
                # Wait before next cycle
                sleep_time = config.CYCLE_INTERVAL_SECONDS
                logger.info(f"Sleeping for {sleep_time} seconds until next cycle")
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user (Ctrl+C)")
    
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
    
    finally:
        logger.info("Trading bot shutting down")


if __name__ == "__main__":
    main()
```

## Workflow Phases

### Phase 1: Initialization (Once)
- Parse command-line arguments (`--dry-run`, `--single-cycle`)
- Setup logging with structured format
- Load configuration from `config/settings.py` (load once, immutable)
- Initialize Saxo client with OAuth or manual token
- Log startup summary (mode, watchlist size, trading hours)

### Phase 2: Pre-Cycle Check
- Check trading hours based on `TRADING_HOURS_MODE`
- Skip cycle if outside allowed hours (log reason)
- For CryptoFX (`mode="always"`), always proceed

### Phase 3: Market Data Retrieval
- Call `get_latest_quotes(instruments)` with watchlist
- Receive normalized market data keyed by `instrument_id`
- Optionally fetch OHLC bars if strategy requires indicators
- Log data freshness and any missing instruments

### Phase 4: Signal Generation
- Pass normalized market data to strategy module
- Receive signals dict: `{instrument_id: "BUY"|"SELL"|"HOLD"}`
- Log all signals for audit trail

### Phase 5: Risk Checks (Optional)
- Check position limits (e.g., max 5 open positions)
- Check exposure limits (e.g., max 50% of portfolio in one asset class)
- Check daily loss limit (halt if exceeded)
- Filter signals that violate risk rules

### Phase 6: Trade Execution
- Iterate through signals (skip "HOLD")
- For each BUY/SELL signal:
  1. Extract instrument data from market_data
  2. Call `execute_signal()` with precheck-first workflow
  3. Log execution result (success/failure)
- Execution module handles:
  - Position checking
  - Order prechecking
  - DRY_RUN vs SIM branching
  - Error handling and logging

### Phase 7: Cycle Summary
- Log cycle completion time
- Log total signals, executed orders, errors
- Sleep for `CYCLE_INTERVAL_SECONDS` before next cycle
- Handle graceful shutdown on interrupt

## Error Handling Strategy

### Recoverable Errors (Log + Continue)
- Market data fetch fails for one instrument → skip that instrument
- Precheck fails for one order → skip that order, continue with others
- HTTP 429 rate limit → backoff and retry
- HTTP 500 server error → log, skip cycle, retry next cycle

### Non-Recoverable Errors (Log + Exit)
- Config file missing or invalid → exit with error
- Auth failure (token expired, can't refresh) → exit, user must re-auth
- Critical exception in main loop → log full traceback, exit

### Logging Template
```python
logger.error(
    f"Cycle error: {error_type}, "
    f"Instrument={instrument_id}, "
    f"Phase={phase}, "
    f"Message={error_message}"
)
```

## Trading Hours Modes

### Mode: `always`
- No time checks
- Always proceed with trading
- Use for: CryptoFX (24/7 trading)

### Mode: `fixed`
- Check current time against fixed hours from config
- Example: `TRADING_START="09:30"`, `TRADING_END="16:00"`, `TIMEZONE="America/New_York"`
- Use for: US equities, Eur equities with fixed hours

### Mode: `instrument` (Future)
- Query Saxo for each instrument's trading session
- Check if instrument is currently tradeable
- Use for: Mixed portfolios (equities + futures with varying hours)

## Multi-Asset Considerations

### Handling Mixed Asset Types
- Config may contain both Stock (market hours) and FxSpot (24/7)
- Options:
  1. Use `mode="always"` and trade all instruments regardless of time
  2. Use `mode="instrument"` (future) to check per-instrument
  3. Split watchlist into time-zone groups (advanced)

### CryptoFX 24/7 Trading
- CryptoFX instruments (BTCUSD, ETHUSD) trade continuously
- Set `TRADING_HOURS_MODE="always"` if watchlist is crypto-only
- Or use mixed mode with per-instrument checks

## Command-Line Arguments

### `--dry-run`
- Enables DRY_RUN mode
- All orders are prechecked but NOT placed
- Use for: Testing strategy logic, cost estimation

### `--single-cycle`
- Run one cycle then exit
- Use for: Manual testing, cron scheduling

### Example Usage
```bash
# Continuous loop in SIM mode
python main.py

# Single cycle in DRY_RUN mode
python main.py --dry-run --single-cycle

# Continuous loop in DRY_RUN mode
python main.py --dry-run
```

## Notes
- Start with simple sequential execution (no parallelism)
- Make cycle timing configurable via `CYCLE_INTERVAL_SECONDS` in config
- Document command-line usage in script docstring
- Add startup banner with ASCII art (optional, fun touch)
- Log cycle duration for performance monitoring
- Persist cycle summary to metrics file (future: dashboards)

## Future Enhancements
- Parallel data fetching for multiple instruments
- Per-instrument trading sessions (`mode="instrument"`)
- Health check endpoint for monitoring
- Metrics export (Prometheus format)
- Dynamic strategy switching based on market regime
- Emergency stop mechanism (e.g., stop file, signal handler)
