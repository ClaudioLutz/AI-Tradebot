# Story 005-001: Execution interface and OrderIntent schema

## Summary
Define the public interface for the trade execution module, and a stable internal schema to convert strategy signals into *order intents* (precheck + placement).

## Background / Context
Epic 004 introduced strategies that emit signals. Epic 005 must convert those signals into orders
in a way that is safe, testable, and debuggable. A stable schema is needed so downstream concerns
(instrument validation, precheck, placement, reconciliation, logging) are consistent and reusable.

## Scope
In scope:
- Define `TradeExecutor` (or equivalent) interface and core DTOs:
  - `OrderIntent` (client_key, account_key, instrument, side, quantity, order type, duration, correlation fields, manual_order flag)
  - `PrecheckResult` (normalized success/failure + cost/margin fields + disclaimers payload)
  - `ExecutionResult` (dry-run vs sim outcomes, order id(s), reconciliation status)
- Define correlation fields:
  - `external_reference` (<= 50 chars) for Saxo order and precheck calls
  - `request_id` (x-request-id header) for order mutations to protect against duplicates and enable safe retries
- Standardize execution logging payload shape.

Out of scope:
- Any live trading (LIVE environment)
- Advanced order types (Limit/Stop/OCO/related orders) beyond what the epic requires

## Acceptance Criteria
1. `OrderIntent` supports the minimum fields needed to place Stock and FxSpot/FxCrypto market orders:
   `(client_key, account_key, asset_type, uic, buy_sell, amount, order_type='Market', order_duration, external_reference, request_id, manual_order)`.
2. `manual_order` defaults to `False` (Automated) but can be set to `True` for UI-driven flows.
3. `external_reference` is generated for every intent and is validated to be <= 50 characters.
4. `request_id` is generated for every mutation attempt and is emitted as `x-request-id` for:
   - POST /trade/v2/orders/precheck (correlation + helps avoid tight-loop duplicate behavior)
   - POST /trade/v2/orders
   - PATCH /trade/v2/orders (future)
   - DELETE /trade/v2/orders (future)
   - **Rule**: Reuse `request_id` ONLY for idempotent retries of the exact same operation. Regenerate `request_id` for new attempts or when modifying parameters.
5. Logging context contains at minimum:
   `{instrument_id, asset_type, uic, symbol, client_key, account_key, external_reference, request_id, order_id?, http_status?}`.
6. Interface supports `dry_run: bool` to drive DRY_RUN vs SIM behavior, without changing caller code.

## Technical Implementation Details

### 1. Data Models (DTOs)

#### OrderIntent
```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class AssetType(Enum):
    STOCK = "Stock"
    FX_SPOT = "FxSpot"
    FX_CRYPTO = "FxCrypto"  # Added for crypto migration

class BuySell(Enum):
    BUY = "Buy"
    SELL = "Sell"

class OrderType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"  # Future use
    STOP = "Stop"  # Future use

class OrderDurationType(Enum):
    DAY_ORDER = "DayOrder"
    GOOD_TILL_CANCEL = "GoodTillCancel"
    GOOD_TILL_DATE = "GoodTillDate"
    FILL_OR_KILL = "FillOrKill"
    IMMEDIATE_OR_CANCEL = "ImmediateOrCancel"

@dataclass
class OrderDuration:
    duration_type: OrderDurationType
    expiration_datetime: Optional[str] = None  # ISO 8601 for GoodTillDate

@dataclass
class OrderIntent:
    """
    Represents a trade intention before validation/precheck.
    Maps directly to Saxo OpenAPI order request schema.
    """
    client_key: str   # Saxo ClientKey (required for Portfolio queries)
    account_key: str  # Saxo AccountKey (e.g., "Cf4xZWiYL6W1nMKpygBLLA==")
    asset_type: AssetType  # Stock, FxSpot, FxCrypto etc.
    uic: int  # Universal Instrument Code
    buy_sell: BuySell  # Buy or Sell
    amount: float  # Quantity (Shares for Equity, Base Units for FX - NOT Lots)
    order_type: OrderType = OrderType.MARKET
    order_duration: OrderDuration = OrderDuration(OrderDurationType.DAY_ORDER)
    manual_order: bool = False  # False = Automated/Algo, True = Human/GUI
    
    # Correlation fields
    external_reference: str = ""  # Max 50 chars, set by executor
    request_id: str = ""  # UUIDv4, set per attempt
    
    # Optional metadata
    symbol: Optional[str] = None  # For logging/debugging
    strategy_id: Optional[str] = None  # Source strategy
    
    def __post_init__(self):
        """Validate critical constraints"""
        if len(self.external_reference) > 50:
            raise ValueError(f"external_reference must be <= 50 chars, got {len(self.external_reference)}")
        if self.amount <= 0:
            raise ValueError(f"amount must be positive, got {self.amount}")
```

