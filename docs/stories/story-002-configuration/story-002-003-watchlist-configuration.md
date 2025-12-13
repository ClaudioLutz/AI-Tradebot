# Story 002-003: Watchlist Configuration (Structured with UIC Resolution)

## Story Overview
Implement structured watchlist configuration that defines instruments using Saxo's AssetType + UIC model. Includes instrument resolver that queries `/ref/v1/instruments` to convert human-readable symbols to Saxo-required identifiers.

## Parent Epic
[Epic 002: Configuration Module Development](../../epics/epic-002-configuration-module.md)

## User Story
**As a** trader  
**I want to** configure instruments using structured AssetType + UIC definitions  
**So that** the bot can reliably place orders using Saxo's required identifiers

## Acceptance Criteria
- [ ] Watchlist uses structured format: `[{"symbol": "AAPL", "asset_type": "Stock", "uic": 211}, ...]`
- [ ] Instrument resolver queries `/ref/v1/instruments` API
- [ ] Resolution results cached to minimize API calls
- [ ] Handles ambiguous matches (same symbol, multiple instruments)
- [ ] Supports Saxo CryptoFX format (BTCUSD not BTC/USD)
- [ ] Validation ensures each entry has valid AssetType + UIC
- [ ] Human-readable symbols can be resolved to structured format
- [ ] Configuration can be loaded from environment or code

## Technical Details

### Prerequisites
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials + auth)
- Saxo REST client available (`data/saxo_client.py`)

### Saxo Instrument Identity Model

Saxo requires **AssetType + UIC** for all order placement:

```python
# WRONG (insufficient for order placement)
symbol = "AAPL"

# CORRECT (Saxo order placement format)
instrument = {
    "symbol": "AAPL",           # Human-readable
    "asset_type": "Stock",      # Required for order placement
    "uic": 211,                 # Required for order placement (Universal Instrument Code)
    "exchange": "NASDAQ"        # Optional metadata
}
```

### Supported Asset Types

1. **Stock** - Equities (AAPL, MSFT, GOOGL)
2. **FxSpot** - FX and CryptoFX (EURUSD, BTCUSD, ETHUSD)
3. **FxCrypto** - Future crypto asset type (migration from FxSpot)
4. **StockOption** - Options (future support)
5. **Etf** - Exchange-traded funds

### Saxo CryptoFX Format

⚠️ **Important:** Saxo uses **no slash** for crypto:
- ✅ Correct: `"BTCUSD"`, `"ETHUSD"`, `"LTCUSD"`
- ❌ Wrong: `"BTC/USD"`, `"ETH/USD"`

Currently traded as `AssetType: FxSpot`, transitioning to `FxCrypto`.

### Implementation

Update `config/config.py`:

