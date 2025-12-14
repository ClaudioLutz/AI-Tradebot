# Story 005-005: Pre-trade disclaimers handling (mandatory support plan)

## Summary
Implement support for Saxo pre-trade disclaimers surfaced via precheck/order placement, including retrieval of disclaimer details and (optionally) registering responses.

## Background / Context
Saxo has announced that handling pre-trade disclaimers will become mandatory for all OpenAPI apps from May 2025.
Orders can be rejected at any time if there are outstanding disclaimers. Precheck and/or order placement can
surface disclaimer tokens that must be handled (blocking vs normal disclaimers).

## Scope
In scope:
- Persist disclaimer tokens surfaced via precheck into `PrecheckOutcome`.
- Implement a "disclaimer resolution" service:
  - GET /dm/v2/disclaimers to fetch the disclaimer texts / metadata for tokens.
  - Policy-driven response handling:
    - Default: **block trading** and log actionable message (safe-by-default).
    - Optional (config): auto-accept *normal* disclaimers only, via POST /dm/v2/disclaimers.
- Ensure placement is blocked when disclaimers are outstanding and policy is "block".

Out of scope:
- UI/UX for presenting disclaimers to a human
- Accepting blocking disclaimers (not possible by definition)

## Technical Details

### API Endpoint Specification

#### Get Disclaimer Details
```
GET https://gateway.saxobank.com/sim/openapi/dm/v2/disclaimers?Token={token}
Authorization: Bearer {access_token}
```

#### Register Disclaimer Response
```
POST https://gateway.saxobank.com/sim/openapi/dm/v2/disclaimers
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "Token": "string",
  "Accepted": boolean
}
```

### Disclaimer Types

| Type | Description | Can Auto-Accept | Blocks Trading |
|------|-------------|-----------------|----------------|
| Normal | Standard risk disclaimers | Yes (with config) | Only until accepted |
| Blocking | Critical disclaimers requiring human review | No (never) | Always blocks automated trading |

### Response Payload Models

#### Precheck Response with Disclaimers
```json
{
  "PreCheckResult": "Ok",
  "EstimatedCost": {
    "Amount": 1234.56,
    "Currency": "USD"
  },
  "PreTradeDisclaimers": {
    "Disclaimers": [
      {
        "Token": "DM_RISK_WARNING_2025_Q1",
        "Type": "Normal"
      },
      {
        "Token": "DM_REGULATORY_NOTICE_EU",
        "Type": "Blocking"
      }
    ]
  }
}
```

#### Disclaimer Details Response
```json
{
  "Token": "DM_RISK_WARNING_2025_Q1",
  "Type": "Normal",
  "Title": "Risk Warning",
  "Content": "Trading in financial instruments involves substantial risk...",
  "RequiresResponse": true,
  "ExpiresAt": "2025-12-31T23:59:59Z"
}
```

#### Disclaimer Response Registration
```json
{
  "Token": "DM_RISK_WARNING_2025_Q1",
  "Accepted": true,
  "RegisteredAt": "2025-12-14T09:42:00Z"
}
```

### Data Models

```python
from dataclasses import dataclass
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

class DisclaimerType(Enum):
    NORMAL = "Normal"
    BLOCKING = "Blocking"

class DisclaimerPolicy(Enum):
    BLOCK_ALL = "block_all"  # Safe default: block on any disclaimer
    AUTO_ACCEPT_NORMAL = "auto_accept_normal"  # Auto-accept Normal, block on Blocking
    MANUAL_REVIEW = "manual_review"  # Log and require manual intervention

@dataclass
class DisclaimerToken:
    """Token identifying a disclaimer requirement"""
    token: str
    type: str  # "Normal" or "Blocking"

@dataclass
class DisclaimerDetails:
    """Full disclaimer content and metadata"""
    token: str
    type: DisclaimerType
    title: str
    content: str
    requires_response: bool
    expires_at: Optional[datetime] = None
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
```

### Implementation Pattern

