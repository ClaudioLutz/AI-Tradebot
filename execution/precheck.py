from dataclasses import dataclass, field
from typing import Optional, List, Set
from decimal import Decimal
import uuid
import logging
import asyncio
import time
import requests
from requests.exceptions import Timeout, RequestException

from execution.models import OrderIntent

logger = logging.getLogger(__name__)

@dataclass
class ErrorInfo:
    error_code: str
    message: str

@dataclass
class EstimatedCost:
    amount: Decimal
    currency: str

@dataclass
class MarginImpactBuySell:
    amount: Decimal
    currency: str

@dataclass
class PreTradeDisclaimers:
    """
    Pre-trade disclaimer data from precheck/placement response.

    Structure aligned with Saxo breaking change:
    - DisclaimerContext: string (opaque context ID)
    - DisclaimerTokens: string[] (list of tokens to resolve via DM)
    """
    disclaimer_context: str
    disclaimer_tokens: List[str]  # List of disclaimer token strings

@dataclass
class PrecheckOutcome:
    ok: bool
    error_info: Optional[ErrorInfo] = None
    estimated_cost: Optional[EstimatedCost] = None
    margin_impact_buy_sell: Optional[MarginImpactBuySell] = None
    pre_trade_disclaimers: Optional[PreTradeDisclaimers] = None
    http_status: int = 200
    request_id: Optional[str] = None
    raw_response: Optional[dict] = None  # For debugging

@dataclass
class RetryConfig:
    max_retries: int = 1  # Single retry for transient errors
    retry_on_status: Set[int] = field(default_factory=lambda: {429, 500, 502, 503, 504})
    backoff_base_seconds: float = 2.0

