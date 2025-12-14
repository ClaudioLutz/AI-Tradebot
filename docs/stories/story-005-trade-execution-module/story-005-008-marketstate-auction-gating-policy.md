# Story 005-008: MarketState / auction-state gating policy for execution

## Summary
Define a default execution policy for Saxo MarketState and auction-related states, and integrate it as a hard gate before precheck/placement.

## Background / Context
Saxo exposes market state values such as Open, OpeningAuction, ClosingAuction, IntraDayAuction, and TradingAtLast.
These states can materially impact order behavior, liquidity, and execution quality. Epic 004 already identified
auction states as a cross-cutting policy decision; Epic 005 must formalize the default so acceptance criteria remain consistent.

## Scope
In scope:
- Define and implement an execution gate `is_trading_allowed(market_state)` with safe defaults.
- Default policy (recommended):
  - Allow: Open
  - Block: Closed, Unknown, OpeningAuction, ClosingAuction, IntraDayAuction, TradingAtLast
  - Configurable overrides for advanced users (e.g., allow PreMarket/PostMarket for specific instruments)
- Determine market state using the best available source (in priority order):
  1) Latest Quote/Price snapshot MarketState (if available from market data module)
  2) Portfolio position/open-order market-state fields (if present)
  3) Instrument session state (if available in instrument details / market data)
