# Epic 002 Pre-Implementation Review: Fixes Applied

**Date:** 2024-12-13  
**Review By:** Pre-implementation analysis  
**Status:** ✅ All identified issues addressed

---

## Executive Summary

This document summarizes all fixes applied to the Epic 002 story files following the pre-implementation review. The review identified several cross-story mismatches that would have caused implementation friction and CI failures. All issues have been resolved.

---

## Must-Fix Items (All Resolved)

### 1. ✅ Unified Watchlist Environment Variable Name

**Issue:** Story 002-003 used `WATCHLIST_JSON` but Story 002-007 documentation listed `WATCHLIST`.

**Resolution:**
- Updated Story 002-007 to use `WATCHLIST_JSON` consistently throughout the environment variables table
- Location: `docs/stories/story-002-configuration/story-002-007-configuration-documentation.md`

---

### 2. ✅ Fixed SAXO_ACCESS_TOKEN Documentation

**Issue:** Story 002-007 listed `SAXO_ACCESS_TOKEN` as always required, but the project is primarily OAuth mode.

**Resolution:**
- Restructured env vars reference into three sections:
  - **Always Required:** `SAXO_REST_BASE`
  - **OAuth Mode Required:** `SAXO_APP_KEY`, `SAXO_APP_SECRET`, `SAXO_REDIRECT_URI`
  - **Manual Token Mode Required:** `SAXO_ACCESS_TOKEN`
- Added notes explaining each mode's requirements
- Location: `docs/stories/story-002-configuration/story-002-007-configuration-documentation.md`

---

### 3. ✅ Fixed Trading Hours Precision Bug (14:30 UTC)

**Issue:** Trading hours used integer hours (`MARKET_OPEN_HOUR=14`) but comments said "9:30 AM EST = 14:30 UTC". Integer hours cannot represent 14:30.

**Resolution:**
- Added new environment variables supporting HH:MM format:
  - `MARKET_OPEN_TIME=14:30` (new, preferred)
  - `MARKET_CLOSE_TIME=21:00` (new, preferred)
  - Legacy aliases `MARKET_OPEN_HOUR`/`MARKET_CLOSE_HOUR` still supported
- Added `_parse_trading_hours()` method that parses both formats
- Added minute-level attributes: `market_open_minute`, `market_close_minute`, `market_open_minutes`, `market_close_minutes`
- Updated `is_within_trading_hours()` to use minute-precision comparisons
- Location: `docs/stories/story-002-configuration/story-002-004-trading-settings.md`

---

### 4. ✅ Clarified Watchlist Mutability Contract

**Issue:** Story 002-003 said "Immutable watchlist" but also defined `add_instrument()`/`remove_instrument()` methods.

**Resolution:**
- Updated Architecture Notes to clarify:
  > **Runtime Mutability:** Watchlist loaded from config at startup; `add_instrument()`/`remove_instrument()` methods allow in-memory modifications during runtime (mutations are not persisted to `.env` - reload config to reset to original)
- Location: `docs/stories/story-002-configuration/story-002-003-watchlist-configuration.md`

---

## High-Impact Test Fixes (All Resolved)

### A. ✅ Tests Now Use Base Environment Fixtures

**Issue:** Tests relied on local `.env` and would fail in CI.

**Resolution:**
- Added two pytest fixtures:
  - `base_manual_env`: For manual token mode tests
  - `base_oauth_env`: For OAuth mode tests
- All tests now use `patch.dict(os.environ, ..., clear=True)` for deterministic behavior
- Location: `docs/stories/story-002-configuration/story-002-006-configuration-testing.md`

---

### B. ✅ OAuth Mode Detection Test Fixed

**Issue:** Test only patched app key/secret but missing `SAXO_REST_BASE` and redirect URI.

**Resolution:**
- Test now uses complete `base_oauth_env` fixture with all required OAuth variables
- Also mocks token file existence and content
- Location: `docs/stories/story-002-configuration/story-002-006-configuration-testing.md`

---

### C. ✅ Manual Mode Detection Uses `clear=True`

**Issue:** `test_manual_mode_detection` used `clear=False` which could leak OAuth keys from developer environment.

**Resolution:**
- Changed to `clear=True` with complete `base_manual_env` fixture
- Location: `docs/stories/story-002-configuration/story-002-006-configuration-testing.md`

---

### D. ✅ Token Masking Test Fixed

**Issue:** Test referenced `config.access_token` attribute but implementation uses `get_access_token()` method.

**Resolution:**
- Changed to use `config.get_access_token()` method:
  ```python
  token = config.get_access_token()  # Use method, not attribute
  assert len(masked) < len(token)
  ```
