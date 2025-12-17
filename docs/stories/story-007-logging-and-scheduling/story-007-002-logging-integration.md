# Story 007-002: Logging Integration & Context Propagation

**Epic:** [Epic 007: Logging and Scheduling System](../../epics/epic-007-logging-and-scheduling.md)
**Status:** Not Started
**Effort:** 5 Story Points
**Priority:** High

## User Story
As a **developer**, I want **the application logic to consistently propagate execution context (Run ID, Cycle ID, Order ID)** so that **I can filter logs to reconstruct the exact timeline of a specific trading decision**.

## Acceptance Criteria
- [ ] `main.py` (or equivalent entry point) generates `run_id` (UUID) at startup.
- [ ] `main.py` generates/increments `cycle_id` for each loop iteration.
- [ ] A `ContextAdapter` or similar mechanism passes these IDs to `fetch_market_data`, `generate_signals`, and `execute_trades`.
- [ ] `SaxoTradeExecutor` emits structured events for:
    - Precheck start/result
    - Disclaimer resolution attempts
    - Order placement (with `external_reference`)
    - Reconciliation outcomes
- [ ] HTTP Client (`SaxoClient`) logs strictly sanitized request/response summaries (Method, URL Path, Status, Latency).
- [ ] Event taxonomy defined in Epic 007 is adhered to (e.g., `execution_precheck_passed`, `execution_order_placed`).

## Technical Details

### 1. Context Propagation

We need a way to set global or thread-local context, or explicitly pass a context object. Given the synchronous nature, passing a `context` dict or using `LoggerAdapter` is preferred.

```python
# common/log_context.py

class TradingContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        # Merge extra context (run_id, cycle_id) into log record
        extra = self.extra.copy()
        if 'extra' in kwargs:
            extra.update(kwargs.pop('extra'))

        # Format context as key=value string appended to message (optional)
        # Or rely on the Filter from Story 007-001 to pull from record.

        kwargs['extra'] = extra
        return msg, kwargs

# Usage in main.py
run_id = str(uuid.uuid4())
logger = TradingContextAdapter(logging.getLogger(__name__), {'run_id': run_id, 'cycle_id': 'INIT'})
```

### 2. Integration Points

**Main Loop:**
```python
while True:
    cycle_id = str(uuid.uuid4())
    cycle_logger = TradingContextAdapter(base_logger, {'run_id': run_id, 'cycle_id': cycle_id})

    cycle_logger.info("cycle_begin")
    # pass cycle_logger or context to sub-components
    orchestrator.run_cycle(context={'run_id': run_id, 'cycle_id': cycle_id})
```

**Trade Executor:**
```python
def execute_order(self, order_intent):
    # Log with context
    self.logger.info("execution_intent_created", extra={
        'instrument_id': order_intent.instrument_id,
        'quantity': order_intent.amount
    })

    # ... logic ...

    self.logger.info("execution_order_placed", extra={
        'saxo_order_id': response.order_id,
        'external_reference': order_intent.external_reference
    })
```

### 3. HTTP Layer

Ensure `SaxoClient` logs:
`http_request_out method=GET path=/port/v1/orders`
`http_response_in status=200 duration_ms=150`

**Critical:** Do NOT log the full URL if it contains query params with secrets (though Saxo usually uses Headers). Do NOT log the full JSON body unless explicitly debug-enabled and redacted.

## Dependencies
- **Story 007-001**: Logging config must be available.
- **Epic 006**: Requires the main orchestration structure to be present to integrate into.

## Testing Strategy
- **Integration Test**: Run a `dry_run` cycle.
- **Verification**: Read the generated log file.
- **Assert**:
    - Every line has `run_id=...`
    - Specific sequence: `cycle_begin` -> `marketdata_fetch` -> `execution_...` -> `cycle_end`.
    - `client_key` is masked in any HTTP logs.