```python
from typing import List, Dict, Any, Optional
import json
import os

class Config:
    """Configuration with structured watchlist and instrument resolution."""
    
    def __init__(self):
        """Initialize configuration."""
        load_dotenv()
        
        # API Credentials Configuration
        self._load_api_credentials()
        self._initialize_authentication()
        
        # Watchlist Configuration
        self._load_watchlist()
        
        # Instrument resolver cache
        self._instrument_cache = {}
        self._cache_file = ".cache/instruments.json"
    
    def _load_watchlist(self):
        """
        Load and configure the watchlist with structured instrument definitions.
        
        The watchlist uses structured format:
        [
            {"symbol": "AAPL", "asset_type": "Stock", "uic": 211},
            {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 12345},
            ...
        ]
        
        Can be configured via:
        1. WATCHLIST_JSON environment variable (JSON string)
        2. Default watchlist defined in code (resolved on first use)
        """
        # Check for JSON environment variable first
        watchlist_json = os.getenv("WATCHLIST_JSON")
        
        if watchlist_json:
            try:
                self.watchlist = json.loads(watchlist_json)
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid WATCHLIST_JSON format: {e}")
        else:
            # Default watchlist with common instruments
            # UICs are placeholders - use resolver to get actual UICs
            self.watchlist = [
                {"symbol": "AAPL", "asset_type": "Stock", "uic": None},
                {"symbol": "MSFT", "asset_type": "Stock", "uic": None},
                {"symbol": "GOOGL", "asset_type": "Stock", "uic": None},
                {"symbol": "TSLA", "asset_type": "Stock", "uic": None},
                {"symbol": "AMZN", "asset_type": "Stock", "uic": None},
                {"symbol": "JPM", "asset_type": "Stock", "uic": None},
                {"symbol": "V", "asset_type": "Stock", "uic": None},
                {"symbol": "WMT", "asset_type": "Stock", "uic": None},
                {"symbol": "SPY", "asset_type": "Etf", "uic": None},
                {"symbol": "QQQ", "asset_type": "Etf", "uic": None},
                {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": None},  # CryptoFX
                {"symbol": "ETHUSD", "asset_type": "FxSpot", "uic": None},  # CryptoFX
            ]
        
        # Load instrument cache
        self._load_instrument_cache()
        
        # Validate watchlist structure
        self._validate_watchlist()
    
    def _load_instrument_cache(self):
        """Load cached instrument resolutions from file."""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'r') as f:
                    self._instrument_cache = json.load(f)
            except Exception as e:
                print(f"⚠️  Warning: Could not load instrument cache: {e}")
                self._instrument_cache = {}
        else:
            self._instrument_cache = {}
    
    def _save_instrument_cache(self):
        """Save instrument resolutions to cache file."""
        os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
        try:
            with open(self._cache_file, 'w') as f:
                json.dump(self._instrument_cache, f, indent=2)
        except Exception as e:
            print(f"⚠️  Warning: Could not save instrument cache: {e}")
    
    def _validate_watchlist(self):
        """
        Validate watchlist structure and content.
        
        Raises:
            ConfigurationError: If watchlist is invalid
        """
        if not self.watchlist:
            raise ConfigurationError("Watchlist cannot be empty")
        
        if not isinstance(self.watchlist, list):
            raise ConfigurationError("Watchlist must be a list")
        
        # Validate each instrument entry
        for idx, instrument in enumerate(self.watchlist):
            if not isinstance(instrument, dict):
                raise ConfigurationError(
                    f"Watchlist entry {idx} must be a dictionary, got: {type(instrument)}"
                )
            
            # Required fields
            if "symbol" not in instrument:
                raise ConfigurationError(f"Watchlist entry {idx} missing 'symbol'")
            
            if "asset_type" not in instrument:
                raise ConfigurationError(f"Watchlist entry {idx} missing 'asset_type'")
            
            # Validate asset type
            valid_asset_types = ["Stock", "Etf", "FxSpot", "FxCrypto", "StockOption"]
            if instrument["asset_type"] not in valid_asset_types:
                raise ConfigurationError(
                    f"Invalid asset_type '{instrument['asset_type']}' for {instrument['symbol']}. "
                    f"Must be one of: {', '.join(valid_asset_types)}"
                )
            
            # Validate symbol format (no slashes for crypto)
            symbol = instrument["symbol"]
            if "/" in symbol:
                raise ConfigurationError(
                    f"Invalid symbol format '{symbol}': Saxo uses no-slash format. "
                    f"Use 'BTCUSD' not 'BTC/USD'"
                )
    
    def resolve_instruments(self, force_refresh: bool = False):
        """
        Resolve all instruments in watchlist to get UICs.
        
        Queries Saxo /ref/v1/instruments API and updates watchlist with UICs.
        Uses cache to minimize API calls unless force_refresh=True.
        
        Args:
            force_refresh: If True, ignore cache and query API
        
        Raises:
            ConfigurationError: If resolution fails or finds ambiguous matches
        """
        from data.saxo_client import SaxoClient
        
        # Initialize Saxo client
        client = SaxoClient(
            base_url=self.base_url,
            access_token=self.get_access_token()
        )
        
        unresolved_count = 0
        resolved_count = 0
        
        for instrument in self.watchlist:
            symbol = instrument["symbol"]
            asset_type = instrument["asset_type"]
            cache_key = f"{symbol}_{asset_type}"
            
            # Check if UIC already set
            if instrument.get("uic") and not force_refresh:
                resolved_count += 1
                continue
            
            # Check cache
            if cache_key in self._instrument_cache and not force_refresh:
                instrument["uic"] = self._instrument_cache[cache_key]["uic"]
                # Copy additional metadata if available
                if "exchange" in self._instrument_cache[cache_key]:
                    instrument["exchange"] = self._instrument_cache[cache_key]["exchange"]
                resolved_count += 1
                print(f"✓ {symbol} ({asset_type}): UIC {instrument['uic']} [cached]")
                continue
            
            # Query API
            print(f"🔍 Resolving {symbol} ({asset_type})...")
            
            try:
                # Query /ref/v1/instruments
                endpoint = "/ref/v1/instruments"
                params = {
                    "Keywords": symbol,
                    "AssetTypes": asset_type,
                    "IncludeNonTradable": False,
                    "$top": 10  # Limit results
                }
                
                response = client._make_request("GET", endpoint, params=params)
                
                if not response or "Data" not in response:
                    raise ConfigurationError(f"No data returned for {symbol}")
                
                instruments_found = response["Data"]
                
                if len(instruments_found) == 0:
                    raise ConfigurationError(
                        f"Instrument not found: {symbol} ({asset_type})\n"
                        f"Please verify symbol and asset type are correct"
                    )
                
                # Handle multiple matches
                if len(instruments_found) > 1:
                    # Try exact symbol match first
                    exact_matches = [
                        inst for inst in instruments_found 
                        if inst.get("Symbol", "").upper() == symbol.upper()
                    ]
                    
                    if len(exact_matches) == 1:
                        selected = exact_matches[0]
                    else:
                        # Multiple matches - show details and raise error
                        print(f"\n⚠️  Multiple instruments found for {symbol}:")
                        for inst in instruments_found[:5]:  # Show first 5
                            print(f"   - UIC: {inst.get('Uic')}, "
                                  f"Symbol: {inst.get('Symbol')}, "
                                  f"Description: {inst.get('Description', 'N/A')}, "
                                  f"Exchange: {inst.get('Exchange', {}).get('ExchangeId', 'N/A')}")
                        
                        raise ConfigurationError(
                            f"Ambiguous match for {symbol} ({asset_type}): {len(instruments_found)} instruments found. "
                            f"Please specify exact UIC manually in watchlist."
                        )
                else:
                    selected = instruments_found[0]
                
                # Extract UIC and metadata
                uic = selected.get("Uic")
                if not uic:
                    raise ConfigurationError(f"No UIC found for {symbol}")
                
                # Update instrument
                instrument["uic"] = uic
                instrument["description"] = selected.get("Description", "")
                
                exchange_info = selected.get("Exchange", {})
                if exchange_info:
                    instrument["exchange"] = exchange_info.get("ExchangeId", "")
                
                # Update cache
                self._instrument_cache[cache_key] = {
                    "uic": uic,
                    "description": instrument.get("description", ""),
                    "exchange": instrument.get("exchange", ""),
                    "resolved_at": datetime.now().isoformat()
                }
                
                resolved_count += 1
                print(f"✓ {symbol} ({asset_type}): UIC {uic}")
                
            except Exception as e:
                unresolved_count += 1
                print(f"✗ {symbol} ({asset_type}): Resolution failed - {e}")
                raise ConfigurationError(f"Failed to resolve {symbol}: {e}")
        
        # Save updated cache
        if resolved_count > 0:
            self._save_instrument_cache()
        
        print(f"\n📊 Instrument Resolution Summary:")
        print(f"   Resolved: {resolved_count}")
        print(f"   Unresolved: {unresolved_count}")
        print(f"   Total: {len(self.watchlist)}")
        
        if unresolved_count > 0:
            raise ConfigurationError(
                f"Failed to resolve {unresolved_count} instrument(s). "
                "Please check errors above."
            )
    
    def get_instruments_by_asset_type(self, asset_type: str) -> List[Dict[str, Any]]:
        """
        Get instruments filtered by asset type.
        
        Args:
            asset_type: Asset type to filter (Stock, Etf, FxSpot, etc.)
        
        Returns:
            List of instrument dictionaries
        """
        return [
            inst for inst in self.watchlist 
            if inst.get("asset_type") == asset_type
        ]
    
    def get_stock_instruments(self) -> List[Dict[str, Any]]:
        """Get only stock instruments from watchlist."""
        return self.get_instruments_by_asset_type("Stock")
    
    def get_etf_instruments(self) -> List[Dict[str, Any]]:
        """Get only ETF instruments from watchlist."""
        return self.get_instruments_by_asset_type("Etf")
    
    def get_crypto_instruments(self) -> List[Dict[str, Any]]:
        """
        Get crypto instruments from watchlist.
        
        Returns both FxSpot and FxCrypto types (for compatibility with Saxo's transition).
        """
        crypto_fx = self.get_instruments_by_asset_type("FxSpot")
        crypto_native = self.get_instruments_by_asset_type("FxCrypto")
        
        # Filter FxSpot to only crypto (symbols ending in USD, EUR, etc.)
        crypto_pairs = []
        for inst in crypto_fx:
            symbol = inst.get("symbol", "")
            # Common crypto base currencies
            if any(symbol.upper().startswith(crypto) for crypto in ["BTC", "ETH", "LTC", "XRP", "ADA"]):
                crypto_pairs.append(inst)
        
        return crypto_pairs + crypto_native
    
    def get_instrument_by_symbol(self, symbol: str, asset_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get instrument by symbol (and optionally asset type).
        
        Args:
            symbol: Instrument symbol
            asset_type: Optional asset type filter
        
        Returns:
            Instrument dictionary or None if not found
        """
        for inst in self.watchlist:
            if inst.get("symbol", "").upper() == symbol.upper():
                if asset_type is None or inst.get("asset_type") == asset_type:
                    return inst
        return None
    
    def add_instrument(self, symbol: str, asset_type: str, uic: Optional[int] = None):
        """
        Add a new instrument to watchlist.
        
        Args:
            symbol: Instrument symbol
            asset_type: Asset type (Stock, Etf, FxSpot, etc.)
            uic: Optional UIC (will be resolved if not provided)
        
        Raises:
            ConfigurationError: If instrument already exists or invalid
        """
        # Check for duplicates
        existing = self.get_instrument_by_symbol(symbol, asset_type)
        if existing:
            raise ConfigurationError(
                f"Instrument already in watchlist: {symbol} ({asset_type})"
            )
        
        # Create instrument entry
        instrument = {
            "symbol": symbol.upper(),
            "asset_type": asset_type,
            "uic": uic
        }
        
        self.watchlist.append(instrument)
        
        # Resolve if UIC not provided
        if uic is None:
            print(f"Resolving new instrument: {symbol}")
            self.resolve_instruments()
    
    def remove_instrument(self, symbol: str, asset_type: Optional[str] = None):
        """
        Remove an instrument from watchlist.
        
        Args:
            symbol: Instrument symbol to remove
            asset_type: Optional asset type (for disambiguation)
        
        Raises:
            ConfigurationError: If instrument not found
        """
        instrument = self.get_instrument_by_symbol(symbol, asset_type)
        
        if not instrument:
            raise ConfigurationError(
                f"Instrument not found in watchlist: {symbol}"
            )
        
        self.watchlist.remove(instrument)
        print(f"✓ Removed {symbol} from watchlist")
    
    def get_watchlist_summary(self) -> Dict[str, Any]:
        """
        Get summary of watchlist configuration.
        
        Returns:
            Dictionary with watchlist details
        """
        stocks = self.get_stock_instruments()
        etfs = self.get_etf_instruments()
        crypto = self.get_crypto_instruments()
        
        resolved_count = sum(1 for inst in self.watchlist if inst.get("uic") is not None)
        
        return {
            "total_instruments": len(self.watchlist),
            "resolved": resolved_count,
            "unresolved": len(self.watchlist) - resolved_count,
            "by_asset_type": {
                "Stock": len(stocks),
                "Etf": len(etfs),
                "Crypto": len(crypto),
            },
            "instruments": [
                {
                    "symbol": inst.get("symbol"),
                    "asset_type": inst.get("asset_type"),
                    "uic": inst.get("uic"),
                    "resolved": inst.get("uic") is not None
                }
                for inst in self.watchlist
            ]
        }
```