#### PrecheckResult
```python
@dataclass
class PrecheckResult:
    """
    Normalized precheck outcome from POST /trade/v2/orders/precheck
    """
    success: bool
    
    # Error details (when success=False)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Cost/margin estimates (when success=True)
    estimated_cost: Optional[float] = None
    estimated_currency: Optional[str] = None
    margin_impact: Optional[float] = None
    
    # Pre-trade disclaimers (May 2025 requirement)
    disclaimer_tokens: list[str] = None
    has_blocking_disclaimers: bool = False
    
    # Raw response for debugging
    raw_response: Optional[dict] = None
    
    def __post_init__(self):
        if self.disclaimer_tokens is None:
            self.disclaimer_tokens = []
```

#### ExecutionResult
```python
from enum import Enum

class ExecutionStatus(Enum):
    SUCCESS = "success"  # Order placed successfully
    DRY_RUN = "dry_run"  # Precheck ok, no placement (DRY_RUN mode)
    FAILED_PRECHECK = "failed_precheck"  # Precheck failed
    FAILED_PLACEMENT = "failed_placement"  # Placement failed
    BLOCKED_BY_DISCLAIMER = "blocked_by_disclaimer"  # Disclaimers blocking
    BLOCKED_BY_POSITION = "blocked_by_position"  # Position guard blocked
    BLOCKED_BY_MARKET_STATE = "blocked_by_market_state"  # Auction/closed
    RECONCILIATION_NEEDED = "reconciliation_needed"  # Timeout/uncertain
    RATE_LIMITED = "rate_limited"  # 429 received

@dataclass
class ExecutionResult:
    """
    Final outcome of an execution attempt
    """
    status: ExecutionStatus
    order_intent: OrderIntent
    precheck_result: Optional[PrecheckResult] = None
    
    # Saxo order details (when placed)
    order_id: Optional[str] = None  # Saxo OrderId
    
    # Error details
    error_message: Optional[str] = None
    http_status: Optional[int] = None
    
    # Timing
    timestamp: str = ""  # ISO 8601
    
    # Reconciliation flag
    needs_reconciliation: bool = False
```

### 2. External Reference Generation

```python
import hashlib
import time
from datetime import datetime

def generate_external_reference(strategy_id: str, asset_type: str, uic: int) -> str:
    """
    Generate deterministic external_reference for order tracking.
    Format: E005:{strategy}:{uic}:{hash}
    Max length: 50 chars
    
    Example: "E005:MA_CROSS:211:a7f3e"
    """
    timestamp = int(time.time())
    content = f"{strategy_id}:{asset_type}:{uic}:{timestamp}"
    hash_suffix = hashlib.md5(content.encode()).hexdigest()[:5]
    
    # Truncate strategy_id if needed to stay under 50 chars
    max_strategy_len = 50 - len(f"E005::::{hash_suffix}") - len(str(uic))
    strategy_abbr = strategy_id[:max_strategy_len]
    
    ref = f"E005:{strategy_abbr}:{uic}:{hash_suffix}"
    
    if len(ref) > 50:
        # Emergency truncation
        ref = ref[:50]
    
    return ref
```

### 3. Request ID Generation