```python
from typing import Dict
import time

class DisclaimerService:
    """Service for handling Saxo pre-trade disclaimers"""
    
    def __init__(self, saxo_client, logger, config: DisclaimerConfig):
        self.saxo_client = saxo_client
        self.logger = logger
        self.config = config
        self._cache: Dict[str, tuple[DisclaimerDetails, float]] = {}
        
    async def evaluate_disclaimers(
        self,
        precheck_outcome: PrecheckOutcome,
        order_intent: OrderIntent
    ) -> DisclaimerResolutionOutcome:
        """
        Evaluate disclaimers from precheck and determine if trading is allowed.
        
        Returns:
            DisclaimerResolutionOutcome with allow_trading flag and details
        """
        
        # No disclaimers = trading allowed
        if not precheck_outcome.pre_trade_disclaimers:
            return DisclaimerResolutionOutcome(
                allow_trading=True,
                blocking_disclaimers=[],
                normal_disclaimers=[],
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )
        
        disclaimers = precheck_outcome.pre_trade_disclaimers
        
        # Categorize disclaimers
        blocking = [d for d in disclaimers if d.type == "Blocking"]
        normal = [d for d in disclaimers if d.type == "Normal"]
        
        self.logger.info(
            "Evaluating disclaimers",
            extra={
                "external_reference": order_intent.external_reference,
                "total_disclaimers": len(disclaimers),
                "blocking_count": len(blocking),
                "normal_count": len(normal),
                "policy": self.config.policy.value
            }
        )
        
        # Blocking disclaimers ALWAYS block trading
        if blocking:
            self.logger.warning(
                "Trading blocked: Blocking disclaimers present",
                extra={
                    "external_reference": order_intent.external_reference,
                    "blocking_tokens": [d.token for d in blocking],
                    "account_key": order_intent.account_key,
                    "uic": order_intent.uic
                }
            )
            
            # Fetch details for blocking disclaimers for logging
            await self._fetch_and_log_disclaimer_details(blocking, order_intent)
            
            return DisclaimerResolutionOutcome(
                allow_trading=False,
                blocking_disclaimers=blocking,
                normal_disclaimers=normal,
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )
        
        # Handle normal disclaimers based on policy
        if self.config.policy == DisclaimerPolicy.BLOCK_ALL:
            self.logger.warning(
                "Trading blocked: Normal disclaimers present (policy: BLOCK_ALL)",
                extra={
                    "external_reference": order_intent.external_reference,
                    "normal_tokens": [d.token for d in normal],
                    "account_key": order_intent.account_key
                }
            )
            
            await self._fetch_and_log_disclaimer_details(normal, order_intent)
            
            return DisclaimerResolutionOutcome(
                allow_trading=False,
                blocking_disclaimers=[],
                normal_disclaimers=normal,
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )
        
        elif self.config.policy == DisclaimerPolicy.AUTO_ACCEPT_NORMAL:
            # Attempt to auto-accept normal disclaimers
            auto_accepted, errors = await self._auto_accept_disclaimers(
                normal,
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
                    normal_disclaimers=normal,
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
                normal_disclaimers=normal,
                auto_accepted=auto_accepted,
                errors=[],
                policy_applied=self.config.policy
            )
        
        else:  # MANUAL_REVIEW
            self.logger.warning(
                "Trading blocked: Manual review required (policy: MANUAL_REVIEW)",
                extra={
                    "external_reference": order_intent.external_reference,
                    "normal_tokens": [d.token for d in normal]
                }
            )
            
            await self._fetch_and_log_disclaimer_details(normal, order_intent)
            
            return DisclaimerResolutionOutcome(
                allow_trading=False,
                blocking_disclaimers=[],
                normal_disclaimers=normal,
                auto_accepted=[],
                errors=[],
                policy_applied=self.config.policy
            )
    
    async def _fetch_and_log_disclaimer_details(
        self,
        disclaimers: List[DisclaimerToken],
        order_intent: OrderIntent
    ):
        """Fetch and log full disclaimer details for operator review"""
        
        for disclaimer in disclaimers:
            try:
                details = await self._get_disclaimer_details(disclaimer.token)
                
                self.logger.warning(
                    "Disclaimer details",
                    extra={
                        "token": details.token,
                        "type": details.type.value,
                        "title": details.title,
                        "content": details.content[:200] + "..." if len(details.content) > 200 else details.content,
                        "requires_response": details.requires_response,
                        "expires_at": details.expires_at.isoformat() if details.expires_at else None,
                        "external_reference": order_intent.external_reference
                    }
                )
            except Exception as e:
                self.logger.error(
                    "Failed to fetch disclaimer details",
                    extra={
                        "token": disclaimer.token,
                        "error": str(e),
                        "external_reference": order_intent.external_reference
                    }
                )
    
    async def _get_disclaimer_details(
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
            response = await self.saxo_client.get(
                f"/dm/v2/disclaimers?Token={token}",
                timeout=self.config.retrieve_timeout
            )
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            
            details = DisclaimerDetails(
                token=data["Token"],
                type=DisclaimerType(data["Type"]),
                title=data.get("Title", ""),
                content=data.get("Content", ""),
                requires_response=data.get("RequiresResponse", True),
                expires_at=datetime.fromisoformat(data["ExpiresAt"].replace("Z", "+00:00")) if "ExpiresAt" in data else None,
                retrieved_at=datetime.utcnow()
            )
            
            # Cache the result
            self._cache[token] = (details, now)
            
            return details
            
        except httpx.TimeoutException:
            raise Exception(f"Timeout fetching disclaimer {token}")
        except Exception as e:
            raise Exception(f"Error fetching disclaimer {token}: {str(e)}")
    
    async def _auto_accept_disclaimers(
        self,
        disclaimers: List[DisclaimerToken],
        order_intent: OrderIntent
    ) -> tuple[List[str], List[str]]:
        """
        Auto-accept normal disclaimers.
        
        Returns:
            (accepted_tokens, errors)
        """
        accepted = []
        errors = []
        
        for disclaimer in disclaimers:
            try:
                # Fetch details first to log what we're accepting
                details = await self._get_disclaimer_details(disclaimer.token)
                
                self.logger.info(
                    "Auto-accepting normal disclaimer",
                    extra={
                        "token": disclaimer.token,
                        "title": details.title,
                        "external_reference": order_intent.external_reference
                    }
                )
                
                # Register acceptance
                response = await self.saxo_client.post(
                    "/dm/v2/disclaimers",
                    json={
                        "Token": disclaimer.token,
                        "Accepted": True
                    },
                    timeout=self.config.auto_accept_timeout
                )
                
                if response.status_code >= 400:
                    error_msg = f"HTTP {response.status_code} for token {disclaimer.token}"
                    self.logger.error(
                        "Failed to register disclaimer acceptance",
                        extra={
                            "token": disclaimer.token,
                            "http_status": response.status_code,
                            "external_reference": order_intent.external_reference
                        }
                    )
                    errors.append(error_msg)
                else:
                    accepted.append(disclaimer.token)
                    self.logger.info(
                        "Disclaimer accepted successfully",
                        extra={
                            "token": disclaimer.token,
                            "external_reference": order_intent.external_reference
                        }
                    )
                    
            except httpx.TimeoutException:
                error_msg = f"Timeout accepting disclaimer {disclaimer.token}"
                self.logger.error(error_msg)
                errors.append(error_msg)
                
            except Exception as e:
                error_msg = f"Error accepting disclaimer {disclaimer.token}: {str(e)}"
                self.logger.exception(
                    "Exception while auto-accepting disclaimer",
                    extra={
                        "token": disclaimer.token,
                        "external_reference": order_intent.external_reference
                    }
                )
                errors.append(error_msg)
        
        return accepted, errors
```

