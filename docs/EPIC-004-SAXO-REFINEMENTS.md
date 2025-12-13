# Epic 004 - Saxo-Aligned Refinements (COMPLETED)

**Date**: December 13, 2025  
**Status**: ✅ Stories Updated - Ready for Implementation  
**Purpose**: Align Epic 004 strategy stories with Saxo Bank API reality and research-backed best practices

---

## Summary

Epic 004 stories have been refined to incorporate **web-validated corrections** about Saxo Bank's actual API behavior, eliminating assumptions and adding critical safeguards. The stories are now ready for implementation.

**Key Improvements**:
- ✅ Saxo MarketState enum alignment (Open, Closed, PreMarket, PostMarket, auction states)
- ✅ Freshness based on `LastUpdated` timestamp, not just `DelayedByMinutes`
- ✅ NoAccess handling as distinct failure mode with operator guidance
- ✅ SIM environment delayed quote policy
- ✅ CryptoFX weekday-only trading (not 24/7)
- ✅ PriceType handling (OldIndicative = market closed)
- ✅ Time discipline: `as_of` parameter now REQUIRED (eliminates time leakage)
- ✅ Reason code namespaces (DQ_* for data quality, SIG_* for strategy logic)
- ✅ Bailey et al. experiment metadata for parameter sweeps

---

## Story-by-Story Changes

### ✅ Story 004-001: Strategy Interface + Signal Schema

**Changes**:
1. **`policy_flags` now has required keys** when populated:
   - `market_state` (Saxo MarketState enum value)
   - `delayed_by_minutes`
   - `price_type_bid` / `price_type_ask` (Saxo PriceType enum)
   - `is_stale` (computed from LastUpdated)
   - `noaccess` (true if NoAccess error)

2. **`decision_time` semantics clarified**:
   - Must be ≤ `timestamp` (data time ≤ signal generation time)
   - Represents bar-close or Quote.LastUpdated time

3. **Reason code namespace added**:
   - `DQ_*` prefix for data-quality gating outcomes
   - `SIG_*` prefix for strategy logic reasons
   - Makes logs/tests stable and filterable

**Impact**: Richer audit trail, Saxo-specific metadata capture

---

### ✅ Story 004-002: Indicator Utilities

**Changes**:
1. **`safe_slice_bars()` signature changed**:
   - `as_of` parameter is now **REQUIRED** (not Optional)
   - **Eliminates time leakage by construction** - no hidden `datetime.now()` calls
   - Caller must explicitly pass `decision_time_utc`

2. **Updated all docstrings and examples** to show required `as_of` usage

3. **Added test** to verify `as_of` is required (TypeError if missing)

**Impact**: Enforces time discipline at the API level - impossible to accidentally create look-ahead bias

---

### ✅ Story 004-003: Moving Average Crossover Strategy

**Changes**:
1. **Handles illiquid instruments** (Saxo-specific):
   - If cannot obtain `long_window + 1` *closed* bars as of `decision_time_utc`, return HOLD
   - Reason code: `SIG_INSUFFICIENT_CLOSED_BARS`
   - Reference: https://openapi.help.saxo/hc/en-us/articles/6105016299677

2. **Uses `decision_time_utc` for `safe_slice_bars()`**:
   - Changed from `last_bar_time` to `decision_time_utc` (passed to strategy)
   - Prevents partial/future bars from being used

3. **Reason codes updated**:
   - `SIG_INSUFFICIENT_BARS` (not enough bars in feed)
   - `SIG_INSUFFICIENT_CLOSED_BARS` (illiquid instrument, bars not closed yet)

**Impact**: Handles Saxo's illiquid instrument behavior correctly

---

### ✅ Story 004-004: Strategy Parameter Handling

**Changes**:
1. **Added Bailey et al. experiment metadata** for parameter sweeps:
   - `STRATEGY_CONFIG_ID`: hash of (sorted params + strategy + version)
   - Optional fields when running sweeps:
     - `EXPERIMENT_NAME`
     - `CONFIGS_TRIED_COUNT` (how many configs were tested)
     - `SELECTION_RATIONALE` (why this one was chosen)

2. **Reference added**: https://carmamaths.org/jon/backtest2.pdf
   - Bailey: must disclose how many configurations were tried to assess overfitting risk

**Impact**: Anti-overfitting safeguard, creates audit trail for parameter experiments

---

### ✅ Story 004-005: Data Quality Gating (MAJOR CHANGES)

**This story had the most extensive refinements** - completely rewritten to align with Saxo API reality.

**Changes**:

1. **MarketState uses Saxo's actual enum**:
   - `Open`, `Closed`, `PreMarket`, `PostMarket`, `OpeningAuction`, `ClosingAuction`, `IntraDayAuction`, `TradingAtLast`
   - Reference: https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate
   - Default: only `Open` is tradable
   - Opt-in extended hours: `{PreMarket, PostMarket}` via `ALLOW_EXTENDED_HOURS=true`

2. **Freshness based on `LastUpdated` timestamp**:
   - **Cannot trust `DelayedByMinutes == 0` alone**
   - Saxo docs: delay can be 0 but LastUpdated still old (illiquid instruments)
   - Reference: https://openapi.help.saxo/hc/en-us/articles/6105016299677
   - Staleness = `now() - LastUpdated > threshold`

3. **NoAccess as distinct failure mode**:
   - Reason code: `DQ_NOACCESS_MARKETDATA` (not "stale")
   - Logs actionable guidance:
     - SIM: "Link Live account for non-FX market data"
     - LIVE: "Enable market data in SaxoTraderGO"
   - References:
     - https://openapi.help.saxo/hc/en-us/articles/4405160773661
     - https://openapi.help.saxo/hc/en-us/articles/4418427366289

