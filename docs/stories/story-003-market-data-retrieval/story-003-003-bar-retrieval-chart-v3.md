# Story 003-003: Bar Retrieval via Chart v3 (OHLC)

## Story Overview
Implement OHLC bar retrieval using **Saxo Chart v3** and normalize output for strategy consumption. Support both full refresh and incremental polling.

This story makes horizon validation explicit (to avoid 400s) and documents the expected behavior for missing bars.

## Parent Epic
[Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)

## User Story
**As a** developer  
**I want to** fetch OHLC bars for an instrument using Saxo Chart v3  
**So that** strategies can compute indicators from consistent bar data

## Acceptance Criteria
- [ ] Implement `get_ohlc_bars()` in `data/market_data.py` using:
  - `GET /chart/v3/charts`
- [ ] Required request params are used:
  - `AssetType`, `Uic`, `Horizon` (minutes per bar)
- [ ] `Horizon` is validated to be one of Saxo-supported values:
  - `1, 5, 10, 15, 30, 60, 120, 240, 360, 480, 1440, 10080, 43200`
- [ ] `Count` is validated to be `<= 1200`
- [ ] Support optional incremental polling parameters:
  - `Mode` (`UpTo` or `From`)
  - `Time` (ISO-8601 timestamp)
- [ ] Duplicate bar handling: if the API returns a bar with the same `Time` as the most recent stored bar, overwrite/merge it (do not append a duplicate)
- [ ] Missing bars for illiquid instruments are treated as normal (no exception)
  - Emit a warning including `{instrument_id, horizon, requested_count, returned_count}`
- [ ] FX/CryptoFX bid/ask OHLC is normalized to mid OHLC by default
- [ ] Return contains instrument metadata and normalized bars
- [ ] Logs contain instrument context and bar counts

## Technical Details

### Prerequisites
- Story 003-001 completed (bar normalization helpers)

### Target Module
- `data/market_data.py`

### Endpoint
- `GET /chart/v3/charts`

Typical query params:
- Required:
  - `AssetType=<asset_type>`
  - `Uic=<uic>`
  - `Horizon=<minutes>`
- Optional:
  - `Count=<int>` (max 1200)
  - `Mode=UpTo|From`
  - `Time=<timestamp>`
  - `FieldGroups=<...>`
  - `AccountKey=<...>` (optional; omit unless needed)
  - `ChartSampleFieldSet=<...>` (exists in API; defer for now)

> Note: `FieldGroups` in Chart v3 is unrelated to InfoPrices `FieldGroups`. Quote retrieval uses `/trade/v1/infoprices/list`.

**FieldGroups default behavior:**
If `FieldGroups` is not specified, Chart v3 responses default to `[Data]` only (OHLC samples). This reduces over-fetching and bandwidth issues. Only specify additional FieldGroups if you need extra response data beyond the core OHLC bars.

**Mode parameter semantics:**
When using `Mode=From` or `Mode=UpTo`, the specified `Time` is **inclusive** (the bar at that timestamp is included in the response). This is important for the duplicate bar overwrite rule.

### Horizon Validation
**Stable "supported" horizon values (minutes):**

> `1, 5, 10, 15, 30, 60, 120, 240, 360, 480, 1440, 10080, 43200`

These values are documented as "supported" in Saxo's Support Center and should work consistently across instruments/environments.

**Important reconciliation note:**
Saxo's Chart v3 reference docs list additional allowed values (e.g., 2, 3, 180, 300, 129600, 518400). However, these additional values may not be consistently supported across all instruments or environments.

**Validation strategy:**
- By default, validate against the stable supported set listed above.
- Optionally, provide an "advanced mode" or config flag to allow additional reference-doc values with a warning that they may not be consistently supported.
- This prevents future confusion when developers see the reference docs and wonder why values like Horizon=180 are rejected.

Fail fast with a clear error message if an unsupported value is passed in default mode.

### Incremental Polling Pattern (Saxo guidance)
- First call: fetch latest bars (commonly `Mode=UpTo`)
- Next call: set `Mode=From` and `Time=<last bar timestamp>` to fetch only new/updated bars

### Duplicate/Overwrite Rule (From-pattern safety)
When using `Mode=From`, Saxo may return samples that include the last known bar time.

Rule:
- if returned bar `Time` equals most recent stored bar `time`, overwrite/merge that last bar.

### Chart Sample Fields Differ by Asset Type
Chart sample fields can vary (e.g., FX-like assets may include bid/ask OHLC fields).
Normalization rules from Story 003-001 apply:
- convert bid/ask OHLC → mid OHLC
- preserve raw fields for debugging

### Edge Cases
- Illiquid instruments: fewer bars than requested is not an error.
- CryptoFX history limitations: history only from 2021-04-19; treat insufficient history as warning.
- Stale `LastUpdated` can occur even when `DelayedByMinutes == 0` (handled in Story 003-005).

## Definition of Done
- [ ] Code compiles and module imports
- [ ] `get_ohlc_bars()` returns normalized bars in expected schema
- [ ] Horizon validation errors are explicit and actionable

## Testing
- Unit tests added in Story 003-006 (mocked Chart v3 responses).

## Story Points
**Estimate:** 2 points

## Dependencies
- Story 003-001

## References
- Saxo OpenAPI Chart v3: https://developer.saxobank.com/openapi/referencedocs/chart/v3/charts
- Saxo Learn - Chart sample shapes: https://www.developer.saxo/openapi/learn/chart
- Saxo Support - Horizon values: https://openapi.help.saxo/hc/en-us/articles/4417058210961-What-horizons-can-I-use
- Saxo Support - Missing chart data behavior: https://openapi.help.saxo/hc/en-us/articles/6105016299677-Why-is-chart-data-missing-for-this-instrument