### Integration with Order Execution Flow

```python
class TradeExecutor:
    """Main trade execution orchestrator with disclaimer support"""
    
    def __init__(
        self,
        precheck_client: PrecheckClient,
        placement_client: OrderPlacementClient,
        disclaimer_service: DisclaimerService,
        logger
    ):
        self.precheck_client = precheck_client
        self.placement_client = placement_client
        self.disclaimer_service = disclaimer_service
        self.logger = logger
    
    async def execute_trade(
        self,
        order_intent: OrderIntent
    ) -> ExecutionOutcome:
        """
        Execute trade with full precheck → disclaimer check → placement flow.
        """
        
        # Step 1: Precheck
        precheck_outcome = await self.precheck_client.execute_precheck(order_intent)
        
        if not precheck_outcome.ok:
            self.logger.warning(
                "Trade execution stopped: Precheck failed",
                extra={
                    "external_reference": order_intent.external_reference,
                    "error_code": precheck_outcome.error_info.error_code
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
        
        # Step 2: Evaluate disclaimers
        disclaimer_outcome = await self.disclaimer_service.evaluate_disclaimers(
            precheck_outcome,
            order_intent
        )
        
        if not disclaimer_outcome.allow_trading:
            # Build detailed error message
            error_parts = []
            
            if disclaimer_outcome.blocking_disclaimers:
                tokens = [d.token for d in disclaimer_outcome.blocking_disclaimers]
                error_parts.append(f"Blocking disclaimers: {', '.join(tokens)}")
            
            if disclaimer_outcome.normal_disclaimers:
                tokens = [d.token for d in disclaimer_outcome.normal_disclaimers]
                error_parts.append(f"Normal disclaimers: {', '.join(tokens)}")
            
            if disclaimer_outcome.errors:
                error_parts.append(f"Errors: {', '.join(disclaimer_outcome.errors)}")
            
            error_message = "; ".join(error_parts)
            
            self.logger.error(
                "Trade execution stopped: Disclaimer check blocked trading",
                extra={
                    "external_reference": order_intent.external_reference,
                    "policy": disclaimer_outcome.policy_applied.value,
                    "blocking_count": len(disclaimer_outcome.blocking_disclaimers),
                    "normal_count": len(disclaimer_outcome.normal_disclaimers),
                    "error_message": error_message
                }
            )
            
            return ExecutionOutcome(
                placement=PlacementOutcome(
                    status=PlacementStatus.FAILURE,
                    error_info=ErrorInfo(
                        error_code="DISCLAIMER_BLOCKED",
                        message=error_message
                    )
                ),
                final_status="failure",
                external_reference=order_intent.external_reference,
                timestamp=datetime.utcnow()
            )
        
        # Step 3: Place order
        self.logger.info(
            "Proceeding to order placement (precheck ok, disclaimers resolved)",
            extra={
                "external_reference": order_intent.external_reference,
                "auto_accepted_count": len(disclaimer_outcome.auto_accepted)
            }
        )
        
        execution_outcome = await self.placement_client.place_order(
            order_intent,
            precheck_outcome
        )
        
        return execution_outcome
```

