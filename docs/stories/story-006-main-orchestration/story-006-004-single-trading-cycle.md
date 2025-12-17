# Story 006-004: Single Trading Cycle Implementation

**Epic:** [Epic 006: Main Orchestration Script](../../epics/epic-006-main-orchestration.md)  
**Status:** Not Started  
**Effort:** 8 Story Points  
**Priority:** High

## User Story
As a **trading bot**, I want **a complete trading cycle implementation** so that I can **orchestrate data fetching, signal generation, and trade execution in a cohesive workflow**.

## Acceptance Criteria
- [ ] `run_cycle()` function implemented with all phases
- [ ] Trading hours check performed before proceeding
- [ ] Market data fetched for all watchlist instruments
- [ ] Signals generated using configured strategy
- [ ] Signals executed via trade execution module
- [ ] Each phase logs progress and results
- [ ] Errors in one instrument don't crash entire cycle
- [ ] Cycle summary logged at completion
- [ ] DRY_RUN flag respected (precheck only, no placement)

## Technical Details

### Complete Trading Cycle Function
```python
def run_cycle(config: Settings, saxo_client: SaxoClient, dry_run: bool = False):
    """
    Execute a single trading cycle.
    
    Phases:
    1. Check trading hours
    2. Fetch market data for watchlist
    3. Generate trading signals
    4. Execute signals (with precheck)
    5. Log cycle summary
    
    Args:
        config: Settings instance (immutable)
        saxo_client: Initialized Saxo client
        dry_run: If True, precheck only (no order placement)
    """
    logger = logging.getLogger(__name__)
    
    # Cycle metrics
    cycle_start = datetime.now()
    signals_generated = 0
    orders_executed = 0
    orders_failed = 0
    instruments_fetched = 0
    
    logger.info("=" * 60)
    logger.info("Starting trading cycle")
    logger.info(f"Mode: {'DRY_RUN' if dry_run else 'SIM'}")
    logger.info(f"Cycle Start: {cycle_start.isoformat()}")
    logger.info("=" * 60)
    
    try:
        # Phase 1: Check trading hours
        if not should_trade_now(config, logger):
            logger.info("Outside trading hours, skipping cycle")
            return
        
        # Phase 2: Fetch market data
        logger.info(f"Fetching market data for {len(config.WATCHLIST)} instruments")
        market_data = fetch_market_data(config.WATCHLIST, logger)
        instruments_fetched = len(market_data)
        logger.info(f"Fetched data for {instruments_fetched} instruments")
        
        if not market_data:
            logger.warning("No market data available, skipping cycle")
            return
        
        # Phase 3: Generate signals
        logger.info("Generating trading signals")
        signals = generate_trading_signals(market_data, config, logger)
        signals_generated = sum(1 for sig in signals.values() if sig != "HOLD")
        logger.info(f"Signals generated: {signals_generated} actionable (non-HOLD)")
        logger.info(f"Signal summary: {signals}")
        
        # Phase 4: Execute signals
        if signals_generated > 0:
            logger.info(f"Executing {signals_generated} signals")
            execution_results = execute_trading_signals(
                signals, 
                market_data, 
                config, 
                dry_run, 
                logger
            )
            orders_executed = execution_results["success"]
            orders_failed = execution_results["failed"]
        else:
            logger.info("No actionable signals (all HOLD), nothing to execute")
        
        # Phase 5: Cycle summary
        cycle_end = datetime.now()
        cycle_duration = (cycle_end - cycle_start).total_seconds()
        
        logger.info("=" * 60)
        logger.info("Cycle Complete")
        logger.info(f"Duration: {cycle_duration:.2f} seconds")
        logger.info(f"Instruments Fetched: {instruments_fetched}/{len(config.WATCHLIST)}")
        logger.info(f"Signals Generated: {signals_generated}")
        logger.info(f"Orders Executed: {orders_executed}")
        logger.info(f"Orders Failed: {orders_failed}")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Error in trading cycle: {e}", exc_info=True)
        logger.error("Cycle aborted due to error")
```

### Phase 2: Market Data Fetching
```python
def fetch_market_data(watchlist: list, logger) -> dict:
    """
    Fetch market data for all instruments in watchlist.
    
    Args:
        watchlist: List of instrument dicts with {symbol, uic, asset_type}
        logger: Logger instance
        
    Returns:
        dict: Market data keyed by instrument_id
    """
    from data.market_data import get_latest_quotes
    
    try:
        market_data = get_latest_quotes(watchlist)
        
        # Log any missing instruments
        fetched_ids = set(market_data.keys())
        expected_ids = set(
            f"{inst['asset_type']}/{inst['uic']}" 
            for inst in watchlist
        )
        missing_ids = expected_ids - fetched_ids
        
        if missing_ids:
            logger.warning(
                f"Failed to fetch data for {len(missing_ids)} instruments: "
                f"{missing_ids}"
            )
        
        return market_data
    
    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}", exc_info=True)
        return {}
```

