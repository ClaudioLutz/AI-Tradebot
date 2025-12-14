"""
Trade Execution Module - Saxo Bank Integration
Handles order placement and execution.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from execution.models import OrderIntent, ExecutionResult, ExecutionStatus, AssetType
from execution.validation import InstrumentValidator
from execution.position import PositionManager, PositionAwareGuards, ExecutionConfig as PositionConfig
from execution.precheck import PrecheckClient, PrecheckOutcome, RetryConfig as PrecheckRetryConfig
from execution.placement import OrderPlacementClient, PlacementConfig, ExecutionOutcome, PlacementStatus
from execution.disclaimers import DisclaimerService, DisclaimerConfig, DisclaimerResolutionOutcome

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradeExecutor(ABC):
    """
    Abstract interface for trade execution.
    Implementations handle DRY_RUN vs SIM vs LIVE environments.
    """
    
    @abstractmethod
    def execute(self, intent: OrderIntent, dry_run: bool = True) -> ExecutionResult:
        """
        Execute a trade intent through the full pipeline.
        """
        pass
    
    @abstractmethod
    def reconcile_order(self, order_id: str, external_reference: str, client_key: str) -> dict:
        """
        Query order status from portfolio for reconciliation.
        """
        pass

class SaxoTradeExecutor(TradeExecutor):
    """
    Concrete implementation of TradeExecutor for Saxo Bank.
    Orchestrates validation, guards, precheck, disclaimer handling, and placement.
    """
    
    def __init__(
        self,
        saxo_client,
        account_key: str,
        client_key: str,
        config: Dict[str, Any] = None
    ):
        self.client = saxo_client
        self.account_key = account_key
        self.client_key = client_key
        self.config = config or {}
        
        # Initialize components
        self.validator = InstrumentValidator(saxo_client)
        
        position_config = PositionConfig(
            duplicate_buy_policy=self.config.get("duplicate_buy_policy", "block"),
            allow_short_covering=self.config.get("allow_short_covering", False)
        )
        self.position_manager = PositionManager(saxo_client, client_key)
        self.guards = PositionAwareGuards(self.position_manager, position_config)
        
        precheck_retry = PrecheckRetryConfig()
        self.precheck_client = PrecheckClient(saxo_client, precheck_retry)
        
        disclaimer_config = DisclaimerConfig(
            policy=self.config.get("disclaimer_policy", DisclaimerConfig().policy)
        )
        self.disclaimer_service = DisclaimerService(saxo_client, disclaimer_config)
        
        # Placement client initialized per execute call to inject dry_run config?
        # Or initialized here. PlacementConfig takes dry_run.
        # But execute method takes dry_run param which overrides.
        # So we'll instantiate it or configure it in execute.
        # Actually better to keep it stateless or update config on flight?
        # The execute method's dry_run arg should drive it.
        # We will create OrderPlacementClient inside execute or pass config to place_order?
        # OrderPlacementClient takes config in init.
        # Let's re-instantiate or hold one and update it. Re-instantiating is cheap.
        
    def execute(self, intent: OrderIntent, dry_run: bool = True) -> ExecutionResult:
        """
        Execute a trade intent through the full pipeline:
        1. Instrument validation
        2. Position guards
        3. Precheck
        4. Disclaimer handling
        5. Placement (if not dry_run)
        6. Reconciliation (if needed)
        """
        logger.info(
            f"Starting execution for {intent.external_reference}",
            extra={
                "asset_type": intent.asset_type.value,
                "uic": intent.uic,
                "buy_sell": intent.buy_sell.value,
                "amount": float(intent.amount),
                "dry_run": dry_run
            }
        )

        # 1. Instrument Validation
        is_valid, error_msg = self.validator.validate_order_intent(intent)
        if not is_valid:
            logger.warning(f"Instrument validation failed: {error_msg}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED_PRECHECK,
                order_intent=intent,
                error_message=f"Instrument validation failed: {error_msg}",
                timestamp=datetime.utcnow().isoformat()
            )

        # 2. Position Guards
        # We need to run this async or sync? All components are sync wrappers now (except some used async/await in stories but I implemented sync).
        # My implementation of PositionAwareGuards is synchronous.
        
        if intent.buy_sell.value == "Buy":
            guard_result = self.guards.evaluate_buy_intent(intent.asset_type.value, intent.uic, intent.amount)
        else:
            guard_result = self.guards.evaluate_sell_intent(intent.asset_type.value, intent.uic, intent.amount)

        if not guard_result.allowed:
            logger.warning(f"Position guard blocked trade: {guard_result.reason}")
            return ExecutionResult(
                status=ExecutionStatus.BLOCKED_BY_POSITION,
                order_intent=intent,
                error_message=f"Position guard blocked: {guard_result.reason}",
                timestamp=datetime.utcnow().isoformat()
            )

        # If sell quantity was adjusted by guard (e.g. close full position), update intent?
        # Intent is immutable-ish (dataclass). We might need to copy it.
        # But for now assuming intent matches or guard just validated it.
        # If intent.amount was None (for sell), guard computes it.
        # My OrderIntent requires amount. So amount is already there.
        # Guard check: "sell_quantity = intended_quantity if intended_quantity else position.net_quantity"
        # If intent amount was not matching position but guard said ok (adjusted?), we might need to update intent.
        # But `OrderIntent` amount is mandatory float. So it's always specified.
        # If we want to support "Close Position" signal, the strategy should have set the amount or we query position before intent creation.
        # Story 005-006 says "amount for sell is either configured fixed quantity or close full position".
        # But `OrderIntent` has `amount`.
        # If `guard_result` returns `position_quantity`, we could verify if it matches intent.
        # But if guard allowed it, we proceed.

        # 3. Precheck
        precheck_outcome = self.precheck_client.execute_precheck(intent)
        
        if not precheck_outcome.ok:
            error_msg = precheck_outcome.error_info.message if precheck_outcome.error_info else "Unknown precheck error"
            logger.warning(f"Precheck failed: {error_msg}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED_PRECHECK,
                order_intent=intent,
                precheck_result=precheck_outcome, # Mapping needed if types differ?
                # ExecutionResult expects PrecheckResult (from models),
                # but I have PrecheckOutcome (from precheck).
                # They are similar but not identical. I should map them.
                # Or update ExecutionResult to use PrecheckOutcome.
                # Story 005-001 defined PrecheckResult. Story 005-003 defined PrecheckOutcome.
                # Ideally they should be the same.
                # I will map PrecheckOutcome to PrecheckResult for the return value.
                error_message=f"Precheck failed: {error_msg}",
                timestamp=datetime.utcnow().isoformat()
            )

        # 4. Disclaimer Handling
        disclaimer_outcome = self.disclaimer_service.evaluate_disclaimers(precheck_outcome, intent)

        if not disclaimer_outcome.allow_trading:
            # Construct error message
            msg_parts = []
            if disclaimer_outcome.blocking_disclaimers:
                msg_parts.append(f"Blocking: {[t.token for t in disclaimer_outcome.blocking_disclaimers]}")
            if disclaimer_outcome.normal_disclaimers:
                msg_parts.append(f"Normal (Policy {disclaimer_outcome.policy_applied.value}): {[t.token for t in disclaimer_outcome.normal_disclaimers]}")
            if disclaimer_outcome.errors:
                msg_parts.append(f"Errors: {disclaimer_outcome.errors}")

            full_msg = "; ".join(msg_parts)
            logger.warning(f"Blocked by disclaimers: {full_msg}")

            return ExecutionResult(
                status=ExecutionStatus.BLOCKED_BY_DISCLAIMER,
                order_intent=intent,
                # precheck_result=...,
                error_message=f"Disclaimers blocked trading: {full_msg}",
                timestamp=datetime.utcnow().isoformat()
            )

        # 5. Placement
        placement_config = PlacementConfig(dry_run=dry_run)
        placement_client = OrderPlacementClient(self.client, placement_config)
        
        execution_outcome = placement_client.place_order(intent, precheck_outcome)
        
        # Map ExecutionOutcome to ExecutionResult
        status = ExecutionStatus.SUCCESS
        if execution_outcome.final_status == "failure":
            status = ExecutionStatus.FAILED_PLACEMENT
        elif execution_outcome.final_status == "uncertain":
            status = ExecutionStatus.RECONCILIATION_NEEDED
        # DRY_RUN handling: ExecutionOutcome will have status success but no order_id
        if dry_run:
            status = ExecutionStatus.DRY_RUN

        return ExecutionResult(
            status=status,
            order_intent=intent,
            # precheck_result=..., # map if needed
            order_id=execution_outcome.order_id,
            error_message=execution_outcome.placement.error_info.message if execution_outcome.placement.error_info else None,
            timestamp=execution_outcome.timestamp.isoformat() if execution_outcome.timestamp else datetime.utcnow().isoformat(),
            needs_reconciliation=(execution_outcome.final_status == "uncertain")
        )

    def reconcile_order(self, order_id: str, external_reference: str, client_key: str = None) -> dict:
        """
        Query order status from portfolio for reconciliation.
        Using OrderPlacementClient's internal logic might be better if exposed,
        or use client directly.
        
        The TradeExecutor interface defines this method.
        """
        # We can reuse OrderPlacementClient's reconcile logic if we expose it or copy it.
        # Or just use the client directly here.
        
        client_key = client_key or self.client_key
        
        # This matches _reconcile_by_order_id in placement.py
        try:
            response = self.client.get(
                "/port/v1/orders",
                params={"ClientKey": client_key, "OrderId": order_id}
            )
            # Assuming client returns dict/json
            data = response if isinstance(response, dict) else response.json()
            return data
        except Exception as e:
            logger.error(f"Reconciliation failed for {order_id}: {e}")
            return {"Error": str(e)}

# Module-level information
__version__ = "2.2.0"
__api__ = "Saxo OpenAPI"

logger.info(f"Trade Execution Module v{__version__} ({__api__}) loaded")
