# Story 003-006: Unit Tests with Mocked Saxo Market Data Responses

## Story Overview
Create unit tests for the market data module covering parsing, normalization, and edge cases using mocked Saxo responses.

This story explicitly covers the “high rework” edge cases:
- Chart horizon validation
- missing bars behavior
- InfoPrices list partial omission semantics
- multi-dimension rate-limit header parsing

## Parent Epic
[Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)

## User Story
**As a** developer  
**I want to** have reliable unit tests for market data retrieval and parsing  
**So that** changes to Saxo payload handling do not silently break strategies

## Acceptance Criteria
- [ ] Unit tests exist for InfoPrices list parsing/normalization
- [ ] Unit tests exist for Chart v3 parsing/normalization
- [ ] FX/CryptoFX bid/ask OHLC → mid OHLC conversion is tested
- [ ] Horizon validation is tested (reject unsupported; accept supported)
- [ ] InfoPrices list partial omission behavior is tested (invalid UIC does not crash; missing instrument flagged)
- [ ] Missing bars behavior is tested (Count=60, returned=12 → warning + 12 returned)
- [ ] Rate limit header parsing is tested (multiple dimensions)
- [ ] 429 handling behavior is tested (Retry-After preferred; no busy-loop)
- [ ] Tests run via `pytest` and pass

## Technical Details

### Prerequisites
- Stories 003-001 through 003-005 implemented

### Test Location
- `tests/test_market_data.py` (extend existing)

### Mocking Strategy
- Use `unittest.mock` (or `pytest` monkeypatch) to mock:
  - `requests.get` inside `data/saxo_client.py`, OR
  - `SaxoClient.get()` (and/or `get_with_headers()`) if introduced

### Suggested Test Cases

#### 1) InfoPrices list success
- Two instruments returned
- Normalized output has correct instrument_ids and quote fields

#### 2) InfoPrices missing Mid
- Mid derived from bid/ask

#### 3) InfoPrices list partial omission
- Requested UICs include one invalid UIC
- Response `Data` contains only the valid instrument
- Assert:
  - no exception raised
  - valid instrument present
  - invalid instrument present as `{"quote": None, "error": {"code": "MISSING_FROM_RESPONSE"}}`

#### 4) Chart v3 stock bars
- Produces expected OHLC/time

#### 5) Chart v3 FX bid/ask bars
- Mid conversion correct

#### 6) Horizon validation
- For each supported horizon value from the Support-page set:
  - does not raise validation error
- For at least one unsupported horizon (e.g., 2 or 3 from reference docs but not in Support set):
  - raises a clear validation error
- Assert that validation treats the Support-page set as the default accepted values

Supported horizon values (minutes) per Saxo Support Center:
- `1, 5, 10, 15, 30, 60, 120, 240, 360, 480, 1440, 10080, 43200`

This test ensures consistency with Story 003-003's Horizon validation strategy.

#### 7) Missing / illiquid bars warning
- Request `Count=60` but response returns 12
- Function returns 12 bars
- Assert that a warning log is emitted including:
  - `{instrument_id, horizon, requested_count, returned_count}`
- This ensures the bot properly handles illiquid instruments and logs the discrepancy per Story 003-003.

#### 8) Rate limit header parsing (multi dimension)
- Mock a response with headers like:
  - `X-RateLimit-Session-Remaining`, `X-RateLimit-Session-Reset`
  - `X-RateLimit-AppDay-Remaining`, `X-RateLimit-AppDay-Reset`
- Assert parse output includes all dimensions

#### 9) 429 retry/backoff with Retry-After precedence
- First call returns 429 with `Retry-After: 2` and/or X-RateLimit reset headers
- Assert the retry delay honors Retry-After (not just Session-Reset)
- Second call returns 200

## Definition of Done
- [ ] Tests are deterministic
- [ ] No external network calls are made
- [ ] Test suite passes locally

## Story Points
**Estimate:** 3 points

## Dependencies
- Stories 003-001 .. 003-005

## References
- Saxo Support - Horizon values: https://openapi.help.saxo/hc/en-us/articles/4417058210961-What-horizons-can-I-use
- Saxo Support - Missing chart data behavior: https://openapi.help.saxo/hc/en-us/articles/6105016299677-Why-is-chart-data-missing-for-this-instrument
- Saxo Learn - Pricing list semantics: https://www.developer.saxo/openapi/learn/pricing
- Saxo Learn - Rate limiting: https://www.developer.saxo/openapi/learn/rate-limiting
