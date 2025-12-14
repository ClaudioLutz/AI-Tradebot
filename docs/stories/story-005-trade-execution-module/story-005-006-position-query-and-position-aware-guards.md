# Story 005-006: Position query and position-aware execution guards

## Summary
Implement the minimal position model and guardrails required by Epic 005: prevent duplicate buys (or warn), and ensure sells only occur when a position exists. This story prioritizes **NetPositions** as the source of truth to avoid gross exposure fallacies.

## Background / Context
Epic 005 requires sell orders to be position-aware: only sell if there is an existing position.
Additionally, the module should prevent duplicate buys (or at least log a warning), to avoid repeatedly
increasing exposure on repeated buy signals.
Research confirms that **NetPositions** are the correct entity for exposure monitoring, as they automatically handle Saxo's Intraday vs End-of-Day netting logic.

## Scope
In scope:
- Implement position query via **NetPositions** endpoint (`/port/v1/netpositions`).
- Normalize positions into a simple in-memory view keyed by `(AssetType, Uic)`:
  - quantity (net)
  - side (long/short if applicable; default assume long-only strategy)
  - account_key association
- Implement guards:
  - Buy intent:
    - if NetPosition already exists (net amount > 0), skip placement (or configurable “warn only”).
  - Sell intent:
    - if no NetPosition exists, skip placement.
    - amount for sell is either:
      - configured fixed quantity, or
      - “close full position” (default safe option for strategies emitting exit signals).

## Acceptance Criteria
1. Executor queries `/port/v1/netpositions` using `ClientKey` context to get a consolidated view, or `AccountKey` if granular view is needed.
2. Query strictly includes `FieldGroups=NetPositionBase,NetPositionView` to ensure critical P&L and exposure fields are returned.
3. Buy guard:
   - If a net long position exists, executor does not place an additional buy by default, and logs `duplicate_buy_prevented`.
4. Sell guard:
   - If no NetPosition exists, executor does not precheck/place the sell and logs `no_position_to_sell`.
5. Position query failures are handled gracefully and do not crash the orchestration loop.
6. Works for `Stock`, `FxSpot`, and `FxCrypto` positions in SIM.

## Technical Architecture

### Position Data Model
```python
@dataclass
class Position:
    """Normalized position representation"""
    asset_type: str  # "Stock", "FxSpot", "FxCrypto"
    uic: int
    account_key: str
    position_id: str
    net_quantity: Decimal  # Positive for long, negative for short
    average_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    currency: str
    symbol: Optional[str] = None
    market_state: Optional[str] = None
    can_be_closed: bool = True
    
@dataclass
class PositionGuardResult:
    """Result of position-aware guard evaluation"""
    allowed: bool
    reason: str
    position_quantity: Optional[Decimal] = None
    recommended_action: Optional[str] = None
```

### API Endpoints

#### Net Positions (Primary Source)
```http
GET /port/v1/netpositions?ClientKey={ClientKey}&FieldGroups=NetPositionBase,NetPositionView
```

> **Critical**: Use `ClientKey` to aggregate exposure across all sub-accounts (Consolidated View) or `AccountKey` for specific ledger view. For the trade executor, `ClientKey` is generally safer to prevent trading against oneself in different sub-accounts.

**Response Structure:**
```json
{
  "Data": [
    {
      "NetPositionId": "212345678",
      "NetPositionBase": {
        "AccountId": "9073654",
        "Amount": 100.0,
        "AssetType": "Stock",
        "CanBeClosed": true,
        "Uic": 211,
        "Status": "Open"
      },
      "NetPositionView": {
        "AverageOpenPrice": 150.25,
        "CurrentPrice": 152.30,
        "MarketValue": 15230.00,
        "ProfitLossOnTrade": 205.00,
        "TradeCostsTotal": 5.00
      }
    }
  ]
}
```

### Position Query Implementation

