from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from enum import Enum
import time
import uuid
import logging
import httpx
from requests.exceptions import Timeout
import requests

from execution.models import OrderIntent
from execution.precheck import PrecheckOutcome

logger = logging.getLogger(__name__)

class DisclaimerPolicy(Enum):
    BLOCK_ALL = "block_all"  # Safe default: block on any disclaimer
    AUTO_ACCEPT_NORMAL = "auto_accept_normal"  # Auto-accept Normal, block on Blocking
    MANUAL_REVIEW = "manual_review"  # Log and require manual intervention

@dataclass
class DisclaimerToken:
    """Token identifying a disclaimer requirement (from precheck/placement)"""
    token: str

@dataclass
class DisclaimerDetails:
    """Full disclaimer content and metadata"""
    disclaimer_token: str
    is_blocking: bool
    title: str
    body: str
    response_options: list[dict]
    retrieved_at: datetime = None

@dataclass
class DisclaimerResolutionOutcome:
    """Outcome of disclaimer resolution attempt"""
    allow_trading: bool
    blocking_disclaimers: List[DisclaimerToken]
    normal_disclaimers: List[DisclaimerToken]
    auto_accepted: List[str]  # List of tokens that were auto-accepted
    errors: List[str]  # Any errors during resolution
    policy_applied: DisclaimerPolicy

@dataclass
class DisclaimerConfig:
    """Configuration for disclaimer handling"""
    policy: DisclaimerPolicy = DisclaimerPolicy.BLOCK_ALL
    cache_ttl_seconds: int = 300  # 5 minutes
    auto_accept_timeout: float = 5.0  # seconds
    retrieve_timeout: float = 5.0  # seconds

