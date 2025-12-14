from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from enum import Enum
import time
import uuid
import logging

from execution.models import OrderIntent, PrecheckResult

logger = logging.getLogger(__name__)

class DisclaimerPolicy(Enum):
    BLOCK_ALL = "block_all"  # Safe default: block on any disclaimer
    AUTO_ACCEPT_NORMAL = "auto_accept_normal"  # Auto-accept Normal if simple, block on Blocking or complex
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
    conditions: list[dict] = field(default_factory=list)
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
        precheck_result: PrecheckResult,
        order_intent: OrderIntent
    ) -> DisclaimerResolutionOutcome:
        """
        Evaluate disclaimers from precheck and determine if trading is allowed.
        Synchronous wrapper.
        """
        # No disclaimers = trading allowed
        if not precheck_result.disclaimer_tokens:
            return DisclaimerResolutionOutcome(
                allow_trading=True,
                blocking_disclaimers=[],
                normal_disclaimers=[],
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )

        disclaimer_tokens = precheck_result.disclaimer_tokens

        # Fetch disclaimer details to classify them
        disclaimer_details = self._fetch_disclaimer_details_batch(
            disclaimer_tokens,
            order_intent
        )

        # Categorize disclaimers using DM field IsBlocking
        blocking = [d for d in disclaimer_details if d.is_blocking]
        normal = [d for d in disclaimer_details if not d.is_blocking]

        self.logger.info(
            "Evaluating disclaimers",
            extra={
                "external_reference": order_intent.external_reference,
                "total_disclaimers": len(disclaimer_tokens),
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
                precheck_result.disclaimer_context,
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
                    conditions=[],
                    retrieved_at=datetime.utcnow()
                ))

        return details_list

    def _get_disclaimer_details(
        self,
        token: str
    ) -> DisclaimerDetails:
        """
        Retrieve disclaimer details from Saxo DM service.
        """
        now = time.time()
        if token in self._cache:
            details, cached_at = self._cache[token]
            if now - cached_at < self.config.cache_ttl_seconds:
                return details

        try:
            response = self.saxo_client.get(
                "/dm/v2/disclaimers",
                params={"DisclaimerTokens": token}
            )
            data = response.json() if hasattr(response, 'json') else response

            if "Data" not in data or not data["Data"]:
                raise Exception(f"No disclaimer data returned for token {token}")

            disclaimer_item = data["Data"][0]

            details = DisclaimerDetails(
                disclaimer_token=disclaimer_item["DisclaimerToken"],
                is_blocking=bool(disclaimer_item.get("IsBlocking", True)),
                title=disclaimer_item.get("Title", ""),
                body=disclaimer_item.get("Body", ""),
                response_options=list(disclaimer_item.get("ResponseOptions", [])),
                conditions=list(disclaimer_item.get("Conditions", [])),
                retrieved_at=datetime.utcnow()
            )

            self._cache[token] = (details, now)
            return details

        except Exception as e:
            raise Exception(f"Error fetching disclaimer {token}: {str(e)}")

    def _auto_accept_disclaimers(
        self,
        disclaimer_details: List[DisclaimerDetails],
        disclaimer_context: Optional[str],
        order_intent: OrderIntent
    ) -> tuple[List[str], List[str]]:
        """
        Auto-accept non-blocking disclaimers if they meet criteria (no conditions, simple acceptance).
        """
        accepted = []
        errors = []

        if not disclaimer_context:
            errors.append("Missing DisclaimerContext for auto-acceptance")
            return accepted, errors

        for details in disclaimer_details:
            if details.is_blocking:
                errors.append(f"Cannot auto-accept blocking disclaimer {details.disclaimer_token}")
                continue

            # CHECK 1: Conditions
            if details.conditions:
                errors.append(f"Disclaimer {details.disclaimer_token} has conditions requiring user input")
                continue

            # CHECK 2: Response Options
            # We look for a simple "Accepted" option.
            # Saxo policy: If user input/conditions required, we can't auto-accept.
            # ResponseOptions usually contains valid values for ResponseType.

            # Handle both "Value" and key-based ResponseType (2.5)
            # ResponseOptions example: [{"ResponseType": "Accepted", ...}]
            # Or dictionary with keys? Assuming list of dicts.

            valid_responses = []
            for opt in details.response_options:
                # Check for ResponseType or Value
                if "ResponseType" in opt:
                    valid_responses.append(opt["ResponseType"])
                elif "Value" in opt:
                    valid_responses.append(opt["Value"])

            if "Accepted" not in valid_responses:
                errors.append(f"Disclaimer {details.disclaimer_token} does not offer 'Accepted' response option. Options: {valid_responses}")
                continue

            # If multiple options, but Accepted is one, is it safe?
            # E.g. "Accepted", "Declined". If we auto-accept, we choose Accepted.
            # E.g. "Accepted", "Dismissed".
            # The risk is if the user SHOULD have made a choice.
            # But "AUTO_ACCEPT_NORMAL" implies we want to accept if possible.
            # As long as there are no "Conditions", we assume we can Accept.

            try:
                request_id = str(uuid.uuid4())
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

            except Exception as e:
                errors.append(f"Error accepting disclaimer {details.disclaimer_token}: {str(e)}")

        return accepted, errors

    def _log_blocking_disclaimers(self, blocking: List[DisclaimerDetails], order_intent: OrderIntent):
        self.logger.warning(
            "Trading blocked: Blocking disclaimers present",
            extra={
                "external_reference": order_intent.external_reference,
                "blocking_tokens": [d.disclaimer_token for d in blocking],
            }
        )

    def _log_normal_disclaimers(self, normal: List[DisclaimerDetails], order_intent: OrderIntent, policy_name: str):
        self.logger.warning(
            f"Trading blocked: Normal disclaimers present (policy: {policy_name})",
            extra={
                "external_reference": order_intent.external_reference,
                "normal_tokens": [d.disclaimer_token for d in normal],
            }
        )
