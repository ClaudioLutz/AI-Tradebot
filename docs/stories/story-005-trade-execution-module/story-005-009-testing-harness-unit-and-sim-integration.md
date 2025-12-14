# Story 005-009: Testing harness: unit + SIM integration for execution module

## Summary
Create a testing strategy and harness that validates execution behavior with deterministic unit tests and optional SIM integration tests.

## Background / Context
The execution module is safety-critical; regressions can cause duplicate orders or unintended exposure.
A dedicated harness helps validate request-shaping, retry behavior, and gating rules, and provides a clear path
for running end-to-end tests in SIM.

## Scope
In scope:
- Unit test suite with mocked HTTP client responses for:
  - instrument details
  - precheck
  - placement
  - portfolio positions / orders
  - disclaimer APIs
- SIM integration tests (opt-in, environment variable gated):
  - Precheck-only test (DRY_RUN style)
  - Place-and-reconcile test (SIM)
- Deterministic "clock" abstraction to test rate limiting and backoff without real sleeps.

## Acceptance Criteria
1. Unit tests cover:
   - precheck-first behavior
   - DRY_RUN vs SIM behavior
   - duplicate buy prevention and sell-without-position skip
   - rate limiting and 429 backoff behavior
   - timeout/TradeNotCompleted reconciliation path
   - disclaimers blocking behavior
2. **Contract Checks** (fail fast on schema drift):
   - DM disclaimers GET: assert `Data[]` envelope is present.
   - Precheck/placement: assert `PreTradeDisclaimers` uses `DisclaimerContext` + `DisclaimerTokens`.
   - Portfolio: assert retrieval supports `{ClientKey}/{OrderId}` and `{ClientKey}` query param.
3. Integration tests can run against SIM when credentials are present and are skipped otherwise.
4. Test harness produces readable logs/artifacts to debug failures (request/response snapshots with redaction).

## Technical Architecture

### Test Structure

```
tests/
├── unit/
│   ├── test_order_intent.py
│   ├── test_position_guards.py
│   ├── test_market_state_gate.py
│   ├── test_rate_limiter.py
│   ├── test_retry_policy.py
│   ├── test_precheck.py
│   ├── test_placement.py
│   └── test_reconciliation.py
├── integration/
│   ├── test_sim_precheck.py
│   ├── test_sim_placement.py
│   └── test_sim_end_to_end.py
└── fixtures/
    ├── mock_responses.py
    ├── test_data.py
    └── test_instruments.py
```

### Mock HTTP Client

```python
from typing import Dict, Any, Optional, Callable
from unittest.mock import AsyncMock
import json

class MockHTTPResponse:
    """Mock HTTP response for testing"""
    
    def __init__(
        self,
        status_code: int,
        json_data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {}
        
    def json(self) -> Dict[str, Any]:
        return self._json_data
        
    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise HTTPError(self.status_code, self._json_data)

class HTTPError(Exception):
    """Mock HTTP error"""
    def __init__(self, status_code: int, data: Dict[str, Any]):
        self.status_code = status_code
        self.error_code = data.get("ErrorCode")
        super().__init__(data.get("Message", f"HTTP {status_code}"))

class MockSaxoClient:
    """
    Mock Saxo client for unit testing
    
    Allows configuring responses for specific endpoints
    """
    
    def __init__(self):
        self.responses: Dict[str, Callable] = {}
        self.call_history: list = []
        
    def mock_response(
        self,
        method: str,
        path: str,
        response: MockHTTPResponse,
        match_params: Optional[Dict] = None
    ):
        """Configure mock response for endpoint"""
        key = f"{method.upper()}:{path}"
        self.responses[key] = lambda **kwargs: response
        
    def mock_dynamic_response(
        self,
        method: str,
        path: str,
        handler: Callable
    ):
        """Configure dynamic response handler"""
        key = f"{method.upper()}:{path}"
        self.responses[key] = handler
        
    async def request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> MockHTTPResponse:
        """Execute mocked request"""
        # Record call
        self.call_history.append({
            "method": method,
            "path": path,
            "kwargs": kwargs
        })
        
        # Find response
        key = f"{method.upper()}:{path}"
        if key in self.responses:
            handler = self.responses[key]
            response = handler(**kwargs)
            
            if response.status_code >= 400:
                response.raise_for_status()
            
            return response
        
        # Default 404
        raise HTTPError(404, {"Message": f"No mock for {key}"})
        
    async def get(self, path: str, **kwargs):
        return await self.request("GET", path, **kwargs)
        
    async def post(self, path: str, **kwargs):
        return await self.request("POST", path, **kwargs)
```