```python
import uuid

def generate_request_id() -> str:
    """
    Generate unique request_id for x-request-id header.
    Uses UUIDv4 for guaranteed uniqueness.
    
    Saxo uses this for duplicate operation detection (15s window).
    """
    return str(uuid.uuid4())
```

### 4. TradeExecutor Interface

```python
from abc import ABC, abstractmethod

class TradeExecutor(ABC):
    """
    Abstract interface for trade execution.
    Implementations handle DRY_RUN vs SIM vs LIVE environments.
    """
    
    @abstractmethod
    def execute(self, intent: OrderIntent, dry_run: bool = True) -> ExecutionResult:
        """
        Execute a trade intent through the full pipeline:
        1. Instrument validation
        2. Position guards
        3. Market state gating
        4. Precheck
        5. Disclaimer handling
        6. Placement (if not dry_run)
        7. Reconciliation (if needed)
        
        Args:
            intent: The order intent to execute
            dry_run: If True, stop after precheck (no placement)
            
        Returns:
            ExecutionResult with outcome details
        """
        pass
    
    @abstractmethod
    def reconcile_order(self, order_id: str, external_reference: str) -> dict:
        """
        Query order status from portfolio for reconciliation.
        
        Args:
            order_id: Saxo OrderId (if available)
            external_reference: ExternalReference from intent
            
        Returns:
            Order status details from portfolio
        """
        pass
```

### 5. Saxo API Request Body Mapping

```python
def intent_to_saxo_order_request(intent: OrderIntent) -> dict:
    """
    Map OrderIntent to Saxo POST /trade/v2/orders request body.
    
    Saxo API schema:
    https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
    """
    request_body = {
        "AccountKey": intent.account_key,
        "Amount": intent.amount,
        "AssetType": intent.asset_type.value,
        "BuySell": intent.buy_sell.value,
        "OrderType": intent.order_type.value,
        "Uic": intent.uic,
        "ManualOrder": intent.manual_order,
        "OrderDuration": {
            "DurationType": intent.order_duration.duration_type.value
        }
    }
    
    # Enforce DayOrder for Market orders per rigorous Saxo requirements
    if intent.order_type == OrderType.MARKET and intent.order_duration.duration_type != OrderDurationType.DAY_ORDER:
        # Override or raise? Safest is to force DayOrder for Market to prevent rejection
        request_body["OrderDuration"]["DurationType"] = OrderDurationType.DAY_ORDER.value

    # Add expiration for GoodTillDate
    if intent.order_duration.expiration_datetime and request_body["OrderDuration"]["DurationType"] == "GoodTillDate":
        request_body["OrderDuration"]["ExpirationDateTime"] = intent.order_duration.expiration_datetime
    
    # Add external reference for correlation
    if intent.external_reference:
        request_body["ExternalReference"] = intent.external_reference
    
    return request_body
```

### 6. Structured Logging Context

```python
import logging
import json

def create_execution_log_context(intent: OrderIntent, result: ExecutionResult) -> dict:
    """
    Create structured log context for execution events.
    All fields are indexed for querying/debugging.
    """
    context = {
        # Instrument identification
        "asset_type": intent.asset_type.value,
        "uic": intent.uic,
        "symbol": intent.symbol,
        
        # Order details
        "buy_sell": intent.buy_sell.value,
        "amount": intent.amount,
        "order_type": intent.order_type.value,
        "manual_order": intent.manual_order,
        
        # Correlation fields
        "client_key": intent.client_key,
        "account_key": intent.account_key,
        "external_reference": intent.external_reference,
        "request_id": intent.request_id,
        "order_id": result.order_id,
        
        # Outcome
        "status": result.status.value,
        "http_status": result.http_status,
        "error_message": result.error_message,
        
        # Metadata
        "strategy_id": intent.strategy_id,
        "timestamp": result.timestamp,
        "needs_reconciliation": result.needs_reconciliation
    }
    
    return {k: v for k, v in context.items() if v is not None}

def log_execution(intent: OrderIntent, result: ExecutionResult, logger: logging.Logger):
    """Log execution with structured context"""
    context = create_execution_log_context(intent, result)
    
    log_level = logging.INFO if result.status == ExecutionStatus.SUCCESS else logging.WARNING
    logger.log(log_level, f"Execution {result.status.value}", extra={"context": json.dumps(context)})
```

