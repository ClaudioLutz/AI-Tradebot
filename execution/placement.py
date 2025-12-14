from dataclasses import dataclass
from typing import Optional, Literal, Dict
from datetime import datetime
from enum import Enum
import uuid
import logging
import time
import requests
from requests.exceptions import Timeout

from execution.models import OrderIntent, OrderDurationType
from execution.precheck import PrecheckOutcome, ErrorInfo

logger = logging.getLogger(__name__)

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

@dataclass
class PlacementConfig:
    dry_run: bool = False

class OrderPlacementClient:
    """HTTP client for Saxo order placement and reconciliation"""

    def __init__(self, saxo_client, config: PlacementConfig = None):
        self.saxo_client = saxo_client
        self.logger = logger
        self.config = config or PlacementConfig()
        self.placement_timeout = 30.0  # seconds
        self.reconciliation_timeout = 10.0  # seconds

    def place_order(
        self,
        order_intent: OrderIntent,
        precheck_outcome: PrecheckOutcome
    ) -> ExecutionOutcome:
        """
        Place order in SIM environment after successful precheck.
        """
        return self._place_order_sync(order_intent, precheck_outcome)

    def _place_order_sync(
        self,
        order_intent: OrderIntent,
        precheck_outcome: PrecheckOutcome
    ) -> ExecutionOutcome:

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
                    order_id=None # No OrderId in dry run
                ),
                final_status="success",
                external_reference=order_intent.external_reference,
                timestamp=datetime.utcnow()
            )

        # Guard: Precheck must have succeeded
        if not precheck_outcome.ok:
            error_code = precheck_outcome.error_info.error_code if precheck_outcome.error_info else "Unknown"
            self.logger.error(
                "Cannot place order: precheck failed",
                extra={
                    "external_reference": order_intent.external_reference,
                    "error_code": error_code
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
                f"Placing order {request_id} in SIM",
                extra={
                    "request_id": request_id,
                    "account_key": order_intent.account_key,
                    "asset_type": order_intent.asset_type,
                    "uic": order_intent.uic,
                    "external_reference": order_intent.external_reference,
                    "buy_sell": order_intent.buy_sell,
                    "amount": order_intent.amount,
                    "manual_order": payload["ManualOrder"]
                }
            )

            # Using synchronous saxo_client.post
            try:
                response_data = self.saxo_client.post(
                    "/trade/v2/orders",
                    json_body=payload,
                    headers={"x-request-id": request_id}
                )

                # Assume 200/201 if successful, need to handle parsing carefully
                # We construct a response-like object or pass data directly
                placement_outcome = self._parse_placement_response_data(
                    response_data,
                    200, # Assume 200
                    request_id,
                    order_intent
                )
            except Exception as e:
                # Handle exceptions (Timeout, API Error)
                status_code = getattr(e, "status_code", 500)

                if isinstance(e, Timeout):
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
                else:
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
                        http_status=status_code,
                        request_id=request_id
                    )

        except Exception as e:
             # Should be caught above, but just in case
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
            reconciliation = self._reconcile_order(
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
            order_id=placement_outcome.order_id if placement_outcome.order_id else (reconciliation.order_id if reconciliation else None),
            external_reference=order_intent.external_reference,
            timestamp=datetime.utcnow()
        )

    def _build_order_payload(self, order_intent: OrderIntent) -> dict:
        """Build Saxo order placement payload"""
        # Note: DayOrder is strictly required for Market orders
        return {
            "AccountKey": order_intent.account_key,
            "Amount": float(order_intent.amount),
            "AssetType": order_intent.asset_type.value,
            "BuySell": order_intent.buy_sell.value,
            "ManualOrder": order_intent.manual_order,
            "OrderType": "Market", # order_intent.order_type.value, assuming Market for now per scope
            "Uic": order_intent.uic,
            "ExternalReference": order_intent.external_reference,
            "OrderDuration": {
                "DurationType": "DayOrder" # Force DayOrder for Market
            }
        }

    def _parse_placement_response_data(
        self,
        data: dict,
        http_status: int,
        request_id: str,
        order_intent: OrderIntent
    ) -> PlacementOutcome:
        """Parse order placement response data"""

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

    def _reconcile_order(
        self,
        order_intent: OrderIntent,
        placement_outcome: PlacementOutcome
    ) -> ReconciliationOutcome:
        """
        Reconcile uncertain order placement by querying portfolio.
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
                return self._reconcile_by_order_id(
                    placement_outcome.order_id,
                    order_intent.external_reference,
                    order_intent.client_key
                )

            # Strategy 2: Scan by ClientKey + ExternalReference
            return self._reconcile_by_external_reference(
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

    def _reconcile_by_order_id(
        self,
        order_id: str,
        external_reference: str,
        client_key: str
    ) -> ReconciliationOutcome:
        """Query portfolio orders by OrderId using ClientKey context"""

        try:
            response_data = self.saxo_client.get(
                "/port/v1/orders",
                params={"ClientKey": client_key, "OrderId": order_id}
            )

            orders = response_data.get("Data", [])

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

        except Exception as e:
             # Timeout or API Error
            self.logger.error(
                "Reconciliation query failed",
                extra={
                    "order_id": order_id,
                    "external_reference": external_reference,
                    "error": str(e)
                }
            )
            return ReconciliationOutcome(
                status=ReconciliationStatus.QUERY_FAILED,
                order_id=order_id,
                error_message=str(e)
            )

    def _reconcile_by_external_reference(
        self,
        client_key: str,
        external_reference: str
    ) -> ReconciliationOutcome:
        """
        Query portfolio orders by ClientKey and search for ExternalReference.
        """

        try:
            # Query recent orders for client
            # Using Status=All to find everything
            response_data = self.saxo_client.get(
                "/port/v1/orders",
                params={"ClientKey": client_key, "Status": "All"}
            )

            orders = response_data.get("Data", [])

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

        except Exception as e:
            return ReconciliationOutcome(
                status=ReconciliationStatus.QUERY_FAILED,
                error_message=str(e)
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

            if reconciliation.status == ReconciliationStatus.NOT_FOUND:
                return "failure" # Not found means placement didn't happen

        # Unable to determine
        return "uncertain"