```python
class PositionManager:
    """Manages position queries and caching"""
    
    def __init__(self, client: SaxoClient, client_key: str,
                 cache_ttl_seconds: int = 30):
        self.client = client
        self.client_key = client_key
        self.cache_ttl = cache_ttl_seconds
        self._position_cache: Dict[Tuple[str, int], Position] = {}
        self._cache_timestamp: Optional[datetime] = None
        
    async def get_positions(self, force_refresh: bool = False) -> Dict[Tuple[str, int], Position]:
        """
        Fetch and cache positions keyed by (AssetType, Uic)
        
        Args:
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            Dictionary of positions keyed by (asset_type, uic)
        """
        if not force_refresh and self._is_cache_valid():
            return self._position_cache
            
        try:
            # Query NetPositions with mandatory FieldGroups
            response = await self.client.get(
                "/port/v1/netpositions",
                params={
                    "ClientKey": self.client_key,
                    "FieldGroups": "NetPositionBase,NetPositionView"
                }
            )
            
            positions = {}
            for item in response.get("Data", []):
                pos_base = item.get("NetPositionBase", {})
                pos_view = item.get("NetPositionView", {})
                
                key = (pos_base["AssetType"], pos_base["Uic"])
                positions[key] = Position(
                    asset_type=pos_base["AssetType"],
                    uic=pos_base["Uic"],
                    account_key=pos_base.get("AccountKey"),
                    position_id=item["NetPositionId"],
                    net_quantity=Decimal(str(pos_base.get("Amount", 0))),
                    average_price=Decimal(str(pos_view.get("AverageOpenPrice", 0))),
                    market_value=Decimal(str(pos_view.get("MarketValue", 0))),
                    unrealized_pnl=Decimal(str(pos_view.get("ProfitLossOnTrade", 0))),
                    currency=pos_base.get("Currency", "USD"),
                    can_be_closed=pos_base.get("CanBeClosed", True)
                )
                
            self._position_cache = positions
            self._cache_timestamp = datetime.utcnow()
            
            logger.info(
                "positions_refreshed",
                count=len(positions),
                client_key=self.client_key
            )
            
            return positions
            
        except Exception as e:
            logger.error(
                "position_query_failed",
                error=str(e),
                client_key=self.client_key
            )
            # Return cached data if available, otherwise empty dict
            return self._position_cache if self._position_cache else {}
            
    def _is_cache_valid(self) -> bool:
        """Check if cached positions are still valid"""
        if not self._cache_timestamp:
            return False
        age = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return age < self.cache_ttl
```

### Position-Aware Guards

```python
class PositionAwareGuards:
    """Implements position-based execution guards"""
    
    def __init__(self, position_manager: PositionManager, 
                 config: ExecutionConfig):
        self.position_manager = position_manager
        self.config = config
        
    async def evaluate_buy_intent(
        self, 
        asset_type: str, 
        uic: int,
        intended_quantity: Decimal
    ) -> PositionGuardResult:
        """
        Evaluate if a buy order should be allowed
        
        Guard Logic:
        - If position exists with quantity > 0: BLOCK (prevent duplicate buy)
        - If position exists with quantity < 0: WARN (would reduce short, advanced use case)
        - If no position: ALLOW
        
        Args:
            asset_type: "Stock", "FxSpot", etc.
            uic: Universal instrument code
            intended_quantity: Proposed buy quantity
            
        Returns:
            PositionGuardResult with allow/block decision
        """
        positions = await self.position_manager.get_positions()
        key = (asset_type, uic)
        
        if key not in positions:
            return PositionGuardResult(
                allowed=True,
                reason="no_existing_position",
                position_quantity=Decimal(0)
            )
            
        position = positions[key]
        
        # Long position exists - prevent duplicate buy
        if position.net_quantity > 0:
            logger.warning(
                "duplicate_buy_prevented",
                asset_type=asset_type,
                uic=uic,
                existing_quantity=float(position.net_quantity),
                intended_quantity=float(intended_quantity),
                policy="strict"
            )
            
            return PositionGuardResult(
                allowed=False,
                reason="duplicate_buy_prevented",
                position_quantity=position.net_quantity,
                recommended_action="skip_or_increase_existing"
            )
            
        # Short position exists - could reduce short
        elif position.net_quantity < 0:
            if self.config.allow_short_covering:
                logger.info(
                    "buy_to_cover_short",
                    asset_type=asset_type,
                    uic=uic,
                    short_quantity=float(position.net_quantity)
                )
                return PositionGuardResult(
                    allowed=True,
                    reason="reducing_short_position",
                    position_quantity=position.net_quantity
                )
            else:
                logger.warning(
                    "short_covering_disabled",
                    asset_type=asset_type,
                    uic=uic
                )
                return PositionGuardResult(
                    allowed=False,
                    reason="short_covering_not_configured",
                    position_quantity=position.net_quantity
                )
                
        return PositionGuardResult(
            allowed=True,
            reason="zero_position",
            position_quantity=Decimal(0)
        )
        
    async def evaluate_sell_intent(
        self,
        asset_type: str,
        uic: int,
        intended_quantity: Optional[Decimal] = None
    ) -> PositionGuardResult:
        """
        Evaluate if a sell order should be allowed
        
        Guard Logic:
        - If no position: BLOCK (cannot sell what you don't own)
        - If position exists: ALLOW (compute close quantity if not specified)
        - If position too small: WARN but ALLOW
        
        Args:
            asset_type: "Stock", "FxSpot", etc.
            uic: Universal instrument code
            intended_quantity: Proposed sell quantity (None = close full position)
            
        Returns:
            PositionGuardResult with allow/block decision and recommended quantity
        """
        positions = await self.position_manager.get_positions()
        key = (asset_type, uic)
        
        if key not in positions:
            logger.warning(
                "no_position_to_sell",
                asset_type=asset_type,
                uic=uic,
                intended_quantity=float(intended_quantity) if intended_quantity else None
            )
            
            return PositionGuardResult(
                allowed=False,
                reason="no_position_to_sell",
                position_quantity=Decimal(0)
            )
            
        position = positions[key]
        
        # Position exists but is short
        if position.net_quantity < 0:
            logger.warning(
                "cannot_sell_short_position",
                asset_type=asset_type,
                uic=uic,
                position_quantity=float(position.net_quantity)
            )
            return PositionGuardResult(
                allowed=False,
                reason="position_is_short",
                position_quantity=position.net_quantity
            )
            
        # Position exists but is zero (should not happen)
        if position.net_quantity == 0:
            logger.warning(
                "zero_position_cannot_sell",
                asset_type=asset_type,
                uic=uic
            )
            return PositionGuardResult(
                allowed=False,
                reason="zero_position",
                position_quantity=Decimal(0)
            )
            
        # Check if position can be closed
        if not position.can_be_closed:
            logger.error(
                "position_locked",
                asset_type=asset_type,
                uic=uic,
                position_quantity=float(position.net_quantity)
            )
            return PositionGuardResult(
                allowed=False,
                reason="position_locked_by_broker",
                position_quantity=position.net_quantity
            )
            
        # Determine quantity to sell
        sell_quantity = intended_quantity if intended_quantity else position.net_quantity
        
        if sell_quantity > position.net_quantity:
            logger.warning(
                "sell_quantity_exceeds_position",
                asset_type=asset_type,
                uic=uic,
                position_quantity=float(position.net_quantity),
                requested_quantity=float(sell_quantity),
                adjusted_quantity=float(position.net_quantity)
            )
            sell_quantity = position.net_quantity
            
        logger.info(
            "sell_allowed",
            asset_type=asset_type,
            uic=uic,
            position_quantity=float(position.net_quantity),
            sell_quantity=float(sell_quantity)
        )
        
        return PositionGuardResult(
            allowed=True,
            reason="position_exists",
            position_quantity=sell_quantity,
            recommended_action=f"sell_{sell_quantity}"
        )
```

