# Story Pack — Epic 005: Trade Execution Module (Saxo)

This folder contains fully specified story documents for **Epic 005** (trade execution). The stories are designed to be implemented incrementally, while keeping the system safe-by-default:

- **Precheck-first** (no exceptions)
- Clear **DRY_RUN** vs **SIM** behavior
- Conservative **market-state gating**, including **auction states**
- Robust **idempotency**, **rate-limiting**, and **timeout reconciliation**
- Minimal but correct **position-aware** buy/sell handling for Stock + FxSpot
- Mandatory support plan for **Pre-Trade Disclaimers** (May 2025 requirement)

## Story Index

1. `story-005-001-execution-interface-and-order-intent-schema.md`
2. `story-005-002-instrument-validation-and-orderability.md`
3. `story-005-003-precheck-client-and-evaluation.md`
4. `story-005-004-order-placement-and-reconciliation.md`
5. `story-005-005-pre-trade-disclaimers-handling.md`
6. `story-005-006-position-query-and-position-aware-guards.md`
7. `story-005-007-rate-limiting-idempotency-and-retry-policy.md`
8. `story-005-008-marketstate-auction-gating-policy.md`
9. `story-005-009-testing-harness-unit-and-sim-integration.md`
10. `story-005-010-developer-documentation-and-runbook.md`

## Conventions

- **Instrument key** is `(AssetType, Uic)`; treat `(Uic, AssetType)` as the unique instrument identifier in all storage/logging.
- **ExternalReference** is set for all order/precheck calls to correlate internal events with Saxo OrderIds (max 50 chars).
- **x-request-id** is set for all order mutations (POST/PATCH/DELETE) to support safe retries and to intentionally allow identical operations when required (15s duplicate-operation window).

## Primary references

All stories include a “Primary Sources” section with the exact Saxo OpenAPI documentation pages used to design the acceptance criteria and edge-case behavior.
