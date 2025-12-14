# Story 005-010: Developer documentation and runbook

## Summary
Provide developer-facing documentation for configuring, running, and troubleshooting the trade execution module, including a clear safety checklist.

## Background / Context
Trade execution involves many moving parts: environment configuration, rate limits, disclaimers, market state gating,
and portfolio reconciliation. Without clear documentation and a runbook, developers will misconfigure the system or
misinterpret failures.

## Scope
In scope:
- Add a doc page describing:
  - DRY_RUN vs SIM behavior
  - required config keys (SIM base URL, account key, instrument mapping)
  - safe defaults (market state gating, disclaimer policy)
  - logging fields and how to correlate executions to Saxo orders (ExternalReference, OrderId)
  - common failure modes and remediation:
    - 429 rate limiting
    - 409 duplicate-operation conflicts (x-request-id)
    - TradeNotCompleted timeouts (portfolio reconciliation)
    - outstanding disclaimers
- Add "Safety Checklist" for running SIM tests.

## Acceptance Criteria
1. Documentation includes a "Quickstart" with a DRY_RUN example and a SIM example.
2. Documentation includes a troubleshooting section covering:
   - rate limiting headers
   - duplicate-operation window and x-request-id
   - TradeNotCompleted reconciliation
   - disclaimers blocking
3. Documentation lists all structured log fields and their meaning.
4. Documentation clarifies the default auction/market-state policy and how to override it.

## Trade Execution Module Developer Guide

### Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Configuration](#configuration)
3. [Quickstart Guide](#quickstart-guide)
4. [Execution Flow](#execution-flow)
5. [Logging and Correlation](#logging-and-correlation)
6. [Troubleshooting](#troubleshooting)
7. [Safety Checklist](#safety-checklist)
8. [API Reference](#api-reference)

---

## Architecture Overview

The trade execution module implements a safety-first, multi-gate approach to order placement:

```
Strategy Signal
    ↓
[1. Market State Gate] ← Auction/Closed filtering
    ↓
[2. Position Guards] ← Duplicate buy / position validation
    ↓
[3. Rate Limiter] ← 1 order/second enforcement
    ↓
[4. Precheck] ← Saxo validation (API call)
    ↓
[5. Disclaimer Check] ← Accept disclaimers if required
    ↓
[6. Order Placement] ← Submit order (API call)
    ↓
[7. Reconciliation] ← Verify order status
```

### Key Components

| Component | Responsibility | Fail Mode |
|-----------|---------------|-----------|
| MarketStateGate | Block trades during auctions/closed | Conservative (block on unknown) |
| PositionGuards | Prevent duplicate buys, ensure position for sells | Buy=fail-open, Sell=fail-closed |
| RateLimiter | Enforce 1 order/second | Block until slot available |
| PrecheckClient | Validate order before placement | Retry on transient errors |
| OrderPlacer | Submit order to Saxo | No auto-retry on TradeNotCompleted |
| Reconciler | Verify order status post-placement | Query portfolio orders |

---

## Configuration

### Environment Variables

```bash
# Required - Saxo API Credentials
SAXO_CLIENT_ID=your_client_id
SAXO_CLIENT_SECRET=your_client_secret
SAXO_ACCOUNT_KEY=your_sim_account_key

# Required - Execution Mode
EXECUTION_MODE=DRY_RUN  # or SIM (never LIVE in this module)
SAXO_BASE_URL=https://gateway.saxobank.com/sim/openapi

# Optional - Execution Configuration
RATE_LIMIT_ORDERS_PER_SECOND=1.0
POSITION_CACHE_TTL_SECONDS=30
MAX_RETRY_ATTEMPTS=2
ALLOW_ON_MISSING_MARKET_STATE=false

# Optional - Policy Overrides
MARKET_STATE_POLICY=default  # or "extended" for pre/post market
DUPLICATE_BUY_POLICY=block  # block, warn, allow
```

### Configuration File (config/execution.yaml)

```yaml
execution:
  # Execution mode
  mode: DRY_RUN  # DRY_RUN, SIM
  
  # Rate limiting
  rate_limit:
    orders_per_second: 1.0
    burst_allowance: 0
    enable_adaptive: true
  
  # Retry policy
  retry:
    max_retries: 2
    base_delay_seconds: 1.0
    max_delay_seconds: 10.0
    exponential_base: 2.0
    jitter: true
    retry_on_conflict: false
    retry_on_trade_not_completed: false
  
  # Position guards
  positions:
    duplicate_buy_policy: block  # block, warn, allow
    allow_short_covering: false
    cache_ttl_seconds: 30
  
  # Market state policy
  market_state:
    version: "1.0"
    allowed_states:
      - Open
    blocked_states:
      - Closed
      - Unknown
      - OpeningAuction
      - ClosingAuction
      - IntraDayAuction
      - TradingAtLast
    allow_on_missing: false
    log_allowed_trades: false
    
    # Per-asset overrides (optional)
    asset_type_overrides:
      FxSpot:
        - Open
        - PreMarket
        - PostMarket
  
  # Disclaimer policy
  disclaimers:
    auto_accept: false  # Never auto-accept in production
    required_disclaimers: []  # List of pre-accepted disclaimer IDs
```

---

## Quickstart Guide

### DRY_RUN Mode (Precheck Only)

```python
from execution.trade_executor import TradeExecutor
from execution.order_intent import OrderIntent
from data.saxo_client import SaxoClient
import asyncio

async def dry_run_example():
    # Initialize client
    client = SaxoClient(
        base_url="https://gateway.saxobank.com/sim/openapi",
        client_id=os.getenv("SAXO_CLIENT_ID"),
        client_secret=os.getenv("SAXO_CLIENT_SECRET")
    )
    await client.authenticate()
    
    # Initialize executor in DRY_RUN mode
    executor = TradeExecutor(
        client=client,
        account_key=os.getenv("SAXO_ACCOUNT_KEY"),
        mode="DRY_RUN"
    )
    
    # Create order intent
    intent = OrderIntent(
        asset_type="Stock",
        uic=211,  # AAPL
        symbol="AAPL:xnas",
        side="Buy",
        quantity=100,
        order_type="Market",
        external_reference="test_buy_001"
    )
    
    # Execute (precheck only in DRY_RUN)
    result = await executor.execute(intent)
    
    print(f"Result: {result.status}")
    print(f"Precheck: {result.precheck_result}")
    print(f"Estimated Cost: ${result.estimated_cash_required}")
    
    await client.close()

# Run
asyncio.run(dry_run_example())
```

**Expected Output:**
```
Result: precheck_success
Precheck: Ok
Estimated Cost: $15025.00
```

### SIM Mode (Full Execution)

```python
async def sim_execution_example():
    client = SaxoClient(
        base_url="https://gateway.saxobank.com/sim/openapi",
        client_id=os.getenv("SAXO_CLIENT_ID"),
        client_secret=os.getenv("SAXO_CLIENT_SECRET")
    )
    await client.authenticate()
    
    # Initialize executor in SIM mode
    executor = TradeExecutor(
        client=client,
        account_key=os.getenv("SAXO_ACCOUNT_KEY"),
        mode="SIM"  # ACTUAL ORDER PLACEMENT
    )
    
    # Create order intent (use limit order to avoid immediate fill)
    intent = OrderIntent(
        asset_type="Stock",
        uic=211,
        symbol="AAPL:xnas",
        side="Buy",
        quantity=1,  # Minimal quantity for testing
        order_type="Limit",
        limit_price=50.00,  # Low price to avoid fill
        duration="DayOrder",
        external_reference=f"sim_test_{uuid.uuid4().hex[:8]}"
    )
    
    # Execute
    result = await executor.execute(intent)
    
    if result.success:
        print(f"✓ Order placed: {result.order_id}")
        print(f"  External Ref: {result.external_reference}")
        print(f"  Status: {result.order_status}")
        
        # Cancel order for cleanup
        await executor.cancel_order(result.order_id)
        print(f"✓ Order cancelled")
    else:
        print(f"✗ Execution failed: {result.reason}")
    
    await client.close()

asyncio.run(sim_execution_example())
```

---

## Execution Flow

### Detailed Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│ 1. SIGNAL RECEIVED                                      │
│    - Strategy emits buy/sell signal                     │
│    - Create OrderIntent with external_reference         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. MARKET STATE GATE                                    │
│    - Query market state (quote → position → instrument) │
│    - Check against policy (default: allow only "Open")  │
│    - BLOCK if: Closed, Auction, TradingAtLast, Unknown │
│    - Logging: market_state_blocking / allowing          │
└────────────────────┬────────────────────────────────────┘
                     │ PASS
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 3. POSITION GUARDS                                      │
│    - Query positions (cached, 30s TTL)                  │
│    - BUY: Block if position exists (duplicate)          │
│    - SELL: Block if no position exists                  │
│    - Logging: duplicate_buy_prevented / no_position     │
└────────────────────┬────────────────────────────────────┘
                     │ PASS
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 4. RATE LIMITER                                         │
│    - Token bucket: 1 order/second                       │
│    - Sleep if no tokens available                       │
│    - Respect X-RateLimit-Reset on 429                   │
│    - Logging: rate_limit_token_wait                     │
└────────────────────┬────────────────────────────────────┘
                     │ PASS
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 5. PRECHECK (API CALL)                                  │
│    - POST /trade/v2/orders/precheck                     │
│    - Validate order parameters                          │
│    - Check margin/buying power                          │
│    - Return: Ok, Disclaimer, or Error                   │
│    - Logging: precheck_success / precheck_failed        │
└────────────────────┬────────────────────────────────────┘
                     │ PreCheckResult
                     ▼
       ┌─────────────┴─────────────┐
       │                           │
    [Ok]                     [Disclaimer]
       │                           │
       │                           ▼
       │              ┌────────────────────────────┐
       │              │ 6. DISCLAIMER HANDLER      │
       │              │ - Log disclaimer required  │
       │              │ - Block if not pre-accepted│
       │              │ - Manual acceptance needed │
       │              └────────────────────────────┘
       │                           │
       │                         STOP
       ▼
┌─────────────────────────────────────────────────────────┐
│ 7. ORDER PLACEMENT (API CALL) - DRY_RUN stops here     │
│    - POST /trade/v2/orders                              │
│    - X-Request-ID: {ext_ref}_place_{timestamp}_{uuid}  │
│    - Return: OrderId, ExternalReference                 │
│    - Logging: order_placed / placement_failed           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 8. RECONCILIATION                                       │
│    - Query /port/v1/orders                              │
│    - Match by ExternalReference                         │
│    - Verify order status (Working, Filled, etc.)        │
│    - Logging: reconciliation_success / mismatch         │
└─────────────────────────────────────────────────────────┘
```

---

## Logging and Correlation

### Structured Log Fields

All execution logs include correlation fields for tracing:

| Field | Description | Example |
|-------|-------------|---------|
| `external_reference` | Unique order identifier (generated by strategy) | `"strat_aapl_buy_20241214_001"` |
| `request_id` | HTTP X-Request-ID header | `"strat_aapl_buy_20241214_001_place_1702541234567_a1b2c3d4"` |
| `order_id` | Saxo OrderId (returned after placement) | `"76543210"` |
| `asset_type` | Instrument type | `"Stock"`, `"FxSpot"` |
| `uic` | Universal Instrument Code | `211` (AAPL) |
| `side` | Order side | `"Buy"`, `"Sell"` |
| `quantity` | Order amount | `100` |
| `account_key` | Saxo account identifier | `"ABCD1234"` |

### Log Event Types

#### Success Events
```json
{
  "event": "market_state_allowing",
  "level": "INFO",
  "timestamp": "2024-12-14T09:30:00Z",
  "asset_type": "Stock",
  "uic": 211,
  "market_state": "Open",
  "external_reference": "strat_aapl_buy_001"
}

{
  "event": "order_placed",
  "level": "INFO",
  "order_id": "76543210",
  "external_reference": "strat_aapl_buy_001",
  "request_id": "strat_aapl_buy_001_place_1702541234567_a1b2c3d4",
  "status": "Working"
}
```

#### Blocking Events
```json
{
  "event": "market_state_blocking",
  "level": "WARNING",
  "asset_type": "Stock",
  "uic": 211,
  "market_state": "ClosingAuction",
  "reason": "default_policy_ClosingAuction",
  "detail": "Market in closing auction (illiquid, volatile pricing)",
  "external_reference": "strat_aapl_buy_001"
}

{
  "event": "duplicate_buy_prevented",
  "level": "WARNING",
  "asset_type": "Stock",
  "uic": 211,
  "existing_quantity": 100,
  "intended_quantity": 100,
  "policy": "strict",
  "external_reference": "strat_aapl_buy_002"
}

{
  "event": "no_position_to_sell",
  "level": "WARNING",
  "asset_type": "Stock",
  "uic": 211,
  "external_reference": "strat_aapl_sell_001"
}
```

#### Error Events
```json
{
  "event": "rate_limit_exceeded",
  "level": "ERROR",
  "status_code": 429,
  "reset_at": "2024-12-14T09:31:00Z",
  "wait_seconds": 45.2,
  "external_reference": "strat_aapl_buy_001"
}

{
  "event": "conflict_no_retry",
  "level": "ERROR",
  "status_code": 409,
  "message": "Duplicate operation detected (409). Check x-request-id.",
  "request_id": "strat_aapl_buy_001_place_1702541234567_a1b2c3d4",
  "external_reference": "strat_aapl_buy_001"
}
```

### Correlation Query Examples

**Find all events for a specific order:**
```bash
grep "external_reference.*strat_aapl_buy_001" logs/execution.log | jq .
```

**Find order_id for external_reference:**
```bash
grep "order_placed" logs/execution.log | \
  jq 'select(.external_reference=="strat_aapl_buy_001") | .order_id'
```

**Count blocked executions by reason:**
```bash
grep "market_state_blocking" logs/execution.log | \
  jq -r .market_state | sort | uniq -c
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. 429 Too Many Requests

**Symptom:**
```
rate_limit_exceeded: status_code=429, reset_at=2024-12-14T09:31:00Z
```

**Cause:** Exceeded Saxo rate limit (1 order/second per session)

**Solution:**
- Check if multiple processes are using same session
- Verify rate limiter is properly initialized
- Inspect `X-RateLimit-SessionOrders-Remaining` header
- Wait for reset time before retrying

**Prevention:**
```python
# Ensure single executor instance per session
executor = TradeExecutor(client, account_key, mode="SIM")

# Check rate limit info
rate_info = executor.get_rate_limit_info()
print(f"Remaining: {rate_info.session_orders_remaining}")
```

#### 2. 409 Conflict (Duplicate Operation)

**Symptom:**
```
conflict_no_retry: status_code=409, message="Duplicate operation detected"
```

**Cause:** Same `X-Request-ID` used within 15-second window

**Root Causes:**
- Retry logic reusing same request_id
- Multiple processes with identical external_reference
- Rapid re-execution of same order

**Solution:**
```python
# Ensure unique request_id per attempt
request_id = RequestIdManager.generate_request_id(
    external_reference=intent.external_reference,
    operation="place"
)
# Format: {ext_ref}_place_{timestamp_ms}_{uuid}
```

**Prevention:**
- Never reuse request_id
- Wait 15+ seconds before retrying same operation
- Use unique external_reference per order intent

#### 3. TradeNotCompleted Timeout

**Symptom:**
```
trade_not_completed_no_retry: message="Order may be pending. Reconcile via portfolio query."
```

**Cause:** Order placement timed out, but order may have been placed

**DO NOT:** Retry placement (risk duplicate order)

**DO:** Reconcile via portfolio query
```python
# Query orders by external_reference
orders = await executor.query_orders(
    external_reference=intent.external_reference
)

if orders:
    print(f"Order exists: {orders[0]['OrderId']}")
    print(f"Status: {orders[0]['Status']}")
else:
    print("Order not found - safe to retry")
```

#### 4. Disclaimer Required

**Symptom:**
```
precheck_disclaimer_required: disclaimer_ids=['12345'], texts=['You must accept...']
```

**Cause:** Instrument requires disclaimer acceptance

**Solution (Development):**
1. Log disclaimer text
2. Manually accept via Saxo platform
3. Add disclaimer ID to config (if appropriate)

**Solution (Production):**
- Pre-accept disclaimers for all instruments in watchlist
- Block execution if unknown disclaimer encountered
- Never auto-accept disclaimers

```python
# Config approach
disclaimers:
  required_disclaimers:
    - "12345"  # Pre-accepted disclaimer
```

#### 5. Position Query Failure

**Symptom:**
```
position_guard_evaluation_failed: error="Connection timeout"
```

**Behavior:**
- BUY: Fail-open (allow order)
- SELL: Fail-closed (block order)

**Remediation:**
```python
# Manual position check
positions = await executor.position_manager.get_positions(force_refresh=True)
print(positions)

# Check Saxo API health
health = await client.get("/monitor/v3/health")
print(health)
```

#### 6. Market State Unknown

**Symptom:**
```
market_state_missing_blocking: policy="allow_on_missing=False"
```

**Cause:** No market state available from any source

**Solution:**
```python
# Check market data connectivity
quote = await client.get_quote(asset_type="Stock", uic=211)
print(f"MarketState: {quote.get('MarketState')}")

# Override policy (use carefully)
config.market_state.allow_on_missing = True  # Allow if missing
```

---

## Safety Checklist

### Before Running in SIM

- [ ] Environment variables configured correctly
- [ ] Using SIM base URL (not LIVE)
- [ ] Using dedicated SIM account key
- [ ] Execution mode set to `DRY_RUN` first, then `SIM`
- [ ] Order quantities are minimal (1-10 shares)
- [ ] Using limit orders with low prices (to avoid fills)
- [ ] Rate limiter is enabled
- [ ] Position guards are enabled
- [ ] Market state gate is configured (default: block auctions)
- [ ] Disclaimers reviewed and pre-accepted if needed
- [ ] Logging configured to capture all execution events
- [ ] Test orders have unique `external_reference`
- [ ] Cleanup plan for test orders (cancel after placement)

### Testing Protocol

1. **DRY_RUN Testing**
   ```bash
   EXECUTION_MODE=DRY_RUN python -m execution.test_executor
   ```
   - Verify precheck succeeds
   - Confirm no actual orders placed
   - Review logs for proper gating

2. **SIM Single Order**
   ```bash
   EXECUTION_MODE=SIM python -m execution.test_single_order
   ```
   - Place one limit order (low price)
   - Verify order ID returned
   - Cancel order immediately
   - Confirm cancellation

3. **SIM Rate Limit Test**
   ```bash
   EXECUTION_MODE=SIM python -m execution.test_rate_limiting
   ```
   - Attempt 3 orders rapidly
   - Verify 1-second spacing
   - Confirm all orders placed

4. **SIM Position Guard Test**
   ```bash
   EXECUTION_MODE=SIM python -m execution.test_position_guards
   ```
   - Place buy order (filled)
   - Attempt duplicate buy (blocked)
   - Place sell order (filled)
   - Attempt sell with no position (blocked)

### Monitoring Checklist

During execution, monitor:
- [ ] Log volume (expect 5-10 events per order)
- [ ] Blocked executions (should see auction blocks during pre/post market)
- [ ] Rate limit warnings (should be rare with proper pacing)
- [ ] Position cache hit rate (should be >80%)
- [ ] Precheck success rate (should be >95%)
- [ ] Reconciliation mismatches (should be 0%)

---

## API Reference

### TradeExecutor

```python
class TradeExecutor:
    """Main execution interface"""
    
    def __init__(
        self,
        client: SaxoClient,
        account_key: str,
        mode: str = "DRY_RUN",
        config: Optional[ExecutionConfig] = None
    ):
        """
        Initialize executor
        
        Args:
            client: Authenticated Saxo client
            account_key: Account identifier
            mode: "DRY_RUN" or "SIM"
            config: Execution configuration (uses defaults if None)
        """
    
    async def execute(
        self,
        intent: OrderIntent
    ) -> ExecutionResult:
        """
        Execute order intent through full gate pipeline
        
        Args:
            intent: Order intent with all required fields
            
        Returns:
            ExecutionResult with success/failure and details
        """
    
    async def cancel_order(
        self,
        order_id: str
    ) -> bool:
        """Cancel order by ID"""
    
    async def query_orders(
        self,
        external_reference: Optional[str] = None
    ) -> List[Dict]:
        """Query orders, optionally filtered by external_reference"""
```

### OrderIntent

```python
@dataclass
class OrderIntent:
    """Order intent specification"""
    asset_type: str
    uic: int
    symbol: str
    side: str  # "Buy" or "Sell"
    quantity: Decimal
    order_type: str  # "Market", "Limit", "Stop"
    external_reference: str
    
    # Optional
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    duration: str = "DayOrder"
```

### ExecutionResult

```python
@dataclass
class ExecutionResult:
    """Result of execution attempt"""
    success: bool
    status: str  # "success", "blocked_market_state", "precheck_failed", etc.
    external_reference: str
    
    # If successful
    order_id: Optional[str] = None
    order_status: Optional[str] = None
    
    # Details
    precheck_result: Optional[str] = None
    estimated_cash_required: Optional[Decimal] = None
    blocked_by: Optional[str] = None
    reason: Optional[str] = None
    error_message: Optional[str] = None
```

---

## Implementation Notes
- Keep the runbook close to code (e.g., docs/stories/story-005-trade-execution/README.md or docs/epics/epic-005...).
- Include copy/paste curl examples for the key endpoints (precheck, place order, query orders, query positions).
- **Safety First**: Multiple layers of protection prevent accidental execution
- **Observability**: Rich structured logging enables debugging and auditing
- **Correlation**: `external_reference` ties together all events for an order
- **Conservative Defaults**: Fail-safe behavior (block on unknown, no auto-retry risky operations)
- **Testing**: Comprehensive test harness with DRY_RUN → SIM progression

## Test Plan
- Manual doc review:
  - Another developer can configure SIM and run DRY_RUN and SIM example without reading code.
- Link checker (optional):
  - Validate primary-source links are reachable.

## Dependencies / Assumptions
- Requires stable configuration keys and logging structure from Stories 005-001 through 005-008.

## Primary Sources
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/learn/breaking-change-pre-trade-disclaimers-on-openapi
- https://www.developer.saxo/openapi/learn/reference-data
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/referencedocs/port/v1/orders/get__port
- https://www.developer.saxo/openapi/referencedocs/port/v1/positions/get__port__positions