- Location: `docs/stories/story-002-configuration/story-002-006-configuration-testing.md`

---

### E. ✅ Wrong Environment Variable Fixed

**Issue:** Validation test used `MAX_POSITION_SIZE` but implementation uses `MAX_POSITION_VALUE_USD`.

**Resolution:**
- Changed `MAX_POSITION_SIZE` to `MAX_POSITION_VALUE_USD` in test:
  ```python
  env['MAX_POSITION_VALUE_USD'] = '1000.0'  # Use correct env var name
  ```
- Location: `docs/stories/story-002-configuration/story-002-006-configuration-testing.md`

---

### F. ✅ Watchlist Summary Schema Defined

**Issue:** Test expected ambiguous keys (`resolved_count` or `instrument_count`).

**Resolution:**
- Defined stable schema for `get_watchlist_summary()`:
  ```python
  # Required keys per stable schema
  assert 'total_instruments' in summary
  assert 'resolved' in summary  # Count of resolved instruments
  assert 'unresolved' in summary  # Count of unresolved instruments
  assert 'by_asset_type' in summary  # Breakdown by asset type
  ```
- Location: `docs/stories/story-002-configuration/story-002-006-configuration-testing.md`

---

### G. ✅ Trading Hours Test Uses Injectable Time

**Issue:** Tests patched `datetime.datetime` which is fragile.

**Resolution:**
- Added injectable parameters to `is_trading_allowed()` and `is_within_trading_hours()`:
  - `current_hour: Optional[int]`
  - `current_minute: Optional[int]`
  - `current_weekday: Optional[int]`
- Tests now inject time directly without mocking datetime:
  ```python
  assert config.is_trading_allowed(crypto, current_hour=3, current_weekday=2)  # Wednesday
  assert not config.is_trading_allowed(crypto, current_hour=3, current_weekday=6)  # Sunday
  ```
- Location: 
  - `docs/stories/story-002-configuration/story-002-004-trading-settings.md`
  - `docs/stories/story-002-configuration/story-002-006-configuration-testing.md`

---

## Validation Story Fix

### ✅ UIC Resolution Validation Now Conditional

**Issue:** Validation required all UICs resolved, which would make "first run" painful and block DRY_RUN mode.

**Resolution:**
- Added `strict` parameter to `_validate_instrument_resolution()`:
  - `strict=None`: Auto-detect from trading mode (strict only for LIVE)
  - `strict=True`: Error on unresolved (for LIVE trading)
  - `strict=False`: Warning only (for DRY_RUN, development)
- In DRY_RUN mode, unresolved instruments generate warnings instead of errors
- Location: `docs/stories/story-002-configuration/story-002-005-configuration-validation.md`

---

## Documentation Fixes

### ✅ Method References Updated

**Issue:** Documentation referenced `config.access_token` attribute instead of `config.get_access_token()` method.

**Resolution:**
- Updated "Never Log Full Tokens" best practice example to show proper method usage
- Location: `docs/stories/story-002-configuration/story-002-007-configuration-documentation.md`

---

## Files Modified

| File | Changes |
|------|---------|
| `story-002-003-watchlist-configuration.md` | Clarified mutability contract |
| `story-002-004-trading-settings.md` | Added HH:MM time format support, injectable time parameters |
| `story-002-005-configuration-validation.md` | Made UIC validation conditional on trading mode |
| `story-002-006-configuration-testing.md` | All test fixes (fixtures, env vars, method names, time injection) |
| `story-002-007-configuration-documentation.md` | Fixed env var names, auth mode requirements, method references |

---

## Definition of Ready Checklist (All Complete)

Before implementation begins, these statements are now true:

- [x] **Single source of truth** for env var names (WATCHLIST_JSON, MAX_POSITION_VALUE_USD, etc.)
- [x] **Single source of truth** for config method names and return schemas (watchlist summary, export format)
- [x] Tests use `patch.dict(..., clear=True)` and always define `SAXO_REST_BASE`
- [x] Trading hours support minutes (MARKET_OPEN_TIME=14:30) or comments are corrected
- [x] Validation around UIC resolution is conditional on runtime mode (DRY_RUN vs LIVE)
- [x] All documentation uses consistent naming and proper method references

---

## Implementation Notes

When implementing Epic 002, ensure:

1. **Config class** uses `get_access_token()` method, not a public `access_token` attribute
2. **Watchlist summary** returns schema with `total_instruments`, `resolved`, `unresolved`, `by_asset_type`
3. **Trading hours** methods accept injectable time parameters for testability
4. **Validation** checks trading mode before enforcing UIC resolution
5. **Tests** always use fixtures with `clear=True` and all required env vars
