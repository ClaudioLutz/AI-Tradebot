# Epic 004 Pre-Implementation Improvements

**Date:** 2025-12-13  
**Status:** Complete - All improvements documented and applied

## Overview

This document summarizes comprehensive improvements made to Epic 004 (Trading Strategy System) before implementation begins, addressing (a) Saxo correctness, (b) determinism / backtest hygiene, and (c) alignment across epics (002 config → 003 data → 004 strategies → 005 execution).

> NOTE (2025-12-13): This document is a **pre-implementation spec refinement** only.
> It does **not** imply code exists yet. Epic 004 repository code can still be placeholder.

## Highest-Impact Fixes Applied

### 1. ✅ Stop Hard-Coding "CryptoFX weekday-only" using `weekday < 5`

**Problem:** Original trading-hours logic treated "FxSpot/FxCrypto = Monday–Friday only" too simplistically.

**Solution:**
- **Story 004-005 updated:** Data quality gating uses **Saxo's `MarketState` enum** from quote snapshots.
- Market-state policy checks `quote.MarketState` (from Epic 003) instead of `weekday < 5`.
- CryptoFX weekday-only is documented explicitly with Saxo reference.
- Weekday check remains as a **fallback only** when `MarketState`/`LastUpdated` are missing.

**Reference:** [Saxo Developer Portal - Crypto FX in OpenAPI](https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi)

### 2. ✅ Make "closed-bar discipline" deterministic (no wall-clock `now` internally)

**Problem:** Original `safe_slice_bars()` used `datetime.now()` to filter bars with `require_closed=True`, breaking reproducibility.

**Solution:**
- **Story 004-002 updated:** `safe_slice_bars()` accepts `as_of: datetime`.
- **Live mode:** Caller passes `decision_time_utc`.
- **Backtest mode:** Caller passes the decision-point time (bar close / quote time).
- Function never calls wall-clock time internally (prevents time leakage).

**Why it matters:** Without `as_of`, wall-clock time contaminates data timestamps, creating non-reproducible results.

### 3. ✅ Clarify Signal timestamps and enforce decision-time discipline

**Problem:** Signal timestamp semantics can drift, causing look-ahead, non-auditable decisions, and flaky tests.

**Solution:**
- **Story 004-001 updated:** Signal schema has two time concepts:
  - `timestamp`: wall-clock generation time
  - `decision_time`: “as-of data time” (bar close or quote `LastUpdated`)
- All strategies receive explicit `decision_time_utc` and only use bars strictly `< decision_time_utc`.

### 4. ✅ Align strategy factory with upcoming registry (avoid hard-coded patterns)

**Problem:** Strategy factory patterns often accumulate switch statements.

**Solution:**
- **Story 004-006 updated:** registry pattern integrated with config loader.
- Adding a new strategy requires registration only (no orchestration edits).

## Saxo-Specific Corrections (Primary Sources)

### A) ✅ MarketState values: use Saxo enum; block auctions by default

Saxo’s `MarketState` includes (non-exhaustive):
- `Open`, `Closed`, `PreMarket`, `PostMarket`
- `OpeningAuction`, `ClosingAuction`, `IntraDayAuction`, `TradingAtLast`

**Default policy for Epic 004:**
- Allowed for actionable signals: `{Open}`
- Block (force HOLD) when state is not `Open`, including all auction states.
- Extended hours (PreMarket/PostMarket) is opt-in and does **not** un-block auction states.

### B) ✅ `DelayedByMinutes == 0` does not guarantee freshness

Saxo notes cases where `DelayedByMinutes` is 0 but `LastUpdated` is still old (illiquid / sparse trading).  
Therefore staleness must be computed from `LastUpdated` (and/or last bar timestamps), not solely delay minutes.

### C) ✅ Simulation constraints: `NoAccess` is a first-class quality outcome

Saxo guidance:
- Market data can return `NoAccess` (common on SIM/demo for non-FX without proper permissions/subscriptions).

**Implication:** Epic 004 gates should treat `NoAccess` / missing quote distinctly from “stale”. The runner should surface actionable guidance.

### D) ✅ Quote semantics: record Saxo quote fields in Signal policy flags

Signal gating should record at minimum:
- `MarketState`
- `DelayedByMinutes`
- `PriceTypeBid` / `PriceTypeAsk`
- computed `is_stale`
- computed `noaccess`

### E) ✅ CryptoFX is weekday-only on Saxo

Saxo’s developer portal states Crypto FX trades on weekdays (not weekends). This should be deterministic and testable in Epic 004.

### F) ✅ Extended hours risk: keep as opt-in; execution constraints noted

Extended hours has lower liquidity / higher volatility; order semantics (stops/conditionals) can behave differently.  
Epic 004 should preserve “strategies may produce signals” but execution must remain aware of extended-hours constraints (Epic 005).

### G) ✅ Look-ahead bias prevention: unified backtest/live path

Event-driven data feed (bar-by-bar) supports unified logic and prevents look-ahead by construction.

### H) ✅ Backtest overfitting: log not only chosen params but how many configs were tried

Bailey et al. show overfitting probability rises quickly with number of configurations tested.  
Story 004-004 should capture experiment metadata like `CONFIGS_TRIED_COUNT`, selection rationale, and holdout policy.

## Remaining To-Do (Docs)

- [ ] Update Epic 004 overview to include the refined Saxo-aligned contract and reason-code namespace
- [ ] Update Story 004-001 to require specific `policy_flags` keys + reason-code namespaces
- [ ] Update Story 004-002 to require `as_of` (no internal wall-clock)
- [ ] Update Story 004-003 to explicitly HOLD on insufficient *closed* bars as-of decision_time
- [ ] Update Story 004-004 to include `STRATEGY_CONFIG_ID` and experiment metadata logging
- [ ] Update Story 004-005 to include `NoAccess`, `PriceType*`, `LastUpdated` staleness, and Saxo MarketState enum
- [ ] Update Story 004-007 fixtures for MarketState variants, NoAccess, and DelayedByMinutes=0-but-old-LastUpdated
- [ ] Update Story 004-008 with "Saxo Market Data Gotchas"

## References

1. Saxo Bank Developer Portal - MarketState enum: https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate
2. Saxo Support - Missing chart data / old LastUpdated: https://openapi.help.saxo/hc/en-us/articles/6105016299677-Why-is-chart-data-missing-for-this-instrument
3. Saxo Support - NoAccess for prices: https://openapi.help.saxo/hc/en-us/articles/4405160773661-Why-do-I-get-NoAccess-instead-of-prices
4. Saxo Support - Enabling market data: https://openapi.help.saxo/hc/en-us/articles/4418427366289-How-do-I-enable-market-data
5. Saxo Developer Portal - Quote schema: https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade/schema-quote
6. Saxo Developer Portal - Crypto FX: https://www.developer.saxo/openapi/learn/crypto-fx-in-openapi
7. Saxo risk warning: https://www.home.saxo/en-gb/legal/risk-warning/saxo-risk-warning
8. Evidence-Based Technical Analysis (excerpt): https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf
9. Bailey et al. (PBO): https://carmamaths.org/jon/backtest2.pdf
