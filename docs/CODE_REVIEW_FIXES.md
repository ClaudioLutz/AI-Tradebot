# Code Review Fixes - Strategy System

**Date:** 2025-12-13  
**Epic:** 004 - Trading Strategy System  
**Status:** ✅ Implemented

## Overview

This document summarizes the critical fixes applied to the trading strategy system based on a comprehensive code review. These fixes address timestamp consistency, look-ahead bias protection, and architectural improvements across multiple stories' acceptance criteria.

---

## 1. Cross-Cutting Contract Fixes (Highest Priority)

### A) ✅ Fixed: Signal.decision_time Contract (Priority 1A)

**Problem:**
- Epic 004 requires: "Each returned `Signal.decision_time` MUST equal the provided `decision_time_utc`"
- Strategy was setting `decision_time` to wall-clock timestamp for insufficient bars
- Strategy was setting `decision_time` to last bar timestamp in happy path

**Solution:**
- All signals now use `decision_time_utc` (converted to ISO8601) for `Signal.decision_time`
- Ensures determinism and matches epic contract
- Bar-close timestamps remain in `data_time_range` for reference

**Files Changed:**
- `strategies/moving_average.py`: Fixed all Signal creation to use `decision_time_str`

**Impact:** Enables true deterministic backtesting and audit trail compliance

---

### B) ✅ Fixed: Idempotency & Timestamp Provider (Priority 1B)

**Problem:**
- `get_current_timestamp()` used `datetime.now()` directly
- No way to inject fixed time for deterministic testing
- Breaks idempotency guarantee for testing/backtesting

**Solution:**
- Added `timestamp_provider` parameter to `get_current_timestamp()`
- Defaults to `datetime.now(timezone.utc)` for live mode
- Can inject fixed time provider for deterministic tests

**Files Changed:**
- `strategies/base.py`: Enhanced `get_current_timestamp()` function

**Example:**
```python
# Live mode (default)
timestamp = get_current_timestamp()

# Deterministic testing
fixed_time = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
timestamp = get_current_timestamp(lambda: fixed_time)
```

---

## 2. Look-Ahead Bias Protection

### A) ✅ Fixed: safe_slice_bars Look-Ahead Protection (Priority 2A)

**Problem:**
- Accepted `is_closed=True` bars WITHOUT checking `bar_time < as_of`
- Subtle failure mode: mislabeled `is_closed` flags could leak future information

**Solution:**
- Always require BOTH conditions:
  1. `bar_time < reference_time` (strictly in the past)
  2. Bar is marked closed OR can be inferred as closed from timestamp
- Logs warning if bar claims `is_closed=True` but timestamp >= decision_time

**Files Changed:**
- `strategies/indicators.py`: Hardened `safe_slice_bars()` function

**Impact:** Prevents accidental look-ahead bias from data quality issues

---

### B) ✅ Fixed: Timezone Validation (Priority 2B)

**Problem:**
- No validation that `decision_time_utc` is timezone-aware UTC
- Can cause subtle bugs with naive datetimes

**Solution:**
- Added `validate_decision_time_utc()` function
- Validates tzinfo is not None and equals `timezone.utc`
- Raises clear ValueError with actionable message
- Applied to both `safe_slice_bars()` and strategy `generate_signals()`

**Files Changed:**
- `strategies/base.py`: New `validate_decision_time_utc()` function
- `strategies/indicators.py`: Added validation in `safe_slice_bars()`
- `strategies/moving_average.py`: Added validation at start of `generate_signals()`

---

## 3. Strategy Correctness & Robustness

### A) ✅ Documented: Cooldown State Management (Priority 3A)

**Status:** State is acceptable for current use case

**Analysis:**
- Cooldown uses `_last_signal_bar_index` state (mutates during execution)
- This is fine if strategies are long-lived objects (one per symbol/timeframe)
- For multi-backtest scenarios, create new strategy instances per run

**Documentation Added:**
- Noted that strategies with state should be instantiated per backtest run
- Alternative: Move cooldown to execution layer (future enhancement)

---

### B) ✅ Fixed: Cooldown Bar Indexing (Priority 3B)

**Problem:**
- Cooldown used `len(bars)` which includes ALL bars (even future ones in backtests)
- Should use `len(valid_bars)` (filtered by `decision_time_utc`)

**Solution:**
- Changed cooldown indexing to use `len(valid_bars) - 1`
- Now correctly counts only the bars actually used for decision

**Files Changed:**
- `strategies/moving_average.py`: Fixed cooldown calculation

---

### C) ✅ Fixed: Threshold Calculation Robustness (Priority 3C)

**Problem:**
- Division by zero check only tested `current_long_ma == 0`
- Didn't use `abs()` for denominator (needed for negative price support)

**Solution:**
- Changed to `abs(current_long_ma) < 1e-10` (near-zero check)
- Use `abs(current_long_ma)` in denominator for robustness
- Supports synthetic series or spreads that can go negative

**Files Changed:**
- `strategies/moving_average.py`: Enhanced threshold filter logic

---

## 4. Signal Schema Completeness

### ✅ Added: decision_context & policy_flags (Priority 4)

**Problem:**
- Story 004-001 expects market state + freshness summary in signals
- Strategy wasn't populating `decision_context` or `policy_flags`

**Solution:**
- Extract from `quote` data if available:
  - **decision_context:** market_state, price_source, price_type info
  - **policy_flags:** delayed_by_minutes, is_tradable
- Enables full audit trail and data quality tracking

**Files Changed:**
- `strategies/moving_average.py`: Added decision_context and policy_flags extraction

