# Story 001-2-007: Update Market Data Module for UIC-based Instruments

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to update the market data module to work with Saxo's UIC-based instrument system instead of Alpaca's symbol-based system so that the application can retrieve pricing data for trading.

## Description
Modify `data/market_data.py` to use Saxo's instrument discovery (`ref/v1/instruments`) and implement functions to find UICs by keyword and retrieve pricing information. This replaces Alpaca's direct symbol lookup.

## Prerequisites
- Story 001-2-005 completed (Saxo client available)
- Story 001-2-009 completed (watchlist format updated) - may be done in parallel

## Acceptance Criteria
- [ ] Alpaca-specific code removed from `market_data.py`
- [ ] Instrument discovery by keyword implemented
- [ ] UIC lookup function created
- [ ] Functions accept UIC + AssetType parameters
- [ ] Error handling for instrument not found
- [ ] Code documented with examples
- [ ] Module can be imported without errors

## Technical Details

### Current Implementation (Alpaca)
- Uses Alpaca SDK methods
- Symbol-based lookup (e.g., "AAPL")
- Direct bar data retrieval

### New Implementation (Saxo)
Key changes:
1. **Instrument Discovery:** Use `/ref/v1/instruments` to find UIC
2. **Pricing:** Prepare for trade pricing endpoints
3. **Asset Types:** Support Stock, FxSpot, FxCrypto, etc.
4. **Data Structure:** Store (UIC, AssetType, Symbol) tuples

### Saxo Instrument Discovery
- Endpoint: `GET /ref/v1/instruments`
- Parameters: `Keywords`, `AssetTypes`
- Returns: List of matching instruments with UICs

## Implementation

### Complete Updated market_data.py

