# Story 001-2-009: Update Configuration Watchlist Format

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to update the configuration module to use Saxo's UIC-based watchlist format instead of Alpaca's symbol-based format so that the application can properly identify instruments for trading.

## Description
Modify `config/settings.py` to change the WATCHLIST format from simple symbol strings to dictionaries containing name, asset_type, and optionally UIC. This aligns with Saxo's instrument identification requirements.

## Prerequisites
- Story 001-2-007 completed (market data module understands UICs)
- Story 001-2-003 completed (environment variables updated)

## Acceptance Criteria
- [ ] WATCHLIST format updated in `config/settings.py`
- [ ] Each watchlist entry includes name and asset_type
- [ ] Optional UIC field included for pre-discovered instruments
- [ ] Comments explain new format
- [ ] Examples provided for different asset types
- [ ] Module can be imported without errors
- [ ] Backwards compatibility notes if needed

## Technical Details

### Current Format (Alpaca)
```python
WATCHLIST = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "TSLA",
    "BTC/USD"
]
```

### New Format (Saxo)
```python
WATCHLIST = [
    {"name": "AAPL", "asset_type": "Stock", "uic": 211},
    {"name": "MSFT", "asset_type": "Stock"},
    {"name": "BTCUSD", "asset_type": "FxSpot", "uic": 21700189},
    {"name": "ETHUSD", "asset_type": "FxSpot", "uic": 21750301},
]
```

### Key Changes
1. **name:** Instrument identifier/keyword (replaces simple string)
2. **asset_type:** Required - Stock, FxSpot, FxCrypto, etc.
3. **uic:** Optional - Can be pre-populated or discovered at runtime

## Implementation

### Complete Updated config/settings.py

```python
"""
Configuration Settings - Saxo Bank Integration
Central configuration for trading bot parameters.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Saxo API Configuration
SAXO_ENV = os.getenv("SAXO_ENV", "SIM")
SAXO_REST_BASE = os.getenv("SAXO_REST_BASE")
SAXO_ACCESS_TOKEN = os.getenv("SAXO_ACCESS_TOKEN")

# Trading Configuration
WATCHLIST = [
    # Stocks - Major US Tech Companies
    {"name": "AAPL", "asset_type": "Stock", "uic": 211},
    {"name": "MSFT", "asset_type": "Stock"},
    {"name": "GOOGL", "asset_type": "Stock"},
    {"name": "TSLA", "asset_type": "Stock"},
    {"name": "AMZN", "asset_type": "Stock"},
    
    # Crypto - Major Pairs (FxSpot or FxCrypto)
    # Note: Saxo is transitioning crypto from FxSpot to FxCrypto
    # UICs remain the same, but AssetType may change
    {"name": "BTCUSD", "asset_type": "FxSpot", "uic": 21700189},
    {"name": "ETHUSD", "asset_type": "FxSpot", "uic": 21750301},
    
    # Note: If UIC is not provided, it will be discovered at runtime
    # using the market data module's find_instrument_uic() function
]

# Watchlist Format Documentation:
# Each watchlist entry is a dictionary with:
#   - name (required): Instrument keyword/symbol for search
#   - asset_type (required): Saxo asset type (Stock, FxSpot, FxCrypto, etc.)
#   - uic (optional): Universal Instrument Code - if known, include for faster lookup
#
# Common Asset Types:
#   - Stock: Equities
#   - FxSpot: Forex pairs (and legacy crypto)
#   - FxCrypto: Crypto pairs (new designation)
#   - CfdOnIndex: Index CFDs
#   - Bond: Bonds
#
# Example Discovery (if UIC not provided):
#   from data.market_data import find_instrument_uic
#   uic = find_instrument_uic("AAPL", "Stock")

# Trading Parameters
TRADE_AMOUNT = 1  # Default trade amount (shares for stocks, units for FX)
MAX_POSITIONS = 5  # Maximum number of open positions
STOP_LOSS_PERCENT = 0.02  # 2% stop loss
TAKE_PROFIT_PERCENT = 0.05  # 5% take profit

# Risk Management
MAX_POSITION_SIZE = 1000  # Maximum dollar amount per position
MAX_DAILY_LOSS = 500  # Maximum loss per day before stopping
MAX_DAILY_TRADES = 10  # Maximum number of trades per day

# Scheduling (if using scheduler)
TRADING_SCHEDULE = "09:30"  # Time to run trading logic (format: "HH:MM")
CHECK_INTERVAL_MINUTES = 15  # How often to check positions/signals

# Logging Configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "logs/trading_bot.log"

# Module information
__version__ = "2.0.0"
__api__ = "Saxo OpenAPI"

print(f"Configuration loaded: {len(WATCHLIST)} instruments in watchlist ({SAXO_ENV} environment)")
```

## Files to Modify
- `config/settings.py` - Update WATCHLIST and related configuration

## Verification Steps
- [ ] File updated successfully
- [ ] No syntax errors
- [ ] Can import module
- [ ] WATCHLIST is list of dictionaries
- [ ] Each entry has required keys
- [ ] Comments explain format
- [ ] Module loads without errors

## Testing

### Test 1: Module Import
```python
from config import settings
print("Config module imported successfully")
```

Expected: No errors