### Test Fixtures

```python
# tests/fixtures/mock_responses.py

MOCK_INSTRUMENT_DETAILS_AAPL = {
    "AssetType": "Stock",
    "Uic": 211,
    "Symbol": "AAPL:xnas",
    "Description": "Apple Inc.",
    "Currency": "USD",
    "Tradable": True,
    "SupportedOrderTypes": ["Market", "Limit", "Stop"]
}

MOCK_PRECHECK_SUCCESS = {
    "PreCheckResult": "Ok",
    "EstimatedCashRequired": 15000.00,
    "EstimatedCosts": 5.00,
    "Warnings": []
}

MOCK_PRECHECK_DISCLAIMER_REQUIRED = {
    "PreCheckResult": "Disclaimer",
    "DisclaimerIds": ["12345"],
    "DisclaimerTexts": ["You must accept disclaimer before trading"]
}

MOCK_ORDER_PLACED = {
    "OrderId": "76543210",
    "ExternalReference": "test_ref_001",
    "Orders": [{
        "OrderId": "76543210",
        "Status": "Working",
        "BuySell": "Buy",
        "AssetType": "Stock",
        "Uic": 211,
        "Amount": 100,
        "Price": 150.00
    }]
}

MOCK_POSITION_AAPL = {
    "Data": [{
        "NetPositionId": "212345678",
        "PositionBase": {
            "AccountId": "9073654",
            "Amount": 100.0,
            "AssetType": "Stock",
            "CanBeClosed": True,
            "Uic": 211,
            "Status": "Open"
        },
        "NetPositionView": {
            "AverageOpenPrice": 150.25,
            "CurrentPrice": 152.30,
            "MarketValue": 15230.00,
            "ProfitLossOnTrade": 205.00
        }
    }]
}

MOCK_RATE_LIMIT_429 = {
    "ErrorCode": "TooManyRequests",
    "Message": "Rate limit exceeded"
}
```

### Deterministic Clock for Testing

```python
from datetime import datetime, timedelta
from typing import Protocol

class Clock(Protocol):
    """Clock interface for testability"""
    
    def now(self) -> datetime:
        """Get current time"""
        ...
        
    async def sleep(self, seconds: float):
        """Sleep for duration"""
        ...

class RealClock:
    """Production clock using system time"""
    
    def now(self) -> datetime:
        return datetime.utcnow()
        
    async def sleep(self, seconds: float):
        await asyncio.sleep(seconds)

class FakeClock:
    """Test clock with manual time control"""
    
    def __init__(self, start_time: Optional[datetime] = None):
        self._current_time = start_time or datetime(2024, 1, 1, 10, 0, 0)
        self._sleep_log: list[float] = []
        
    def now(self) -> datetime:
        return self._current_time
        
    async def sleep(self, seconds: float):
        """Record sleep without actually sleeping"""
        self._sleep_log.append(seconds)
        self._current_time += timedelta(seconds=seconds)
        
    def advance(self, seconds: float):
        """Manually advance time"""
        self._current_time += timedelta(seconds=seconds)
        
    def get_sleep_log(self) -> list[float]:
        """Get history of sleep calls"""
        return self._sleep_log
```

