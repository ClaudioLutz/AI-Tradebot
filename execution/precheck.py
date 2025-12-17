from typing import Optional, List, Set, Any
from decimal import Decimal
import uuid
import logging
import time
import requests
from requests.exceptions import Timeout, RequestException

from execution.models import OrderIntent, PrecheckResult
from execution.utils import intent_to_saxo_order_request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class RetryConfig:
    max_retries: int = 3
    retry_on_status: Set[int] = field(default_factory=lambda: {429, 500, 502, 503, 504})
    backoff_base_seconds: float = 1.0

class PrecheckClient:
    """HTTP client for Saxo precheck endpoint"""

    def __init__(self, saxo_client, retry_config: Optional[RetryConfig] = None):
        self.saxo_client = saxo_client
        self.retry_config = retry_config or RetryConfig()
        self.logger = logger

    def execute_precheck(self, order_intent: OrderIntent) -> PrecheckResult:
        """
        Execute precheck for an order intent with retry logic.
        """
        return self._execute_precheck_with_retry(order_intent)

    def _execute_precheck_with_retry(self, order_intent: OrderIntent) -> PrecheckResult:
        """Execute precheck. SaxoClient handles retries for network/rate limits."""
        try:
            return self._perform_single_precheck(order_intent)
        except Exception as e:
            status_code = getattr(e, "status_code", 500)
            return PrecheckResult(
                success=False,
                error_message=str(e),
                error_code=f"HTTP_{status_code}"
            )

    def _perform_single_precheck(self, order_intent: OrderIntent) -> PrecheckResult:
        """
        Execute a single precheck attempt.
        """
        # If request_id is present in intent, use it. Otherwise generate one.
        # Note: We do NOT update intent.request_id here, as that should be done by executor if needed.
        # But we must capture what we used.
        request_id = order_intent.request_id if order_intent.request_id else str(uuid.uuid4())

        # Use utils to build payload correctly (including OrderType etc.)
        payload = intent_to_saxo_order_request(order_intent)

        # Add Precheck specific fields
        payload["FieldGroups"] = ["Costs", "MarginImpactBuySell", "PreTradeDisclaimers"]

        # Saxo requires headers for x-request-id
        headers = {"x-request-id": request_id}

        self.logger.info(f"Executing precheck {request_id} for {order_intent.external_reference}")

        # Assuming saxo_client.post raises exception on non-2xx
        # If saxo_client.post returns a dict, it's successful or 200 with ErrorInfo
        response_data = self.saxo_client.post(
            "/trade/v2/orders/precheck",
            json_body=payload,
            headers=headers,
            endpoint_type="orders" # Use same rate limit bucket as orders? or default? Story says order rate limits apply.
        )

        result = self._parse_precheck_response(response_data)
        result.request_id = request_id
        return result

    def _parse_precheck_response(self, data: dict) -> PrecheckResult:
        """
        Parse Saxo precheck response data into PrecheckResult.
        """
        # Check for ErrorInfo (Business logic error)
        if "ErrorInfo" in data:
            return PrecheckResult(
                success=False,
                error_code=data["ErrorInfo"].get("ErrorCode"),
                error_message=data["ErrorInfo"].get("Message"),
                raw_response=data
            )

        # Extract costs
        estimated_cost = None
        estimated_currency = None
        if "EstimatedCost" in data:
            estimated_cost = float(data["EstimatedCost"]["Amount"])
            estimated_currency = data["EstimatedCost"]["Currency"]

        margin_impact = None
        if "MarginImpactBuySell" in data:
            margin_impact = float(data["MarginImpactBuySell"]["Amount"])
        elif "MarginImpact" in data:
            margin_impact = float(data["MarginImpact"]["Amount"])

        # Extract Disclaimers
        disclaimer_tokens = []
        disclaimer_context = None
        if "PreTradeDisclaimers" in data:
            ptd = data["PreTradeDisclaimers"]
            disclaimer_context = ptd.get("DisclaimerContext")
            disclaimer_tokens = ptd.get("DisclaimerTokens", [])

        return PrecheckResult(
            success=True,
            estimated_cost=estimated_cost,
            estimated_currency=estimated_currency,
            margin_impact=margin_impact,
            disclaimer_tokens=disclaimer_tokens,
            disclaimer_context=disclaimer_context,
            raw_response=data
        )
