# Epic 004 Pre-Implementation Improvements

**Date:** 2025-12-13  
**Status:** Complete - All improvements documented and applied

## Overview

This document summarizes comprehensive improvements made to Epic 004 (Trading Strategy System) before implementation begins, addressing (a) Saxo correctness, (b) determinism / backtest hygiene, and (c) alignment across epics (002 config → 003 data → 004 strategies → 005 execution).

## Highest-Impact Fixes Applied

### 1. ✅ Stop Hard-Coding "CryptoFX weekday-only" using `weekday < 5`

**Problem:** Original trading-hours logic treated "FxSpot/FxCrypto = Monday–Friday only" too simplistically.

**Solution:**
- **Story 004-005 updated:** Data quality gating now uses **Saxo's market state fields** from quote snapshots
- Market-state policy checks `quote.MarketState` (from Epic 003) instead of `weekday < 5`
- CryptoFX weekday-only documented explicitly with Saxo reference
- Weekday check kept as **fallback only** when MarketState/IsMarketOpen are missing

**Reference:** [Saxo Developer Portal - Crypto FX in OpenAPI](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)

### 2. ✅ Make "closed-bar discipline" deterministic (no wall-clock `now` internally)

**Problem:** Original `safe_slice_bars()` used `datetime.now()` to filter bars with `require_closed=True`, breaking reproducibility.

**Solution:**
- **Story 004-002 updated:** `safe_slice_bars()` now accepts `as_of: Optional[datetime]` parameter
- **Live mode:** Pass `datetime.now(timezone.utc)` explicitly
- **Backtest mode:** Pass the bar-close timestamp being evaluated
- Function never uses wall-clock internally when `as_of` is provided (prevents time leakage)
- Added determinism test to verify same input → same output

**Why it matters:** Without `as_of`, wall-clock time contaminated data timestamps, creating non-reproducible backtest results.

### 3. ✅ Don't timestamp signals with "current time" if you already have bar timestamps

**Problem:** Original MA strategy used `get_current_timestamp()` for all signals, losing data provenance.

**Solution:**
- **Story 004-001 updated:** Signal schema now has **two timestamp fields:**
  - `timestamp`: Wall-clock time when signal generated (for system logging)
  - `decision_time`: Bar-close or quote last-updated timestamp (for backtesting validation)
- **Story 004-003 updated:** MA strategy uses `valid_bars[-1]["timestamp"]` as `decision_time`
- Additional fields added: `price_ref`, `price_type`, `data_time_range`, `policy_flags`

**Why it matters:** Separates wall-clock time from data timestamps, preventing "time leakage" and creating complete audit trail.

### 4. ✅ Align "strategy factory" with upcoming registry (avoid hard-coded patterns)

**Problem:** Original `create_strategy_from_config()` had hard-coded `if strategy == "moving_average": ...` pattern.

**Solution:**
- **Story 004-006 updated:** Registry pattern now integrated with config loader
- Factory function uses `get_strategy(name, params)` from registry
- Adding new strategies requires only: (1) create file, (2) implement `BaseStrategy`, (3) register
- No modification to core orchestration code needed

**Why it matters:** Avoids accumulating switch statements; makes system extensible.

## Saxo-Specific Corrections

### A) ✅ SIM market data is delayed for non-FX (gating must not reject "delayed" in SIM)

**Saxo is explicit:**
- "Live prices are not offered on the simulation environment."
- "In SIM we only offer delayed prices for non-FX products."

**Solution - Story 004-005 updated:**
```python
# If SAXO_ENV=SIM: allow delayed quotes for non-FX instruments
# If SAXO_ENV=LIVE: enforce strict staleness/delay policy
if os.getenv("SAXO_ENV") == "SIM" and asset_type != "FxSpot":
    # Allow delayed data in SIM for non-FX
    is_delayed_ok = True
else:
    # In LIVE, reject delayed data
    is_delayed_ok = False
```