```python
"""
Market Data Module - Saxo Bank Integration
Handles instrument discovery and market data retrieval.
"""
from data.saxo_client import SaxoClient, SaxoAPIError
from typing import Dict, List, Optional, Any


class InstrumentNotFoundError(Exception):
    """Raised when instrument cannot be found."""
    pass


class MarketDataError(Exception):
    """Raised when market data retrieval fails."""
    pass


def find_instruments(
    keyword: str,
    asset_types: str = "Stock",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for instruments by keyword.
    
    Args:
        keyword: Search term (e.g., "AAPL", "Apple", "BTCUSD")
        asset_types: Comma-separated asset types (e.g., "Stock", "FxSpot")
        limit: Maximum number of results to return
    
    Returns:
        List of instrument dictionaries containing UIC, Symbol, Description, etc.
    
    Raises:
        MarketDataError: If search fails
    
    Example:
        >>> instruments = find_instruments("AAPL", "Stock")
        >>> print(instruments[0]['Identifier'])  # UIC
        211
    """
    client = SaxoClient()
    
    try:
        params = {
            "Keywords": keyword,
            "AssetTypes": asset_types,
            "limit": limit
        }
        
        response = client.get("/ref/v1/instruments", params=params)
        
        # Extract instrument data
        instruments = []
        if isinstance(response, dict):
            instruments = response.get("Data", [])
        elif isinstance(response, list):
            instruments = response
        
        return instruments
    
    except SaxoAPIError as e:
        raise MarketDataError(f"Instrument search failed: {e}")


def find_instrument_uic(
    keyword: str,
    asset_type: str = "Stock"
) -> Optional[int]:
    """
    Find the UIC (Universal Instrument Code) for an instrument.
    
    Args:
        keyword: Search term (e.g., "AAPL", "BTCUSD")
        asset_type: Asset type (Stock, FxSpot, FxCrypto, etc.)
    
    Returns:
        UIC (integer) if found, None otherwise
    
    Raises:
        InstrumentNotFoundError: If no matching instrument found
        MarketDataError: If search fails
    
    Example:
        >>> uic = find_instrument_uic("AAPL", "Stock")
        >>> print(uic)
        211
    """
    instruments = find_instruments(keyword, asset_type, limit=5)
    
    if not instruments:
        raise InstrumentNotFoundError(
            f"No instrument found for '{keyword}' with AssetType '{asset_type}'"
        )
    
    # Return the first match's UIC
    first_match = instruments[0]
    return first_match.get("Identifier")


def get_instrument_details(
    uic: int,
    asset_type: str
) -> Dict[str, Any]:
    """
    Get detailed information about an instrument.
    
    Args:
        uic: Universal Instrument Code
        asset_type: Asset type (Stock, FxSpot, etc.)
    
    Returns:
        Dictionary with instrument details
    
    Raises:
        MarketDataError: If retrieval fails
    
    Example:
        >>> details = get_instrument_details(211, "Stock")
        >>> print(details['Symbol'])
        AAPL:xnas
    """
    client = SaxoClient()
    
    try:
        params = {
            "Uics": uic,
            "AssetTypes": asset_type
        }
        
        response = client.get("/ref/v1/instruments/details", params=params)
        
        # Extract first instrument detail
        if isinstance(response, dict):
            data = response.get("Data", [])
            if data:
                return data[0]
        
        raise MarketDataError(f"No details found for UIC {uic}")
    
    except SaxoAPIError as e:
        raise MarketDataError(f"Failed to get instrument details: {e}")


def discover_watchlist_instruments(
    symbols: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Discover UICs for a list of symbols.
    
    Args:
        symbols: List of dicts with 'name' and 'asset_type' keys
        
    Returns:
        List of dicts with 'name', 'asset_type', 'uic', 'details'
    
    Example:
        >>> watchlist = [
        ...     {"name": "AAPL", "asset_type": "Stock"},
        ...     {"name": "BTCUSD", "asset_type": "FxSpot"}
        ... ]
        >>> discovered = discover_watchlist_instruments(watchlist)
        >>> for item in discovered:
        ...     print(f"{item['name']}: UIC {item['uic']}")
    """
    results = []
    
    for symbol_info in symbols:
        name = symbol_info.get("name")
        asset_type = symbol_info.get("asset_type", "Stock")
        
        try:
            uic = find_instrument_uic(name, asset_type)
            details = get_instrument_details(uic, asset_type)
            
            results.append({
                "name": name,
                "asset_type": asset_type,
                "uic": uic,
                "details": details,
                "status": "found"
            })
            
        except (InstrumentNotFoundError, MarketDataError) as e:
            results.append({
                "name": name,
                "asset_type": asset_type,
                "uic": None,
                "details": None,
                "status": "error",
                "error": str(e)
            })
    
    return results


# Placeholder for future pricing implementation
def get_instrument_price(uic: int, asset_type: str) -> Optional[float]:
    """
    Get current price for an instrument (placeholder).
    
    Note: This is a placeholder. Full implementation requires
    trade pricing endpoints or streaming subscriptions.
    
    Args:
        uic: Universal Instrument Code
        asset_type: Asset type
    
    Returns:
        Price as float, or None if unavailable
    
    TODO: Implement using Saxo trade pricing endpoints
    """
    # Placeholder - will be implemented in a future story
    # when we integrate trade pricing or info prices
    raise NotImplementedError(
        "Price retrieval not yet implemented. "
        "Will be added in a future story with trade pricing integration."
    )


# Module-level information
__version__ = "2.0.0"
__api__ = "Saxo OpenAPI"

print(f"Market Data Module v{__version__} ({__api__}) loaded")
```

## Files to Modify
- `data/market_data.py` - Complete rewrite for Saxo

## Verification Steps
- [ ] File updated successfully
- [ ] No syntax errors
- [ ] Can import module
- [ ] Alpaca code removed
- [ ] Functions properly documented
- [ ] Type hints included

## Testing

### Test 1: Module Import
```python
from data import market_data
print("Module imported successfully")
```

Expected: No errors

### Test 2: Find Instruments
```python
from data.market_data import find_instruments

results = find_instruments("AAPL", "Stock", limit=3)
print(f"Found {len(results)} instruments")
for inst in results:
    print(f"  {inst.get('Symbol')}: UIC {inst.get('Identifier')}")
```