## Implementation Notes
- Treat `(AssetType, Uic)` as the canonical instrument key (Saxo docs consistently describe instruments by UIC + AssetType).
- **AssetType Migration**: Be aware of `FxSpot` vs `FxCrypto` distinction.
- Use an internal `ExecutionContext` to carry correlation/log metadata through all steps.
- ExternalReference:
  - Keep short and deterministic enough for tracing (e.g., "E005:{strategy}:{ts}:{hash}").
  - Enforce max-length and ensure truncation is logged when applied.
  - **Not Unique Server-Side**: The API does NOT enforce uniqueness. Use it for client-side scanning/reconciliation.
- x-request-id:
  - Generate a UUIDv4 per placement attempt and persist it in logs.
  - Do not reuse request_id across attempts unless you explicitly want Saxo to treat the operation as the same.
  - **Explicit Rule**: If a request fails with an ambiguous error (timeout) and you wish to retry *idempotently*, use the same `request_id`. If you are retrying because of a logical rejection or starting a fresh attempt sequence, generate a *new* `request_id` to avoid 409 Conflict / duplicate detection windows.
- Default order duration:
  - For market orders, **MUST** be `DayOrder`.

## Test Plan
- Unit tests:
  - Validate `external_reference` length handling (accept <= 50; reject/trim > 50 with log).
  - Validate `request_id` generation and header injection into HTTP client.
  - Validate serialization of `OrderIntent` into the exact request body fields expected by Saxo.
  - Verify `manual_order` flag propagates correctly.
  - Verify `FxCrypto` is supported.
- Contract-style tests:
  - Snapshot JSON for a Stock market order and an FxSpot market order.

### Example Unit Tests

```python
import pytest
from execution.models import OrderIntent, AssetType, BuySell, OrderType

def test_external_reference_max_length():
    """Test that external_reference exceeding 50 chars raises error"""
    intent = OrderIntent(
        client_key="client_123",
        account_key="test_key",
        asset_type=AssetType.STOCK,
        uic=211,
        buy_sell=BuySell.BUY,
        amount=100,
        external_reference="x" * 51  # Too long
    )
    
    with pytest.raises(ValueError, match="external_reference must be <= 50 chars"):
        intent.__post_init__()

def test_intent_to_saxo_request_mapping():
    """Test OrderIntent maps correctly to Saxo API format"""
    intent = OrderIntent(
        client_key="client_123",
        account_key="Cf4xZWiYL6W1nMKpygBLLA==",
        asset_type=AssetType.STOCK,
        uic=211,
        buy_sell=BuySell.BUY,
        amount=100,
        external_reference="E005:TEST:211:abc12",
        manual_order=True
    )
    
    request = intent_to_saxo_order_request(intent)
    
    assert request["AccountKey"] == "Cf4xZWiYL6W1nMKpygBLLA=="
    assert request["AssetType"] == "Stock"
    assert request["Uic"] == 211
    assert request["BuySell"] == "Buy"
    assert request["Amount"] == 100
    assert request["OrderType"] == "Market"
    assert request["ExternalReference"] == "E005:TEST:211:abc12"
    assert request["ManualOrder"] is True
    assert request["OrderDuration"]["DurationType"] == "DayOrder"

def test_request_id_uniqueness():
    """Test that request_id values are unique"""
    ids = {generate_request_id() for _ in range(1000)}
    assert len(ids) == 1000  # All unique
```

## Dependencies / Assumptions
- Requires environment configuration providing:
  - AccountKey for SIM trading
  - Base URL for SIM: `https://gateway.saxobank.com/sim/openapi/`
  - OAuth token handling (already implemented elsewhere)
- Signals produced by Epic 004 must provide enough information to map to an instrument (AssetType + Uic) and a side.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade/schema-orderdurationtype
- https://www.developer.saxo/openapi/learn/reference-data