### Phase 3: Signal Generation
```python
def generate_trading_signals(market_data: dict, config: Settings, logger) -> dict:
    """
    Generate trading signals for all instruments.
    
    Args:
        market_data: Normalized market data dict
        config: Settings instance
        logger: Logger instance
        
    Returns:
        dict: Signals keyed by instrument_id {instrument_id: "BUY"|"SELL"|"HOLD"}
    """
    try:
        # Use configured strategy (or default)
        strategy_name = getattr(config, 'STRATEGY_NAME', 'simple_strategy')
        
        if strategy_name == 'simple_strategy':
            from strategies.simple_strategy import generate_signals
            signals = generate_signals(market_data)
        else:
            logger.error(f"Unknown strategy: {strategy_name}")
            return {}
        
        return signals
    
    except Exception as e:
        logger.error(f"Failed to generate signals: {e}", exc_info=True)
        return {}
```

### Phase 4: Signal Execution
```python
def execute_trading_signals(
    signals: dict, 
    market_data: dict, 
    config: Settings, 
    dry_run: bool, 
    logger
) -> dict:
    """
    Execute trading signals for all actionable instruments.
    
    Args:
        signals: Dict of signals {instrument_id: "BUY"|"SELL"|"HOLD"}
        market_data: Normalized market data dict
        config: Settings instance
        dry_run: If True, precheck only
        logger: Logger instance
        
    Returns:
        dict: Execution summary with success/failed counts
    """
    from execution.trade_executor import execute_signal
    
    success_count = 0
    failed_count = 0
    
    for instrument_id, signal in signals.items():
        if signal == "HOLD":
            continue
        
        try:
            # Get instrument data
            instrument_data = market_data.get(instrument_id)
            if not instrument_data:
                logger.warning(f"No data for {instrument_id}, skipping")
                failed_count += 1
                continue
            
            # Build instrument dict for execution
            instrument = {
                "instrument_id": instrument_data["instrument_id"],
                "asset_type": instrument_data["asset_type"],
                "uic": instrument_data["uic"],
                "symbol": instrument_data["symbol"]
            }
            
            # Execute signal
            logger.info(
                f"Executing {signal} for {instrument['symbol']} "
                f"({instrument_id})"
            )
            
            success = execute_signal(
                instrument=instrument,
                signal=signal,
                account_key=config.SAXO_ACCOUNT_KEY,
                amount=getattr(config, 'DEFAULT_QUANTITY', 100),
                dry_run=dry_run
            )
            
            if success:
                logger.info(f"Successfully executed {signal} for {instrument_id}")
                success_count += 1
            else:
                logger.error(f"Failed to execute {signal} for {instrument_id}")
                failed_count += 1
        
        except Exception as e:
            logger.error(
                f"Error executing {signal} for {instrument_id}: {e}", 
                exc_info=True
            )
            failed_count += 1
    
    return {
        "success": success_count,
        "failed": failed_count
    }
```

## Error Handling Strategy

### Instrument-Level Errors (Recoverable)
- One instrument fails data fetch → Log warning, continue with others
- One signal fails execution → Log error, continue with others
- Precheck fails for one order → Skip that order, continue

### Cycle-Level Errors (Abort Cycle)
- All instruments fail data fetch → Abort cycle, return early
- Signal generation crashes → Abort cycle, log error
- Critical exception in cycle logic → Abort cycle, propagate error

### Logging Pattern
```python
try:
    # Critical operation
    result = critical_function()
except RecoverableError as e:
    logger.warning(f"Recoverable error: {e}. Continuing...")
    # Continue execution
except CriticalError as e:
    logger.error(f"Critical error: {e}. Aborting cycle.", exc_info=True)
    raise  # Propagate to main loop
```

## Integration with Main Loop
```python
def main():
    """Main trading bot execution."""
    args = parse_arguments()
    setup_logging()
    logger = logging.getLogger(__name__)
    log_startup_banner(args, logger)
    
    try:
        config = load_configuration(logger)
        saxo_client = initialize_saxo_client(config, logger)
        
        if args.single_cycle:
            # Run once and exit
            run_cycle(config, saxo_client, dry_run=args.dry_run)
        else:
            # Continuous loop
            while True:
                run_cycle(config, saxo_client, dry_run=args.dry_run)
                
                sleep_time = config.CYCLE_INTERVAL_SECONDS
                logger.info(f"Sleeping for {sleep_time} seconds until next cycle")
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
    finally:
        logger.info("Trading bot shutting down")
```

## Implementation Steps
1. Create `run_cycle()` function skeleton with logging
2. Integrate `should_trade_now()` check (Phase 1)
3. Implement `fetch_market_data()` wrapper (Phase 2)
4. Implement `generate_trading_signals()` wrapper (Phase 3)
5. Implement `execute_trading_signals()` with iteration (Phase 4)
6. Add cycle metrics tracking (duration, counts)
7. Add comprehensive logging at each phase
8. Add error handling (instrument-level vs cycle-level)
9. Test with mock data
10. Test with real API in DRY_RUN mode
11. Test error scenarios (missing data, API failures)