Expected: Lists AAPL instruments with UICs

### Test 3: Find Specific UIC
```python
from data.market_data import find_instrument_uic

try:
    uic = find_instrument_uic("AAPL", "Stock")
    print(f"AAPL UIC: {uic}")
except Exception as e:
    print(f"Error: {e}")
```

Expected: Returns UIC (likely 211 for AAPL)

### Test 4: Get Instrument Details
```python
from data.market_data import get_instrument_details

details = get_instrument_details(211, "Stock")
print(f"Symbol: {details.get('Symbol')}")
print(f"Description: {details.get('Description')}")
```

Expected: Displays Apple stock details

### Test 5: Watchlist Discovery
```python
from data.market_data import discover_watchlist_instruments

watchlist = [
    {"name": "AAPL", "asset_type": "Stock"},
    {"name": "MSFT", "asset_type": "Stock"}
]

results = discover_watchlist_instruments(watchlist)
for item in results:
    if item['status'] == 'found':
        print(f"✓ {item['name']}: UIC {item['uic']}")
    else:
        print(f"✗ {item['name']}: {item['error']}")
```

Expected: Shows UICs for each symbol

## Documentation

### Important Notes in Code
- Document UIC concept clearly
- Explain AssetType importance
- Note crypto AssetType transition (FxSpot vs FxCrypto)
- Provide examples for common use cases
- Mark pricing function as placeholder

### Crypto Asset Types
Include note about Saxo's crypto transition:
```python
# Note: Saxo is transitioning crypto pairs from FxSpot to FxCrypto
# Known affected UICs: BTCUSD (21700189), ETHUSD (21750301)
# Code should handle both asset types for crypto instruments
```

## Time Estimate
**1 hour** (implement + test + document)

## Dependencies
- Story 001-2-005 completed (Saxo client)
- Story 001-2-009 may be done in parallel (watchlist format)

## Blocks
- Story 001-2-009 (needs this for watchlist validation)
- Story 001-2-010 (integration testing)

## Future Enhancements (Not in this story)
- Price retrieval via trade pricing endpoints
- Streaming price subscriptions
- Historical data retrieval
- Caching of instrument lookups
- Batch instrument queries

## Common UICs for Testing
Document common test UICs:
- **AAPL (Stock):** UIC 211
- **BTCUSD (FxSpot/FxCrypto):** UIC 21700189
- **ETHUSD (FxSpot/FxCrypto):** UIC 21750301
- **EURUSD (FxSpot):** UIC 21

Note: UICs may vary by account/region - always discover via API

## Migration Notes

### Key Differences from Alpaca
| Aspect | Alpaca | Saxo |
|--------|--------|------|
| Identification | Symbol string | UIC + AssetType |
| Lookup | Direct | Search via API |
| Pricing | Bar data | Trade pricing/info prices |
| Asset Types | Limited | Comprehensive |

## Asset Type Reference
Common Saxo asset types:
- `Stock` - Equities
- `FxSpot` - Forex pairs (and legacy crypto)
- `FxCrypto` - Crypto pairs (new)
- `CfdOnIndex` - Index CFDs
- `Bond` - Bonds
- `FxForwards` - FX forwards

## Error Handling

### Common Errors
1. **Instrument Not Found:** Invalid symbol or asset type
2. **Multiple Matches:** Keyword too generic
3. **API Errors:** Network, authentication, rate limits

### Error Messages
Provide helpful error messages:
- Include the searched keyword
- Suggest checking asset type
- Reference documentation

## References
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 7)
- [Saxo Reference Data API](https://www.developer.saxo/openapi/referencedocs/ref/)
- [Saxo Instruments Endpoint](https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments)

## Success Criteria
✅ Story is complete when:
1. `market_data.py` updated for Saxo
2. All Alpaca code removed
3. Instrument discovery working
4. UIC lookup functional
5. Watchlist discovery implemented
6. All verification tests pass
7. Code well-documented
8. Module imports without errors
