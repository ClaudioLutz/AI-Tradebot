# Story 002-003: Watchlist Configuration

## Story Overview
Implement watchlist configuration that defines which financial instruments (stocks, ETFs, crypto) the trading bot will monitor and trade.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** trader  
**I want to** configure a watchlist of instruments to monitor  
**So that** the bot only trades my selected stocks and cryptocurrencies

## Acceptance Criteria
- [ ] Watchlist supports stock symbols (e.g., "AAPL", "MSFT")
- [ ] Watchlist supports crypto pairs (e.g., "BTC/USD", "ETH/USD")
- [ ] Watchlist is easily configurable and modifiable
- [ ] Watchlist validates symbol format
- [ ] Support for 5-20 instruments minimum
- [ ] Watchlist can be loaded from environment or code

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials loading)

### Supported Instrument Types
1. **Stocks:** US equities (AAPL, MSFT, GOOGL, TSLA, AMZN, etc.)
2. **ETFs:** Exchange-traded funds (SPY, QQQ, etc.)
3. **Crypto:** Cryptocurrency pairs (BTC/USD, ETH/USD, etc.)

### Implementation

Add to the `Config.__init__()` method:

```python
def __init__(self):
    """
    Initialize configuration by loading from environment variables.
    
    Raises:
        ConfigurationError: If required credentials are missing
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # API Credentials Configuration
    self._load_api_credentials()
    
    # Watchlist Configuration
    self._load_watchlist()

def _load_watchlist(self):
    """
    Load and configure the watchlist of instruments to monitor.
    
    The watchlist can be configured via:
    1. WATCHLIST environment variable (comma-separated)
    2. Default watchlist defined in code
    
    Crypto symbols must use slash format: BTC/USD, ETH/USD
    """
    # Check for environment variable first
    watchlist_env = os.getenv("WATCHLIST")
    
    if watchlist_env:
        # Parse comma-separated watchlist from environment
        self.watchlist = [
            symbol.strip() 
            for symbol in watchlist_env.split(',') 
            if symbol.strip()
        ]
    else:
        # Default watchlist: Mix of stocks and crypto
        self.watchlist = [
            # Tech stocks
            "AAPL",    # Apple Inc.
            "MSFT",    # Microsoft Corporation
            "GOOGL",   # Alphabet Inc.
            "AMZN",    # Amazon.com Inc.
            "TSLA",    # Tesla Inc.
            
            # Other sectors
            "JPM",     # JPMorgan Chase & Co.
            "V",       # Visa Inc.
            "WMT",     # Walmart Inc.
            
            # ETFs
            "SPY",     # SPDR S&P 500 ETF
            "QQQ",     # Invesco QQQ Trust
            
            # Cryptocurrencies (slash format for Saxo)
            "BTC/USD", # Bitcoin
            "ETH/USD", # Ethereum
        ]
    
    # Validate watchlist
    self._validate_watchlist()

def _validate_watchlist(self):
    """
    Validate watchlist symbols format and constraints.
    
    Raises:
        ConfigurationError: If watchlist is invalid
    """
    if not self.watchlist:
        raise ConfigurationError("Watchlist cannot be empty")
    
    if len(self.watchlist) < 1:
        raise ConfigurationError("Watchlist must contain at least 1 symbol")
    
    # Validate individual symbols
    for symbol in self.watchlist:
        if not symbol or not isinstance(symbol, str):
            raise ConfigurationError(f"Invalid symbol in watchlist: {symbol}")
        
        # Check for invalid characters
        if not all(c.isalnum() or c in ['/', '-', '.'] for c in symbol):
            raise ConfigurationError(
                f"Invalid symbol format: {symbol}. "
                "Symbols can only contain letters, numbers, /, -, and ."
            )

def get_stock_symbols(self) -> List[str]:
    """
    Get only stock symbols from watchlist (exclude crypto).
    
    Returns:
        List of stock symbols
    """
    return [symbol for symbol in self.watchlist if '/' not in symbol]

def get_crypto_symbols(self) -> List[str]:
    """
    Get only crypto symbols from watchlist.
    
    Returns:
        List of crypto symbols (with slash format)
    """
    return [symbol for symbol in self.watchlist if '/' in symbol]

def add_symbol(self, symbol: str) -> None:
    """
    Add a new symbol to the watchlist.
    
    Args:
        symbol: Symbol to add (e.g., "NVDA" or "SOL/USD")
    
    Raises:
        ConfigurationError: If symbol is invalid or already exists
    """
    symbol = symbol.strip().upper()
    
    if symbol in self.watchlist:
        raise ConfigurationError(f"Symbol {symbol} already in watchlist")
    
    self.watchlist.append(symbol)
    self._validate_watchlist()

def remove_symbol(self, symbol: str) -> None:
    """
    Remove a symbol from the watchlist.
    
    Args:
        symbol: Symbol to remove
    
    Raises:
        ConfigurationError: If symbol not in watchlist
    """
    symbol = symbol.strip().upper()
    
    if symbol not in self.watchlist:
        raise ConfigurationError(f"Symbol {symbol} not in watchlist")
    
    self.watchlist.remove(symbol)
    self._validate_watchlist()

def get_watchlist_summary(self) -> Dict[str, Any]:
    """
    Get summary of watchlist configuration.
    
    Returns:
        Dictionary with watchlist details
    """
    return {
        "total_symbols": len(self.watchlist),
        "stocks": self.get_stock_symbols(),
        "crypto": self.get_crypto_symbols(),
        "stock_count": len(self.get_stock_symbols()),
        "crypto_count": len(self.get_crypto_symbols()),
    }
```