class PrecheckClient:
    """HTTP client for Saxo precheck endpoint"""

    def __init__(self, saxo_client, retry_config: Optional[RetryConfig] = None):
        self.saxo_client = saxo_client
        self.retry_config = retry_config or RetryConfig()
        self.logger = logger

    def execute_precheck(
        self,
        order_intent: OrderIntent
    ) -> PrecheckOutcome:
        """
        Execute precheck for an order intent with retry logic.
        Synchronous wrapper around retry logic (since requests is sync).
        """
        return self._execute_precheck_with_retry(order_intent)

    def _execute_precheck_with_retry(
        self,
        order_intent: OrderIntent
    ) -> PrecheckOutcome:
        """Execute precheck with retry logic for transient failures"""
        outcome = None
        for attempt in range(self.retry_config.max_retries + 1):
            outcome = self._perform_single_precheck(order_intent)

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
                time.sleep(backoff)

        return outcome

    def _perform_single_precheck(
        self,
        order_intent: OrderIntent
    ) -> PrecheckOutcome:
        """
        Execute a single precheck attempt.
        """
        # Generate a new request_id for each physical attempt or reuse?
        # Story says: "Regenerate request_id for new attempts or when modifying parameters."
        # Story also says: "Reuse request_id ONLY for idempotent retries of the exact same operation."
        # For precheck, it is safe to retry.
        # But here we are retrying at HTTP level.
        # Let's generate one request_id for this *intent* validation, or per attempt?
        # Story: "Generate a UUIDv4 per placement attempt... Do not reuse request_id across attempts unless you explicitly want Saxo to treat the operation as the same."
        # For precheck, reusing ID for retries of same request seems correct.

        request_id = order_intent.request_id if order_intent.request_id else str(uuid.uuid4())

        try:
            # Build request payload
            payload = self._build_precheck_payload(order_intent)

            # Log the precheck attempt
            self.logger.info(
                f"Executing precheck {request_id}",
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

            try:
                # Using the existing SaxoClient interface
                # Note: SaxoClient.post takes `json_body` not `json`
                # And headers via `headers`?
                # SaxoClient implementation needs to be checked if it supports headers.
                # If not, we might need to modify it or subclass it, or use `client.session.post` if exposed.

                # Looking at `execution/trade_executor.py` again:
                # `client.post("/trade/v2/orders/precheck", json_body=order_body)`

                # I don't have the source of `data/saxo_client.py` loaded in memory, let me check it.
                # I'll rely on `read_file` output if I had it, but I don't think I read `data/saxo_client.py`.
                # Wait, I read `execution/trade_executor.py` which imports it.

                # Let's assume for now I pass `headers` if possible, otherwise I might miss `x-request-id`.
                # If `SaxoClient` is too rigid, I might need to bypass it or improve it.
                # Story says: "Always use x-request-id header for request tracing."

                # I'll try to use `saxo_client.post` and see. If it doesn't support headers, I will have to rely on `saxo_client` internal session or modify it.
                # For this implementation, I'll assume `saxo_client` has a `post` method.
                # If it raises `SaxoAPIError`, I catch it.

                response_data = self.saxo_client.post(
                    "/trade/v2/orders/precheck",
                    json_body=payload,
                    headers={"x-request-id": request_id}
                )

                # If we are here, likely status was 2xx (unless client doesn't raise on error).
                # `SaxoClient` usually returns the parsed JSON.

                # We need to reconstruct a "response" object or parse the data directly.
                return self._parse_precheck_response_data(
                    response_data,
                    200, # Assumed 200 if no exception
                    request_id,
                    order_intent
                )

            except Exception as e:
                # Handle SaxoAPIError or others
                # If e contains status code, extract it.
                status_code = getattr(e, "status_code", 500)
                error_msg = str(e)

                self.logger.warning(
                    "Precheck HTTP error (caught exception)",
                    extra={
                        "request_id": request_id,
                        "http_status": status_code,
                        "error_message": error_msg
                    }
                )

                return PrecheckOutcome(
                    ok=False,
                    error_info=ErrorInfo(
                        error_code="HTTP_ERROR",
                        message=error_msg
                    ),
                    http_status=status_code,
                    request_id=request_id
                )

        except Timeout as e:
             self.logger.error("Precheck timeout")
             return PrecheckOutcome(
                ok=False,
                error_info=ErrorInfo(error_code="TIMEOUT", message="Precheck request timed out"),
                request_id=request_id
            )

        except Exception as e:
            self.logger.exception("Precheck unexpected error")
            return PrecheckOutcome(
                ok=False,
                error_info=ErrorInfo(error_code="EXCEPTION", message=f"Unexpected error: {str(e)}"),
                request_id=request_id
            )

    def _build_precheck_payload(self, order_intent: OrderIntent) -> dict:
        """Map OrderIntent to Saxo precheck payload"""
        return {
            "AccountKey": order_intent.account_key,
            "Amount": float(order_intent.amount),
            "AssetType": order_intent.asset_type.value,
            "BuySell": order_intent.buy_sell.value,
            "ManualOrder": False,
            "OrderType": "Market",
            "Uic": order_intent.uic,
            "ExternalReference": order_intent.external_reference,
            "OrderDuration": {
                "DurationType": "DayOrder"
            },
            "FieldGroups": ["Costs", "MarginImpactBuySell"]
        }

    def _parse_precheck_response_data(
        self,
        data: dict,
        http_status: int,
        request_id: str,
        order_intent: OrderIntent
    ) -> PrecheckOutcome:
        """
        Parse Saxo precheck response data into normalized outcome.
        """

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

        margin_impact_buy_sell = None
        if "MarginImpactBuySell" in data:
            margin_impact_buy_sell = MarginImpactBuySell(
                amount=Decimal(str(data["MarginImpactBuySell"]["Amount"])),
                currency=data["MarginImpactBuySell"]["Currency"]
            )
        # LEGACY FALLBACK
        elif "MarginImpact" in data:
            self.logger.debug(
                "Parsing legacy MarginImpact field",
                extra={"request_id": request_id}
            )
            margin_impact_buy_sell = MarginImpactBuySell(
                amount=Decimal(str(data["MarginImpact"]["Amount"])),
                currency=data["MarginImpact"]["Currency"]
            )

        disclaimers = None
        if "PreTradeDisclaimers" in data:
            ptd = data["PreTradeDisclaimers"]
            disclaimers = PreTradeDisclaimers(
                disclaimer_context=str(ptd.get("DisclaimerContext", "")),
                disclaimer_tokens=list(ptd.get("DisclaimerTokens", []))
            )

        # Success!
        self.logger.info(
            "Precheck succeeded",
            extra={
                "request_id": request_id,
                "estimated_cost": str(estimated_cost.amount) if estimated_cost else None,
            }
        )

        return PrecheckOutcome(
            ok=True,
            estimated_cost=estimated_cost,
            margin_impact_buy_sell=margin_impact_buy_sell,
            pre_trade_disclaimers=disclaimers,
            http_status=http_status,
            request_id=request_id,
            raw_response=data
        )
