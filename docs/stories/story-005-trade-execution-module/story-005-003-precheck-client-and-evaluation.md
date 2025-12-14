# Story 005-003: Precheck client and evaluation

## Summary
Implement a robust precheck step for all orders using Saxo's precheck endpoint, normalize the result, and block placement when precheck indicates failure.

## Background / Context
Epic 005 requires a strict "precheck-first" workflow. Saxo's precheck endpoint can validate the order,
return estimated costs/margin, and surface required pre-trade disclaimers. Importantly, precheck may return
HTTP 200 even when the order is not valid; the client must check the response payload for errors.

## Scope
In scope:
- Implement HTTP client wrapper for POST /trade/v2/orders/precheck.
- Map `OrderIntent` → Precheck request body (Market orders, Stock + FxSpot).
- Normalize response into `PrecheckOutcome`:
  - `ok: bool`
  - `error_info` (code/message) when not ok
  - `estimated_cost`, `margin_impact` (if returned)
  - `pre_trade_disclaimers` payload (for downstream story)
- Enforce rule: placement is only attempted when precheck is ok and disclaimers policy allows.

## Technical Details

### API Endpoint Specification
```
POST https://gateway.saxobank.com/sim/openapi/trade/v2/orders/precheck
Content-Type: application/json
Authorization: Bearer {access_token}
x-request-id: {uuid}
```

### Request Payload Structure
```json
{
  "AccountKey": "string",
  "Amount": number,
  "AssetType": "Stock" | "FxSpot",
  "BuySell": "Buy" | "Sell",
  "ManualOrder": false,
  "OrderType": "Market",
  "Uic": number,
  "ExternalReference": "string",
  "OrderDuration": {
    "DurationType": "DayOrder"
  },
  "FieldGroups": ["Costs", "MarginImpact"]
}
```

### Response Payload Models

#### Success Response (HTTP 200, no errors)
```json
{
  "EstimatedCost": {
    "Amount": 1234.56,
    "Currency": "USD"
  },
  "MarginImpact": {
    "Amount": 500.00,
    "Currency": "USD"
  },
  "PreCheckResult": "Ok",
  "OrderId": null
}
```

#### Failed Validation (HTTP 200, with ErrorInfo)
```json
{
  "ErrorInfo": {
    "ErrorCode": "InsufficientFunds",
    "Message": "Account does not have sufficient funds to place this order"
  },
  "PreCheckResult": "Error"
}
```

#### With Pre-Trade Disclaimers
```json
{
  "PreCheckResult": "Ok",
  "PreTradeDisclaimers": {
    "DisclaimerContext": {
      "ContextType": "OrderPrecheck",
      "AccountKey": "Gv1B3n...",
      "Uic": 211
    },
    "DisclaimerTokens": [
      "DM_RISK_WARNING_2025_Q1",
      "DM_REGULATORY_NOTICE_EU"
    ]
  }
}
```

### Data Models

#### PrecheckOutcome
```python
from dataclasses import dataclass
from typing import Optional, List
from decimal import Decimal

@dataclass
class ErrorInfo:
    error_code: str
    message: str

@dataclass
class EstimatedCost:
    amount: Decimal
    currency: str

@dataclass
class MarginImpact:
    amount: Decimal
    currency: str

@dataclass
class DisclaimerContext:
    """Context information for disclaimers"""
    context_type: str  # "OrderPrecheck", "OrderPlacement", etc.
    account_key: str
    uic: int
    
@dataclass
class PreTradeDisclaimers:
    """Pre-trade disclaimer data from precheck response"""
    disclaimer_context: DisclaimerContext
    disclaimer_tokens: List[str]  # List of disclaimer token strings

@dataclass
class PrecheckOutcome:
    ok: bool
    error_info: Optional[ErrorInfo] = None
    estimated_cost: Optional[EstimatedCost] = None
    margin_impact: Optional[MarginImpact] = None
    pre_trade_disclaimers: Optional[PreTradeDisclaimers] = None
    http_status: int = 200
    request_id: Optional[str] = None
    raw_response: Optional[dict] = None  # For debugging
```

### Implementation Pattern