### Unit Test Examples

```python
# tests/unit/test_position_guards.py

import pytest
from decimal import Decimal
from execution.position_guards import PositionAwareGuards, Position

@pytest.fixture
def mock_position_manager():
    """Create mock position manager"""
    manager = AsyncMock()
    manager.get_positions = AsyncMock()
    return manager

@pytest.fixture
def position_guards(mock_position_manager):
    """Create position guards with mock manager"""
    from execution.config import ExecutionConfig
    config = ExecutionConfig()
    return PositionAwareGuards(mock_position_manager, config)

@pytest.mark.asyncio
async def test_buy_blocked_when_position_exists(
    position_guards,
    mock_position_manager
):
    """Test: Buy order is blocked when long position exists"""
    # Arrange
    existing_position = Position(
        asset_type="Stock",
        uic=211,
        account_key="test_account",
        position_id="12345",
        net_quantity=Decimal("100"),
        average_price=Decimal("150.00"),
        market_value=Decimal("15000.00"),
        unrealized_pnl=Decimal("200.00"),
        currency="USD"
    )
    
    mock_position_manager.get_positions.return_value = {
        ("Stock", 211): existing_position
    }
    
    # Act
    result = await position_guards.evaluate_buy_intent(
        asset_type="Stock",
        uic=211,
        intended_quantity=Decimal("100")
    )
    
    # Assert
    assert not result.allowed
    assert result.reason == "duplicate_buy_prevented"
    assert result.position_quantity == Decimal("100")

@pytest.mark.asyncio
async def test_sell_blocked_when_no_position(
    position_guards,
    mock_position_manager
):
    """Test: Sell order is blocked when no position exists"""
    # Arrange
    mock_position_manager.get_positions.return_value = {}
    
    # Act
    result = await position_guards.evaluate_sell_intent(
        asset_type="Stock",
        uic=211
    )
    
    # Assert
    assert not result.allowed
    assert result.reason == "no_position_to_sell"
    assert result.position_quantity == Decimal("0")

# tests/unit/test_rate_limiter.py

import pytest
from execution.rate_limiter import TokenBucketRateLimiter, RateLimitConfig

@pytest.fixture
def fake_clock():
    """Create fake clock for testing"""
    return FakeClock()

@pytest.fixture
def rate_limiter(fake_clock):
    """Create rate limiter with fake clock"""
    config = RateLimitConfig(orders_per_second=1.0)
    limiter = TokenBucketRateLimiter(config)
    limiter._clock = fake_clock  # Inject fake clock
    return limiter

@pytest.mark.asyncio
async def test_rate_limiter_enforces_one_per_second(
    rate_limiter,
    fake_clock
):
    """Test: Rate limiter blocks second request within 1 second"""
    # Act: First request (immediate)
    await rate_limiter.acquire("order1")
    sleep_log = fake_clock.get_sleep_log()
    assert len(sleep_log) == 0  # No sleep needed
    
    # Act: Second request (should wait ~1 second)
    await rate_limiter.acquire("order2")
    sleep_log = fake_clock.get_sleep_log()
    assert len(sleep_log) == 1
    assert sleep_log[0] >= 0.9  # Approximately 1 second

@pytest.mark.asyncio
async def test_rate_limiter_allows_after_reset(
    rate_limiter,
    fake_clock
):
    """Test: Rate limiter respects reset time from 429"""
    # Arrange: Set reset time 5 seconds in future
    reset_time = fake_clock.now() + timedelta(seconds=5)
    rate_limiter.set_reset_time(int(reset_time.timestamp()))
    
    # Act
    await rate_limiter.acquire("order")
    
    # Assert: Should have waited ~5 seconds
    sleep_log = fake_clock.get_sleep_log()
    assert len(sleep_log) == 1
    assert 4.9 <= sleep_log[0] <= 5.1

# tests/unit/test_retry_policy.py

@pytest.mark.asyncio
async def test_409_conflict_no_retry():
    """Test: 409 Conflict error does not retry"""
    # Arrange
    mock_client = MockSaxoClient()
    mock_client.mock_response(
        "POST",
        "/trade/v2/orders",
        MockHTTPResponse(
            409,
            {"ErrorCode": "DuplicateOperation", "Message": "Duplicate request"}
        )
    )
    
    config = RetryConfig(retry_on_conflict=False)
    rate_limiter = TokenBucketRateLimiter(RateLimitConfig())
    retry_policy = RetryPolicy(config, rate_limiter)
    
    # Act & Assert
    with pytest.raises(HTTPError) as exc_info:
        await retry_policy.execute_with_retry(
            operation=lambda: mock_client.post("/trade/v2/orders"),
            operation_name="place_order",
            external_reference="test_ref"
        )
    
    assert exc_info.value.status_code == 409
    # Should only have attempted once (no retries)
    assert len(mock_client.call_history) == 1

@pytest.mark.asyncio
async def test_500_server_error_retries():
    """Test: 500 Server Error retries with backoff"""
    # Arrange
    call_count = 0
    
    def dynamic_response(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return MockHTTPResponse(500, {"Message": "Internal error"})
        else:
            return MockHTTPResponse(200, {"OrderId": "12345"})
    
    mock_client = MockSaxoClient()
    mock_client.mock_dynamic_response("POST", "/trade/v2/orders", dynamic_response)
    
    fake_clock = FakeClock()
    config = RetryConfig(max_retries=2)
    rate_limiter = TokenBucketRateLimiter(RateLimitConfig())
    rate_limiter._clock = fake_clock
    retry_policy = RetryPolicy(config, rate_limiter)
    
    # Act
    result = await retry_policy.execute_with_retry(
        operation=lambda: mock_client.post("/trade/v2/orders"),
        operation_name="place_order",
        external_reference="test_ref"
    )
    
    # Assert
    assert result.status_code == 200
    assert call_count == 3  # Initial + 2 retries
    # Should have exponential backoff sleeps
    sleep_log = fake_clock.get_sleep_log()
    assert len(sleep_log) >= 2  # Backoff sleeps
```