### Environment Variable Configuration (Optional)

Add to `.env`:

```bash
# Optional: Custom watchlist as JSON
# If not set, uses default watchlist
# WATCHLIST_JSON=[{"symbol":"AAPL","asset_type":"Stock","uic":211},{"symbol":"BTCUSD","asset_type":"FxSpot","uic":12345}]
```

## Files to Modify
- `config/config.py` - Add structured watchlist with resolver
- `.env.example` - Add optional WATCHLIST_JSON variable
- `.gitignore` - Add `.cache/` directory

## Definition of Done
- [ ] Structured watchlist format implemented
- [ ] Instrument resolver queries `/ref/v1/instruments`
- [ ] Resolution results cached
- [ ] Handles ambiguous matches
- [ ] Supports Saxo CryptoFX format (no slash)
- [ ] Asset type filtering methods
- [ ] Add/remove instruments
- [ ] Validation ensures valid structure
- [ ] All tests pass

## Testing

### Test 1: Load Default Watchlist
```python
from config.config import Config

config = Config()
summary = config.get_watchlist_summary()

print(f"Total instruments: {summary['total_instruments']}")
print(f"Stocks: {summary['by_asset_type']['Stock']}")
print(f"Crypto: {summary['by_asset_type']['Crypto']}")
print(f"\nFirst 3 instruments:")
for inst in summary['instruments'][:3]:
    print(f"  - {inst['symbol']} ({inst['asset_type']}): UIC {inst['uic']}")
```