**Example Output:**
```python
{
    "decision_context": {
        "market_state": "Open",
        "price_source": "Streaming",
        "price_type_raw": "Tradable",
        "price_type_bid_ask_mid": "Mid"
    },
    "policy_flags": {
        "delayed_by_minutes": 0,
        "is_tradable": True
    }
}
```

---

## 5. Repository Hygiene

### ✅ Fixed: Deprecated simple_strategy.py (Priority 6A)

**Problem:**
- Legacy placeholder file from Epic 001
- Doesn't implement `BaseStrategy`, doesn't return `Signal` objects
- Conflicts with new architecture

**Solution:**
- Marked as DEPRECATED with clear warnings
- Functions now raise `NotImplementedError` with migration guidance
- Documented proper migration path to `BaseStrategy`

**Files Changed:**
- `strategies/simple_strategy.py`: Complete deprecation with guidance

---

## 6. Future Enhancements (Deferred)

### Registry Enhancement (Priority 5)

**Recommendation:** Add `StrategySpec` dataclass
- Supports versioning, parameter schema, validation
- Enables `get_strategy_spec(name) -> StrategySpec`
- Cleanly addresses Story 004-004 (parameter validation) and 004-006 (registry requirements)

**Status:** Deferred to future story implementation (current registry is functional for MVP)

---

### Comprehensive Test Suite (Priority 6B)

**Recommendation:** Add test modules
- `tests/test_indicators.py` - Unit tests for indicator functions
- `tests/test_strategy_registry.py` - Registry functionality tests
- `tests/test_moving_average_strategy.py` - MA strategy tests with fixtures
- Test harness for deterministic backtesting

**Status:** To be implemented in Story 004-007 (Strategy Testing Harness)

---

## Summary of Changes

### Files Modified (7)

1. **strategies/base.py**
   - Added `timestamp_provider` param to `get_current_timestamp()`
   - Added `validate_decision_time_utc()` function
   - Enhanced documentation

2. **strategies/indicators.py**
   - Hardened `safe_slice_bars()` against look-ahead bias
   - Added timezone validation for `as_of` parameter
   - Always check `bar_time < as_of` even when `is_closed=True`

3. **strategies/moving_average.py**
   - Fixed timestamp contract (use `decision_time_utc` everywhere)
   - Added timezone validation
   - Fixed cooldown indexing to use `valid_bars`
   - Enhanced threshold calculation robustness
   - Added `decision_context` and `policy_flags` extraction

4. **strategies/simple_strategy.py**
   - Deprecated with clear migration guidance

5. **strategies/registry.py**
   - No changes (functional as-is)

---

## Verification Checklist

- [x] All signals use `decision_time_utc` for `Signal.decision_time`
- [x] Timestamp provider supports injection for deterministic tests
- [x] `safe_slice_bars()` enforces `bar_time < as_of` in all cases
- [x] Timezone validation prevents naive datetime bugs
- [x] Cooldown indexing uses correct bar count
- [x] Threshold calculation handles edge cases robustly
- [x] Signals include `decision_context` and `policy_flags`
- [x] `simple_strategy.py` properly deprecated
- [x] All changes documented with inline comments

---

## Acceptance Criteria Impact

### Epic 004 - Trading Strategy System
✅ **Time Discipline:** All signals now use `decision_time_utc` consistently  
✅ **Look-Ahead Protection:** Hardened against data quality issues  
✅ **Timezone Safety:** Validates UTC-aware datetimes  
✅ **Audit Trail:** Complete with decision_context and policy_flags  

### Story 004-001 - Strategy Interface
✅ **Signal Schema:** decision_context and policy_flags populated  
✅ **Time Contract:** decision_time matches decision_time_utc  

### Story 004-002 - Indicator Utilities
✅ **Closed-Bar Discipline:** Enhanced with dual condition checks  
✅ **Timezone Validation:** Prevents naive datetime usage  

### Story 004-003 - Moving Average Strategy
✅ **Crossover Logic:** Robust threshold and cooldown handling  
✅ **Signal Quality:** Complete metadata and audit info  

---

## Migration Notes for Developers

### If You're Using `get_current_timestamp()`
```python
# Old (still works)
timestamp = get_current_timestamp()

# New (for deterministic tests)
from datetime import datetime, timezone
fixed_time = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
timestamp = get_current_timestamp(lambda: fixed_time)
```

### If You're Implementing a New Strategy
1. Always call `validate_decision_time_utc(decision_time_utc)` at start
2. Use `decision_time_utc.isoformat().replace('+00:00', 'Z')` for signal.decision_time
3. Extract `decision_context` and `policy_flags` from quote data if available
4. Test with timezone-aware datetimes only

### If You're Running Backtests
- Create new strategy instances per backtest run (for strategies with state)
- Pass timezone-aware UTC datetimes to `generate_signals()`
- Inject fixed timestamp provider for deterministic results

---

## Related Documentation

- **Epic 004:** `docs/epics/epic-004-trading-strategy-system.md`
- **Story 004-001:** `docs/stories/story-004-trading-strategy/story-004-001-strategy-interface-and-signal-schema.md`
- **Strategy Guide:** `docs/STRATEGY_DEVELOPMENT_GUIDE.md`

---

## Questions or Issues?

For questions about these changes or to report bugs, please:
1. Review this document and related story documentation
2. Check inline code comments for implementation details
3. Use `/reportbug` command if you discover issues

---

**Reviewed by:** Code Review Analysis  
**Implemented by:** AI Development Assistant  
**Review Date:** 2025-12-13  
**Implementation Date:** 2025-12-13
