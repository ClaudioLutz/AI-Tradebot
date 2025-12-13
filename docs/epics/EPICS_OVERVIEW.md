# Project Epics Overview

This document provides a high-level overview of all epics defined for the Trading Bot project. Each epic represents a significant milestone in the project's development.

## Project Invariants

The following core principles apply across all epics:

- **Broker:** Saxo Bank OpenAPI (SIM environment as default)
- **Authentication:** OAuth refresh flow for long-running sessions (>24h); manual 24h token optional for quick tests
- **Instrument Representation:** All instruments identified by `{asset_type, uic}` pairs; symbol is a human-readable label only
- **Execution Safety:** Precheck-first workflow; DRY_RUN mode supported for testing without placement
- **Configuration Philosophy:** Load once at startup, immutable during runtime, deterministic

---

## [Epic 001-1: Initial Setup and Environment](./epic-001-1-initial-setup-and-environment.md)
**Status:** Legacy (Alpaca-based prototype - retained for historical reference)
**Overview:** Original setup epic focused on Alpaca paper trading infrastructure. This epic has been superseded by Epic 001-2 for Saxo Bank integration.
**Key Goals:** 
- ⚠️ **Note:** New implementations should follow Epic 001-2 instead.

## [Epic 001-2: Saxo Bank Migration and Integration](./epic-001-2-saxo-bank-migration.md)
**Status:** Active (Current broker baseline)
**Overview:** Establish Saxo Bank OpenAPI connectivity with OAuth refresh flow as primary authentication method. Supports both SIM and Live environments.
**Key Goals:**
- OAuth login with automatic refresh for long-running sessions.
- Manual 24h token fallback for testing.
- Client and account context retrieval (ClientKey, AccountKey).
- Connection verification against SIM environment.

## [Epic 002: Configuration Module Development (Saxo Bank)](./epic-002-configuration-module.md)
**Overview:** Create a centralized configuration module (`config/settings.py`) that manages OAuth/manual authentication modes, instrument watchlists (UIC/AssetType), and trading hours logic.
**Key Goals:**
- Support both OAuth and manual token authentication modes.
- Resolve instruments to `{asset_type, uic}` pairs with symbol labels.
- Implement flexible trading hours (always/fixed/instrument modes).
- Load configuration once at startup (immutable).

## [Epic 003: Market Data Retrieval Module (Saxo)](./epic-003-market-data-retrieval.md)
**Overview:** Develop the market data adapter (`data/market_data.py`) to fetch quotes and bars from Saxo OpenAPI for instruments defined in the watchlist.
**Key Goals:**
- Fetch InfoPrice/Quote data for real-time pricing.
- Retrieve OHLC bars for strategy indicators.
- Normalize market data keyed by `instrument_id` (`{asset_type}:{uic}`).
- Handle Saxo-specific rate limits and error recovery.

## [Epic 004: Trading Strategy System](./epic-004-trading-strategy-system.md)
**Overview:** Build a modular strategy system in the `strategies/` folder, with strategies as pure functions over normalized market data.
**Key Goals:**
- Separate trading logic from broker-specific details.
- Operate on `instrument_id` keys with symbol labels for readability.
- Enable easy experimentation with different strategies.
- Provide a clear interface for signal generation.

## [Epic 005: Trade Execution Module (Saxo)](./epic-005-trade-execution-module.md)
**Overview:** Develop the execution module (`execution/trade_executor.py`) responsible for order placement via Saxo OpenAPI with precheck-first workflow.
**Key Goals:**
- Implement precheck-first validation (cost estimation, order validation).
- Support DRY_RUN mode for safe testing.
- Execute orders using `{AccountKey, AssetType, Uic}` triplets.
- Handle Saxo position model and error categorization.

## [Epic 006: Main Orchestration Script (Multi-Asset)](./epic-006-main-orchestration.md)
**Overview:** Create the `main.py` orchestrator script that ties together all modules with support for multi-asset trading hours.
**Key Goals:**
- Implement config-driven trading hours (always/fixed/instrument modes).
- Orchestrate the full cycle: config → data → strategy → risk checks → execution.
- Handle graceful shutdown and error recovery.
- Support CryptoFX 24/7 and equity market hours.

## [Epic 007: Logging and Scheduling System (Saxo-aware)](./epic-007-logging-and-scheduling.md)
**Overview:** Implement comprehensive logging infrastructure with Saxo-specific fields and establish scheduling mechanisms.
**Key Goals:**
- Log Saxo-critical fields: `client_id`, `account_key`, `instrument_id`, `uic`, `asset_type`, `order_id`.
- Create audit trail for all trading decisions and API interactions.
- Support flexible scheduling based on `TRADING_HOURS_MODE`.
- Enable debugging and performance analysis.

## [Epic 008: Testing and Monitoring System (Saxo SIM)](./epic-008-testing-and-monitoring.md)
**Overview:** Establish a comprehensive testing framework using Saxo SIM environment and monitoring capabilities.
**Key Goals:**
- Unit tests for config, instrument resolution, and order construction.
- Integration tests with SIM (precheck-only by default).
- Monitor OAuth refresh, data freshness, API error rates.
- Track operational health metrics.

---

## Epic Dependencies

```
Epic 001-2 (Saxo Integration)
    ↓
Epic 002 (Configuration)
    ↓
Epic 003 (Market Data) ─┐
    ↓                    ├─→ Epic 006 (Orchestration)
Epic 004 (Strategy) ─────┤       ↓
    ↓                    │   Epic 007 (Logging/Scheduling)
Epic 005 (Execution) ────┘       ↓
                             Epic 008 (Testing/Monitoring)
```

**Critical Path:** Epics 001-2 → 002 → (003, 004, 005) → 006 → 007 → 008

---

## Terminology Standards

To maintain consistency across all epics and code:

| ❌ Avoid | ✅ Use Instead | Notes |
|---------|----------------|-------|
| "Alpaca" | "Saxo OpenAPI" | Primary broker |
| "symbol only" (e.g., `"AAPL"`) | `{asset_type, uic}` | Instrument identification |
| "ticker" | "instrument" or "symbol (label)" | Clarify semantic role |
| "BTC/USD" | "BTCUSD" | CryptoFX formatting |
| "paper trading" | "SIM environment" | Saxo terminology |
| "api key" | "OAuth token" or "access token" | Auth method |
| `get_bars()` | `fetch_ohlc()` or similar | Saxo-agnostic method names |

---

## Related Documentation

- [Saxo Migration Guide](../SAXO_MIGRATION_GUIDE.md) - Complete migration from Alpaca
- [OAuth Setup Guide](../OAUTH_SETUP_GUIDE.md) - OAuth implementation details
- [Epic 002 Revision Summary](../EPIC-002-REVISION-SUMMARY.md) - Configuration design decisions