4. **SIM environment delayed quote policy**:
   - `ALLOW_DELAYED_DATA_IN_SIM` (default: true for development progress)
   - Loud WARNING when enabled
   - Reference: https://openapi.help.saxo/hc/en-us/articles/4416934146449

5. **PriceType handling**:
   - Check `PriceTypeBid` / `PriceTypeAsk` from quote
   - `OldIndicative` = market closed / last known price → default HOLD
   - Record in `Signal.policy_flags`
   - References:
     - https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade/schema-quote
     - https://www.developer.saxo/openapi/learn/pricing

6. **CryptoFX weekday-only trading**:
   - Saxo CryptoFX trades **WEEKDAYS ONLY** (not 24/7)
   - Weekend check: if `asset_type == "CryptoFx" and now.weekday() >= 5`, return HOLD
   - Reason code: `DQ_CRYPTOFX_WEEKEND`
   - Reference: https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi

7. **Extended hours risk warning**:
   - When `ALLOW_EXTENDED_HOURS=true`, log WARNING:
     - Lower liquidity / higher volatility
     - Wider spreads
     - Stop/conditional orders behave differently
   - Reference: https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning

8. **Check now requires `decision_time_utc` parameter**:
   - `check_data_quality(market_data, decision_time_utc)` - no longer uses `datetime.now()` internally

9. **Comprehensive unit tests** for all Saxo-specific behaviors

**Impact**: Complete alignment with Saxo API reality, prevents silent failures, actionable error messages

---

### Story 004-006, 004-007, 004-008: Minor/No Changes

These stories remain largely unchanged:
- **004-006** (Registry): Already extensible pattern
- **004-007** (Testing harness): Minor note about fixed timestamps in fixtures
- **004-008** (Developer docs): Would benefit from Saxo-specific section (not critical pre-implementation)

---

## Implementation Readiness

### ✅ Ready to Implement

All Epic 004 stories are now:
1. **Saxo-aligned**: Based on actual API behavior, not assumptions
2. **Reference-backed**: Each Saxo-specific behavior has official documentation link
3. **Safe-by-default**: HOLD on questionable data/market conditions
4. **Time-disciplined**: Look-ahead bias prevented by construction
5. **Testable**: Clear acceptance criteria and test scenarios
6. **Auditable**: Rich signal schema + reason codes + experiment metadata

### Implementation Order (Recommended)

The original README sequence (001 → 002 → 003 → 004 → 005 → 006 → 007 → 008) is still valid.

**Alternative for safety-first**:
1. **004-001** (Interface + Signal schema)
2. **004-002** (Indicator utilities)
3. **004-005** (Data quality gating) ← Implement BEFORE strategy
4. **004-003** (MA crossover strategy)
5. **004-004** (Parameter handling)
6. **004-006** (Registry)
7. **004-007** (Testing harness)
8. **004-008** (Developer docs)

Rationale: Having data quality gates in place before any strategy can emit BUY/SELL prevents accidental trades on bad data.

---

## Key Saxo API Gotchas Addressed

### ❌ Assumption → ✅ Reality

| Assumption (Wrong) | Saxo Reality | Story Fix |
|--------------------|--------------|-----------|
| DelayedByMinutes=0 means fresh | Can be 0 with old LastUpdated (illiquid) | 004-005: Use LastUpdated timestamp |
| NoAccess is like "stale data" | NoAccess requires operator action (permissions) | 004-005: Distinct failure + guidance |
| SIM has live quotes for all | SIM lacks many non-FX live quotes | 004-005: ALLOW_DELAYED_DATA_IN_SIM |
| CryptoFX trades 24/7 | Weekdays only on Saxo | 004-005: Weekend check |
| Market is Open or Closed | Many states (PreMarket, auction, etc.) | 004-005: Full MarketState enum |
| PriceType doesn't matter | OldIndicative = market closed | 004-005: PriceType handling |
| `as_of` is optional convenience | Required for time discipline | 004-002: as_of REQUIRED |

---

## References (All Stories)

### Saxo Bank API Documentation
1. [MarketState Enum](https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate)
2. [Chart Data Missing / Delayed](https://openapi.help.saxo/hc/en-us/articles/6105016299677)
3. [NoAccess Error](https://openapi.help.saxo/hc/en-us/articles/4405160773661)
4. [Enable Market Data](https://openapi.help.saxo/hc/en-us/articles/4418427366289)
5. [Quote Schema](https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade/schema-quote)
6. [CryptoFX Trading](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)
7. [Saxo Risk Warning (Extended Hours)](https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning)
8. [Pricing Learn](https://www.developer.saxo/openapi/learn/pricing)
9. [SIM Account Linkage](https://openapi.help.saxo/hc/en-us/articles/4416934146449)

### Academic / Research
1. [Evidence-Based Technical Analysis (Aronson)](https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf) - Look-ahead bias prevention
2. [Bailey et al. - Backtest Overfitting](https://carmamaths.org/jon/backtest2.pdf) - Parameter experiment disclosure
3. [Brock, Lakonishok, LeBaron (1992)](https://support-and-resistance.technicalanalysis.org.uk/BrockLakonishokLeBaron1992.pdf) - MA crossover as regime change

---

## Next Steps

1. **Start implementation** using refined stories (001 → 008)
2. **Reference this document** when Saxo-specific behavior questions arise
3. **Test with SIM environment** first (delayed quote handling)
4. **Link Live account to SIM** for non-FX market data access
5. **Document any new Saxo gotchas** discovered during implementation

---

## Document History

- **2025-12-13**: Initial refinement based on web-validated Saxo API research
- Stories refined: 004-001, 004-002, 004-003, 004-004, 004-005
- Primary sources: Saxo developer portal, Saxo support articles, academic papers
- Status: ✅ COMPLETE - Ready for implementation