### Test 2: Resolve Instruments
```python
from config.config import Config

config = Config()
print("Resolving instruments (this will query Saxo API)...")
config.resolve_instruments()

summary = config.get_watchlist_summary()
print(f"\nResolved: {summary['resolved']}/{summary['total_instruments']}")
```

### Test 3: Filter by Asset Type
```python
from config.config import Config

config = Config()
config.resolve_instruments()

stocks = config.get_stock_instruments()
crypto = config.get_crypto_instruments()

print(f"Stocks ({len(stocks)}):")
for inst in stocks[:3]:
    print(f"  - {inst['symbol']}: UIC {inst['uic']}")

print(f"\nCrypto ({len(crypto)}):")
for inst in crypto:
    print(f"  - {inst['symbol']}: UIC {inst['uic']}")
```

### Test 4: Get Instrument by Symbol
```python
from config.config import Config

config = Config()
config.resolve_instruments()

aapl = config.get_instrument_by_symbol("AAPL", "Stock")
print(f"AAPL:")
print(f"  UIC: {aapl['uic']}")
print(f"  Asset Type: {aapl['asset_type']}")
print(f"  Description: {aapl.get('description', 'N/A')}")
```

### Test 5: Add Instrument
```python
from config.config import Config

config = Config()
initial_count = len(config.watchlist)

config.add_instrument("NVDA", "Stock")  # Will auto-resolve UIC

new_count = len(config.watchlist)
print(f"Instruments: {initial_count} → {new_count}")

nvda = config.get_instrument_by_symbol("NVDA")
print(f"NVDA UIC: {nvda['uic']}")
```