### Integration Test Framework

```python
# tests/integration/conftest.py

import pytest
import os
from typing import Optional

def is_sim_enabled() -> bool:
    """Check if SIM integration tests should run"""
    return os.getenv("RUN_SIM_TESTS", "false").lower() == "true"

@pytest.fixture(scope="session")
def sim_credentials():
    """Get SIM credentials from environment"""
    if not is_sim_enabled():
        pytest.skip("SIM tests disabled (set RUN_SIM_TESTS=true)")
    
    return {
        "client_id": os.getenv("SAXO_CLIENT_ID"),
        "client_secret": os.getenv("SAXO_CLIENT_SECRET"),
        "account_key": os.getenv("SAXO_SIM_ACCOUNT_KEY"),
        "base_url": "https://gateway.saxobank.com/sim/openapi"
    }

@pytest.fixture
async def sim_client(sim_credentials):
    """Create authenticated SIM client"""
    from data.saxo_client import SaxoClient
    
    client = SaxoClient(
        base_url=sim_credentials["base_url"],
        client_id=sim_credentials["client_id"],
        client_secret=sim_credentials["client_secret"]
    )
    
    await client.authenticate()
    yield client
    await client.close()

# tests/integration/test_sim_precheck.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_sim_precheck_stock_order(sim_client, sim_credentials):
    """Test: Precheck works in SIM for stock order"""
    # Arrange
    order_data = {
        "AccountKey": sim_credentials["account_key"],
        "AssetType": "Stock",
        "Uic": 211,  # AAPL
        "BuySell": "Buy",
        "Amount": 1,  # Minimal quantity
        "OrderType": "Market"
    }
    
    # Act
    response = await sim_client.post(
        "/trade/v2/orders/precheck",
        json=order_data
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["PreCheckResult"] in ["Ok", "Disclaimer"]
    assert "EstimatedCashRequired" in data

@pytest.mark.integration
@pytest.mark.asyncio
async def test_sim_place_and_cancel_order(sim_client, sim_credentials):
    """Test: Place and cancel order in SIM"""
    # Arrange
    import uuid
    external_ref = f"test_{uuid.uuid4().hex[:8]}"
    
    order_data = {
        "AccountKey": sim_credentials["account_key"],
        "AssetType": "Stock",
        "Uic": 211,  # AAPL
        "BuySell": "Buy",
        "Amount": 1,
        "OrderType": "Limit",
        "OrderPrice": 50.00,  # Low price to avoid fill
        "OrderDuration": {"DurationType": "DayOrder"},
        "ExternalReference": external_ref
    }
    
    try:
        # Act: Place order
        place_response = await sim_client.post(
            "/trade/v2/orders",
            json=order_data,
            headers={"X-Request-ID": external_ref}
        )
        
        # Assert placement
        assert place_response.status_code in [200, 201]
        order_id = place_response.json()["OrderId"]
        assert order_id
        
        # Cleanup: Cancel order
        cancel_response = await sim_client.delete(
            f"/trade/v2/orders/{order_id}",
            params={"AccountKey": sim_credentials["account_key"]}
        )
        
        assert cancel_response.status_code in [200, 202]
        
    except Exception as e:
        pytest.fail(f"SIM test failed: {e}")
```