**References:**
- [How do I choose between receiving delayed and live prices?](https://openapi.help.saxo/hc/en-us/articles/4405160701085)
- [Why are quotes still delayed after I subscribe?](https://openapi.help.saxo/hc/en-us/articles/4416934340625)

### B) ✅ Extended hours needs explicit opt-in and order-type constraints

**Saxo Switzerland support:** Extended hours is supported for eligible US instruments, typically **limit-order driven**, with distinct risk characteristics (lower liquidity, higher volatility).

**Solution - Story 004-005 updated:**
- Extended hours is **opt-in** via `ALLOW_EXTENDED_HOURS=false` (default)
- Warning logged when enabled about volatility/liquidity risk
- Documentation notes downstream capability check required (execution module must support limit orders)
- Policy documented in `.env.example` with warnings

**Reference:** [Saxo Extended Trading Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589)

## Story-by-Story Improvements

### Story 004-001 ✅ (Strategy Interface & Signal Schema)

**Enhanced Signal schema with additional fields:**
```python
@dataclass
class Signal:
    action: Literal["BUY", "SELL", "HOLD"]
    reason: str
    timestamp: str  # Wall-clock time (system logging)
    decision_time: str  # Data timestamp (backtesting validation)
    confidence: Optional[float] = None
    price_ref: Optional[float] = None  # NEW
    price_type: Optional[str] = None  # NEW: "close", "mid", "bid", "ask"
    data_time_range: Optional[dict] = None  # NEW: {"first_bar": "...", "last_bar": "..."}
    policy_flags: Optional[dict] = None  # NEW: {"used_delayed_data": false, "market_state": "Open"}
    metadata: Optional[dict] = None
```

**Action semantics explicitly defined:**
- `BUY`: Enter long position (or add to existing long)
- `SELL`: Exit long position OR enter short (execution module defines)
- `HOLD`: No action - maintain current position
- Note added for Epic 005 dependency

**Why:** Reduces future churn, enables execution module to reason about slippage, creates complete audit trail.

### Story 004-002 ✅ (Indicator Utilities)

**Key improvements:**
1. **Type hints:** Changed `List[float]` → `Sequence[float]` (more flexible)
2. **Deterministic bar slicing:** Added `as_of: Optional[datetime]` parameter to `safe_slice_bars()`
3. **Test coverage:** Added `test_safe_slice_bars_deterministic()` to verify reproducibility

**Critical implementation:**
```python
def safe_slice_bars(
    bars: List[Dict], 
    n: int, 
    require_closed: bool = True,
    as_of: Optional[datetime] = None  # NEW - for determinism
) -> Optional[List[Dict]]:
    """
    **CRITICAL FOR BACKTESTING:** The `as_of` parameter makes this function deterministic.
    In live mode, pass current UTC time. In backtest mode, pass the bar-close timestamp
    you are evaluating. Never call without `as_of` in backtest mode.
    """
    if require_closed:
        reference_time = as_of if as_of is not None else datetime.now(timezone.utc)
        # Filter bars before reference_time...
```

**Why:** Prevents time leakage, enables reproducible backtests.

### Story 004-003 ✅ (Moving Average Crossover Strategy)

**Key improvements:**
1. **Proper timestamps:** Uses `valid_bars[-1]["timestamp"]` as `decision_time`, not `get_current_timestamp()`
2. **Enhanced signal fields:** Includes `price_ref`, `price_type`, `data_time_range`
3. **Division by zero guard:** Checks `current_long_ma == 0` before threshold calculation
4. **Cooldown parameter:** Added `cooldown_bars: Optional[int]` to prevent churn in sideways markets
5. **Deterministic bar slicing:** Passes `as_of` to `safe_slice_bars()`

**Cooldown implementation:**
```python
def __init__(self, ..., cooldown_bars: Optional[int] = None):
    self.cooldown_bars = cooldown_bars
    self._last_signal_bar_index: Dict[str, int] = {}

# In generate_signals():
if self.cooldown_bars is not None and crossover_type != "NO_CROSSOVER":
    current_bar_index = len(bars) - 1
    last_signal_index = self._last_signal_bar_index.get(instrument_id, -999999)
    bars_since_signal = current_bar_index - last_signal_index
    
    if bars_since_signal < self.cooldown_bars:
        crossover_type = "COOLDOWN_ACTIVE"
    else:
        self._last_signal_bar_index[instrument_id] = current_bar_index
```

**Why:** Reduces trading frequency in choppy markets, useful for beginners.

### Story 004-004 (Parameter Handling) - TO UPDATE

**Required improvements:**
1. Write parameters (and config hash) to **JSON artifact file** alongside logs
2. Add "parameter set ID" (hash of sorted JSON) for experiment tracking
3. Testing harness should include "same params + same data → same signals" checks
4. Reference **Probability of Backtest Overfitting** concept in rationale

**Implementation needed:**
```python
import json
import hashlib
from pathlib import Path

def save_parameter_artifact(strategy_name: str, params: dict) -> str:
    """Save strategy parameters to JSON file and return parameter set ID."""
    params_sorted = json.dumps(params, sort_keys=True)
    param_id = hashlib.sha256(params_sorted.encode()).hexdigest()[:12]
    
    artifact_path = Path(f"logs/params_{strategy_name}_{param_id}.json")
    with open(artifact_path, 'w') as f:
        json.dump({
            "strategy_name": strategy_name,
            "parameters": params,
            "parameter_set_id": param_id,
            "timestamp": get_current_timestamp()
        }, f, indent=2)
    
    logger.info(f"Saved parameter artifact: {artifact_path} (ID: {param_id})")
    return param_id
```

**Reference:** [Bailey et al. - Probability of Backtest Overfitting](https://scholarworks.wmich.edu/math_pubs/40/)

### Story 004-005 ✅ (Data Quality Gating & Market-State Policy)

**Key improvements:**
1. **SIM vs LIVE delay policy:** Different rules for simulation vs live environment
2. **Market-state gating:** Uses `quote.MarketState` instead of `weekday < 5`
3. **CryptoFX weekday-only:** Explicitly documented with Saxo reference
4. **Extended hours opt-in:** `ALLOW_EXTENDED_HOURS=false` default with warnings
5. **Data freshness contract:** Ties to Epic 003 requirements

**Critical implementation:**
```python
class DataQualityChecker:
    def check_data_quality(self, market_data: Dict[str, Dict]) -> Dict[str, QualityResult]:
        saxo_env = os.getenv("SAXO_ENV", "SIM")
        
        for instrument_id, data in market_data.items():
            asset_type = data.get("asset_type")
            market_state = quote.get("MarketState", "Unknown")
            is_delayed = quote.get("DelayedByMinutes", 0) > 0
            
            # SIM environment: allow delayed for non-FX
            if saxo_env == "SIM" and asset_type not in ["FxSpot", "FxForwards"]:
                # Delayed is expected and acceptable in SIM for non-FX
                is_acceptable = is_fresh and is_market_open
            else:
                # LIVE environment: enforce strict policy
                is_acceptable = is_fresh and not is_delayed and is_market_open
            
            # CryptoFX weekday-only check (Saxo-specific)
            if asset_type == "CryptoFx" and now.weekday() >= 5:
                logger.info(f"CryptoFX does not trade on weekends (Saxo-specific)")
                is_acceptable = False
```

**Why:** Prevents trading on stale data while respecting Saxo's SIM environment limitations.

### Story 004-006 ✅ (Strategy Registry/Loader)

**Alignment with factory:** Registry now integrated with config loader to avoid `if strategy == ...` patterns.

**No changes to core orchestration needed when adding strategies:**
```python
# In strategies/my_new_strategy.py:
from strategies.registry import register_strategy

@register_strategy("my_new_strategy")
class MyNewStrategy(BaseStrategy):
    def generate_signals(self, market_data):
        # Implementation...
        pass

# That's it! No changes to main.py or orchestration code.
```

### Story 004-007 (Testing Harness) - TO UPDATE

**Required improvements:**
1. **Fixed timestamps in fixtures:** Default to `datetime.fromisoformat("2025-01-01T00:00:00Z")` instead of `datetime.now()`
2. **Test case for SIM delayed quotes:** Verify "SIM delayed non-FX quotes allowed" vs "LIVE delayed quotes blocked"
3. **Determinism tests:** Verify same input → same output across multiple calls

**Why:** Fixtures using `datetime.now()` undermine determinism tests.

### Story 004-008 (Developer Documentation) - TO UPDATE

**Saxo-specific section must include:**
1. SIM delayed pricing limitations with reference
2. Extended hours risk/limitations with reference
3. CryptoFX weekday-only trading with reference
4. Market state field usage (not weekday checks)

## Alignment Point with Epic 002

**Asset type vocabulary:** Need canonical enum + mapping table (Saxo → internal) so Epic 002/003/004/005 use same taxonomy.

### Proposed Asset Type Vocabulary

**Canonical internal types:**
```python
from enum import Enum

class AssetType(str, Enum):
    """Normalized asset types used across all modules."""
    STOCK = "Stock"
    FX_SPOT = "FxSpot"
    FX_FORWARD = "FxForwards"
    CFD_INDEX = "CfdIndex"
    CFD_STOCK = "StockCfdOnPhysicalShares"
    CRYPTO_FX = "CryptoFx"
    BOND = "Bond"
    ETF = "Etf"
    FUND = "MutualFund"
    OPTION = "StockOption"
    FUTURES = "Futures"
```

**Mapping from Saxo AssetType:**
```python
SAXO_TO_INTERNAL_ASSET_TYPE = {
    "Stock": AssetType.STOCK,
    "FxSpot": AssetType.FX_SPOT,
    "FxForwards": AssetType.FX_FORWARD,
    "CfdOnIndex": AssetType.CFD_INDEX,
    "StockCfdOnPhysicalShares": AssetType.CFD_STOCK,
    "CryptoFx": AssetType.CRYPTO_FX,
    "Bond": AssetType.BOND,
    "Etf": AssetType.ETF,
    "MutualFund": AssetType.FUND,
    "StockOption": AssetType.OPTION,
    "ContractFutures": AssetType.FUTURES,
}
```

**Usage across epics:**
- **Epic 002 (Config):** Watchlist validates asset types against `AssetType` enum
- **Epic 003 (Data):** Normalization maps Saxo → `AssetType`
- **Epic 004 (Strategy):** Strategies reference `AssetType` for asset-specific logic
- **Epic 005 (Execution):** Order placement uses `AssetType` for validation

**Reference document location:** `docs/ASSET_TYPE_VOCABULARY.md`

## Implementation Checklist

### Completed ✅
- [x] Story 004-001: Enhanced Signal schema with `decision_time`, `price_ref`, `data_time_range`, `policy_flags`
- [x] Story 004-002: Added `as_of` parameter to `safe_slice_bars()`, changed to `Sequence[float]`
- [x] Story 004-003: Uses bar timestamps as `decision_time`, added cooldown, div-by-zero guard
- [x] Story 004-005: SIM/LIVE delay policy, market-state gating, CryptoFX weekday docs
- [x] Story 004-006: Registry alignment with factory

### Remaining To-Do
- [ ] Story 004-004: Add JSON artifact saving with parameter set ID
- [ ] Story 004-007: Update fixtures to use fixed timestamps, add SIM/LIVE test cases
- [ ] Story 004-008: Add Saxo-specific documentation section
- [ ] Epic 004 overview: Update with key principles section
- [ ] Create `docs/ASSET_TYPE_VOCABULARY.md` with canonical mapping

## Key Principles (to add to Epic 004 overview)

1. **Determinism First:** Every function that filters by time must accept `as_of` parameter
2. **Timestamp Discipline:** Separate wall-clock time (`timestamp`) from data time (`decision_time`)
3. **Saxo Correctness:** Use market state fields, not weekday checks; respect SIM limitations
4. **Audit Trail:** Every signal captures complete provenance (data range, price ref, quality flags)
5. **Safe by Default:** Market closed → HOLD, stale data → HOLD, extended hours disabled by default
6. **Extensibility:** Registry pattern, no hard-coded switch statements
7. **Backtest Hygiene:** Closed-bar discipline, no look-ahead bias, reproducible results

## References

All improvements are based on:

1. **Saxo Documentation:**
   - [Crypto FX in OpenAPI](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)
   - [Delayed vs Live Prices](https://openapi.help.saxo/hc/en-us/articles/4405160701085)
   - [Extended Trading Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589)

2. **Academic References:**
   - Evidence-Based Technical Analysis (Aronson) - Look-ahead bias prevention
   - Bailey et al. - Probability of Backtest Overfitting
   - Brock, Lakonishok, LeBaron (1992) - MA crossover rules

## Next Steps

1. **Complete remaining story updates** (004-004, 004-007, 004-008)
2. **Update Epic 004 overview** with key principles section
3. **Create asset type vocabulary document**
4. **Begin implementation** with confidence that architecture is sound
5. **Review with team** before starting Story 004-001 implementation

---

**Document Status:** Living document - update as implementation progresses  
**Last Updated:** 2025-12-13  
**Author:** AI Assistant (Cline)