### Test 6: Crypto Format Validation
```python
from config.config import Config, ConfigurationError

config = Config()

# This should fail - wrong format
try:
    config.add_instrument("BTC/USD", "FxSpot")  # Wrong: has slash
except ConfigurationError as e:
    print(f"Expected error: {e}")

# This should succeed - correct format
config.add_instrument("BTCUSD", "FxSpot")  # Correct: no slash
print("✓ BTCUSD added successfully")
```

## Story Points
**Estimate:** 5 points

## Dependencies
- Story 002-001 completed (module structure)
- Story 002-002 completed (credentials + auth)
- Saxo REST client available

## Blocks
- Story 002-004 (trading settings need asset type awareness)
- Story 002-005 (validation needs instrument resolution)

## Instrument Resolution Best Practices
1. **Cache results** - Minimize API calls
2. **Handle ambiguity** - Multiple matches need manual specification
3. **Exact matching** - Prefer exact symbol matches when multiple found
4. **Error clarity** - Show available options when ambiguous
5. **Offline operation** - Use cache when network unavailable

## Saxo API Reference

### `/ref/v1/instruments` Query
```
GET /ref/v1/instruments?Keywords=AAPL&AssetTypes=Stock&IncludeNonTradable=false
```

Response:
```json
{
  "Data": [
    {
      "Uic": 211,
      "Symbol": "AAPL",
      "Description": "Apple Inc.",
      "AssetType": "Stock",
      "Exchange": {
        "ExchangeId": "NASDAQ"
      },
      "Tradable": true
    }
  ]
}
```