```python
class PrecheckClient:
    """HTTP client for Saxo precheck endpoint"""
    
    def __init__(self, saxo_client, logger):
        self.saxo_client = saxo_client
        self.logger = logger
        
    async def execute_precheck(
        self, 
        order_intent: OrderIntent
    ) -> PrecheckOutcome:
        """
        Execute precheck for an order intent.
        
        Returns PrecheckOutcome with ok=True only if:
        - HTTP 2xx received
        - No ErrorInfo in response
        - PreCheckResult == "Ok"
        """
        request_id = str(uuid.uuid4())
        
        try:
            # Build request payload
            payload = self._build_precheck_payload(order_intent)
            
            # Log the precheck attempt
            self.logger.info(
                "Executing precheck",
                extra={
                    "request_id": request_id,
                    "account_key": order_intent.account_key,
                    "asset_type": order_intent.asset_type,
                    "uic": order_intent.uic,
                    "external_reference": order_intent.external_reference,
                    "buy_sell": order_intent.buy_sell,
                    "amount": order_intent.amount
                }
            )
            
            # Execute HTTP request
            response = await self.saxo_client.post(
                "/trade/v2/orders/precheck",
                json=payload,
                headers={"x-request-id": request_id},
                timeout=10.0
            )
            
            # Parse response
            return self._parse_precheck_response(
                response, 
                request_id,
                order_intent
            )
            
        except httpx.TimeoutException as e:
            self.logger.error(
                "Precheck timeout",
                extra={
                    "request_id": request_id,
                    "external_reference": order_intent.external_reference,
                    "error": str(e)
                }
            )
            return PrecheckOutcome(
                ok=False,
                error_info=ErrorInfo(
                    error_code="TIMEOUT",
                    message="Precheck request timed out"
                ),
                request_id=request_id
            )
            
        except Exception as e:
            self.logger.exception(
                "Precheck unexpected error",
                extra={
                    "request_id": request_id,
                    "external_reference": order_intent.external_reference
                }
            )
            return PrecheckOutcome(
                ok=False,
                error_info=ErrorInfo(
                    error_code="EXCEPTION",
                    message=f"Unexpected error: {str(e)}"
                ),
                request_id=request_id
            )
    
    def _build_precheck_payload(self, order_intent: OrderIntent) -> dict:
        """Map OrderIntent to Saxo precheck payload"""
        return {
            "AccountKey": order_intent.account_key,
            "Amount": float(order_intent.amount),
            "AssetType": order_intent.asset_type,
            "BuySell": order_intent.buy_sell,
            "ManualOrder": False,
            "OrderType": "Market",
            "Uic": order_intent.uic,
            "ExternalReference": order_intent.external_reference,
            "OrderDuration": {
                "DurationType": "DayOrder"
            },
            "FieldGroups": ["Costs", "MarginImpactBuySell"]
        }
    
    def _parse_precheck_response(
        self, 
        response: httpx.Response,
        request_id: str,
        order_intent: OrderIntent
    ) -> PrecheckOutcome:
        """
        Parse Saxo precheck response into normalized outcome.
        
        Critical: HTTP 200 does NOT mean success - must check ErrorInfo!
        """
        data = response.json()
        http_status = response.status_code
        
        # Check for HTTP errors (4xx, 5xx)
        if http_status >= 400:
            error_msg = data.get("Message", "Unknown error")
            error_code = data.get("ErrorCode", f"HTTP_{http_status}")
            
            self.logger.warning(
                "Precheck HTTP error",
                extra={
                    "request_id": request_id,
                    "http_status": http_status,
                    "error_code": error_code,
                    "error_message": error_msg,
                    "account_key": order_intent.account_key,
                    "uic": order_intent.uic,
                    "external_reference": order_intent.external_reference
                }
            )
            
            return PrecheckOutcome(
                ok=False,
                error_info=ErrorInfo(
                    error_code=error_code,
                    message=error_msg
                ),
                http_status=http_status,
                request_id=request_id,
                raw_response=data
            )
        
        # HTTP 200: Check for ErrorInfo in payload
        if "ErrorInfo" in data:
            error_info = data["ErrorInfo"]
            error_code = error_info.get("ErrorCode", "UNKNOWN")
            error_message = error_info.get("Message", "No message provided")
            
            self.logger.warning(
                "Precheck validation failed",
                extra={
                    "request_id": request_id,
                    "error_code": error_code,
                    "error_message": error_message,
                    "account_key": order_intent.account_key,
                    "asset_type": order_intent.asset_type,
                    "uic": order_intent.uic,
                    "external_reference": order_intent.external_reference
                }
            )
            
            return PrecheckOutcome(
                ok=False,
                error_info=ErrorInfo(
                    error_code=error_code,
                    message=error_message
                ),
                http_status=http_status,
                request_id=request_id,
                raw_response=data
            )
        
        # Extract optional fields
        estimated_cost = None
        if "EstimatedCost" in data:
            estimated_cost = EstimatedCost(
                amount=Decimal(str(data["EstimatedCost"]["Amount"])),
                currency=data["EstimatedCost"]["Currency"]
            )
        
        margin_impact = None
        if "MarginImpact" in data:
            margin_impact = MarginImpact(
                amount=Decimal(str(data["MarginImpact"]["Amount"])),
                currency=data["MarginImpact"]["Currency"]
            )
        
        disclaimers = None
        if "PreTradeDisclaimers" in data:
            ptd = data["PreTradeDisclaimers"]
            context = DisclaimerContext(
                context_type=ptd.get("DisclaimerContext", {}).get("ContextType", "OrderPrecheck"),
                account_key=ptd.get("DisclaimerContext", {}).get("AccountKey", order_intent.account_key),
                uic=ptd.get("DisclaimerContext", {}).get("Uic", order_intent.uic)
            )
            disclaimers = PreTradeDisclaimers(
                disclaimer_context=context,
                disclaimer_tokens=ptd.get("DisclaimerTokens", [])
            )
        
        # Success!
        self.logger.info(
            "Precheck succeeded",
            extra={
                "request_id": request_id,
                "account_key": order_intent.account_key,
                "uic": order_intent.uic,
                "external_reference": order_intent.external_reference,
                "estimated_cost": estimated_cost.amount if estimated_cost else None,
                "has_disclaimers": disclaimers is not None and len(disclaimers) > 0
            }
        )
        
        return PrecheckOutcome(
            ok=True,
            estimated_cost=estimated_cost,
            margin_impact=margin_impact,
            pre_trade_disclaimers=disclaimers,
            http_status=http_status,
            request_id=request_id,
            raw_response=data
        )
```

