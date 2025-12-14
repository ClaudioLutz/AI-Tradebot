# Story 005-004: Order placement and reconciliation (SIM)

## Summary
Place market orders in SIM after a successful precheck, and reconcile uncertain outcomes (timeouts / TradeNotCompleted) by querying Portfolio open orders.

## Background / Context
Order placement can be subject to timeouts or uncertain status, especially on exchange-based products.
Saxo explicitly documents the `TradeNotCompleted` scenario and recommends querying the portfolio using the returned OrderId (when present).
Additionally, duplicate order protections and rate limiting must be respected.

## Scope
In scope:
- Implement POST /trade/v2/orders for market orders (Stock + FxSpot) in SIM.
- Use `external_reference` and `x-request-id`.
- Handle outcomes:
  - Success with OrderId
  - Failure with ErrorInfo
  - Timeout / TradeNotCompleted → run reconciliation logic:
    - if OrderId present → query Portfolio open orders by OrderId
    - else → query open orders filtered by ExternalReference (if present in order response model in portfolio) OR fall back to time-window logging-only
- Ensure DRY_RUN never places orders.

## Technical Details

### API Endpoint Specification

#### Order Placement
```
POST https://gateway.saxobank.com/sim/openapi/trade/v2/orders
Content-Type: application/json
Authorization: Bearer {access_token}
x-request-id: {uuid}
```

#### Portfolio Orders Query
```
GET https://gateway.saxobank.com/sim/openapi/port/v1/orders?ClientKey={ClientKey}&OrderId={OrderId}
GET https://gateway.saxobank.com/sim/openapi/port/v1/orders?ClientKey={ClientKey}&Status=All
Authorization: Bearer {access_token}
```

### Request Payload Structure

#### Market Order Request
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
  }
}
```

### Response Payload Models

#### Success Response
```json
{
  "OrderId": "76545897",
  "Orders": [
    {
      "OrderId": "76545897",
      "ExternalReference": "BOT_BUY_AAPL_20251214_094100"
    }
  ]
}
```

#### Failure Response (HTTP 200 with ErrorInfo)
```json
{
  "ErrorInfo": {
    "ErrorCode": "InstrumentNotTradable",
    "Message": "The instrument cannot be traded at this time"
  }
}
```

#### Failure With Pre-Trade Disclaimers (placement errors may include disclaimers)
```json
{
  "ErrorInfo": {
    "ErrorCode": "DisclaimersNotAccepted",
    "Message": "Pre-trade disclaimers must be accepted before placing this order"
  },
  "PreTradeDisclaimers": {
    "DisclaimerContext": "OrderPlacement",
    "DisclaimerTokens": [
      "DM_RISK_WARNING_2025_Q1"
    ]
  }
}
```

#### TradeNotCompleted Response
```json
{
  "ErrorInfo": {
    "ErrorCode": "TradeNotCompleted",
    "Message": "Trade request has been received but not yet completed"
  },
  "OrderId": "76545897"
}
```

#### Timeout (no response)
```
Connection timeout after 30 seconds
```

### Data Models

```python
from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class PlacementStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNCERTAIN = "uncertain"
    TIMEOUT = "timeout"

class ReconciliationStatus(Enum):
    FOUND_WORKING = "found_working"
    FOUND_FILLED = "found_filled"
    FOUND_CANCELLED = "found_cancelled"
    NOT_FOUND = "not_found"
    QUERY_FAILED = "query_failed"
    NOT_ATTEMPTED = "not_attempted"

@dataclass
class PlacementOutcome:
    """Outcome of order placement attempt"""
    status: PlacementStatus
    order_id: Optional[str] = None
    error_info: Optional[ErrorInfo] = None
    http_status: Optional[int] = None
    request_id: Optional[str] = None
    requires_reconciliation: bool = False
    raw_response: Optional[dict] = None

