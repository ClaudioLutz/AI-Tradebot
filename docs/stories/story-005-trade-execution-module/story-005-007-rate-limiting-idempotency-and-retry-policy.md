# Story 005-007: Rate limiting, idempotency, and retry policy

## Summary
Define and implement a robust execution reliability layer: enforce Saxo rate limits, avoid duplicate order operations, and implement safe retry/backoff behavior.

## Background / Context
Saxo OpenAPI enforces global and per-session limits, including a max of 1 order per session per second.
It also rejects identical order operations within a rolling 15-second window unless the caller uses distinct
`x-request-id` values. Placement can also timeout (TradeNotCompleted) where the order may still have been placed.
These constraints must be reflected in acceptance criteria and implementation to prevent accidental duplication
and to maintain system stability.

## Scope
In scope:
- Enforce a local rate limiter for order placement (and other order mutations) to respect 1 order/sec/session.
- Implement retry policy by error category:
  - 429 Too Many Requests → backoff until reset (respect rate limit headers when present)
  - 5xx / transient network errors → limited retries with exponential backoff + jitter
  - 409 Conflict (duplicate operation) → do not retry automatically; treat as de-bounce failure
  - TradeNotCompleted → do not retry placement; reconcile via portfolio
- Ensure the orchestrator loop never crashes on HTTP exceptions.

## Acceptance Criteria
1. Executor enforces max 1 order placement per second per session (local limiter is global/process-wide).
2. Rate limiter reads and uses `X-RateLimit-*` headers to compute next allowed time (not just `sleep(1.0)`).
3. On 429, executor backs off and retries up to N times (configurable), and logs rate limit headers when present.
4. On 409 conflict (duplicate operation), executor does not retry automatically and logs an explicit message
   referencing x-request-id / duplicate-window behavior.
5. On TradeNotCompleted/timeouts for exchange-based products, executor performs reconciliation instead of retrying placement.
6. All retries include correlation fields (`external_reference`, `request_id`) and do not violate duplicate-operation protections.
7. Retry invariants are documented and enforced (see Retry Invariants section below).

## Technical Architecture

### Rate Limiter Implementation

```python
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import time

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    orders_per_second: float = 1.0  # Saxo limit: 1 order/sec/session
    burst_allowance: int = 0  # No burst for orders
    enable_adaptive: bool = True  # Adapt based on 429 responses
    
class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for order operations
    
    Enforces 1 order/second limit per session as required by Saxo
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens: float = 1.0
        self.max_tokens: float = 1.0 + config.burst_allowance
        self.last_update: float = time.time()
        self.lock = asyncio.Lock()
        self._wait_until: Optional[float] = None
        
    async def acquire(self, operation: str = "order") -> None:
        """
        Acquire a token before making an order request
        
        Args:
            operation: Type of operation (for logging)
        """
        async with self.lock:
            now = time.time()
            
            # If we have a rate limit reset time, wait until then
            if self._wait_until and now < self._wait_until:
                wait_seconds = self._wait_until - now
                logger.info(
                    "rate_limit_waiting",
                    operation=operation,
                    wait_seconds=round(wait_seconds, 2)
                )
                await asyncio.sleep(wait_seconds)
                now = time.time()
                self._wait_until = None
            
            # Refill tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(
                self.max_tokens,
                self.tokens + (elapsed * self.config.orders_per_second)
            )
            self.last_update = now
            
            # Wait if no tokens available
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.config.orders_per_second
                logger.info(
                    "rate_limit_token_wait",
                    operation=operation,
                    wait_seconds=round(wait_time, 2),
                    tokens_available=round(self.tokens, 3)
                )
                await asyncio.sleep(wait_time)
                self.tokens = 1.0
                self.last_update = time.time()
            
            # Consume token
            self.tokens -= 1.0
            logger.debug(
                "rate_limit_token_acquired",
                operation=operation,
                tokens_remaining=round(self.tokens, 3)
            )
            
    def set_reset_time(self, reset_timestamp: Optional[int]) -> None:
        """
        Set explicit wait time based on X-RateLimit-Reset header
        
        Args:
            reset_timestamp: Unix timestamp when rate limit resets
        """
        if reset_timestamp:
            self._wait_until = float(reset_timestamp)
            logger.warning(
                "rate_limit_reset_scheduled",
                reset_at=datetime.fromtimestamp(reset_timestamp).isoformat(),
                wait_seconds=round(self._wait_until - time.time(), 2)
            )
```

### Rate Limit Header Parser

