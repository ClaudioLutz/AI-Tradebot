# Asset Type Vocabulary - Canonical Mapping

**Purpose:** Define canonical asset type vocabulary used consistently across all epics (002, 003, 004, 005)

**Last Updated:** 2025-12-13

## Overview

This document establishes the normalized asset type taxonomy used throughout the trading bot system. All modules must use these canonical types to ensure consistency from configuration → data retrieval → strategy execution.

## Canonical Asset Types

```python
from enum import Enum

class AssetType(str, Enum):
    """
    Normalized asset types used across all modules.
    
    These types align with Saxo Bank's AssetType taxonomy but use
    consistent naming across our internal system.
    """
    # Equities
    STOCK = "Stock"
    ETF = "Etf"
    FUND = "MutualFund"
    
    # Foreign Exchange
    FX_SPOT = "FxSpot"
    FX_FORWARD = "FxForwards"
    CRYPTO_FX = "CryptoFx"  # Crypto-denominated FX (e.g., BTCUSD)
    
    # Derivatives
    OPTION = "StockOption"
    FUTURES = "Futures"
    
    # CFDs (Contracts for Difference)
    CFD_INDEX = "CfdIndex"
    CFD_STOCK = "StockCfdOnPhysicalShares"
    
    # Fixed Income
    BOND = "Bond"
```

## Saxo Bank AssetType Mapping

Map Saxo's `AssetType` field to our canonical types:

```python
SAXO_TO_INTERNAL_ASSET_TYPE = {
    # Equities
    "Stock": AssetType.STOCK,
    "Etf": AssetType.ETF,
    "MutualFund": AssetType.FUND,
    
    # Foreign Exchange
    "FxSpot": AssetType.FX_SPOT,
    "FxForwards": AssetType.FX_FORWARD,
    "CryptoFx": AssetType.CRYPTO_FX,
    
    # Derivatives
    "StockOption": AssetType.OPTION,
    "ContractFutures": AssetType.FUTURES,
    
    # CFDs
    "CfdOnIndex": AssetType.CFD_INDEX,
    "CfdOnFuturesFutures": AssetType.FUTURES,  # Saxo treats this as futures
    "StockCfdOnPhysicalShares": AssetType.CFD_STOCK,
    
    # Fixed Income
    "Bond": AssetType.BOND,
}

def normalize_saxo_asset_type(saxo_asset_type: str) -> AssetType:
    """
    Convert Saxo AssetType to canonical internal type.
    
    Args:
        saxo_asset_type: AssetType value from Saxo API response
    
    Returns:
        Canonical AssetType enum value
    
    Raises:
        ValueError: If saxo_asset_type is not recognized
    """
    if saxo_asset_type not in SAXO_TO_INTERNAL_ASSET_TYPE:
        raise ValueError(
            f"Unknown Saxo AssetType: {saxo_asset_type}. "
            f"Known types: {list(SAXO_TO_INTERNAL_ASSET_TYPE.keys())}"
        )
    return SAXO_TO_INTERNAL_ASSET_TYPE[saxo_asset_type]
```

## Asset Type Characteristics

### Trading Hours

| Asset Type | Typical Trading Hours | Saxo Market State Behavior |
|------------|----------------------|---------------------------|
| `STOCK` | Exchange hours (e.g., 9:30-16:00 ET for US) | MarketState = Open/Closed |
| `ETF` | Exchange hours | MarketState = Open/Closed |
| `FX_SPOT` | 24/5 (Sunday evening - Friday evening) | MarketState = Open/Closed |
| `CRYPTO_FX` | **Weekdays only** (NOT 24/7) | MarketState = Open/Closed |
| `FUTURES` | Exchange hours + extended sessions | MarketState = Open/Closed |
| `CFD_*` | Depends on underlying asset | MarketState = Open/Closed |

**Important:** CryptoFX trades weekdays only in Saxo, despite common assumption of 24/7 trading.

**Reference:** [Saxo Developer Portal - Crypto FX](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)

### Data Availability in SIM vs LIVE

| Asset Type | SIM Environment | LIVE Environment |
|------------|-----------------|------------------|
| `FX_SPOT` | Real-time | Real-time |
| `FX_FORWARD` | Real-time | Real-time |
| `STOCK` | **Delayed** (15-20 min) | Real-time (with subscription) |
| `ETF` | **Delayed** (15-20 min) | Real-time (with subscription) |
| `OPTION` | **Delayed** | Real-time (with subscription) |
| `CFD_*` | **Delayed** | Real-time (with subscription) |

**Important:** In SIM environment, non-FX instruments are delayed. This is expected and acceptable for testing.

