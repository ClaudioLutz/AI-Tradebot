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
        
        if not name:
            results.append({
                "name": "Unknown",
                "asset_type": asset_type,
                "uic": None,
                "details": None,
                "status": "error",
                "error": "Missing instrument name"
            })
            continue
        
        try:
            uic = find_instrument_uic(name, asset_type)
            if uic is None:
                raise InstrumentNotFoundError(f"No UIC found for {name}")
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