@dataclass
class ReconciliationOutcome:
    """Outcome of order reconciliation query"""
    status: ReconciliationStatus
    order_id: Optional[str] = None
    order_status: Optional[str] = None  # Working, Filled, Cancelled, etc.
    fill_price: Optional[float] = None
    filled_amount: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class ExecutionOutcome:
    """Final execution outcome combining placement and reconciliation"""
    placement: PlacementOutcome
    reconciliation: Optional[ReconciliationOutcome] = None
    final_status: Literal["success", "failure", "uncertain"] = "uncertain"
    order_id: Optional[str] = None
    external_reference: str = ""
    timestamp: datetime = None
```

### Implementation Pattern

```python
class OrderPlacementClient:
    """HTTP client for Saxo order placement and reconciliation"""
    
    def __init__(self, saxo_client, logger, config):
        self.saxo_client = saxo_client
        self.logger = logger
        self.config = config
        self.placement_timeout = 30.0  # seconds
        self.reconciliation_timeout = 10.0  # seconds
        
    async def place_order(
        self,
        order_intent: OrderIntent,
        precheck_outcome: PrecheckOutcome
    ) -> ExecutionOutcome:
        """
        Place order in SIM environment after successful precheck.
        
        Handles three scenarios:
        1. Success: returns OrderId
        2. Failure: returns ErrorInfo
        3. Uncertain (timeout/TradeNotCompleted): attempts reconciliation
        """
        
        # Guard: Never place in DRY_RUN mode
        if self.config.dry_run:
            self.logger.info(
                "DRY_RUN: Skipping actual order placement",
                extra={
                    "external_reference": order_intent.external_reference,
                    "precheck_ok": precheck_outcome.ok
                }
            )
            return ExecutionOutcome(
                placement=PlacementOutcome(
                    status=PlacementStatus.SUCCESS,
                    order_id=None
                ),
                final_status="success",
                external_reference=order_intent.external_reference,
                timestamp=datetime.utcnow()
            )
        
        # Guard: Precheck must have succeeded
        if not precheck_outcome.ok:
            self.logger.error(
                "Cannot place order: precheck failed",
                extra={
                    "external_reference": order_intent.external_reference,
                    "error_code": precheck_outcome.error_info.error_code
                }
            )
            return ExecutionOutcome(
                placement=PlacementOutcome(
                    status=PlacementStatus.FAILURE,
                    error_info=precheck_outcome.error_info
                ),
                final_status="failure",
                external_reference=order_intent.external_reference,
                timestamp=datetime.utcnow()
            )
        
        # Attempt placement
        request_id = str(uuid.uuid4())
        
        try:
            payload = self._build_order_payload(order_intent)
            
            self.logger.info(
                "Placing order in SIM",
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
            
            response = await self.saxo_client.post(
                "/trade/v2/orders",
                json=payload,
                headers={"x-request-id": request_id},
                timeout=self.placement_timeout
            )
            
            placement_outcome = self._parse_placement_response(
                response,
                request_id,
                order_intent
            )
            
        except httpx.TimeoutException:
            self.logger.warning(
                "Order placement timeout",
                extra={
                    "request_id": request_id,
                    "external_reference": order_intent.external_reference,
                    "timeout_seconds": self.placement_timeout
                }
            )
            placement_outcome = PlacementOutcome(
                status=PlacementStatus.TIMEOUT,
                request_id=request_id,
                requires_reconciliation=True
            )
            
        except Exception as e:
            self.logger.exception(
                "Order placement unexpected error",
                extra={
                    "request_id": request_id,
                    "external_reference": order_intent.external_reference
                }
            )
            placement_outcome = PlacementOutcome(
                status=PlacementStatus.FAILURE,
                error_info=ErrorInfo(
                    error_code="EXCEPTION",
                    message=str(e)
                ),
                request_id=request_id
            )
        
        # Handle reconciliation if needed
        reconciliation = None
        if placement_outcome.requires_reconciliation:
            reconciliation = await self._reconcile_order(
                order_intent,
                placement_outcome
            )
        
        # Determine final status
        final_status = self._determine_final_status(
            placement_outcome,
            reconciliation
        )
        
        return ExecutionOutcome(
            placement=placement_outcome,
            reconciliation=reconciliation,
            final_status=final_status,
            order_id=placement_outcome.order_id,
            external_reference=order_intent.external_reference,
            timestamp=datetime.utcnow()
        )
    
    def _build_order_payload(self, order_intent: OrderIntent) -> dict:
        """Build Saxo order placement payload"""
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
            }
        }
    
    def _parse_placement_response(
        self,
        response: httpx.Response,
        request_id: str,
        order_intent: OrderIntent
    ) -> PlacementOutcome:
        """Parse order placement response"""
        data = response.json()
        http_status = response.status_code
        
        # Handle HTTP errors
        if http_status >= 400:
            error_code = data.get("ErrorCode", f"HTTP_{http_status}")
            error_msg = data.get("Message", "Unknown error")
            
            self.logger.error(
                "Order placement HTTP error",
                extra={
                    "request_id": request_id,
                    "http_status": http_status,
                    "error_code": error_code,
                    "error_message": error_msg,
                    "external_reference": order_intent.external_reference
                }
            )
            
            return PlacementOutcome(
                status=PlacementStatus.FAILURE,
                error_info=ErrorInfo(
                    error_code=error_code,
                    message=error_msg
                ),
                http_status=http_status,
                request_id=request_id,
                raw_response=data
            )
        
        # Check for ErrorInfo in 200 response
        if "ErrorInfo" in data:
            error_info = data["ErrorInfo"]
            error_code = error_info.get("ErrorCode", "UNKNOWN")
            error_message = error_info.get("Message", "No message")
            
            # TradeNotCompleted is special - requires reconciliation
            if error_code == "TradeNotCompleted":
                order_id = data.get("OrderId")
                
                self.logger.warning(
                    "Order placement: TradeNotCompleted",
                    extra={
                        "request_id": request_id,
                        "order_id": order_id,
                        "external_reference": order_intent.external_reference
                    }
                )
                
                return PlacementOutcome(
                    status=PlacementStatus.UNCERTAIN,
                    order_id=order_id,
                    error_info=ErrorInfo(
                        error_code=error_code,
                        message=error_message
                    ),
                    http_status=http_status,
                    request_id=request_id,
                    requires_reconciliation=True,
                    raw_response=data
                )
            
            # Other errors are definitive failures
            self.logger.error(
                "Order placement failed",
                extra={
                    "request_id": request_id,
                    "error_code": error_code,
                    "error_message": error_message,
                    "external_reference": order_intent.external_reference
                }
            )
            
            return PlacementOutcome(
                status=PlacementStatus.FAILURE,
                error_info=ErrorInfo(
                    error_code=error_code,
                    message=error_message
                ),
                http_status=http_status,
                request_id=request_id,
                raw_response=data
            )
        
        # Success path - extract OrderId
        order_id = data.get("OrderId")
        if not order_id and "Orders" in data and len(data["Orders"]) > 0:
            order_id = data["Orders"][0].get("OrderId")
        
        if not order_id:
            self.logger.error(
                "Order placement response missing OrderId",
                extra={
                    "request_id": request_id,
                    "external_reference": order_intent.external_reference,
                    "response_keys": list(data.keys())
                }
            )
            return PlacementOutcome(
                status=PlacementStatus.UNCERTAIN,
                http_status=http_status,
                request_id=request_id,
                requires_reconciliation=True,
                raw_response=data
            )
        
        self.logger.info(
            "Order placed successfully",
            extra={
                "request_id": request_id,
                "order_id": order_id,
                "external_reference": order_intent.external_reference,
                "account_key": order_intent.account_key,
                "uic": order_intent.uic
            }
        )
        
        return PlacementOutcome(
            status=PlacementStatus.SUCCESS,
            order_id=order_id,
            http_status=http_status,
            request_id=request_id,
            raw_response=data
        )
    
    async def _reconcile_order(
        self,
        order_intent: OrderIntent,
        placement_outcome: PlacementOutcome
    ) -> ReconciliationOutcome:
        """
        Reconcile uncertain order placement by querying portfolio.
        
        Strategy:
        1. If OrderId available: query by OrderId (most reliable)
        2. Else: rely on LOCAL STATE first (did we get a 201/202?).
        3. Last ditch: query by ClientKey + Status=All (scan for ExternalReference)
           - Note: This is non-contractual and best-effort.
        """
        
        self.logger.info(
            "Starting order reconciliation",
            extra={
                "external_reference": order_intent.external_reference,
                "order_id": placement_outcome.order_id,
                "placement_status": placement_outcome.status.value
            }
        )
        
        try:
            # Strategy 1: Query by OrderId if available
            if placement_outcome.order_id:
                return await self._reconcile_by_order_id(
                    placement_outcome.order_id,
                    order_intent.external_reference
                )
            
            # Strategy 2: Query by AccountKey + ExternalReference
            # This is expensive and not guaranteed to return ExternalReference in all views,
            # but is the only option if OrderId is missing.
            return await self._reconcile_by_external_reference(
                order_intent.client_key,
                order_intent.external_reference
            )
            
        except Exception as e:
            self.logger.exception(
                "Reconciliation query failed",
                extra={
                    "external_reference": order_intent.external_reference,
                    "order_id": placement_outcome.order_id
                }
            )
            return ReconciliationOutcome(
                status=ReconciliationStatus.QUERY_FAILED,
                error_message=str(e)
            )
    
    async def _reconcile_by_order_id(
        self,
        order_id: str,
        external_reference: str,
        client_key: str
    ) -> ReconciliationOutcome:
        """Query portfolio orders by OrderId using ClientKey context"""
        
        try:
            response = await self.saxo_client.get(
                f"/port/v1/orders?ClientKey={client_key}&OrderId={order_id}",
                timeout=self.reconciliation_timeout
            )
            
            if response.status_code != 200:
                return ReconciliationOutcome(
                    status=ReconciliationStatus.QUERY_FAILED,
                    order_id=order_id,
                    error_message=f"HTTP {response.status_code}"
                )
            
            data = response.json()
            orders = data.get("Data", [])
            
            if not orders:
                self.logger.warning(
                    "Reconciliation: OrderId not found in portfolio",
                    extra={
                        "order_id": order_id,
                        "external_reference": external_reference
                    }
                )
                return ReconciliationOutcome(
                    status=ReconciliationStatus.NOT_FOUND,
                    order_id=order_id
                )
            
            order = orders[0]
            order_status = order.get("Status", "Unknown")
            
            # Map Saxo order status to reconciliation status
            if order_status == "Working":
                recon_status = ReconciliationStatus.FOUND_WORKING
            elif order_status in ["Filled", "FillAndStore"]:
                recon_status = ReconciliationStatus.FOUND_FILLED
            elif order_status in ["Cancelled", "Rejected"]:
                recon_status = ReconciliationStatus.FOUND_CANCELLED
            else:
                recon_status = ReconciliationStatus.FOUND_WORKING
            
            self.logger.info(
                "Reconciliation: Order found",
                extra={
                    "order_id": order_id,
                    "order_status": order_status,
                    "external_reference": external_reference
                }
            )
            
            return ReconciliationOutcome(
                status=recon_status,
                order_id=order_id,
                order_status=order_status,
                fill_price=order.get("Price"),
                filled_amount=order.get("FilledAmount")
            )
            
        except httpx.TimeoutException:
            self.logger.error(
                "Reconciliation query timeout",
                extra={
                    "order_id": order_id,
                    "external_reference": external_reference
                }
            )
            return ReconciliationOutcome(
                status=ReconciliationStatus.QUERY_FAILED,
                order_id=order_id,
                error_message="Timeout"
            )
    
    async def _reconcile_by_external_reference(
        self,
        client_key: str,
        external_reference: str
    ) -> ReconciliationOutcome:
        """
        Query portfolio orders by ClientKey and search for ExternalReference.

        Note: This is a 'scan' operation and acts as a last-ditch effort.
        It assumes the Portfolio API returns ExternalReference, which is common
        but not strictly guaranteed in all list views.
        """
        
        try:
            # Query recent orders for client
            response = await self.saxo_client.get(
                f"/port/v1/orders?ClientKey={client_key}&Status=All",
                timeout=self.reconciliation_timeout
            )
            
            if response.status_code != 200:
                return ReconciliationOutcome(
                    status=ReconciliationStatus.QUERY_FAILED,
                    error_message=f"HTTP {response.status_code}"
                )
            
            data = response.json()
            orders = data.get("Data", [])
            
            # Search for matching ExternalReference
            for order in orders:
                if order.get("ExternalReference") == external_reference:
                    order_id = order.get("OrderId")
                    order_status = order.get("Status", "Unknown")
                    
                    self.logger.info(
                        "Reconciliation: Order found by ExternalReference",
                        extra={
                            "order_id": order_id,
                            "order_status": order_status,
                            "external_reference": external_reference
                        }
                    )
                    
                    if order_status == "Working":
                        recon_status = ReconciliationStatus.FOUND_WORKING
                    elif order_status in ["Filled", "FillAndStore"]:
                        recon_status = ReconciliationStatus.FOUND_FILLED
                    elif order_status in ["Cancelled", "Rejected"]:
                        recon_status = ReconciliationStatus.FOUND_CANCELLED
                    else:
                        recon_status = ReconciliationStatus.FOUND_WORKING
                    
                    return ReconciliationOutcome(
                        status=recon_status,
                        order_id=order_id,
                        order_status=order_status,
                        fill_price=order.get("Price"),
                        filled_amount=order.get("FilledAmount")
                    )
            
            # Not found
            self.logger.warning(
                "Reconciliation: ExternalReference not found in portfolio",
                extra={
                    "client_key": client_key,
                    "external_reference": external_reference,
                    "orders_checked": len(orders)
                }
            )
            
            return ReconciliationOutcome(
                status=ReconciliationStatus.NOT_FOUND
            )
            
        except httpx.TimeoutException:
            return ReconciliationOutcome(
                status=ReconciliationStatus.QUERY_FAILED,
                error_message="Timeout"
            )
    
    def _determine_final_status(
        self,
        placement: PlacementOutcome,
        reconciliation: Optional[ReconciliationOutcome]
    ) -> Literal["success", "failure", "uncertain"]:
        """Determine final execution status from placement and reconciliation"""
        
        # Clear success or failure from placement
        if placement.status == PlacementStatus.SUCCESS:
            return "success"
        
        if placement.status == PlacementStatus.FAILURE:
            return "failure"
        
        # Uncertain placement - check reconciliation
        if reconciliation:
            if reconciliation.status in [
                ReconciliationStatus.FOUND_WORKING,
                ReconciliationStatus.FOUND_FILLED
            ]:
                return "success"
            
            if reconciliation.status == ReconciliationStatus.FOUND_CANCELLED:
                return "failure"
        
        # Unable to determine
        return "uncertain"