**References:**
- [Saxo - Delayed vs Live Prices](https://openapi.help.saxo/hc/en-us/articles/4405160701085)
- [Saxo - Why are quotes delayed?](https://openapi.help.saxo/hc/en-us/articles/4416934340625)

### Extended Trading Hours Support

| Asset Type | Extended Hours Support | Notes |
|------------|----------------------|-------|
| `STOCK` | Yes (eligible US stocks) | Pre-market and after-hours, typically limit-order only |
| `ETF` | Yes (eligible US ETFs) | Limited liquidity |
| `FX_SPOT` | N/A (24/5 market) | Not applicable |
| `CRYPTO_FX` | No (weekday regular hours) | Not available |
| `FUTURES` | Depends on contract | Some contracts have extended sessions |

**Reference:** [Saxo Extended Trading Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589)

## Usage Across Epics

### Epic 002: Configuration Module

**Watchlist validation:**
```python
from docs.ASSET_TYPE_VOCABULARY import AssetType

def validate_watchlist_instrument(instrument: dict):
    """Validate instrument configuration."""
    asset_type_str = instrument.get("asset_type")
    
    # Validate against canonical enum
    try:
        asset_type = AssetType(asset_type_str)
    except ValueError:
        valid_types = [t.value for t in AssetType]
        raise ValueError(
            f"Invalid asset_type '{asset_type_str}'. "
            f"Valid types: {valid_types}"
        )
    
    return asset_type
```

### Epic 003: Market Data Retrieval

**Normalization from Saxo response:**
```python
from docs.ASSET_TYPE_VOCABULARY import normalize_saxo_asset_type, AssetType

def normalize_instrument_data(saxo_response: dict) -> dict:
    """Normalize Saxo instrument data to internal format."""
    saxo_asset_type = saxo_response["AssetType"]
    
    # Map to canonical type
    asset_type = normalize_saxo_asset_type(saxo_asset_type)
    
    return {
        "instrument_id": f"{asset_type.value}:{saxo_response['Uic']}",
        "asset_type": asset_type.value,  # Use canonical string value
        "uic": saxo_response["Uic"],
        "symbol": saxo_response["Symbol"],
        # ... other fields
    }
```

### Epic 004: Trading Strategy System

**Asset-specific strategy logic:**
```python
from docs.ASSET_TYPE_VOCABULARY import AssetType

def generate_signals(self, market_data: dict) -> dict:
    """Generate signals with asset-specific logic."""
    signals = {}
    
    for instrument_id, data in market_data.items():
        asset_type = AssetType(data["asset_type"])
        
        # Asset-specific thresholds
        if asset_type in [AssetType.STOCK, AssetType.ETF]:
            threshold_bps = 50  # Equities: 0.5% threshold
        elif asset_type in [AssetType.FX_SPOT, AssetType.CRYPTO_FX]:
            threshold_bps = 20  # FX: 0.2% threshold (higher volatility)
        elif asset_type in [AssetType.CFD_INDEX, AssetType.CFD_STOCK]:
            threshold_bps = 40  # CFDs: 0.4% threshold
        else:
            threshold_bps = 50  # Default
        
        # Generate signal with asset-specific parameters...
```

### Epic 005: Trade Execution Module

**Order validation by asset type:**
```python
from docs.ASSET_TYPE_VOCABULARY import AssetType

def validate_order_for_asset_type(order: dict, asset_type: AssetType):
    """Validate order parameters against asset type constraints."""
    
    # Extended hours validation
    if order.get("use_extended_hours"):
        if asset_type not in [AssetType.STOCK, AssetType.ETF]:
            raise ValueError(
                f"Extended hours not supported for {asset_type.value}"
            )
    
    # Order type validation
    if asset_type == AssetType.CRYPTO_FX:
        if order["order_type"] not in ["LIMIT", "MARKET"]:
            raise ValueError(
                f"CryptoFX only supports LIMIT or MARKET orders"
            )
    
    # Minimum order size by asset type...
```

## Testing

### Example Test Case
```python
import pytest
from docs.ASSET_TYPE_VOCABULARY import AssetType, normalize_saxo_asset_type

def test_saxo_mapping():
    """Test Saxo AssetType mapping to canonical types."""
    assert normalize_saxo_asset_type("Stock") == AssetType.STOCK
    assert normalize_saxo_asset_type("FxSpot") == AssetType.FX_SPOT
    assert normalize_saxo_asset_type("CryptoFx") == AssetType.CRYPTO_FX

def test_unknown_asset_type():
    """Test error handling for unknown asset type."""
    with pytest.raises(ValueError, match="Unknown Saxo AssetType"):
        normalize_saxo_asset_type("UnknownType")

def test_asset_type_enum():
    """Test AssetType enum values."""
    assert AssetType.STOCK.value == "Stock"
    assert AssetType.FX_SPOT.value == "FxSpot"
    assert AssetType.CRYPTO_FX.value == "CryptoFx"
```

## Implementation Location

Place the canonical `AssetType` enum and mapping in a shared location:

```
config/
├── __init__.py
├── asset_types.py  # New: Canonical AssetType enum and mappings
├── config.py
└── settings.py
```

**File:** `config/asset_types.py`

This makes it accessible to all modules without circular dependencies.

## Migration Notes

When implementing across epics:

1. **Epic 002 (Config):** Update watchlist validation to use `AssetType` enum
2. **Epic 003 (Data):** Add `normalize_saxo_asset_type()` to normalization pipeline
3. **Epic 004 (Strategy):** Import `AssetType` for asset-specific logic
4. **Epic 005 (Execution):** Use `AssetType` for order validation

Ensure all string comparisons use canonical enum values (not ad-hoc strings).

## References

1. [Saxo OpenAPI - Asset Types](https://www.developer.saxo/openapi/learn)
2. [Saxo OpenAPI - Crypto FX](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)
3. [Saxo - Delayed vs Live Prices](https://openapi.help.saxo/hc/en-us/articles/4405160701085)
4. [Saxo - Extended Trading Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589)

---

**Status:** Ready for implementation  
**Next Step:** Create `config/asset_types.py` with canonical enum and mapping