- Integrate gate before precheck (so you don't precheck trades you will not place).

## Acceptance Criteria
1. Default behavior blocks execution during auction and TradingAtLast states.
2. Gate is evaluated before precheck/placement and returns a structured "blocked_by_market_state" result.
3. Gate is configurable (e.g., allow PreMarket/PostMarket) without code change.
4. All blocked events are logged with `{asset_type, uic, market_state, policy_version, external_reference}`.
5. If market state is missing/unknown, behavior is conservative (block) unless explicitly configured otherwise.

## Technical Architecture

### Market State Enumeration

```python
from enum import Enum
from typing import Optional, Set

class MarketState(Enum):
    """
    Saxo MarketState values
    
    Source: https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/schema-marketstate
    """
    UNKNOWN = "Unknown"
    OPEN = "Open"
    CLOSED = "Closed"
    OPENING_AUCTION = "OpeningAuction"
    CLOSING_AUCTION = "ClosingAuction"
    INTRA_DAY_AUCTION = "IntraDayAuction"
    TRADING_AT_LAST = "TradingAtLast"
    PRE_MARKET = "PreMarket"
    POST_MARKET = "PostMarket"
    
class InstrumentSessionState(Enum):
    """
    Instrument session state from ref/v1/instruments
    
    Source: https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments/schema-instrumentsessionstate
    """
    CONTINUOUS = "Continuous"
    AUCTION = "Auction"
    CLOSED = "Closed"
    PRE_OPEN = "PreOpen"
    POST_CLOSE = "PostClose"
```

### Market State Gate Policy

```python
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class MarketStatePolicy:
    """
    Configuration for market state gating policy
    
    Defines which market states allow trade execution
    """
    # Policy version for auditing
    version: str = "1.0"
    
    # Default allowed states (conservative)
    allowed_states: Set[str] = field(default_factory=lambda: {"Open"})
    
    # Explicitly blocked states
    blocked_states: Set[str] = field(default_factory=lambda: {
        "Closed",
        "Unknown",
        "OpeningAuction",
        "ClosingAuction",
        "IntraDayAuction",
        "TradingAtLast"
    })
    
    # Behavior when market state is missing/unknown
    allow_on_missing: bool = False  # Conservative: block if unknown
    
    # Per-asset-type overrides (advanced)
    asset_type_overrides: Dict[str, Set[str]] = field(default_factory=dict)
    
    # Log verbosity
    log_allowed_trades: bool = False  # Only log blocks by default
    
    @classmethod
    def get_default(cls) -> "MarketStatePolicy":
        """Get conservative default policy"""
        return cls()
    
    @classmethod
    def get_extended(cls) -> "MarketStatePolicy":
        """Get policy allowing pre/post market (for advanced users)"""
        return cls(
            allowed_states={"Open", "PreMarket", "PostMarket"},
            blocked_states={
                "Closed",
                "Unknown",
                "OpeningAuction",
                "ClosingAuction",
                "IntraDayAuction",
                "TradingAtLast"
            }
        )

@dataclass
class MarketStateGateResult:
    """Result of market state gate evaluation"""
    allowed: bool
    market_state: Optional[str]
    reason: str
    policy_version: str
    source: str  # "quote", "position", "instrument", "missing"
```

### Market State Provider

```python
from typing import Optional, Protocol

class MarketStateProvider(Protocol):
    """Interface for retrieving market state"""
    
    async def get_market_state(
        self,
        asset_type: str,
        uic: int
    ) -> Optional[str]:
        """Get current market state for instrument"""
        ...

class CompositeMarketStateProvider:
    """
    Retrieves market state from multiple sources with fallback priority
    
    Priority:
    1. Latest quote/price (most recent)
    2. Position market state (if position exists)
    3. Instrument details (static/cached)
    """
    
    def __init__(
        self,
        market_data_client,
        position_manager=None,
        instrument_cache=None
    ):
        self.market_data_client = market_data_client
        self.position_manager = position_manager
        self.instrument_cache = instrument_cache
        
    async def get_market_state(
        self,
        asset_type: str,
        uic: int
    ) -> tuple[Optional[str], str]:
        """
        Get market state with source tracking
        
        Returns:
            (market_state, source) tuple
        """
        # Try 1: Latest quote
        try:
            quote = await self.market_data_client.get_quote(
                asset_type=asset_type,
                uic=uic
            )
            if quote and quote.get("MarketState"):
                logger.debug(
                    "market_state_from_quote",
                    asset_type=asset_type,
                    uic=uic,
                    state=quote["MarketState"]
                )
                return quote["MarketState"], "quote"
        except Exception as e:
            logger.warning(
                "market_state_quote_failed",
                asset_type=asset_type,
                uic=uic,
                error=str(e)
            )
        
        # Try 2: Position (if available)
        if self.position_manager:
            try:
                positions = await self.position_manager.get_positions()
                key = (asset_type, uic)
                if key in positions and positions[key].market_state:
                    logger.debug(
                        "market_state_from_position",
                        asset_type=asset_type,
                        uic=uic,
                        state=positions[key].market_state
                    )
                    return positions[key].market_state, "position"
            except Exception as e:
                logger.warning(
                    "market_state_position_failed",
                    asset_type=asset_type,
                    uic=uic,
                    error=str(e)
                )
        
        # Try 3: Instrument details (cached)
        if self.instrument_cache:
            try:
                instrument = await self.instrument_cache.get_instrument(
                    asset_type=asset_type,
                    uic=uic
                )
                if instrument and instrument.get("TradingStatus"):
                    logger.debug(
                        "market_state_from_instrument",
                        asset_type=asset_type,
                        uic=uic,
                        status=instrument["TradingStatus"]
                    )
                    return instrument["TradingStatus"], "instrument"
            except Exception as e:
                logger.warning(
                    "market_state_instrument_failed",
                    asset_type=asset_type,
                    uic=uic,
                    error=str(e)
                )
        
        # No market state available
        logger.warning(
            "market_state_unavailable",
            asset_type=asset_type,
            uic=uic
        )
        return None, "missing"
```

### Market State Gate Implementation

```python
class MarketStateGate:
    """
    Evaluates whether trading is allowed based on market state
    
    This gate is evaluated BEFORE precheck to avoid unnecessary API calls
    """
    
    def __init__(
        self,
        policy: MarketStatePolicy,
        state_provider: CompositeMarketStateProvider
    ):
        self.policy = policy
        self.state_provider = state_provider
        
    async def evaluate(
        self,
        asset_type: str,
        uic: int,
        external_reference: str
    ) -> MarketStateGateResult:
        """
        Evaluate if trading is allowed for this instrument
        
        Args:
            asset_type: "Stock", "FxSpot", etc.
            uic: Universal instrument code
            external_reference: Correlation ID
            
        Returns:
            MarketStateGateResult with allow/block decision
        """
        # Get current market state
        market_state, source = await self.state_provider.get_market_state(
            asset_type, uic
        )
        
        # Handle missing market state
        if market_state is None:
            if self.policy.allow_on_missing:
                logger.warning(
                    "market_state_missing_allowing",
                    asset_type=asset_type,
                    uic=uic,
                    external_reference=external_reference,
                    policy="allow_on_missing=True"
                )
                return MarketStateGateResult(
                    allowed=True,
                    market_state=None,
                    reason="missing_state_policy_allows",
                    policy_version=self.policy.version,
                    source=source
                )
            else:
                logger.error(
                    "market_state_missing_blocking",
                    asset_type=asset_type,
                    uic=uic,
                    external_reference=external_reference,
                    policy="allow_on_missing=False"
                )
                return MarketStateGateResult(
                    allowed=False,
                    market_state=None,
                    reason="missing_state_conservative_block",
                    policy_version=self.policy.version,
                    source=source
                )
        
        # Check asset-type-specific overrides
        override_states = self.policy.asset_type_overrides.get(asset_type)
        if override_states:
            allowed = market_state in override_states
            reason = "asset_type_override"
        else:
            # Use default policy
            allowed = market_state in self.policy.allowed_states
            reason = "default_policy"
        
        # Log decision
        if allowed:
            if self.policy.log_allowed_trades:
                logger.info(
                    "market_state_allowing",
                    asset_type=asset_type,
                    uic=uic,
                    market_state=market_state,
                    source=source,
                    reason=reason,
                    policy_version=self.policy.version,
                    external_reference=external_reference
                )
        else:
            # Always log blocks
            logger.warning(
                "market_state_blocking",
                asset_type=asset_type,
                uic=uic,
                market_state=market_state,
                source=source,
                reason=reason,
                policy_version=self.policy.version,
                external_reference=external_reference,
                detail=self._get_block_detail(market_state)
            )
        
        return MarketStateGateResult(
            allowed=allowed,
            market_state=market_state,
            reason=f"{reason}_{market_state}",
            policy_version=self.policy.version,
            source=source
        )
    
    def _get_block_detail(self, market_state: str) -> str:
        """Get human-readable explanation for block"""
        explanations = {
            "Closed": "Market is closed",
            "OpeningAuction": "Market in opening auction (illiquid, volatile pricing)",
            "ClosingAuction": "Market in closing auction (illiquid, volatile pricing)",
            "IntraDayAuction": "Market in intraday auction (volatility halt or news)",
            "TradingAtLast": "Trading at last (low liquidity, stale prices)",
            "Unknown": "Market state unknown (conservative block)"
        }
        return explanations.get(market_state, f"State {market_state} not in allowed list")
```

### Integration with Executor

```python
class TradeExecutor:
    """Example integration of market state gate"""
    
    def __init__(
        self,
        saxo_client,
        market_state_gate: MarketStateGate,
        position_guards,
        rate_limiter
    ):
        self.client = saxo_client
        self.market_state_gate = market_state_gate
        self.position_guards = position_guards
        self.rate_limiter = rate_limiter
        
    async def execute_order_intent(
        self,
        intent: OrderIntent
    ) -> ExecutionResult:
        """
        Execute order with all gates
        
        Gate order:
        1. Market state gate (fast, no API call if cached)
        2. Position-aware guards (cached position data)
        3. Rate limiting
        4. Precheck (API call)
        5. Placement (API call)
        """
        ext_ref = intent.external_reference
        
        # GATE 1: Market State
        market_gate_result = await self.market_state_gate.evaluate(
            asset_type=intent.asset_type,
            uic=intent.uic,
            external_reference=ext_ref
        )
        
        if not market_gate_result.allowed:
            return ExecutionResult(
                success=False,
                status="blocked_market_state",
                market_state=market_gate_result.market_state,
                reason=market_gate_result.reason,
                external_reference=ext_ref
            )
        
        # GATE 2: Position Guards
        if intent.side == "Buy":
            guard_result = await self.position_guards.evaluate_buy_intent(
                intent.asset_type, intent.uic, intent.quantity
            )
        else:
            guard_result = await self.position_guards.evaluate_sell_intent(
                intent.asset_type, intent.uic, intent.quantity
            )
        
        if not guard_result.allowed:
            return ExecutionResult(
                success=False,
                status=f"blocked_position_guard",
                reason=guard_result.reason,
                external_reference=ext_ref
            )
        
        # Continue with rate limiting, precheck, placement...
        # (See other stories for these steps)
        
        return await self._continue_execution(intent)
```

### Configuration Example

```yaml
# config/execution_policy.yaml

market_state_policy:
  version: "1.0"
  
  # Conservative default
  default:
    allowed_states:
      - Open
    blocked_states:
      - Closed
      - Unknown
      - OpeningAuction
      - ClosingAuction
      - IntraDayAuction
      - TradingAtLast
    allow_on_missing: false
    log_allowed_trades: false
  
  # Asset-specific overrides (optional)
  asset_type_overrides:
    # Allow FX trading in extended hours (24h market)
    FxSpot:
      - Open
      - PreMarket
      - PostMarket
```

## Implementation Notes
- Keep gating independent from strategy logic: strategies emit signals; executor decides whether trading is allowed *now*.
- Centralize the policy in one module so future epics (risk, live) can reuse it.
- Add "why" metadata in logs so a human can distinguish:
  - "AuctionStateBlocked" vs "Closed" vs "Unknown"
- **Performance**: Market state gate should be very fast (use cached data)
- **Fallback Chain**: Try multiple sources (quote → position → instrument) for robustness
- **Conservative Default**: Block on unknown/missing state to prevent execution in uncertain conditions
- **Audit Trail**: Log all blocked executions with full context for post-trade analysis
- **FX Consideration**: 24-hour FX markets may not have traditional "Closed" state

## Test Plan
- Unit tests:
  - Each MarketState value maps to allow/block correctly under default config.
  - Config override allows selected states.
  - Missing state defaults to block.
- Integration (SIM):
  - If market data provides MarketState, verify gate respects it (log-only check is sufficient if auction states are hard to reproduce).

## Dependencies / Assumptions
- Depends on a market-state signal from market data (Epic 003/004) OR a portfolio-derived fallback.
- This policy should remain stable across Epic 004 and Epic 005; document it clearly for developers.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/trade/v1/prices/post__trade__multileg/schema-marketstate
- https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments/get__ref__details/schema-instrumentsessionstate
- https://www.developer.saxo/openapi/referencedocs/trade/v1/infoprices/get__trade/schema-quote