## Common Issues and Solutions

### Issue: "Instrument not found"
**Solution:** 
- Verify symbol spelling
- Check asset type is correct
- Confirm instrument available on Saxo platform

### Issue: "Ambiguous match: Multiple instruments found"
**Solution:** 
- Review list of matches printed in error
- Manually specify UIC in watchlist:
  ```python
  {"symbol": "SYMBOL", "asset_type": "Stock", "uic": 12345}
  ```

### Issue: "Invalid symbol format" with slash
**Solution:** Remove slash from crypto symbols:
- Wrong: `"BTC/USD"`
- Correct: `"BTCUSD"`

### Issue: Resolution fails with authentication error
**Solution:** 
- Verify token is valid: `config.get_access_token()`
- Check OAuth tokens haven't expired
- Run `python scripts/saxo_login.py` if needed

### Issue: Cache contains stale data
**Solution:** Force refresh:
```python
config.resolve_instruments(force_refresh=True)
```

## Architecture Notes
- **Structured Data:** Explicit AssetType + UIC eliminates ambiguity
- **Lazy Resolution:** UICs resolved on demand, not at initialization
- **Caching Layer:** Reduces API calls and enables offline operation
- **Runtime Mutability:** Watchlist loaded from config at startup; `add_instrument()`/`remove_instrument()` methods allow in-memory modifications during runtime (mutations are not persisted to `.env` - reload config to reset to original)
- **Type Safety:** Validation ensures structured format consistency

## CryptoFX Transition Handling
Saxo is transitioning CryptoFX from `FxSpot` to `FxCrypto` asset type.

**Current approach:**
- Use `FxSpot` for crypto (BTCUSD, ETHUSD)
- Accept both `FxSpot` and `FxCrypto` in validation
- Filter `get_crypto_instruments()` to recognize both types
- Monitor Saxo release notes for migration timeline

**When to update:**
- Check [Saxo Release Notes](https://www.developer.saxo/openapi/releasenotes/completed-planned-changes)
- Update default watchlist when `FxCrypto` becomes standard
- Keep backward compatibility during transition

## Future Enhancements (Not in this story)
- Bulk instrument lookup optimization
- Instrument metadata enrichment (sector, market cap, etc.)
- Dynamic watchlist from market scanners
- Watchlist presets (top gainers, sector ETFs, etc.)
- Cross-exchange resolution
- Real-time tradability checking

## References
- Parent Epic: `docs/epics/epic-002-configuration-module.md`
- [Saxo Instrument Search Guide](https://openapi.help.saxo/hc/en-us/articles/6076270868637-Why-can-I-not-find-an-instrument)
- [Saxo Order Placement](https://www.developer.saxo/openapi/learn/order-placement)
- [Saxo CryptoFX Guide](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)
- [Saxo Release Notes](https://www.developer.saxo/openapi/releasenotes/completed-planned-changes)

## Success Criteria
✅ Story is complete when:
1. Structured watchlist format implemented
2. Instrument resolver queries API correctly
3. Resolution results cached efficiently
4. Ambiguous matches handled with clear errors
5. Saxo CryptoFX format supported (no slash)
6. Asset type filtering methods working
7. Add/remove instruments functional
8. Validation ensures correct structure
9. All verification tests pass
10. Documentation complete with examples