## Dependencies
- Epic 003: Market Data Retrieval (`data.market_data.get_latest_quotes`)
- Epic 004: Trading Strategy System (`strategies.simple_strategy.generate_signals`)
- Epic 005: Trade Execution Module (`execution.trade_executor.execute_signal`)

## Testing Strategy
```python
# tests/test_trading_cycle.py
import unittest
from unittest.mock import Mock, patch, MagicMock

class TestTradingCycle(unittest.TestCase):
    """Test trading cycle orchestration."""
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    @patch('main.generate_trading_signals')
    @patch('main.execute_trading_signals')
    def test_complete_cycle(self, mock_execute, mock_signals, mock_data, mock_hours):
        """Test complete cycle with all phases."""
        # Setup mocks
        mock_hours.return_value = True
        mock_data.return_value = {
            "FxSpot/12345": {"symbol": "BTCUSD", "bid": 50000, "ask": 50010}
        }
        mock_signals.return_value = {"FxSpot/12345": "BUY"}
        mock_execute.return_value = {"success": 1, "failed": 0}
        
        config = Mock()
        config.WATCHLIST = [{"symbol": "BTCUSD", "uic": 12345, "asset_type": "FxSpot"}]
        config.SAXO_ACCOUNT_KEY = "ACC123"
        
        saxo_client = Mock()
        
        # Run cycle
        run_cycle(config, saxo_client, dry_run=False)
        
        # Verify all phases called
        mock_hours.assert_called_once()
        mock_data.assert_called_once()
        mock_signals.assert_called_once()
        mock_execute.assert_called_once()
    
    @patch('main.should_trade_now')
    def test_cycle_skips_outside_hours(self, mock_hours):
        """Test cycle skips when outside trading hours."""
        mock_hours.return_value = False
        
        config = Mock()
        saxo_client = Mock()
        
        run_cycle(config, saxo_client, dry_run=False)
        
        # Only hours check should be called
        mock_hours.assert_called_once()
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    def test_cycle_handles_no_data(self, mock_data, mock_hours):
        """Test cycle handles empty market data."""
        mock_hours.return_value = True
        mock_data.return_value = {}  # No data
        
        config = Mock()
        config.WATCHLIST = []
        saxo_client = Mock()
        
        # Should not crash
        run_cycle(config, saxo_client, dry_run=False)
    
    @patch('main.should_trade_now')
    @patch('main.fetch_market_data')
    @patch('main.generate_trading_signals')
    def test_cycle_handles_all_hold_signals(self, mock_signals, mock_data, mock_hours):
        """Test cycle handles all HOLD signals."""
        mock_hours.return_value = True
        mock_data.return_value = {"FxSpot/12345": {}}
        mock_signals.return_value = {"FxSpot/12345": "HOLD"}
        
        config = Mock()
        config.WATCHLIST = [{}]
        saxo_client = Mock()
        
        # Should not attempt execution
        run_cycle(config, saxo_client, dry_run=False)
```

## Validation Checklist
- [ ] Cycle runs successfully with valid data
- [ ] Trading hours check prevents execution outside hours
- [ ] Market data fetched for all watchlist instruments
- [ ] Missing instruments logged but don't crash cycle
- [ ] Signals generated from market data
- [ ] All HOLD signals skip execution
- [ ] BUY/SELL signals trigger execution
- [ ] DRY_RUN mode prevents order placement
- [ ] SIM mode places orders
- [ ] Cycle summary logs all metrics
- [ ] Errors in one instrument don't affect others
- [ ] Critical errors abort cycle cleanly

## Related Stories
- [Story 006-002: Configuration and Client Initialization](./story-006-002-configuration-client-initialization.md)
- [Story 006-003: Trading Hours Logic](./story-006-003-trading-hours-logic.md)
- [Story 006-005: Main Loop and Continuous Operation](./story-006-005-main-loop-continuous-operation.md)
- [Story 003-002: Batch Quote Retrieval](../story-003-market-data-retrieval/story-003-002-batch-quote-retrieval-infoprices-list.md)
- [Story 004-001: Strategy Interface and Signal Schema](../story-004-trading-strategy/story-004-001-strategy-interface-and-signal-schema.md)
- [Story 005-001: Execution Interface and Order Intent Schema](../story-005-trade-execution-module/story-005-001-execution-interface-and-order-intent-schema.md)

## Notes
- Keep cycle phases clearly separated for maintainability
- Log extensively for audit trail and debugging
- Fail gracefully - one instrument error shouldn't crash bot
- Metrics tracking enables performance monitoring
- Consider adding cycle ID for traceability in logs
- Future: Add cycle results to metrics database
- Future: Add health check endpoint that returns last cycle status
- DRY_RUN is critical for testing without risking real money