### Configuration Examples

#### Safe Default (Block All)
```python
config = DisclaimerConfig(
    policy=DisclaimerPolicy.BLOCK_ALL,
    cache_ttl_seconds=300
)
# Any disclaimer (Normal or Blocking) will block trading
# Requires manual intervention to clear
```

#### Auto-Accept Normal (Recommended for Production)
```python
config = DisclaimerConfig(
    policy=DisclaimerPolicy.AUTO_ACCEPT_NORMAL,
    cache_ttl_seconds=300,
    auto_accept_timeout=5.0,
    retrieve_timeout=5.0
)
# Normal disclaimers are auto-accepted
# Blocking disclaimers still block trading
# Most balanced approach for automated trading
```

#### Manual Review
```python
config = DisclaimerConfig(
    policy=DisclaimerPolicy.MANUAL_REVIEW,
    cache_ttl_seconds=300
)
# All disclaimers require manual review
# Most conservative approach
```

### Logging Specification

#### Disclaimer Detected Log
```json
{
  "timestamp": "2025-12-14T09:42:00Z",
  "level": "INFO",
  "message": "Evaluating disclaimers",
  "external_reference": "BOT_BUY_AAPL_20251214_094200",
  "total_disclaimers": 2,
  "blocking_count": 1,
  "normal_count": 1,
  "policy": "block_all"
}
```

#### Blocking Disclaimer Warning
```json
{
  "timestamp": "2025-12-14T09:42:00Z",
  "level": "WARNING",
  "message": "Trading blocked: Blocking disclaimers present",
  "external_reference": "BOT_BUY_AAPL_20251214_094200",
  "blocking_tokens": ["DM_REGULATORY_NOTICE_EU"],
  "account_key": "Gv1B3n...",
  "uic": 211
}
```

#### Disclaimer Details Log
```json
{
  "timestamp": "2025-12-14T09:42:01Z",
  "level": "WARNING",
  "message": "Disclaimer details",
  "token": "DM_REGULATORY_NOTICE_EU",
  "type": "Blocking",
  "title": "EU Regulatory Notice",
  "content": "This instrument is subject to special regulatory requirements...",
  "requires_response": true,
  "expires_at": "2025-12-31T23:59:59Z",
  "external_reference": "BOT_BUY_AAPL_20251214_094200"
}
```

