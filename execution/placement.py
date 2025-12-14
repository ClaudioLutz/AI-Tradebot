from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
import time
import uuid
import logging

from execution.models import OrderIntent, PrecheckResult, ExecutionStatus
from execution.utils import intent_to_saxo_order_request, generate_request_id

logger = logging.getLogger(__name__)

@dataclass
class PlacementConfig:
    dry_run: bool = False
    max_retries: int = 0  # Placement usually shouldn't be blindly retried without reconciliation
    timeout_seconds: float = 10.0

@dataclass
class ExecutionOutcome:
    """
    Result of the placement attempt
    """
    final_status: str  # success, failure, uncertain
    order_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    placement: Any = None # Raw placement response wrapper or similar
    reconciliation: Optional[dict] = None

@dataclass
class PlacementStatus:
    # Wrapper for raw response info
    http_status: int
    error_info: Optional[Any] = None
    raw: Optional[dict] = None

class OrderPlacementClient:
    """
    Handles the final step of order placement.
    """

    def __init__(self, saxo_client, config: PlacementConfig = None):
        self.client = saxo_client
        self.config = config or PlacementConfig()
        self.logger = logger

    def place_order(self, intent: OrderIntent, precheck_result: PrecheckResult) -> ExecutionOutcome:
        """
        Place the order.
        """
        if not precheck_result.success:
             return ExecutionOutcome(
                final_status="failure",
                placement=PlacementStatus(http_status=0, error_info={"Message": "Precheck failed"})
            )

        request_id = generate_request_id() # Generate new ID for placement

        if self.config.dry_run:
            self.logger.info(f"DRY RUN: Skipping placement for {intent.external_reference}")
            return ExecutionOutcome(
                final_status="success",
                order_id="DRY_RUN_ID",
                placement=PlacementStatus(http_status=200, raw={"OrderId": "DRY_RUN_ID"})
            )

        # Build payload using utility to ensure consistency and Decimal handling
        payload = intent_to_saxo_order_request(intent)

        # Ensure we pass tokens from precheck if available?
        # Saxo usually doesn't require passing tokens back in placement,
        # unless they are specialized tokens not handled by DM.
        # But DM v2 flow implies we accepted disclaimers separately.
        # So standard placement payload is enough.

        try:
            self.logger.info(
                f"Placing order {intent.external_reference}",
                extra={"request_id": request_id, "amount": float(intent.amount)}
            )

            # saxo_client.post(url, json_body, headers)
            response_data = self.client.post(
                "/trade/v2/orders",
                json_body=payload,
                headers={"x-request-id": request_id}
            )

            # Success
            order_id = response_data.get("OrderId")
            if not order_id:
                # Check for potential uncertainty (e.g. TradeNotCompleted)
                # If no OrderId, we can try to reconcile by ExternalReference
                return self._reconcile_placement(intent, request_id, error=Exception(f"No OrderId returned: {response_data}"))

            self.logger.info(f"Order placed successfully: {order_id}")
            return ExecutionOutcome(
                final_status="success",
                order_id=order_id,
                placement=PlacementStatus(http_status=200, raw=response_data)
            )

        except Exception as e:
            # Handle failure vs uncertainty (2.3)
            self.logger.error(f"Placement error for {intent.external_reference}: {e}")

            # If we can determine it's a definitive failure (e.g. 4xx), return failure immediately
            status_code = getattr(e, "status_code", None)

            # SaxoAPIError has status_code. 400-499 are client errors (failed).
            # 429 is rate limit (failed or uncertain? failed usually as not accepted)
            # 500+ or Timeout are uncertain.

            if status_code and 400 <= status_code < 500 and status_code != 408:
                # Definitive failure
                return ExecutionOutcome(
                    final_status="failure",
                    placement=PlacementStatus(http_status=status_code, error_info={"Message": str(e)})
                )

            # Otherwise treat as uncertain and reconcile
            return self._reconcile_placement(intent, request_id, error=e)

    def _reconcile_placement(self, intent: OrderIntent, request_id: str, error: Exception) -> ExecutionOutcome:
        """
        Attempt to determine order status after a failure/timeout.
        """
        # Strategy:
        # 1. If we have an OrderId (from partial response?), use it.
        # 2. Scan by ExternalReference.

        # We don't have OrderId from exception usually.

        self.logger.warning("Attempting reconciliation...")

        # Scan by ExternalReference (fallback)
        found_order = self._scan_by_external_reference(intent)

        if found_order:
            order_id = found_order.get("OrderId")
            self.logger.info(f"Reconciliation found order {order_id}")
            return ExecutionOutcome(
                final_status="success", # It exists
                order_id=order_id,
                reconciliation=found_order
            )

        return ExecutionOutcome(
            final_status="uncertain", # We couldn't confirm it exists or failed
            placement=PlacementStatus(http_status=500, error_info={"Message": str(error)})
        )

    def _scan_by_external_reference(self, intent: OrderIntent) -> Optional[dict]:
        """
        Scan portfolio for order with matching ExternalReference.
        """
        try:
            # Using Portfolio Orders endpoint.
            # Attempt to use server-side filtering if supported, otherwise fetch open orders.
            # We restrict fields to minimize payload.

            params = {
                "ClientKey": intent.client_key,
                "FieldGroups": "DisplayAndFormat",
                # Optimistic attempt at OData filtering if supported by endpoint variants
                # If ignored, we still filter client-side below.
                "$filter": f"ExternalReference eq '{intent.external_reference}'"
            }

            response = self.client.get(
                "/port/v1/orders", # Note: Some environments might need /me or /orders/{ClientKey}
                params=params
            )

            data = response.json() if hasattr(response, 'json') else response
            orders = data.get("Data", [])

            for order in orders:
                if order.get("ExternalReference") == intent.external_reference:
                    return order

            return None

        except Exception as e:
            self.logger.error(f"Reconciliation scan failed: {e}")
            return None

    def _reconcile_by_order_id(self, order_id: str, intent: OrderIntent) -> ExecutionOutcome:
        """
        Direct reconciliation if we had an OrderId (not currently used by main flow but kept for completeness).
        """
        try:
            # Direct lookup endpoint: /port/v1/orders/{ClientKey}/{OrderId}
            url = f"/port/v1/orders/{intent.client_key}/{order_id}"

            response = self.client.get(url)
            data = response.json() if hasattr(response, 'json') else response

            if data:
                 return ExecutionOutcome(
                    final_status="success",
                    order_id=order_id,
                    reconciliation=data
                )
        except Exception:
            pass

        return ExecutionOutcome(final_status="uncertain", order_id=order_id)