```

### State Machine Diagram

```
┌─────────────────┐
│ PRECHECK PASSED │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PLACE ORDER    │
└────────┬────────┘
         │
    ┌────┴────┬───────────┬──────────┐
    │         │           │          │
    ▼         ▼           ▼          ▼
SUCCESS   FAILURE   UNCERTAIN   TIMEOUT
   │         │           │          │
   │         │      ┌────┴──────────┤
   │         │      ▼               │
   │         │  RECONCILE           │
   │         │      │               │
   │         │  ┌───┴────┬──────────┴───┐
   │         │  ▼        ▼          ▼   ▼
   │         │ FOUND   FOUND    NOT   QUERY
   │         │ WORKING FILLED   FOUND  FAIL
   │         │  │        │        │     │
   ▼         ▼  ▼        ▼        ▼     ▼
SUCCESS  FAILURE SUCCESS  FAILURE  UNCERTAIN
```

### Logging Specification

#### Placement Success
```json
{
  "timestamp": "2025-12-14T09:42:00Z",
  "level": "INFO",
  "message": "Order placed successfully",
  "request_id": "uuid-here",
  "order_id": "76545897",
  "external_reference": "BOT_BUY_AAPL_20251214_094200",
  "account_key": "Gv1B3n...",
  "uic": 211
}
```

#### Placement Failure
```json
{
  "timestamp": "2025-12-14T09:42:00Z",
  "level": "ERROR",
  "message": "Order placement failed",
  "request_id": "uuid-here",
  "error_code": "InstrumentNotTradable",
  "error_message": "The instrument cannot be traded at this time",
  "external_reference": "BOT_BUY_AAPL_20251214_094200"
}
```

#### Reconciliation Success
```json
{
  "timestamp": "2025-12-14T09:42:10Z",
  "level": "INFO",
  "message": "Reconciliation: Order found",
  "order_id": "76545897",
  "order_status": "Filled",
  "external_reference": "BOT_BUY_AAPL_20251214_094200"
}
```

## Acceptance Criteria
1. In SIM (`dry_run=False`), a successful precheck leads to exactly one placement attempt.
2. Placement uses the SIM base URL and correct endpoint for /trade/v2/orders.
3. Placement response handling:
   - On success, OrderId is captured and logged.
   - On failure, ErrorInfo is logged and no further action is attempted for that intent.
4. Timeouts / TradeNotCompleted handling:
   - If OrderId is present, executor queries Portfolio orders (using `ClientKey` + `OrderId`) to determine current order status.
   - If OrderId is missing, executor attempts to scan portfolio by `ClientKey` looking for `ExternalReference` (best effort).
   - Reconciliation outcome is logged (e.g., "placed", "not found", "unknown").
5. Placement is never attempted if precheck failed or disclaimers policy blocks the trade.
6. If placement fails and returns `PreTradeDisclaimers`, the executor captures and logs them (same shape as precheck: `DisclaimerContext: string`, `DisclaimerTokens: string[]`) so operators can resolve via the DM flow.
7. DRY_RUN mode logs but never executes actual placement.

## Implementation Notes
- Prefer `OrderDuration.DurationType = DayOrder` for Market orders unless there is a strategy-level override.
- Ensure the body uses the Saxo field names exactly (AccountKey, Amount, BuySell, OrderType, Uic, AssetType, OrderDuration, ExternalReference, ManualOrder).
- Build reconciliation around `GET /port/v1/orders` using `OrderId` filter.
- Keep reconciliation bounded (e.g., single query, then mark unknown; do not loop indefinitely).
- Use `x-request-id` header for all placement requests to enable request tracing.
- Placement can fail with `PreTradeDisclaimers` (per Saxo release notes). Treat that as a *hard block* unless disclaimer policy resolves them (Story 005-005).
- Implement appropriate timeouts: 30s for placement, 10s for reconciliation queries.
- Always log with structured fields including correlation IDs.

## Test Plan
- Unit tests (mock HTTP):
  - Success path returns OrderId.
  - Failure path returns ErrorInfo.
  - Timeout path triggers portfolio query by OrderId.
  - TradeNotCompleted triggers reconciliation.
  - Reconciliation finds order by OrderId.
  - Reconciliation finds order by ExternalReference.
  - Reconciliation fails to find order.
- Integration (SIM):
  - Place a small market order.
  - Verify order appears in open orders or is immediately filled (depending on instrument), and logs show OrderId.
  - Test DRY_RUN mode skips actual placement.

## Dependencies / Assumptions
- Depends on precheck (Story 005-003).
- Depends on portfolio orders query endpoint for reconciliation.
- Assumes OAuth token already available and SIM environment configured.
- Assumes ExternalReference is unique per order attempt.
- Assumes network connectivity and reasonable API response times.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/referencedocs/port/v1/orders/get__port
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/error-handling