### Test 2: Watchlist Format
```python
from config.settings import WATCHLIST

print(f"Watchlist size: {len(WATCHLIST)}")
print("\nFirst entry:")
first = WATCHLIST[0]
print(f"  Name: {first['name']}")
print(f"  Asset Type: {first['asset_type']}")
print(f"  UIC: {first.get('uic', 'Not specified')}")
```

Expected: Displays watchlist entry correctly

### Test 3: Validate All Entries
```python
from config.settings import WATCHLIST

required_keys = ['name', 'asset_type']
for i, entry in enumerate(WATCHLIST):
    missing = [key for key in required_keys if key not in entry]
    if missing:
        print(f"Entry {i} missing keys: {missing}")
    else:
        print(f"✓ Entry {i}: {entry['name']} ({entry['asset_type']})")
```

Expected: All entries have required keys

### Test 4: Environment Variables
```python
from config.settings import SAXO_ENV, SAXO_REST_BASE

print(f"Environment: {SAXO_ENV}")
print(f"API Base: {SAXO_REST_BASE}")
```

Expected: Displays Saxo configuration

### Test 5: Integration with Market Data
```python
from config.settings import WATCHLIST
from data.market_data import discover_watchlist_instruments

# Discover UICs for watchlist
results = discover_watchlist_instruments(WATCHLIST)
for item in results:
    if item['status'] == 'found':
        print(f"✓ {item['name']}: UIC {item['uic']}")
    else:
        print(f"✗ {item['name']}: {item['error']}")
```

Expected: Discovers UICs for all watchlist instruments

## Documentation

### Watchlist Format Guide
Include comprehensive comments explaining:
- Dictionary structure
- Required vs optional fields
- Common asset types
- How UIC discovery works
- Examples for each asset type

### Migration Guide
Document the migration:
```
# OLD (Alpaca):
WATCHLIST = ["AAPL", "MSFT", "BTC/USD"]

# NEW (Saxo):
WATCHLIST = [
    {"name": "AAPL", "asset_type": "Stock"},
    {"name": "MSFT", "asset_type": "Stock"},
    {"name": "BTCUSD", "asset_type": "FxSpot"}
]
```

### Asset Type Reference
Document common asset types and examples:
- **Stock:** US equities, European stocks
- **FxSpot:** Major forex pairs, commodity currencies
- **FxCrypto:** Bitcoin, Ethereum, etc. (new designation)
- **CfdOnIndex:** S&P 500, NASDAQ, etc.

## Time Estimate
**30 minutes** (update config + test + document)

## Dependencies
- Story 001-2-007 completed (market data module)
- Story 001-2-003 completed (environment variables)

## Blocks
- Story 001-2-010 (integration testing needs proper watchlist)

## Configuration Best Practices

### Pre-populate UICs
If you know the UICs, include them:
- Faster startup (no discovery needed)
- More reliable (no search ambiguity)
- Better for production

### Runtime Discovery
If UIC not provided:
- Market data module will discover it
- First run may be slower
- Good for development/testing

### Asset Type Accuracy
Critical for correct instrument lookup:
- Wrong asset type = instrument not found
- Check Saxo documentation for correct types
- Some instruments available in multiple types

## Common Watchlist Examples

### US Stocks Only
```python
WATCHLIST = [
    {"name": "AAPL", "asset_type": "Stock"},
    {"name": "MSFT", "asset_type": "Stock"},
    {"name": "GOOGL", "asset_type": "Stock"},
]
```

### Forex Pairs
```python
WATCHLIST = [
    {"name": "EURUSD", "asset_type": "FxSpot"},
    {"name": "GBPUSD", "asset_type": "FxSpot"},
    {"name": "USDJPY", "asset_type": "FxSpot"},
]
```

### Mixed Portfolio
```python
WATCHLIST = [
    {"name": "AAPL", "asset_type": "Stock"},
    {"name": "EURUSD", "asset_type": "FxSpot"},
    {"name": "BTCUSD", "asset_type": "FxSpot"},
]
```

## Crypto Asset Type Note

Include warning about crypto transition:
```python
# IMPORTANT: Crypto Asset Type Transition
# Saxo is moving crypto pairs from FxSpot to FxCrypto
# Affected pairs: BTCUSD, ETHUSD, and others
# For maximum compatibility, code should accept both types
# UICs remain the same: BTCUSD=21700189, ETHUSD=21750301
```

## Error Handling

### Missing Keys
If required keys missing:
- Error during validation
- Clear message about required keys
- Example of correct format

### Invalid Asset Types
If asset type invalid:
- May fail during discovery
- Reference Saxo documentation
- List valid asset types in error

## Future Enhancements (Not in this story)
- Watchlist validation on load
- Dynamic watchlist loading from file
- Watchlist grouping (by sector, asset class, etc.)
- Position sizing per instrument
- Per-instrument risk parameters

## References
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 9)
- [Saxo Asset Types](https://developer.saxobank.com/openapi/learn/asset-types)
- Epic 002: `docs/epics/epic-002-configuration-module.md`

## Success Criteria
✅ Story is complete when:
1. `config/settings.py` updated with new format
2. WATCHLIST is list of dictionaries
3. All entries have required keys
4. Comments explain format
5. Examples provided
6. Module imports without errors
7. Integration with market data works
8. All verification tests pass