class DisclaimerService:
    """Service for handling Saxo pre-trade disclaimers"""

    def __init__(self, saxo_client, config: DisclaimerConfig = None):
        self.saxo_client = saxo_client
        self.logger = logger
        self.config = config or DisclaimerConfig()
        self._cache: Dict[str, Tuple[DisclaimerDetails, float]] = {}

    def evaluate_disclaimers(
        self,
        precheck_outcome: PrecheckOutcome,
        order_intent: OrderIntent
    ) -> DisclaimerResolutionOutcome:
        """
        Evaluate disclaimers from precheck and determine if trading is allowed.
        Synchronous wrapper.
        """
        # No disclaimers = trading allowed
        if not precheck_outcome.pre_trade_disclaimers or not precheck_outcome.pre_trade_disclaimers.disclaimer_tokens:
            return DisclaimerResolutionOutcome(
                allow_trading=True,
                blocking_disclaimers=[],
                normal_disclaimers=[],
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )

        disclaimers = precheck_outcome.pre_trade_disclaimers

        # Fetch disclaimer details to classify them
        disclaimer_details = self._fetch_disclaimer_details_batch(
            disclaimers.disclaimer_tokens,
            order_intent
        )

        # Categorize disclaimers using DM field IsBlocking
        blocking = [d for d in disclaimer_details if d.is_blocking]
        normal = [d for d in disclaimer_details if not d.is_blocking]

        self.logger.info(
            "Evaluating disclaimers",
            extra={
                "external_reference": order_intent.external_reference,
                "total_disclaimers": len(disclaimers.disclaimer_tokens),
                "blocking_count": len(blocking),
                "normal_count": len(normal),
                "policy": self.config.policy.value
            }
        )

        # Blocking disclaimers ALWAYS block trading
        if blocking:
            self._log_blocking_disclaimers(blocking, order_intent)

            return DisclaimerResolutionOutcome(
                allow_trading=False,
                blocking_disclaimers=[DisclaimerToken(d.disclaimer_token) for d in blocking],
                normal_disclaimers=[DisclaimerToken(d.disclaimer_token) for d in normal],
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )

        # Handle normal disclaimers based on policy
        if self.config.policy == DisclaimerPolicy.BLOCK_ALL:
            self._log_normal_disclaimers(normal, order_intent, "BLOCK_ALL")
            return DisclaimerResolutionOutcome(
                allow_trading=False,
                blocking_disclaimers=[],
                normal_disclaimers=[DisclaimerToken(d.disclaimer_token) for d in normal],
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )

        elif self.config.policy == DisclaimerPolicy.AUTO_ACCEPT_NORMAL:
            # Attempt to auto-accept normal disclaimers
            auto_accepted, errors = self._auto_accept_disclaimers(
                normal,
                disclaimers.disclaimer_context,
                order_intent
            )

            if errors:
                self.logger.error(
                    "Trading blocked: Failed to auto-accept some disclaimers",
                    extra={
                        "external_reference": order_intent.external_reference,
                        "errors": errors,
                        "accepted_count": len(auto_accepted),
                        "total_count": len(normal)
                    }
                )

                return DisclaimerResolutionOutcome(
                    allow_trading=False,
                    blocking_disclaimers=[],
                    normal_disclaimers=[DisclaimerToken(d.disclaimer_token) for d in normal],
                    auto_accepted=auto_accepted,
                    errors=errors,
                    policy_applied=self.config.policy
                )

            self.logger.info(
                "Trading allowed: All normal disclaimers auto-accepted",
                extra={
                    "external_reference": order_intent.external_reference,
                    "accepted_tokens": auto_accepted,
                    "account_key": order_intent.account_key
                }
            )

            return DisclaimerResolutionOutcome(
                allow_trading=True,
                blocking_disclaimers=[],
                normal_disclaimers=[DisclaimerToken(d.disclaimer_token) for d in normal],
                auto_accepted=auto_accepted,
                errors=[],
                policy_applied=self.config.policy
            )

        else:  # MANUAL_REVIEW
            self._log_normal_disclaimers(normal, order_intent, "MANUAL_REVIEW")
            return DisclaimerResolutionOutcome(
                allow_trading=False,
                blocking_disclaimers=[],
                normal_disclaimers=[DisclaimerToken(d.disclaimer_token) for d in normal],
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )

    def _fetch_disclaimer_details_batch(
        self,
        tokens: List[str],
        order_intent: OrderIntent
    ) -> List[DisclaimerDetails]:
        """
        Fetch disclaimer details for multiple tokens.
        """
        if not tokens:
            return []

        details_list = []
        for token in tokens:
            try:
                details = self._get_disclaimer_details(token)
                details_list.append(details)
            except Exception as e:
                self.logger.error(
                    "Failed to fetch disclaimer details",
                    extra={
                        "token": token,
                        "error": str(e),
                        "external_reference": order_intent.external_reference
                    }
                )
                # On error, assume it's blocking (conservative)
                details_list.append(DisclaimerDetails(
                    disclaimer_token=token,
                    is_blocking=True,
                    title="Unknown Disclaimer",
                    body=f"Failed to retrieve details: {str(e)}",
                    response_options=[],
                    retrieved_at=datetime.utcnow()
                ))

        return details_list

    def _get_disclaimer_details(
        self,
        token: str
    ) -> DisclaimerDetails:
        """
        Retrieve disclaimer details from Saxo DM service.
        Uses in-memory cache with TTL to avoid repeated calls.
        """

        # Check cache
        now = time.time()
        if token in self._cache:
            details, cached_at = self._cache[token]
            if now - cached_at < self.config.cache_ttl_seconds:
                self.logger.debug(f"Using cached disclaimer details for {token}")
                return details

        # Fetch from API
        self.logger.debug(f"Fetching disclaimer details for {token}")

        try:
            # Batch endpoint uses DisclaimerTokens[]; if we do per-token fetch (fallback), still use DisclaimerTokens
            # Note: saxo_client.get param values can be lists if supported, or we might need to construct query string manually
            # But here we are fetching one by one as per loop above (though batch is better, simpler for now to loop)
            # The client wrapper usually handles params.
            # If saxo_client.get handles list params correctly (repeated keys), we could do batch.
            # But let's stick to single token fetching inside _get_disclaimer_details which is called in a loop.

            response = self.saxo_client.get(
                "/dm/v2/disclaimers",
                params={"DisclaimerTokens": token}
            )

            # response is expected to be dict or have .json()
            data = response
            if hasattr(response, 'json'):
                 data = response.json()

            # CRITICAL: DM endpoint returns a Data[] feed, not a flat object
            # Parse the first item from the Data array
            if "Data" not in data or not data["Data"]:
                raise Exception(f"No disclaimer data returned for token {token}")

            disclaimer_item = data["Data"][0]  # Single token query returns one item

            details = DisclaimerDetails(
                disclaimer_token=disclaimer_item["DisclaimerToken"],
                is_blocking=bool(disclaimer_item.get("IsBlocking", True)),
                title=disclaimer_item.get("Title", ""),
                body=disclaimer_item.get("Body", ""),
                response_options=list(disclaimer_item.get("ResponseOptions", [])),
                retrieved_at=datetime.utcnow()
            )

            # Cache the result
            self._cache[token] = (details, now)

            return details

        except Exception as e:
            raise Exception(f"Error fetching disclaimer {token}: {str(e)}")

    def _auto_accept_disclaimers(
        self,
        disclaimer_details: List[DisclaimerDetails],
        disclaimer_context: str,
        order_intent: OrderIntent
    ) -> tuple[List[str], List[str]]:
        """
        Auto-accept non-blocking disclaimers.
        """
        accepted = []
        errors = []

        for details in disclaimer_details:
            # DEFENSIVE CHECK: Never auto-accept blocking disclaimers
            if details.is_blocking:
                error_msg = f"Attempted to auto-accept BLOCKING disclaimer {details.disclaimer_token} - BLOCKED"
                self.logger.critical(
                    error_msg,
                    extra={
                        "disclaimer_token": details.disclaimer_token,
                        "is_blocking": details.is_blocking,
                        "external_reference": order_intent.external_reference
                    }
                )
                errors.append(error_msg)
                continue

            try:
                self.logger.info(
                    "Auto-accepting normal disclaimer",
                    extra={
                        "disclaimer_token": details.disclaimer_token,
                        "title": details.title,
                        "is_blocking": details.is_blocking,
                        "external_reference": order_intent.external_reference
                    }
                )

                # Register acceptance with DM service
                request_id = str(uuid.uuid4())

                # saxo_client.post(endpoint, json_body, headers)
                self.saxo_client.post(
                    "/dm/v2/disclaimers",
                    json_body={
                        "DisclaimerContext": disclaimer_context,
                        "DisclaimerToken": details.disclaimer_token,
                        "ResponseType": "Accepted",
                        "UserInput": ""
                    },
                    headers={"x-request-id": request_id}
                )

                accepted.append(details.disclaimer_token)
                self.logger.info(
                    "Disclaimer accepted successfully",
                    extra={
                        "disclaimer_token": details.disclaimer_token,
                        "request_id": request_id,
                        "external_reference": order_intent.external_reference
                    }
                )

            except Exception as e:
                error_msg = f"Error accepting disclaimer {details.disclaimer_token}: {str(e)}"
                self.logger.exception(
                    "Exception while auto-accepting disclaimer",
                    extra={
                        "disclaimer_token": details.disclaimer_token,
                        "external_reference": order_intent.external_reference
                    }
                )
                errors.append(error_msg)

        return accepted, errors

    def _log_blocking_disclaimers(self, blocking: List[DisclaimerDetails], order_intent: OrderIntent):
        self.logger.warning(
            "Trading blocked: Blocking disclaimers present",
            extra={
                "external_reference": order_intent.external_reference,
                "blocking_tokens": [d.disclaimer_token for d in blocking],
                "account_key": order_intent.account_key,
                "uic": order_intent.uic
            }
        )
        for detail in blocking:
            self.logger.warning(
                "Blocking disclaimer detail",
                extra={
                    "disclaimer_token": detail.disclaimer_token,
                    "is_blocking": detail.is_blocking,
                    "title": detail.title,
                    "body": detail.body[:200] + "..." if len(detail.body) > 200 else detail.body,
                    "external_reference": order_intent.external_reference
                }
            )

    def _log_normal_disclaimers(self, normal: List[DisclaimerDetails], order_intent: OrderIntent, policy_name: str):
        self.logger.warning(
            f"Trading blocked: Normal disclaimers present (policy: {policy_name})",
            extra={
                "external_reference": order_intent.external_reference,
                "normal_tokens": [d.disclaimer_token for d in normal],
                "account_key": order_intent.account_key
            }
        )
        for detail in normal:
            self.logger.warning(
                "Normal disclaimer detail",
                extra={
                    "disclaimer_token": detail.disclaimer_token,
                    "is_blocking": detail.is_blocking,
                    "title": detail.title,
                    "body": detail.body[:200] + "..." if len(detail.body) > 200 else detail.body,
                    "external_reference": order_intent.external_reference
                }
            )
