# Epic 003: Market Data Retrieval Module (Saxo)

## Epic Overview
Develop the market data adapter (`data/market_data.py`) to fetch quotes and OHLC bars from Saxo OpenAPI for instruments defined in the watchlist. This module provides normalized market data keyed by `instrument_id`, abstracting Saxo-specific API calls from other components.

## Business Value
- Provides reliable market data feed for multi-asset strategies
- Abstracts Saxo API complexity from strategy logic
- Handles rate limiting and error recovery
- Supports equities, FX, and CryptoFX asset classes
- Enables data-driven trading decisions with normalized data structure

## Scope

### In Scope
- `data/market_data.py` module creation
- Saxo REST client integration for market data endpoints
- **InfoPrice/Quote fetching** for real-time pricing (latest bid/ask)
- **OHLC bars fetching** for strategy indicators (e.g., 1-minute bars)
- Data normalization keyed by `instrument_id` (`"{asset_type}:{uic}"`)
- Support for watchlist instruments: `{asset_type, uic, symbol}`
- Error handling and retry logic
- Rate limit management (Saxo-specific limits)
- Comprehensive logging for data retrieval operations

### Out of Scope
- WebSocket streaming (real-time subscription feeds)
- Historical data backtesting (multi-day datasets)
- Data storage/caching to database
- Custom technical indicators calculation (RSI, MACD, etc.)
- Multiple timeframe support beyond primary strategy timeframe

## Technical Considerations

### Saxo Market Data Endpoints
- **InfoPrice (`/trade/v1/infoprices`)**: Real-time quote (bid/ask/last) for instruments
- **Chart Data (`/chart/v1/charts`)**: OHLC bars with configurable horizon (e.g., 60 bars of 1-minute data)

### Data Model
- **Input:** List of instruments from config: `[{asset_type, uic, symbol}, ...]`
- **Internal Key:** `instrument_id = f"{asset_type}:{uic}"` (unique, deterministic)
- **Output:** Normalized dict keyed by `instrument_id`:
  ```python
  {
    "Stock:211": {
      "instrument_id": "Stock:211",
      "asset_type": "Stock",
      "uic": 211,
      "symbol": "AAPL",  # human-readable label
      "quote": {"bid": 150.25, "ask": 150.30, "last": 150.28, "timestamp": "..."},
      "bars": [...]  # optional, if OHLC requested
    }
  }
  ```

### Error Handling
- Handle invalid UIC/AssetType combinations gracefully
- Catch HTTP errors (401, 403, 429, 500) with appropriate retries
- Log failures with full context (instrument_id, HTTP status, error body)
- Return partial results if some instruments fail (don't crash entire fetch)

### Rate Limits
- Saxo OpenAPI rate limits vary by endpoint and subscription tier
- Implement exponential backoff for 429 responses
- Batch requests where possible (InfoPrice supports multiple UICs)

## Dependencies
- **Epic 001-2:** Saxo Bank Migration (Saxo client + authentication)
- **Epic 002:** Configuration Module (watchlist with resolved instruments)

## Success Criteria
- [ ] `data/market_data.py` module created
- [ ] Saxo client integrated for market data calls
- [ ] `get_latest_quotes()` function fetches InfoPrice for watchlist instruments
- [ ] `get_ohlc_bars()` function fetches chart data for specified horizon/interval
- [ ] Data returned keyed by `instrument_id` with symbol label for readability
- [ ] Error handling prevents crashes on API failures
- [ ] Rate limiting respected with exponential backoff
- [ ] Module is testable with mock Saxo responses

## Acceptance Criteria
1. Can fetch latest quote (bid/ask/last) for all watchlist instruments
2. Can fetch OHLC bars (configurable horizon/interval) for strategy indicators
3. Returns normalized data structure keyed by `instrument_id`
4. Handles network errors and API failures gracefully without crashing
5. Logs all API requests with instrument context (asset_type, uic, symbol)
6. Works with equities (Stock), FX (FxSpot), and CryptoFX asset types
7. Respects Saxo API rate limits with retry logic
8. Invalid instruments return clear error messages with diagnostic info

## Related Documents
- [Saxo OpenAPI - InfoPrices](https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices)
- [Saxo OpenAPI - Charts](https://www.developer.saxo/openapi/referencedocs/chart/v1/charts)
- `data/market_data.py` (to be enhanced)
- `data/saxo_client.py` (Saxo REST client)

## Example Function Signatures

```python
def get_latest_quotes(instruments: List[Dict]) -> Dict[str, Dict]:
    """
    Fetch latest quotes (InfoPrice) for given instruments.
    
    Args:
        instruments: List of dicts with {asset_type, uic, symbol}
    
    Returns:
        Dict keyed by instrument_id:
        {
            "Stock:211": {
                "instrument_id": "Stock:211",
                "asset_type": "Stock",
                "uic": 211,
                "symbol": "AAPL",
                "quote": {
                    "bid": 150.25,
                    "ask": 150.30,
                    "last": 150.28,
                    "timestamp": "2025-12-13T08:30:00Z"
                }
            },
            ...
        }
    
    Raises:
        APIError: If API call fails after retries
    """
    pass


def get_ohlc_bars(instrument: Dict, horizon: int = 60, interval: str = "1m") -> Dict:
    """
    Fetch OHLC bars for a single instrument.
    
    Args:
        instrument: Dict with {asset_type, uic, symbol}
        horizon: Number of bars to fetch (default 60)
        interval: Bar interval (e.g., "1m", "5m", "1h")
    
    Returns:
        Dict with instrument metadata + bars:
        {
            "instrument_id": "FxSpot:21",
            "asset_type": "FxSpot",
            "uic": 21,
            "symbol": "EURUSD",
            "bars": [
                {"time": "...", "open": 1.05, "high": 1.051, "low": 1.049, "close": 1.050, "volume": 1000},
                ...
            ]
        }
    
    Raises:
        APIError: If chart data retrieval fails
    """
    pass
```

## Technical Notes

### Instrument ID Construction
- Always construct `instrument_id = f"{asset_type}:{uic}"` for consistent keying
- Include `symbol` in output for human-readable logs/debugging
- Never use symbol alone as a key (not unique across asset types)

### Data Freshness
- InfoPrice timestamps indicate last update time
- Validate timestamps to detect stale data (warn if >5min old for active markets)
- CryptoFX instruments may have 24/7 updates; equities only during trading hours

### Retry Strategy
- Implement exponential backoff: 1s, 2s, 4s, 8s (max 3 retries)
- Retry on: 429 (rate limit), 500/502/503 (server errors), network timeouts
- Do NOT retry on: 401/403 (auth), 400 (bad request - likely code bug)

### Batch Optimization
- InfoPrice endpoint supports multiple UICs in a single request (comma-separated)
- Batch requests by asset type for efficiency
- Chart endpoint is per-instrument (no batching)

### Logging
- Log successful fetches with count and instrument_ids
- Log failures with full error context: `{instrument_id, asset_type, uic, symbol, http_status, error_body}`
- Include request timing for performance monitoring

## CryptoFX Notes
- Use symbol format "BTCUSD" (no slash) for CryptoFX instruments
- AssetType may be "FxSpot" for crypto pairs (not "FxCrypto" - verify via instrument details)
- 24/7 trading availability (no market hours check needed)
