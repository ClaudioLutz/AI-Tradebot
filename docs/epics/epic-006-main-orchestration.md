# Epic 006: Main Orchestration Script

## Epic Overview
Create the main.py orchestrator script that ties together all modules into a cohesive trading bot workflow. This script serves as the entry point and coordinates the data retrieval, signal generation, and trade execution cycle.

## Business Value
- Provides single entry point to run the trading bot
- Orchestrates complete trading workflow end-to-end
- Enables automated trading cycles
- Simplifies bot operation for non-technical users
- Creates foundation for scheduled/continuous operation

## Scope

### In Scope
- main.py script creation
- Configuration loading and initialization
- Module integration (data_fetcher, strategy, trader)
- Complete trading cycle implementation (data → signal → execute)
- Basic execution loop with timing
- Command-line argument support (optional)
- Market hours awareness (check if market is open)
- Graceful error handling and recovery
- Startup and shutdown procedures

### Out of Scope
- Advanced scheduling logic (covered in Epic 007)
- Complex workflow orchestration
- Multi-strategy parallel execution
- Distributed computing
- Web interface or GUI
- Real-time event-driven architecture

## Technical Considerations
- Import all required modules (config, data_fetcher, strategy, trader)
- Initialize Alpaca API client with credentials from config
- Implement single cycle: fetch data → generate signals → execute trades
- Add main loop with configurable delay (e.g., 60 seconds)
- Check market status using api.get_clock() before trading
- Handle exceptions to prevent crashes
- Log each cycle's activity
- Support manual single-run or continuous loop operation
- Clean exit on keyboard interrupt (Ctrl+C)

## Dependencies
- Epic 001: Initial Setup and Environment Configuration
- Epic 002: Configuration Module Development
- Epic 003: Market Data Retrieval Module
- Epic 004: Trading Strategy System
- Epic 005: Trade Execution Module

## Success Criteria
- [ ] main.py script created and executable
- [ ] All modules properly imported and initialized
- [ ] Complete trading cycle runs successfully
- [ ] Data fetching → signal generation → trade execution flow works
- [ ] Loop continues with appropriate delays
- [ ] Market hours check prevents trading when closed
- [ ] Exceptions are caught and logged
- [ ] Graceful shutdown on Ctrl+C
- [ ] Can run in both single-cycle and loop modes

## Acceptance Criteria
1. Script runs without errors when executed via `python main.py`
2. Fetches data for all symbols in watchlist
3. Generates signals using configured strategy
4. Executes trades based on signals
5. Logs all major steps and outcomes
6. Checks if market is open before trading stocks
7. Continues running in loop until manually stopped
8. Handles API errors without crashing
9. Cleans up resources on exit

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- main.py (to be created)

## Main Script Structure
```python
import time
import logging
from config.config import API_KEY, API_SECRET, BASE_URL, WATCHLIST
import data_fetcher
from strategies import example_strategy
import trader
import alpaca_trade_api as tradeapi

def main():
    """Main trading bot execution loop."""
    # Initialize API client
    api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        while True:
            # Check if market is open
            clock = api.get_clock()
            if not clock.is_open:
                logging.info("Market is closed. Waiting...")
                time.sleep(60)
                continue
            
            # 1. Fetch market data
            market_data = data_fetcher.get_latest_data(WATCHLIST)
            logging.info(f"Fetched data for {len(market_data)} symbols")
            
            # 2. Generate signals
            signals = example_strategy.generate_signals(market_data)
            logging.info(f"Generated signals: {signals}")
            
            # 3. Execute trades
            for symbol, signal in signals.items():
                trader.execute_signal(symbol, signal)
            
            # 4. Wait before next cycle
            logging.info("Cycle complete. Waiting 60 seconds...")
            time.sleep(60)
            
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()
```

## Workflow Steps
1. **Initialization**
   - Load configuration from config module
   - Initialize Alpaca API client
   - Setup logging
   - Log startup message with configuration summary

2. **Pre-Cycle Check**
   - Check if market is open (for stocks)
   - Skip cycle if closed (or handle crypto separately)
   - Log market status

3. **Data Retrieval**
   - Call data_fetcher.get_latest_data(WATCHLIST)
   - Validate data received
   - Log fetched prices

4. **Signal Generation**
   - Pass market data to strategy module
   - Receive trading signals
   - Log signals for each symbol

5. **Trade Execution**
   - Iterate through signals
   - Call trader.execute_signal() for each
   - Log execution results

6. **Cycle Completion**
   - Log cycle summary
   - Wait for next cycle (configurable delay)
   - Handle graceful shutdown on interrupt

## Error Handling Strategy
- Wrap main loop in try-except block
- Catch and log all exceptions
- Continue to next cycle on recoverable errors
- Exit gracefully on critical failures
- Log stack traces for debugging

## Notes
- Start with simple sequential execution
- Add parallel processing in future if needed
- Make cycle timing configurable via config.py
- Consider separate handling for 24/7 crypto vs market-hours stocks
- Document command-line usage in script docstring
- Add --dry-run flag support for testing
