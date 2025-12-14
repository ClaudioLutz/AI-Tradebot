from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
from decimal import Decimal

class AssetType(Enum):
    STOCK = "Stock"
    FX_SPOT = "FxSpot"
    FX_CRYPTO = "FxCrypto"  # Added for crypto migration

class BuySell(Enum):
    BUY = "Buy"
    SELL = "Sell"

class OrderType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"  # Future use
    STOP = "Stop"  # Future use

class OrderDurationType(Enum):
    DAY_ORDER = "DayOrder"
    GOOD_TILL_CANCEL = "GoodTillCancel"
    GOOD_TILL_DATE = "GoodTillDate"
    FILL_OR_KILL = "FillOrKill"
    IMMEDIATE_OR_CANCEL = "ImmediateOrCancel"

class MarketState(Enum):
    OPEN = "Open"
    CLOSED = "Closed"
    OPENING_AUCTION = "OpeningAuction"
    CLOSING_AUCTION = "ClosingAuction"
    INTRADAY_AUCTION = "IntraDayAuction"
    TRADING_AT_LAST = "TradingAtLast"
    PRE_TRADING = "PreTrading"
    POST_TRADING = "PostTrading"
    PRE_MARKET = "PreMarket"   # Added alias for story alignment
    POST_MARKET = "PostMarket" # Added alias for story alignment
    UNKNOWN = "Unknown"

@dataclass
class OrderDuration:
    duration_type: OrderDurationType
    expiration_datetime: Optional[str] = None  # ISO 8601 for GoodTillDate

@dataclass
class OrderIntent:
    """
    Represents a trade intention before validation/precheck.
    Maps directly to Saxo OpenAPI order request schema.
    """
    client_key: str   # Saxo ClientKey (required for Portfolio queries)
    account_key: str  # Saxo AccountKey (e.g., "Cf4xZWiYL6W1nMKpygBLLA==")
    asset_type: AssetType  # Stock, FxSpot, FxCrypto etc.
    uic: int  # Universal Instrument Code
    buy_sell: BuySell  # Buy or Sell
    amount: Decimal  # Quantity (Shares for Equity, Base Units for FX - NOT Lots)
    order_type: OrderType = OrderType.MARKET
    order_duration: OrderDuration = field(default_factory=lambda: OrderDuration(OrderDurationType.DAY_ORDER))
    manual_order: bool = False  # False = Automated/Algo, True = Human/GUI

    # Correlation fields
    external_reference: str = ""  # Max 50 chars, set by executor
    request_id: str = ""  # UUIDv4, set per attempt

    # Optional metadata
    symbol: Optional[str] = None  # For logging/debugging
    strategy_id: Optional[str] = None  # Source strategy

    def __post_init__(self):
        """Validate critical constraints"""
        if len(self.external_reference) > 50:
            raise ValueError(f"external_reference must be <= 50 chars, got {len(self.external_reference)}")
        if self.amount <= 0:
            raise ValueError(f"amount must be positive, got {self.amount}")

@dataclass
class PrecheckResult:
    """
    Normalized precheck outcome from POST /trade/v2/orders/precheck
    """
    success: bool

    # Error details (when success=False)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Cost/margin estimates (when success=True)
    estimated_cost: Optional[float] = None
    estimated_currency: Optional[str] = None
    margin_impact: Optional[float] = None

    # Pre-trade disclaimers (May 2025 requirement)
    disclaimer_tokens: List[str] = field(default_factory=list)
    disclaimer_context: Optional[str] = None
    has_blocking_disclaimers: bool = False

    # Raw response for debugging
    raw_response: Optional[dict] = None

class ExecutionStatus(Enum):
    SUCCESS = "success"  # Order placed successfully
    DRY_RUN = "dry_run"  # Precheck ok, no placement (DRY_RUN mode)
    FAILED_PRECHECK = "failed_precheck"  # Precheck failed
    FAILED_PLACEMENT = "failed_placement"  # Placement failed
    BLOCKED_BY_DISCLAIMER = "blocked_by_disclaimer"  # Disclaimers blocking
    BLOCKED_BY_POSITION = "blocked_by_position"  # Position guard blocked
    BLOCKED_BY_MARKET_STATE = "blocked_by_market_state"  # Auction/closed
    RECONCILIATION_NEEDED = "reconciliation_needed"  # Timeout/uncertain
    RATE_LIMITED = "rate_limited"  # 429 received

@dataclass
class ExecutionResult:
    """
    Final outcome of an execution attempt
    """
    status: ExecutionStatus
    order_intent: OrderIntent
    precheck_result: Optional[PrecheckResult] = None

    # Saxo order details (when placed)
    order_id: Optional[str] = None  # Saxo OrderId

    # Error details
    error_message: Optional[str] = None
    http_status: Optional[int] = None

    # Timing
    timestamp: str = ""  # ISO 8601

    # Reconciliation flag
    needs_reconciliation: bool = False
