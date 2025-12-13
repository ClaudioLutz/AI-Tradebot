# Epic 001.2: Saxo Bank Migration and Integration

## Overview
Migrate the trading bot from Alpaca API to Saxo Bank OpenAPI (SIM environment), maintaining the modular architecture while adapting to Saxo's authentication model, instrument identification system, and trading endpoints.

## Business Value
- Access to Saxo Bank's comprehensive trading platform with broader market access
- Support for European trading hours and instruments
- Professional-grade API with precheck capabilities for safer order testing
- Foundation for potential live trading with institutional-grade broker

## Dependencies
- **Prerequisite:** Epic 001 (Initial Setup) must be completed
- **Blocks:** Epic 002-008 require updates to align with Saxo API structure

## Technical Scope

### Authentication Changes
- Replace Alpaca's long-lived API keys with Saxo's OAuth flow (AppKey/AppSecret)
- **Primary mode:** OAuth with automatic token refresh for long-running sessions (>24h)
- **Optional mode:** Manual 24h SIM tokens (developer portal) for quick testing
- Token persistence and automatic refresh on expiry

### API Integration Changes
- Replace `alpaca-trade-api` SDK with direct REST API calls using `requests`
- Implement Saxo REST client wrapper
- Update all API endpoints from Alpaca to Saxo OpenAPI

### Data Model Changes
- Migrate from symbol-based identification (e.g., "AAPL") to UIC + AssetType model
- Implement instrument discovery via `ref/v1/instruments`
- Update watchlist configuration format

### Trading Module Changes
- Update order placement from Alpaca's order API to Saxo's `/trade/v2/orders`
- Implement order precheck functionality for cost estimation
- Handle AccountKey requirement for all trading operations

## Stories
1. **Story 001-2-001:** Saxo Developer Portal Setup & 24h Token Acquisition
2. **Story 001-2-002:** Update Dependencies (Remove Alpaca, Add Saxo Requirements)
3. **Story 001-2-003:** Update Environment Variables Configuration
4. **Story 001-2-004:** Update Environment Verification Script
5. **Story 001-2-005:** Implement Saxo REST Client Module
6. **Story 001-2-006:** Update API Connection Test
7. **Story 001-2-007:** Update Market Data Module for UIC-based Instruments
8. **Story 001-2-008:** Update Trade Execution Module
9. **Story 001-2-009:** Update Configuration Watchlist Format
10. **Story 001-2-010:** Integration Testing & Migration Documentation

## Acceptance Criteria
- [x] All Alpaca-specific code replaced with Saxo equivalents
- [x] OAuth authentication with automatic refresh implemented
- [x] Manual 24h token mode supported as fallback
- [x] Connection test successfully validates Saxo API access
- [x] Client and Account context (ClientKey, AccountKey) retrieved
- [x] Market data retrieval working with UIC-based instruments
- [ ] Order precheck and placement functional in SIM environment
- [ ] All existing tests updated and passing
- [x] Migration guide documentation completed
- [x] System maintains modular architecture integrity

## Technical Risks & Mitigations

### Risk: Token Expiration (24h tokens)
**Mitigation:** 
- Document token refresh process clearly
- Include token validation in connection test
- Foundation for OAuth implementation in future stories

### Risk: Instrument Discovery Complexity
**Mitigation:**
- Start with simple keyword-based lookup
- Document common UICs for test instruments
- Implement caching strategy for discovered instruments

### Risk: Order Placement Differences
**Mitigation:**
- Mandatory precheck before all orders
- Comprehensive error handling and logging
- Start with market orders only (simplest)

### Risk: Asset Type Transition (FxSpot → FxCrypto)
**Mitigation:**
- Code defensively to accept both asset types
- Validate via instrument details endpoint
- Document known affected UICs

## Success Metrics
- Zero Alpaca dependencies remaining in codebase
- 100% test coverage for Saxo client module
- Successful connection test execution
- Successful order precheck execution (no actual trades initially)

## Timeline Estimate
**Duration:** 8-12 hours of development work
- Setup & Environment: 2 hours
- Client Implementation: 2-3 hours
- Market Data Migration: 2-3 hours
- Trade Execution Migration: 2-3 hours
- Testing & Documentation: 2-3 hours

## Notes
- This epic maintains paper trading / SIM environment only
- Live trading requires OAuth implementation (future epic)
- Switzerland location: No restrictions for SIM API access
- Developer Portal one-day tokens are SIM-only
- All existing architectural patterns (config, data, strategies, execution) remain intact

## References
- [Saxo Bank Developer Portal - Environments](https://developer.saxobank.com/openapi/learn/environments)
- [Saxo Bank OpenAPI - OAuth Authorization](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
- [Saxo Bank OpenAPI - Trade Orders](https://www.developer.saxo/openapi/referencedocs/trade/v2/orders)
- [Saxo Bank OpenAPI - Reference Instruments](https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments)
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md`
