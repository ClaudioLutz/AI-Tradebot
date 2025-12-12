# Epic 003: Market Data Retrieval Module

## Epic Overview
Develop the data_fetcher.py module to handle all interactions with Alpaca's Market Data API. This module provides real-time price data for stocks and cryptocurrencies in the watchlist, abstracting API calls from other components.

## Business Value
- Provides reliable real-time market data feed
- Abstracts API complexity from strategy logic
- Handles rate limiting and error recovery
- Supports both stock and crypto asset classes
- Enables data-driven trading decisions

## Scope

### In Scope
- data_fetcher.py module creation
- Alpaca REST API client initialization
- Function to fetch latest bars for multiple symbols
- Support for stocks and crypto (BTC/USD, ETH/USD)
- Data parsing into convenient format (dict/DataFrame)
- Error handling and retry logic
- Rate limit management (200 requests/minute)
- Basic logging for data retrieval operations

### Out of Scope
- WebSocket streaming (real-time updates)
- Historical data backtesting
- Data storage/caching to database
- Custom technical indicators calculation
- Multiple timeframe support (focus on 1-minute bars initially)

## Technical Considerations
- Use alpaca-trade-api REST client with v2 API
- Fetch data using api.get_bars() for multiple symbols
- Default timeframe: 1Min bars
- Parse response into Python dict mapping symbol -> price data
- Handle API rate limits (200 req/min) with retry logic
- Catch and log connection errors, timeouts, invalid symbols
- Support polling approach (fetch on demand) initially
- Return consistent data structure for strategy consumption

## Dependencies
- Epic 001: Initial Setup and Environment Configuration
- Epic 002: Configuration Module Development

## Success Criteria
- [ ] data_fetcher.py module created
- [ ] Alpaca REST client properly initialized
- [ ] get_latest_data() function fetches multiple symbols
- [ ] Function returns data in consistent format (dict or DataFrame)
- [ ] Stocks and crypto symbols both supported
- [ ] Error handling prevents crashes on API failures
- [ ] Rate limiting respected with appropriate delays
- [ ] Module is testable with mock data

## Acceptance Criteria
1. Can fetch latest 1-minute bar for all watchlist symbols
2. Returns price, volume, and timestamp for each symbol
3. Handles network errors gracefully without crashing
4. Logs all API requests and errors
5. Works with both stock tickers (AAPL) and crypto pairs (BTC/USD)
6. Respects Alpaca API rate limits
7. Invalid symbols return clear error messages

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- data_fetcher.py (to be created)

## Example Function Signature
```python
def get_latest_data(symbols: list) -> dict:
    """
    Fetch latest market data for given symbols.
    
    Args:
        symbols: List of ticker symbols (e.g., ["AAPL", "BTC/USD"])
    
    Returns:
        Dict mapping symbol to {price, volume, timestamp}
    
    Raises:
        APIError: If API call fails after retries
    """
    pass
```

## Technical Notes
- Consider exponential backoff for retry logic
- Log both successful and failed requests
- Return None or empty dict for symbols with no data
- Document expected return format clearly
- Keep module read-only (no trading logic)