```python
from typing import Dict, Optional

@dataclass
class RateLimitInfo:
    """Parsed rate limit information from response headers"""
    session_orders_limit: Optional[int] = None
    session_orders_remaining: Optional[int] = None
    session_orders_reset: Optional[int] = None  # Unix timestamp
    session_requests_limit: Optional[int] = None
    session_requests_remaining: Optional[int] = None
    session_requests_reset: Optional[int] = None
    
    @property
    def is_near_limit(self) -> bool:
        """Check if we're close to hitting the limit"""
        if self.session_orders_remaining is not None:
            return self.session_orders_remaining < 3
        return False
        
def parse_rate_limit_headers(headers: Dict[str, str]) -> RateLimitInfo:
    """
    Parse Saxo rate limit headers from HTTP response
    
    Headers:
    - X-RateLimit-SessionOrders-Limit
    - X-RateLimit-SessionOrders-Remaining
    - X-RateLimit-SessionOrders-Reset
    - X-RateLimit-SessionRequests-Limit
    - X-RateLimit-SessionRequests-Remaining
    - X-RateLimit-SessionRequests-Reset
    """
    return RateLimitInfo(
        session_orders_limit=_safe_int(headers.get("X-RateLimit-SessionOrders-Limit")),
        session_orders_remaining=_safe_int(headers.get("X-RateLimit-SessionOrders-Remaining")),
        session_orders_reset=_safe_int(headers.get("X-RateLimit-SessionOrders-Reset")),
        session_requests_limit=_safe_int(headers.get("X-RateLimit-SessionRequests-Limit")),
        session_requests_remaining=_safe_int(headers.get("X-RateLimit-SessionRequests-Remaining")),
        session_requests_reset=_safe_int(headers.get("X-RateLimit-SessionRequests-Reset"))
    )

def _safe_int(value: Optional[str]) -> Optional[int]:
    """Safely convert string to int"""
    try:
        return int(value) if value else None
    except (ValueError, TypeError):
        return None
```

### Retry Policy Implementation