### Error Handling Matrix

| Scenario | HTTP Status | ErrorInfo Present | Outcome.ok | Action |
|----------|-------------|-------------------|------------|---------|
| Valid order | 200 | No | True | Proceed to placement (if disclaimers ok) |
| Insufficient funds | 200 | Yes | False | Block and log |
| Invalid UIC | 400 | - | False | Block and log |
| Rate limit | 429 | - | False | Retry with backoff |
| Server error | 500 | - | False | Retry once, then fail |
| Timeout | - | - | False | Retry once, then fail |
| Network error | - | - | False | Log and fail |

### Retry Logic

```python
class RetryConfig:
    max_retries: int = 1  # Single retry for transient errors
    retry_on_status: Set[int] = {429, 500, 502, 503, 504}
    backoff_base_seconds: float = 2.0
    
async def execute_precheck_with_retry(
    self, 
    order_intent: OrderIntent
) -> PrecheckOutcome:
    """Execute precheck with retry logic for transient failures"""
    for attempt in range(self.retry_config.max_retries + 1):
        outcome = await self.execute_precheck(order_intent)
        
        # Success or non-retryable error
        if outcome.ok or outcome.http_status not in self.retry_config.retry_on_status:
            return outcome
        
        # Retry logic
        if attempt < self.retry_config.max_retries:
            backoff = self.retry_config.backoff_base_seconds * (2 ** attempt)
            self.logger.info(
                f"Retrying precheck after {backoff}s",
                extra={
                    "attempt": attempt + 1,
                    "max_retries": self.retry_config.max_retries,
                    "http_status": outcome.http_status,
                    "external_reference": order_intent.external_reference
                }
            )
            await asyncio.sleep(backoff)
    
    return outcome
```

### Logging Specification

