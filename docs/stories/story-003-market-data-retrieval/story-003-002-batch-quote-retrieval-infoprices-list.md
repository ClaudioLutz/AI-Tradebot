# Story 003-002: Batch Quote Retrieval via InfoPrices List

## Story Overview
Implement batch quote retrieval for the watchlist using Saxo **InfoPrices**. Prefer the **list** endpoint to reduce request volume and improve stability under Saxo rate limits.

This story also documents Saxo’s **list semantics**: list endpoints can return **partial results** (including omitting invalid instruments) without raising an HTTP error.

## Parent Epic
[Epic 003: Market Data Retrieval Module (Saxo)](../../epics/epic-003-market-data-retrieval.md)

## User Story
**As a** developer  
**I want to** retrieve the latest quotes for many instruments in a single request where possible  
**So that** the bot stays under rate limits and receives consistent snapshot quotes

## Acceptance Criteria
- [ ] Implement `get_latest_quotes(instruments, field_groups=None)` in `data/market_data.py`
- [ ] Function groups instruments by `asset_type` and uses:
  - `GET /trade/v1/infoprices/list` with `Uics=<comma-separated>`
- [ ] `FieldGroups` defaults to `"Quote"` when not provided
- [ ] Do not send duplicate UICs within the same list call
- [ ] For each instrument, normalize at least:
  - `LastUpdated`, `Quote.Bid`, `Quote.Ask`, `Quote.Mid`, `Quote.DelayedByMinutes`, `Quote.MarketState`
- [ ] When present, capture additional quote metadata defined in Story 003-001:
  - `PriceTypeBid`, `PriceTypeAsk`, `ErrorCode`, `PriceSource`, `PriceSourceType`
- [ ] The return value is keyed by `instrument_id = "{asset_type}:{uic}"`
- [ ] Partial failures do not abort the whole call (return what succeeded)
- [ ] If the response `Data` omits an instrument that was requested, return a structured per-instrument error entry (do not return `None` silently)
  - example: `{"quote": None, "error": {"code": "MISSING_FROM_RESPONSE"}}`
- [ ] Logs include `{instrument_id, asset_type, uic, symbol}` and HTTP error context
- [ ] Supports optional `FieldGroups` passthrough

## Technical Details

### Prerequisites
- Story 003-001 completed (normalization helpers exist)
- Saxo client available: `data/saxo_client.py`

### Endpoint
Preferred: `GET /trade/v1/infoprices/list`

Query params:
- `AssetType` (string)
- `Uics` (comma-separated integers)
- `AccountKey` (optional)
- `FieldGroups` (optional; defaults to `"Quote"`)

> Note: the list endpoint batches **within an AssetType**. Implement grouping by `asset_type`.

### Not Supported Initially (Documented Intentionally)
Saxo’s InfoPrices surfaces include additional optional parameters such as:
- `Amount`, `AmountType`, `ToOpenClose`, ...

However:
- the list call cannot specify per-instrument sizes,
- Saxo generally recommends leaving many optional fields blank and letting defaults apply.

So for this story:
- omit these optional parameters for now,
- document that per-instrument "amount" support (if ever needed) would require per-instrument calls or a different design.

**Important note on sizing parameters:**
Even though omitted initially, be aware that `Amount` and `AmountType` parameters exist and have default sizing semantics (defaults to minimal order size). Adding them later may change returned cost/price-detail field groups if you ever request those additional FieldGroups.

### Suggested Function Contract

```python
def get_latest_quotes(
    instruments: List[Dict[str, Any]],
    field_groups: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return normalized quote snapshots keyed by instrument_id."""
```

### List Semantics: Partial Results / Omitted Items
Saxo list endpoints have “unusual semantics” for invalid input:
- the API may return a successful HTTP response,
- but the response `Data` list can be **missing** some requested instruments.

**Required behavior:**
- compute requested set `{uic}` and returned set `{uic}`
- for each missing uic, return a structured error entry:
  - `error.code = "MISSING_FROM_RESPONSE"`
  - include `error.details = {"asset_type": ..., "uic": ..., "reason": "List endpoint may omit invalid items"}`

### Duplicate UICs
Do not send the same UIC more than once in a single request.
- Deduplicate UICs before calling the endpoint.
- Log a warning if the input list contained duplicates.

### Logging Requirements
Include:
- number of instruments requested
- batch sizes per `asset_type`
- instrument-level errors (including missing-from-response)
- request timing (optional but recommended)

## Definition of Done
- [ ] Code compiles and module imports
- [ ] `get_latest_quotes()` returns expected normalized structures
- [ ] Missing instruments are represented as explicit error entries

## Testing
- Unit tests added in Story 003-006 (mocked responses for `/infoprices/list`).
- Add a unit test where `Uics` includes one invalid UIC and assert:
  - response contains only valid instruments
  - missing instrument is flagged with `MISSING_FROM_RESPONSE`

## Story Points
**Estimate:** 2 points

## Dependencies
- Story 003-001

## References
- Saxo Learn - Pricing semantics (InfoPrices/Quote fields + list semantics): https://www.developer.saxo/openapi/learn/pricing
- Saxo Reference - InfoPrices list: https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade__list