Update the `get_summary()` method:

```python
def get_summary(self) -> Dict[str, Any]:
    """
    Get a summary of current configuration (without sensitive data).
    
    Returns:
        Dictionary containing non-sensitive configuration details
    """
    return {
        "base_url": self.base_url,
        "environment": self.environment,
        "token_masked": self.get_masked_token(),
        "is_simulation": self.is_simulation(),
        "watchlist": self.get_watchlist_summary(),
    }
```

### Environment Variable Configuration (Optional)

Add to `.env` file for custom watchlist:

```bash
# Optional: Custom watchlist (comma-separated)
# If not set, uses default watchlist
WATCHLIST=AAPL,MSFT,GOOGL,TSLA,BTC/USD,ETH/USD
```

## Files to Modify
- `config/config.py` - Add watchlist configuration
- `.env.example` - Add optional WATCHLIST variable

## Definition of Done
- [ ] Watchlist loaded from environment or defaults
- [ ] Stocks and crypto symbols supported
- [ ] Watchlist validation working
- [ ] Helper methods for filtering by type
- [ ] Can add/remove symbols dynamically
- [ ] All tests pass

## Testing

### Test 1: Load Default Watchlist
```python
from config.config import Config

config = Config()
summary = config.get_watchlist_summary()
print(f"Total symbols: {summary['total_symbols']}")
print(f"Stocks: {summary['stock_count']}")
print(f"Crypto: {summary['crypto_count']}")
print(f"Stock list: {summary['stocks'][:3]}")  # First 3
print(f"Crypto list: {summary['crypto']}")
```

Expected output:
```
Total symbols: 12
Stocks: 10
Crypto: 2
Stock list: ['AAPL', 'MSFT', 'GOOGL']
Crypto list: ['BTC/USD', 'ETH/USD']
```

### Test 2: Filter Stocks and Crypto
```python
from config.config import Config

config = Config()
stocks = config.get_stock_symbols()
crypto = config.get_crypto_symbols()

print(f"Stocks: {len(stocks)}")
print(f"Crypto: {len(crypto)}")
print(f"Has BTC/USD: {'BTC/USD' in crypto}")
```