#### Precheck Attempt Log
```json
{
  "timestamp": "2025-12-14T09:41:00Z",
  "level": "INFO",
  "message": "Executing precheck",
  "request_id": "uuid-here",
  "account_key": "Gv1B3n...",
  "asset_type": "Stock",
  "uic": 211,
  "external_reference": "BOT_BUY_AAPL_20251214_094100",
  "buy_sell": "Buy",
  "amount": 100.0
}
```

#### Precheck Success Log
```json
{
  "timestamp": "2025-12-14T09:41:01Z",
  "level": "INFO",
  "message": "Precheck succeeded",
  "request_id": "uuid-here",
  "account_key": "Gv1B3n...",
  "uic": 211,
  "external_reference": "BOT_BUY_AAPL_20251214_094100",
  "estimated_cost": 15234.50,
  "has_disclaimers": false
}
```

#### Precheck Failure Log
```json
{
  "timestamp": "2025-12-14T09:41:01Z",
  "level": "WARNING",
  "message": "Precheck validation failed",
  "request_id": "uuid-here",
  "error_code": "InsufficientFunds",
  "error_message": "Account does not have sufficient funds to place this order",
  "account_key": "Gv1B3n...",
  "asset_type": "Stock",
  "uic": 211,
  "external_reference": "BOT_BUY_AAPL_20251214_094100"
}
```

## Acceptance Criteria
1. Every execution attempt calls precheck first (DRY_RUN and SIM).
2. Precheck response is evaluated correctly:
   - HTTP 200 is not treated as success unless `ErrorInfo` (or equivalent) indicates success.
3. Precheck errors are logged with:
   `{account_key, asset_type, uic, external_reference, http_status, error_code, error_message}`.
4. In DRY_RUN:
   - precheck is executed and logged; no placement occurs.
5. In SIM:
   - precheck must succeed before placement is attempted.
6. Precheck handling does not crash orchestration on HTTP errors/timeouts; it returns a structured failure.

## Implementation Notes
- Implement a "field groups" selection for precheck if you want costs/margin fields; keep it minimal at first.
- Capture and persist the raw precheck response in debug logs (with redaction if needed) to aid troubleshooting.
- Normalize the response model even if Saxo adds fields over time (treat unknown fields as ignorable).
- Use structured logging with correlation fields for all precheck operations.
- Implement single-retry logic for transient failures (429, 5xx, timeouts).
- Always use `x-request-id` header for request tracing.

## Test Plan
- Unit tests (mock HTTP):
  - HTTP 200 with ErrorInfo populated → outcome is failure.
  - HTTP 4xx/5xx → outcome is failure with http_status captured.
  - Response containing PreTradeDisclaimers → outcome carries disclaimers payload.
  - Timeout handling → returns structured failure outcome.
  - Network errors → returns structured failure outcome.
- Integration (SIM):
  - Precheck a small market order for a known tradable instrument.
  - Verify logs contain all required correlation fields.
  - Test with insufficient funds scenario (if possible).

## Dependencies / Assumptions
- Depends on Story 005-001 (schema) and Story 005-002 (instrument constraints) for request shaping/validation.
- Disclaimer handling details are specified in Story 005-005 (the precheck must forward the data).
- Assumes OAuth token is valid and refreshed as needed.
- Assumes network connectivity to Saxo SIM environment.

## Critical Schema Notes

### PreTradeDisclaimers Structure
Per Saxo's breaking-change documentation, the precheck response contains:
- `DisclaimerContext`: Object with context information (ContextType, AccountKey, Uic)
- `DisclaimerTokens`: Array of strings (not objects with Type field)
- Classification into "Normal" vs "Blocking" comes from fetching DM disclaimer details (Story 005-005), NOT from the precheck payload
- Do NOT assume a "Type" field exists in the precheck response

### FieldGroups Specification
Per Saxo precheck API documentation, use:
- `"Costs"`: Returns estimated cost fields
- `"MarginImpactBuySell"`: Returns margin impact (NOT "MarginImpact")
- Verify actual field names against primary source docs to prevent "passes in DRY_RUN but fails in SIM" issues

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/learn/breaking-change-pre-trade-disclaimers-on-openapi
- https://www.developer.saxo/openapi/learn/pre-trade-disclaimers
- https://www.developer.saxo/openapi/learn/error-handling