```python
from enum import Enum
from typing import Callable, TypeVar, Optional
import random

class RetryCategory(Enum):
    """Categories for retry behavior"""
    TRANSIENT_NETWORK = "transient_network"  # Retry with backoff
    RATE_LIMITED = "rate_limited"  # Retry after reset
    CONFLICT = "conflict"  # Do not retry
    TRADE_NOT_COMPLETED = "trade_not_completed"  # Reconcile, do not retry
    CLIENT_ERROR = "client_error"  # Do not retry (4xx)
    SERVER_ERROR = "server_error"  # Retry with backoff
    UNKNOWN = "unknown"  # Conservative retry

@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 2
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 10.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    # Category-specific overrides
    retry_on_conflict: bool = False
    retry_on_trade_not_completed: bool = False

def classify_error(
    status_code: int,
    error_code: Optional[str],
    error_message: str
) -> RetryCategory:
    """
    Classify error for retry decision
    
    Args:
        status_code: HTTP status code
        error_code: Saxo error code if available
        error_message: Error message text
        
    Returns:
        RetryCategory indicating how to handle
    """
    # 429 Too Many Requests
    if status_code == 429:
        return RetryCategory.RATE_LIMITED
        
    # 409 Conflict (duplicate operation)
    if status_code == 409:
        return RetryCategory.CONFLICT
        
    # 4xx Client Errors (don't retry)
    if 400 <= status_code < 500:
        # Special case: TradeNotCompleted
        if "TradeNotCompleted" in error_message or error_code == "TradeNotCompleted":
            return RetryCategory.TRADE_NOT_COMPLETED
        return RetryCategory.CLIENT_ERROR
        
    # 5xx Server Errors (retry)
    if 500 <= status_code < 600:
        return RetryCategory.SERVER_ERROR
        
    # Network/timeout errors (retry)
    if status_code == 0 or status_code is None:
        return RetryCategory.TRANSIENT_NETWORK
        
    return RetryCategory.UNKNOWN

class RetryPolicy:
    """Implements retry logic with exponential backoff and jitter"""
    
    def __init__(self, config: RetryConfig, rate_limiter: TokenBucketRateLimiter):
        self.config = config
        self.rate_limiter = rate_limiter
        
    async def execute_with_retry(
        self,
        operation: Callable,
        operation_name: str,
        external_reference: str,
        **kwargs
    ) -> any:
        """
        Execute operation with retry logic
        
        Args:
            operation: Async callable to execute
            operation_name: Name for logging
            external_reference: Correlation ID
            **kwargs: Arguments to pass to operation
            
        Returns:
            Result from operation
            
        Raises:
            Exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # Acquire rate limit token before each attempt
                await self.rate_limiter.acquire(operation_name)
                
                logger.info(
                    "executing_operation",
                    operation=operation_name,
                    attempt=attempt + 1,
                    max_attempts=self.config.max_retries + 1,
                    external_reference=external_reference
                )
                
                result = await operation(**kwargs)
                
                # Success - parse rate limit headers if present
                if hasattr(result, 'headers'):
                    rate_info = parse_rate_limit_headers(result.headers)
                    if rate_info.is_near_limit:
                        logger.warning(
                            "approaching_rate_limit",
                            remaining=rate_info.session_orders_remaining,
                            operation=operation_name
                        )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Determine retry category
                status_code = getattr(e, 'status_code', None)
                error_code = getattr(e, 'error_code', None)
                error_message = str(e)
                
                category = classify_error(status_code, error_code, error_message)
                
                logger.warning(
                    "operation_failed",
                    operation=operation_name,
                    attempt=attempt + 1,
                    status_code=status_code,
                    category=category.value,
                    error=error_message,
                    external_reference=external_reference
                )
                
                # Handle specific categories
                if category == RetryCategory.CONFLICT:
                    if not self.config.retry_on_conflict:
                        logger.error(
                            "conflict_no_retry",
                            operation=operation_name,
                            message="Duplicate operation detected (409). Check x-request-id.",
                            external_reference=external_reference
                        )
                        raise
                        
                elif category == RetryCategory.TRADE_NOT_COMPLETED:
                    if not self.config.retry_on_trade_not_completed:
                        logger.error(
                            "trade_not_completed_no_retry",
                            operation=operation_name,
                            message="Order may be pending. Reconcile via portfolio query.",
                            external_reference=external_reference
                        )
                        raise
                        
                elif category == RetryCategory.CLIENT_ERROR:
                    logger.error(
                        "client_error_no_retry",
                        operation=operation_name,
                        status_code=status_code,
                        external_reference=external_reference
                    )
                    raise
                    
                elif category == RetryCategory.RATE_LIMITED:
                    # Parse reset time if available
                    if hasattr(e, 'headers'):
                        rate_info = parse_rate_limit_headers(e.headers)
                        if rate_info.session_orders_reset:
                            self.rate_limiter.set_reset_time(rate_info.session_orders_reset)
                
                # Check if we should retry
                if attempt < self.config.max_retries:
                    delay = self._calculate_backoff(attempt)
                    logger.info(
                        "retrying_after_delay",
                        operation=operation_name,
                        delay_seconds=round(delay, 2),
                        next_attempt=attempt + 2,
                        external_reference=external_reference
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "max_retries_exhausted",
                        operation=operation_name,
                        attempts=attempt + 1,
                        external_reference=external_reference
                    )
                    raise
        
        # Should not reach here
        raise last_exception
        
    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff with jitter
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = min(
            self.config.base_delay_seconds * (self.config.exponential_base ** attempt),
            self.config.max_delay_seconds
        )
        
        if self.config.jitter:
            # Add random jitter ±25%
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
            
        return max(0.1, delay)  # Minimum 100ms
```

### Request ID Management

```python
import uuid

class RequestIdManager:
    """
    Manages x-request-id headers for idempotency
    
    Saxo enforces 15-second duplicate operation window based on x-request-id
    """
    
    @staticmethod
    def generate_request_id(external_reference: str, operation: str) -> str:
        """
        Generate unique request ID
        
        Format: {external_reference}_{operation}_{timestamp_ms}_{uuid}
        
        Args:
            external_reference: Order external reference
            operation: "precheck", "place", "modify", etc.
            
        Returns:
            Unique request ID
        """
        unique_id = str(uuid.uuid4())[:8]
        timestamp = int(time.time() * 1000)  # milliseconds
        return f"{external_reference}_{operation}_{timestamp}_{unique_id}"
        
    @staticmethod
    def should_regenerate_on_retry(category: RetryCategory) -> bool:
        """
        Determine if request_id should change on retry
        
        - Same request_id: Idempotent retry of exact same operation
        - New request_id: New attempt after transient failure
        
        Recommendation: Generate NEW request_id on retry to avoid
        409 Conflict if the original request partially succeeded
        
        Saxo's duplicate detection is based on:
        - Same URL + same request body + same x-request-id
        - Within 15-second window
        
        Changing request_id allows retry to proceed even if first attempt
        is still in-flight or uncertain.
        """
        # Always use new request_id on retry
        return True
```

### Retry Invariants

To ensure safe retry behavior and prevent accidental duplicate orders, the following invariants must be maintained:

#### Invariant 1: Stable External Reference
**Rule**: On retry after timeout/unknown outcome, **reuse the same `external_reference`**  
**Rationale**: Reconciliation queries need a stable correlation ID to find existing orders  
**Implementation**: `external_reference` is generated once per `OrderIntent` and never changes

```python
# CORRECT - external_reference stays constant
intent = OrderIntent(external_reference="E005_BUY_AAPL_001", ...)
attempt_1 = await execute(intent)  # timeout
attempt_2 = await execute(intent)  # retry with same external_reference
```

#### Invariant 2: Fresh Request ID on Retry
**Rule**: On retry, **generate NEW `x-request-id`** unless explicitly duplicating  
**Rationale**: Saxo's 15-second duplicate window uses `(URL + body + x-request-id)`. Changing request_id allows retry even if first attempt is in-flight  
**Implementation**: Generate new request_id for each placement attempt

```python
# CORRECT - new request_id per attempt
attempt_1: x-request-id = "E005_BUY_AAPL_001_place_1702541234567_a1b2"
attempt_2: x-request-id = "E005_BUY_AAPL_001_place_1702541245890_c3d4"  # NEW
```

#### Invariant 3: Persist Intent State
**Rule**: Persist `{external_reference → last_attempt_state}` even if lightweight  
**Rationale**: Prevents restarts from re-issuing same intent without reconciliation  
**Implementation**: Lightweight local store (SQLite, JSON file, or in-memory with checkpoint)

```python
class IntentTracker:
    """Tracks order intent state across retries and restarts"""
    
    def __init__(self, storage_path: str):
        self.storage = {}  # In-memory, persisted to disk
        
    def record_attempt(
        self,
        external_reference: str,
        status: str,  # "pending", "timeout", "confirmed"
        order_id: Optional[str] = None
    ):
        self.storage[external_reference] = {
            "status": status,
            "order_id": order_id,
            "last_attempt": time.time()
        }
        self._persist()
        
    def should_retry(self, external_reference: str) -> bool:
        """Check if retry is safe"""
        state = self.storage.get(external_reference)
        if not state:
            return True  # First attempt
        
        if state["status"] == "confirmed":
            return False  # Already placed
        
        if state["status"] == "timeout":
            # Must reconcile first
            return False
        
        return True
```

#### Invariant 4: Reconcile Before Retry
**Rule**: After timeout/TradeNotCompleted, **reconcile before retrying placement**  
**Rationale**: Order may have been placed despite timeout; avoid duplicate  
**Implementation**: Query portfolio orders by external_reference

```python
async def safe_retry_after_timeout(intent: OrderIntent):
    """Safe retry pattern after timeout"""
    
    # Step 1: Check if order exists
    existing_orders = await portfolio.query_orders(
        external_reference=intent.external_reference
    )
    
    if existing_orders:
        # Order was placed despite timeout
        logger.info(
            "order_found_in_reconciliation",
            external_reference=intent.external_reference,
            order_id=existing_orders[0]["OrderId"]
        )
        return existing_orders[0]
    
    # Step 2: Safe to retry with NEW request_id
    logger.info(
        "safe_to_retry_after_reconciliation",
        external_reference=intent.external_reference
    )
    return await place_order(intent)
```

### Integration Example