#### Auto-Accept Success Log
```json
{
  "timestamp": "2025-12-14T09:42:02Z",
  "level": "INFO",
  "message": "Trading allowed: All normal disclaimers auto-accepted",
  "external_reference": "BOT_BUY_AAPL_20251214_094200",
  "accepted_tokens": ["DM_RISK_WARNING_2025_Q1"],
  "account_key": "Gv1B3n..."
}
```

### Decision Flow Diagram

```
┌──────────────────┐
│ Precheck Returns │
│   Disclaimers    │
└────────┬─────────┘
         │
         ▼
   ┌────────────┐
   │ Categorize │
   └─────┬──────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
BLOCKING    NORMAL
    │          │
    │     ┌────┴────────────┐
    │     │                 │
    │     ▼                 ▼
    │  BLOCK_ALL    AUTO_ACCEPT_NORMAL
    │     │                 │
    │     │            ┌────┴─────┐
    │     │            │          │
    │     │            ▼          ▼
    │     │        SUCCESS     FAILURE
    │     │            │          │
    ▼     ▼            ▼          ▼
  BLOCK  BLOCK      ALLOW      BLOCK
TRADING TRADING    TRADING    TRADING
```

## Acceptance Criteria
1. If precheck returns `PreTradeDisclaimers`, executor does not place the order unless the configured policy allows it.
2. Default behavior is safe: executor logs and returns a "blocked_by_disclaimer" outcome.
3. The system can fetch disclaimer details for the provided tokens.
4. If configured for auto-accept:
   - Only "normal" disclaimers are accepted automatically.
   - Blocking disclaimers always block trading with an explicit log entry.
5. Disclaimer tokens and handling outcomes are logged with correlation fields:
   `{external_reference, request_id, account_key, asset_type, uic}`.
6. Disclaimer details (title, content) are logged for operator review when trading is blocked.

## Implementation Notes
- Disclaimer logic should be isolated so it can be unit-tested independently from precheck/placement.
- Store (token → disclaimer metadata) in a short TTL cache to avoid repeated DM calls during loops.
- Treat disclaimers as a "hard gate" in orchestration:
  - precheck ok + disclaimers ok → may place
  - precheck ok + disclaimers outstanding → block or resolve first, depending on policy
- Cache TTL should be configurable (default: 5 minutes).
- Always log full disclaimer details when blocking trading for operator visibility.
- Implement proper timeout handling for disclaimer API calls.
- Never attempt to auto-accept Blocking disclaimers - these must be handled manually.

## Test Plan
- Unit tests (mock HTTP):
  - Precheck returns tokens → executor blocks by default.
  - GET disclaimers returns disclaimer content → stored and logged.
  - Auto-accept mode posts responses only for acceptable disclaimers; blocks if any blocking disclaimers exist.
  - Cache mechanism works correctly (no duplicate API calls within TTL).
  - Timeout handling for disclaimer API calls.
- Integration (SIM):
  - If an instrument/account triggers disclaimers, verify blocking behavior and DM retrieval.
  - If no disclaimers occur, ensure code path remains inactive (no DM calls).
  - Test each policy mode (BLOCK_ALL, AUTO_ACCEPT_NORMAL, MANUAL_REVIEW).

## Dependencies / Assumptions
- Depends on precheck output (Story 005-003).
- Requires DM service group permissions for the application.
- Configuration must include a disclaimer policy (block vs auto-accept).
- Assumes OAuth token has appropriate scopes for DM endpoints.
- Assumes disclaimer tokens are unique and stable.

## Primary Sources
- https://www.developer.saxo/openapi/learn/breaking-change-pre-trade-disclaimers-on-openapi
- https://www.developer.saxo/openapi/referencedocs/dm/v2/disclaimers/get__dm__disclaimers
- https://www.developer.saxo/openapi/referencedocs/dm/v2/disclaimers/post__dm__disclaimers
- https://www.developer.saxo/openapi/referencedocs/trade/v2/orders/post__trade__precheck
- https://www.developer.saxo/openapi/learn/error-handling