Expected:
```
Stocks: 10
Crypto: 2
Has BTC/USD: True
```

### Test 3: Add Symbol
```python
from config.config import Config

config = Config()
initial_count = len(config.watchlist)

config.add_symbol("NVDA")
new_count = len(config.watchlist)

print(f"Initial: {initial_count}, After add: {new_count}")
print(f"NVDA in watchlist: {'NVDA' in config.watchlist}")
```

Expected:
```
Initial: 12, After add: 13
NVDA in watchlist: True
```

### Test 4: Remove Symbol
```python
from config.config import Config

config = Config()
config.remove_symbol("WMT")

print(f"WMT removed: {'WMT' not in config.watchlist}")
print(f"Total symbols: {len(config.watchlist)}")
```

Expected:
```
WMT removed: True
Total symbols: 11
```

### Test 5: Environment Variable Watchlist
```python
import os
os.environ['WATCHLIST'] = 'AAPL,TSLA,BTC/USD'

from config.config import Config
config = Config()

print(f"Watchlist: {config.watchlist}")
print(f"Count: {len(config.watchlist)}")
```

Expected:
```
Watchlist: ['AAPL', 'TSLA', 'BTC/USD']
Count: 3
```

### Test 6: Invalid Symbol Error
```python
from config.config import Config, ConfigurationError

config = Config()
try:
    config.add_symbol("AAPL")  # Already exists
except ConfigurationError as e:
    print(f"Expected error: {e}")
```

Expected: "Expected error: Symbol AAPL already in watchlist"

## Story Points
**Estimate:** 3 points

## Dependencies
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials)

## Blocks
- Story 002-005 (global settings needs watchlist)
- Story 002-006 (validation needs watchlist)

## Default Watchlist Rationale
- **AAPL, MSFT, GOOGL, AMZN, TSLA:** Major tech stocks with high liquidity
- **JPM, V, WMT:** Diversification across sectors
- **SPY, QQQ:** ETFs for market tracking
- **BTC/USD, ETH/USD:** Major cryptocurrencies

## Watchlist Best Practices
1. **Liquidity:** Choose highly liquid instruments
2. **Diversification:** Mix sectors and asset types
3. **Size:** 5-20 symbols for manageable monitoring
4. **Validation:** Always validate before trading
5. **Updates:** Easy to add/remove symbols as needed

## Saxo Bank Symbol Format Notes
- **Stocks:** Standard ticker format (AAPL, MSFT)
- **Crypto:** Must use slash format (BTC/USD, not BTCUSD)
- **Case:** Symbols normalized to uppercase
- **Availability:** Check Saxo OpenAPI for supported instruments

## Common Issues and Solutions

### Issue: Crypto symbols not found
**Solution:** Ensure using slash format: BTC/USD not BTCUSD

### Issue: Empty watchlist error
**Solution:** Provide at least one valid symbol

### Issue: Symbol already exists error
**Solution:** Check if symbol in watchlist before adding

### Issue: Invalid symbol format
**Solution:** Use only letters, numbers, /, -, and .

## Architecture Notes
- **Flexibility:** Environment variable overrides code defaults
- **Validation:** Built-in format and constraint checking
- **Type Separation:** Easy filtering of stocks vs crypto
- **Mutability:** Runtime add/remove support for testing

## Future Enhancements (Not in this story)
- Load watchlist from external file (JSON/CSV)
- Instrument metadata (sector, exchange, etc.)
- Dynamic watchlist from market scanners
- Symbol validation against Saxo API
- Watchlist presets (aggressive, conservative, etc.)

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- Saxo OpenAPI Instruments: [https://developer.saxobank.com](https://developer.saxobank.com)

## Success Criteria
✅ Story is complete when:
1. Watchlist loads from environment or defaults
2. Supports stocks and crypto formats
3. Validation working correctly
4. Helper methods implemented
5. Add/remove functionality working
6. All verification tests pass
7. Documentation complete