```python
class OrderExecutor:
    """Example integration of rate limiting and retry with invariants"""
    
    def __init__(self, client: SaxoClient):
        self.client = client
        
        # Initialize rate limiter (global singleton)
        rate_config = RateLimitConfig(orders_per_second=1.0)
        self.rate_limiter = TokenBucketRateLimiter(rate_config)
        
        # Initialize retry policy
        retry_config = RetryConfig(
            max_retries=2,
            retry_on_conflict=False,
            retry_on_trade_not_completed=False
        )
        self.retry_policy = RetryPolicy(retry_config, self.rate_limiter)
        
        # Initialize intent tracker
        self.intent_tracker = IntentTracker("data/intent_state.json")
        
    async def place_order(self, order_intent: OrderIntent) -> OrderResult:
        """Place order with rate limiting, retry, and invariants"""
        
        external_ref = order_intent.external_reference
        
        # Check if safe to retry (Invariant 3)
        if not self.intent_tracker.should_retry(external_ref):
            existing_state = self.intent_tracker.get_state(external_ref)
            if existing_state["status"] == "timeout":
                # Must reconcile first (Invariant 4)
                return await self.reconcile_and_retry(order_intent)
            else:
                raise Exception(f"Order {external_ref} already processed")
        
        # Record attempt
        self.intent_tracker.record_attempt(external_ref, "pending")
        
        # Generate NEW request_id for this attempt (Invariant 2)
        request_id = RequestIdManager.generate_request_id(external_ref, "place")
        
        async def _place_operation():
            return await self.client.post(
                "/trade/v2/orders",
                json=order_intent.to_dict(),
                headers={
                    "X-Request-ID": request_id  # Fresh for each attempt
                }
            )
        
        try:
            response = await self.retry_policy.execute_with_retry(
                operation=_place_operation,
                operation_name="place_order",
                external_reference=external_ref  # Stable (Invariant 1)
            )
            
            result = OrderResult.from_response(response)
            self.intent_tracker.record_attempt(
                external_ref,
                "confirmed",
                result.order_id
            )
            return result
            
        except Exception as e:
            # Log final failure
            logger.error(
                "order_placement_failed_final",
                external_reference=external_ref,
                request_id=request_id,
                error=str(e)
            )
            
            # Record timeout for reconciliation
            if "timeout" in str(e).lower():
                self.intent_tracker.record_attempt(external_ref, "timeout")
            
            raise
    
    async def reconcile_and_retry(self, intent: OrderIntent) -> OrderResult:
        """Reconcile before retry (Invariant 4)"""
        
        logger.info(
            "reconciling_before_retry",
            external_reference=intent.external_reference
        )
        
        # Query existing orders
        orders = await self.portfolio.query_orders(
            external_reference=intent.external_reference
        )
        
        if orders:
            # Found existing order
            logger.info(
                "order_found_skipping_retry",
                external_reference=intent.external_reference,
                order_id=orders[0]["OrderId"]
            )
            self.intent_tracker.record_attempt(
                intent.external_reference,
                "confirmed",
                orders[0]["OrderId"]
            )
            return OrderResult.from_portfolio_order(orders[0])
        
        # No order found - safe to retry
        logger.info(
            "no_order_found_retrying",
            external_reference=intent.external_reference
        )
        
        # Clear timeout state and retry
        self.intent_tracker.clear_state(intent.external_reference)
        return await self.place_order(intent)
```

## Implementation Notes
- **Rate Limiter Scope**: Use a singleton rate limiter per process to enforce global 1 order/sec limit across all strategies/accounts
- **Header-Driven Throttling**: Parse rate limit headers (`X-RateLimit-SessionOrders-*`) and use them to compute next allowed time, not just `sleep(1.0)`
- **Token Bucket**: Provides smooth rate limiting with deterministic behavior for testing
- **Jitter**: Prevents thundering herd when multiple operations retry simultaneously
- **Request ID Strategy**: Generate new request_id on each retry to avoid 409 Conflict
- **Retry Invariants**: Enforce the four invariants (stable external_reference, fresh request_id, persist state, reconcile before retry)
- **Conservative Defaults**: Most errors don't auto-retry; prefer reconciliation over duplicate risk
- **Correlation**: Include `external_reference` in all log events for end-to-end tracing
- **Persistence**: Implement lightweight intent state tracking (SQLite/JSON) so restarts don't re-issue without reconciliation
- Keep retry budget low (e.g., 2–3 retries) to avoid cascading actions in fast loops

## Test Plan
- Unit tests:
  - Rate limiter blocks/queues a second order attempt within 1 second.
  - 429 response triggers backoff (simulate header Reset=1).
  - 409 conflict is treated as terminal for that intent.
  - Timeout triggers reconciliation path, not a second placement.

## Dependencies / Assumptions
- Depends on Story 005-004 reconciliation mechanics and Story 005-001 request_id header.
- Requires a clock abstraction or injectable sleep for deterministic tests.

## Critical Correctness Notes

### Saxo Duplicate Detection Mechanics
Saxo detects duplicate operations based on:
1. **Same URL** (endpoint path)
2. **Same request body** (all fields including external_reference)
3. **Same x-request-id** header
4. **Within 15-second rolling window**

**Implication**: Changing external_reference OR x-request-id allows retry to proceed. For safe retry after timeout, keep external_reference constant (for reconciliation) but change x-request-id (to bypass duplicate detection).

### Rate Limiting Behavior
Per Saxo documentation:
- Limit is **per session** (OAuth token), not per process
- Multiple processes sharing same token share the limit
- Headers provide real-time limit status
- 429 responses include `X-RateLimit-SessionOrders-Reset` timestamp
- Respect reset time rather than fixed backoff

## Primary Sources
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
- https://developer.saxobank.com/openapi/learn/rate-limiting (additional rate limit guidance)
- https://openapi.help.saxo/hc/en-us/articles/4418504615057-How-do-I-label-orders-with-a-client-defined-order-ID (external reference usage)
