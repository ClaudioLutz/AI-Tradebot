# Epic 004: Trading Strategy System - Story Breakdown

This directory contains detailed user stories for implementing the Trading Strategy System with research-backed refinements.

## Overview

Epic 004 builds a modular, testable, and safe-by-default strategy system that prevents common pitfalls like look-ahead bias and backtest overfitting while respecting Saxo-specific market constraints.

## Stories

### Story 004-001: Strategy Interface and Signal Schema
**Estimated Effort:** 2-3 hours

Define standardized interface and rich signal schema with action, reason, confidence, and timestamp fields. Creates foundation for auditable, timestamp-aware signal generation.

**Key Deliverables:**
- `strategies/base.py` with BaseStrategy and Signal dataclass
- `signals_to_actions()` helper function
- Timestamp validation prevents look-ahead bias

### Story 004-002: Indicator Utilities
**Estimated Effort:** 3-4 hours

Pure, deterministic indicator functions with "closed-bar" discipline to prevent look-ahead bias.

**Key Deliverables:**
- `strategies/indicators.py` with SMA, EMA, crossover detection
- `safe_slice_bars(require_closed=True)` enforces look-ahead prevention
- `detect_crossover()` implements proper regime change detection

### Story 004-003: Moving Average Crossover Strategy
**Estimated Effort:** 4-5 hours

Reference implementation demonstrating best practices, proper crossover detection (previous vs current), and comprehensive edge case handling.

**Key Deliverables:**
- `strategies/moving_average.py` - production-ready strategy
- Uses `long_window + 1` bars for proper crossover detection
- Extensive metadata for audit trails

### Story 004-004: Strategy Parameter Handling
**Estimated Effort:** 3-4 hours

Configuration-based parameter management with explicit logging to prevent backtest overfitting.

**Key Deliverables:**
- `strategies/config.py` with parameter loader and validator
- Config support (JSON and individual env vars)
- Automatic parameter logging creates audit trail

### Story 004-005: Data-Quality Gating and Market-State Policy
**Estimated Effort:** 4-5 hours

Safe-by-default policies preventing trades on stale data or during inappropriate market conditions.

**Key Deliverables:**
- `strategies/data_quality.py` with DataQualityChecker
- Saxo-specific: CryptoFX weekday-only, extended hours opt-in
- Market state validation (open/closed)

### Story 004-006: Strategy Registry/Loader
**Estimated Effort:** 2-3 hours

Extensible registry system avoiding hard-coded "if strategy == ..." logic.

**Key Deliverables:**
- `strategies/registry.py` with decorator-based registration
- Factory function for strategy instantiation
- Minimal boilerplate for new strategies

### Story 004-007: Strategy Unit Testing Harness
**Estimated Effort:** 3-4 hours

Reusable test fixtures and helpers enabling robust isolation testing.

**Key Deliverables:**
- `tests/fixtures/strategy_fixtures.py` with deterministic scenarios
- `tests/helpers/strategy_helpers.py` with assertion helpers
- Example test suite demonstrating best practices

### Story 004-008: Developer Documentation
**Estimated Effort:** 3-4 hours

Comprehensive guide with research-backed best practices and Saxo-specific notes.

**Key Deliverables:**
- `docs/STRATEGY_DEVELOPMENT_GUIDE.md`
- Look-ahead bias explanation and prevention
- Backtest overfitting warning with references
- Saxo-specific considerations (CryptoFX, extended hours)

## Total Estimated Effort
**24-30 hours** for complete implementation and testing

## Implementation Order

Stories should be implemented in sequence as each builds on the previous:

1. **001** → Interface foundation
2. **002** → Indicator utilities
3. **003** → Reference strategy implementation
4. **004** → Parameter management
5. **005** → Data quality gates
6. **006** → Registry system
7. **007** → Testing infrastructure
8. **008** → Documentation

## Key Research-Backed Refinements

### 1. Correct Market Availability (Saxo-Specific)
- **CryptoFX trades weekdays only** (not 24/7)
- **SIM may provide delayed prices for non-FX**; allow delayed in SIM via policy to avoid “everything HOLD”
- Extended hours have lower liquidity and higher volatility
- References: Saxo Developer Portal, Saxo Help

### 2. Look-Ahead Bias Prevention
- Closed-bar discipline via `require_closed=True` flag
- Explicit timestamps on all signals
- Bar structure includes `is_closed` field
- Reference: Evidence-Based Technical Analysis (Aronson)

### 3. Backtest Overfitting Prevention
- Automatic parameter logging creates audit trail
- Makes parameter experimentation explicit
- Supports future out-of-sample validation
- Reference: Bailey et al. - The Probability of Backtest Overfitting

### 4. Proper Crossover Detection
- Compares previous vs current MA relationship
- Treats crossovers as regime changes, not instantaneous comparisons
- Reference: Brock, Lakonishok, LeBaron (1992)

## References

1. [Evidence-Based Technical Analysis (Aronson)](https://catalogimages.wiley.com/images/db/pdf/9781118460146.excerpt.pdf) - Look-ahead bias prevention
2. [Bailey et al. - The Probability of Backtest Overfitting](https://carmamaths.org/jon/backtest2.pdf) - Parameter transparency
3. [Brock, Lakonishok, LeBaron (1992)](https://law-journals-books.vlex.com/vid/simple-technical-trading-rules-stochastic-855602882) - MA crossover methodology
4. [Saxo Developer Portal - Crypto FX](https://developer.saxobank.com/openapi/learn/crypto-fx-in-openapi) - CryptoFX weekday-only trading
5. [Saxo Extended Trading Hours](https://www.help.saxo/hc/en-ch/articles/7574076258589) - Extended hours risks

## Related Epics

- **Epic 001-2:** Saxo Bank Migration (broker connectivity)
- **Epic 002:** Configuration Module (parameter loading)
- **Epic 003:** Market Data Retrieval (normalized data input)
- **Epic 005:** Trade Execution Module (signal consumers)