### Test Configuration

```python
# pytest.ini

[pytest]
markers =
    unit: Unit tests with mocks
    integration: Integration tests against SIM
    slow: Slow-running tests

# Run only unit tests by default
addopts = -v -m "not integration"

# For integration tests:
# pytest -m integration
```

```bash
# .github/workflows/test.yml (CI example)

name: Test Execution Module

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      - name: Run unit tests
        run: pytest tests/unit -v --cov=execution
      
  sim-integration:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt pytest pytest-asyncio
      - name: Run SIM integration tests
        env:
          RUN_SIM_TESTS: 'true'
          SAXO_CLIENT_ID: ${{ secrets.SAXO_SIM_CLIENT_ID }}
          SAXO_CLIENT_SECRET: ${{ secrets.SAXO_SIM_CLIENT_SECRET }}
          SAXO_SIM_ACCOUNT_KEY: ${{ secrets.SAXO_SIM_ACCOUNT_KEY }}
        run: pytest tests/integration -v -m integration
```

## Implementation Notes
- For integration tests:
  - Use a dedicated SIM account key and restrict order sizes to minimal safe amounts.
  - Ensure tests clean up or at least log created orders/positions.
- Consider contract fixtures with recorded JSON (VCR-style) for non-sensitive endpoints (ref data), if allowed.
- **Fake Clock**: Essential for deterministic rate limiting tests without real delays
- **Mock Client**: Isolates tests from network issues and allows full control over responses
- **Fixtures**: Centralize mock data to ensure consistency across tests
- **Cleanup**: Always cancel SIM orders in finally blocks or fixtures
- **CI/CD**: Run unit tests on every commit, integration tests only on main branch

## Test Plan
- This story is itself the testing plan:
  - Implement mocks and fixtures.
  - Add CI target "unit".
  - Add optional CI/manual target "sim-integration".

## Dependencies / Assumptions
- Depends on all prior stories for the concrete executor components.
- Requires a way to inject HTTP client and clock into executor.

## Primary Sources
- https://www.developer.saxo/openapi/learn/rate-limiting
- https://www.developer.saxo/openapi/learn/order-placement
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
- https://www.developer.saxo/openapi/referencedocs/port/v1/positions/get__port__positions
- https://www.developer.saxo/openapi/referencedocs/port/v1/orders/get__port