### Configuration

```python
@dataclass
class ExecutionConfig:
    """Configuration for position-aware guards"""
    
    # Position guard behavior
    duplicate_buy_policy: str = "block"  # "block", "warn", "allow"
    allow_short_covering: bool = False
    position_cache_ttl_seconds: int = 30
    
    # Position query retry settings
    position_query_retries: int = 2
    position_query_timeout_seconds: int = 10
```

### Error Handling

```python
class PositionQueryError(Exception):
    """Raised when position query fails critically"""
    pass

# Graceful degradation strategy
async def safe_position_check(
    guards: PositionAwareGuards,
    asset_type: str,
    uic: int,
    side: str
) -> PositionGuardResult:
    """
    Safely evaluate position guards with fallback behavior
    
    If position query fails:
    - BUY: Allow (fail-open for buy signals)
    - SELL: Block (fail-closed for sell signals to prevent short)
    """
    try:
        if side.upper() == "BUY":
            return await guards.evaluate_buy_intent(asset_type, uic, Decimal("100"))
        else:
            return await guards.evaluate_sell_intent(asset_type, uic)
            
    except Exception as e:
        logger.error(
            "position_guard_evaluation_failed",
            error=str(e),
            asset_type=asset_type,
            uic=uic,
            side=side
        )
        
        # Fail-safe defaults
        if side.upper() == "BUY":
            return PositionGuardResult(
                allowed=True,
                reason="position_query_failed_fail_open",
                position_quantity=None
            )
        else:
            return PositionGuardResult(
                allowed=False,
                reason="position_query_failed_fail_closed",
                position_quantity=None
            )
```

## Implementation Notes
- **NetPositions over Positions**: NetPositions provide the rolled-up view of exposure, which is what we care about for "Do I have a position?" logic. It correctly handles intraday and end-of-day netting modes.
- Keep the initial implementation long-only:
  - do not open short positions unless explicitly configured later.
- Use the market-state fields returned by positions (where available) only as a supplemental signal; the primary gating is handled in Story 005-008.
- **Cache Strategy**: Position cache with 30-second TTL reduces API load while maintaining reasonable freshness
- **Fail-Safe Behavior**: Buy orders fail-open (allow), sell orders fail-closed (block) on position query failures
- **Decimal Precision**: Use `Decimal` type for all quantity/price calculations to avoid floating-point errors
- **Correlation**: Log `external_reference` in all position-related events for traceability

## Test Plan
- Unit tests (mock positions response):
  - No NetPosition → sell skipped.
  - Existing NetPosition → buy skipped.
  - Existing NetPosition → sell amount computed correctly (full close or configured).
- Integration (SIM):
  - Create a small position via buy order, then verify subsequent buy signals are skipped.
  - Trigger sell, verify sell is placed and position reduces/closes.

## Dependencies / Assumptions
- Requires access to Portfolio NetPositions endpoints.
- Assumes consistent instrument id mapping between market data signals and portfolio responses.

## Primary Sources
- https://www.developer.saxo/openapi/referencedocs/port/v1/netpositions/get__port__netpositions
- https://www.developer.saxo/openapi/learn/reference-data
