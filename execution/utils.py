import hashlib
import time
import uuid
import logging
import json
from typing import Optional, Dict, Any
from execution.models import OrderIntent, ExecutionResult, ExecutionStatus, OrderType, OrderDurationType

logger = logging.getLogger(__name__)

class RateLimitedSaxoClient:
    """
    Wrapper around Saxo client to handle Rate Limiting (429).
    Respects X-RateLimit-SessionOrders-Reset and other headers.
    """
    def __init__(self, client):
        self.client = client
        self.max_retries = 3
        self.default_reset_seconds = 1.0

    def _handle_request(self, method, url, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                # Delegate to inner client
                if method == "GET":
                    return self.client.get(url, **kwargs)
                elif method == "POST":
                    return self.client.post(url, **kwargs)
                elif method == "PUT":
                    return self.client.put(url, **kwargs)
                elif method == "DELETE":
                    return self.client.delete(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported method {method}")
            except Exception as e:
                status_code = getattr(e, "status_code", 500)

                if status_code == 429:
                    # Check for reset header
                    reset_time = self.default_reset_seconds
                    if hasattr(e, "response") and e.response:
                        headers = getattr(e.response, "headers", {})
                        # Saxo headers for session limits
                        if "X-RateLimit-SessionOrders-Reset" in headers:
                             try:
                                 reset_time = float(headers["X-RateLimit-SessionOrders-Reset"])
                             except ValueError:
                                 pass
                        elif "Retry-After" in headers:
                            try:
                                reset_time = float(headers["Retry-After"])
                            except ValueError:
                                pass

                    if attempt < self.max_retries:
                        logger.warning(f"Rate limited (429). Retrying after {reset_time:.2f}s")
                        time.sleep(reset_time)
                        continue

                # Re-raise other errors or if max retries reached
                raise e

    def get(self, url, params=None, headers=None):
        return self._handle_request("GET", url, params=params, headers=headers)

    def post(self, url, json_body=None, headers=None):
        return self._handle_request("POST", url, json_body=json_body, headers=headers)

    def put(self, url, json_body=None, headers=None):
        return self._handle_request("PUT", url, json_body=json_body, headers=headers)

    def delete(self, url, params=None, headers=None):
        return self._handle_request("DELETE", url, params=params, headers=headers)

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
    # Length of known parts: "E005:" (5) + ":" (1) + str(uic) (approx 5-10) + ":" (1) + hash (5) = 17-22 chars
    # We want to be safe, so let's calculate exact reserved length
    reserved_suffix_len = len(f":{hash_suffix}") # 6 chars
    prefix = "E005:"
    uic_str = str(uic)

    # Base pattern: prefix + strategy + ":" + uic + suffix
    # we need len(prefix) + len(strategy) + 1 + len(uic) + len(suffix) <= 50
    # len(strategy) <= 50 - len(prefix) - 1 - len(uic) - len(suffix)

    max_strategy_len = 50 - len(prefix) - 1 - len(uic_str) - reserved_suffix_len

    # Ensure at least some chars for strategy, though it should be positive if 50 is the limit
    if max_strategy_len < 0:
         max_strategy_len = 0 # Should not happen unless UIC is extremely long

    strategy_abbr = strategy_id[:max_strategy_len]

    ref = f"{prefix}{strategy_abbr}:{uic_str}:{hash_suffix}"

    if len(ref) > 50:
        # Emergency truncation
        ref = ref[:50]

    return ref

def generate_request_id() -> str:
    """
    Generate unique request_id for x-request-id header.
    Uses UUIDv4 for guaranteed uniqueness.

    Saxo uses this for duplicate operation detection (15s window).
    """
    return str(uuid.uuid4())

def intent_to_saxo_order_request(intent: OrderIntent) -> dict:
    """
    Map OrderIntent to Saxo POST /trade/v2/orders request body.

    Saxo API schema:
    https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade
    """
    request_body = {
        "AccountKey": intent.account_key,
        "Amount": float(intent.amount),
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
