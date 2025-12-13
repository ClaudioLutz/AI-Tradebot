"""
Moving Average Crossover Strategy

This is the reference implementation demonstrating best practices for all strategies.

Strategy Logic:
- Calculate short-term MA (e.g., 5 periods) and long-term MA (e.g., 20 periods)
- BUY signal: Short MA crosses ABOVE long MA (golden cross)
- SELL signal: Short MA crosses BELOW long MA (death cross)
- HOLD: No crossover detected or insufficient data

Academic Reference:
- Brock, Lakonishok, LeBaron (1992) - "Simple Technical Trading Rules and
  the Stochastic Properties of Stock Returns"
- Crossovers are treated as regime changes, not instantaneous MA comparisons

Key Features:
- Proper crossover detection (previous vs current comparison)
- Optional threshold filter to reduce noise
- Optional cooldown period to prevent excessive trading
- Safe-by-default data handling
- Complete audit trail via Signal metadata
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from strategies.base import BaseStrategy, Signal, get_current_timestamp
from strategies.indicators import (
    simple_moving_average,
    safe_slice_bars,
    detect_crossover,
)

logger = logging.getLogger(__name__)


class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover strategy with proper crossover detection.
    
    Generates BUY/SELL signals when short MA crosses long MA, using
    previous vs current comparison to detect regime changes.
    
    Attributes:
        short_window: Number of periods for short MA (must be < long_window)
        long_window: Number of periods for long MA
        threshold_bps: Optional noise filter in basis points (e.g., 50 = 0.5%)
        cooldown_bars: Optional minimum bars between trades to prevent churn
    
    Example:
        >>> strategy = MovingAverageCrossoverStrategy(short_window=5, long_window=20)
        >>> signals = strategy.generate_signals(market_data, decision_time_utc)
    """
    
    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        threshold_bps: Optional[int] = None,
        cooldown_bars: Optional[int] = None,
    ):
        """
        Initialize Moving Average Crossover strategy.
        
        Args:
            short_window: Short MA period (default 5)
            long_window: Long MA period (default 20)
            threshold_bps: Minimum MA separation in bps to trigger signal (optional)
            cooldown_bars: Minimum bars between trades to prevent churn (optional)
        
        Raises:
            ValueError: If short_window >= long_window or windows invalid
        """
        if short_window <= 0 or long_window <= 0:
            raise ValueError("Window sizes must be positive integers")
        
        if short_window >= long_window:
            raise ValueError(
                f"short_window ({short_window}) must be < long_window ({long_window})"
            )
        
        if threshold_bps is not None and threshold_bps < 0:
            raise ValueError(f"threshold_bps must be non-negative, got {threshold_bps}")
        
        if cooldown_bars is not None and cooldown_bars < 0:
            raise ValueError(f"cooldown_bars must be non-negative, got {cooldown_bars}")
        
        self.short_window = short_window
        self.long_window = long_window
        self.threshold_bps = threshold_bps
        self.cooldown_bars = cooldown_bars
        
        # Track last signal bar index per instrument for cooldown
        self._last_signal_bar_index: Dict[str, int] = {}
        
        logger.info(
            f"Initialized MovingAverageCrossoverStrategy: "
            f"short={short_window}, long={long_window}, "
            f"threshold={threshold_bps}bps, cooldown={cooldown_bars}bars"
        )
    
    def generate_signals(
        self,
        market_data: Dict[str, Dict],
        decision_time_utc: datetime,
    ) -> Dict[str, Signal]:
        """
        Generate trading signals for all instruments using MA crossover logic.

        Args:
            market_data: Dict keyed by instrument_id with market data
            decision_time_utc: Strategy decision timestamp in UTC. Strategy must only
                use bars strictly < decision_time_utc.

        Returns:
            Dict keyed by instrument_id with Signal objects
        """
        signals = {}
        wall_clock_timestamp = get_current_timestamp()
        
        for instrument_id, data in market_data.items():
            symbol = data.get("symbol", "UNKNOWN")
            bars = data.get("bars", [])
            
            # Validate sufficient bars (need long_window + 1 for current + previous)
            required_bars = self.long_window + 1
            if not bars or len(bars) < required_bars:
                logger.debug(
                    f"{instrument_id} ({symbol}): Insufficient bars "
                    f"({len(bars) if bars else 0}/{required_bars})"
                )
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="SIG_INSUFFICIENT_BARS",
                    timestamp=wall_clock_timestamp,
                    decision_time=wall_clock_timestamp,
                    strategy_version="moving_average_v1.0",
                    metadata={"required": required_bars, "available": len(bars) if bars else 0}
                )
                continue
            
            # Use safe_slice_bars to enforce closed-bar discipline
            # IMPORTANT: Use decision_time_utc (passed to strategy) not last bar time
            # This prevents illiquid instruments from using partial/future bars
            valid_bars = safe_slice_bars(
                bars, 
                required_bars, 
                as_of=decision_time_utc, 
                require_closed=True
            )
            
            if valid_bars is None:
                logger.warning(
                    f"{instrument_id} ({symbol}): Insufficient CLOSED bars as of decision time. "
                    f"Illiquid instruments may return fewer samples than expected. "
                    f"Ref: https://openapi.help.saxo/hc/en-us/articles/6105016299677"
                )
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="SIG_INSUFFICIENT_CLOSED_BARS",
                    timestamp=wall_clock_timestamp,
                    decision_time=decision_time_utc.isoformat().replace('+00:00', 'Z'),
                    strategy_version="moving_average_v1.0",
                    metadata={
                        "required": required_bars, 
                        "available": len(bars) if bars else 0,
                        "closed_bars": 0
                    }
                )
                continue
            
            # Extract decision time (last bar close) and data time range
            decision_time = valid_bars[-1]["timestamp"]
            data_time_range = {
                "first_bar": valid_bars[0]["timestamp"],
                "last_bar": valid_bars[-1]["timestamp"]
            }
            last_close_price = valid_bars[-1]["close"]
            
            # Extract closing prices
            closes = [bar["close"] for bar in valid_bars]
            
            # Calculate current MAs (using all available bars)
            current_short_ma = simple_moving_average(closes, self.short_window)
            current_long_ma = simple_moving_average(closes, self.long_window)
            
            # Calculate previous MAs (excluding most recent bar)
            prev_closes = closes[:-1]
            prev_short_ma = simple_moving_average(prev_closes, self.short_window)
            prev_long_ma = simple_moving_average(prev_closes, self.long_window)
            
            # Handle None returns (shouldn't happen given our validation, but be safe)
            if None in [current_short_ma, current_long_ma, prev_short_ma, prev_long_ma]:
                logger.warning(
                    f"{instrument_id} ({symbol}): MA calculation returned None"
                )
                signals[instrument_id] = Signal(
                    action="HOLD",
                    reason="SIG_INSUFFICIENT_DATA",
                    timestamp=wall_clock_timestamp,
                    decision_time=decision_time,
                    strategy_version="moving_average_v1.0",
                )
                continue
            
            # Type assertions for type checker (we've validated None above)
            assert current_short_ma is not None
            assert current_long_ma is not None
            assert prev_short_ma is not None
            assert prev_long_ma is not None
            
            # Guard against division by zero in threshold calculation
            if self.threshold_bps is not None and current_long_ma == 0:
                logger.warning(
                    f"{instrument_id} ({symbol}): current_long_ma is zero, cannot apply threshold"
                )
                # Treat as no crossover to avoid invalid calculation
                crossover_type = "NO_CROSSOVER"
            else:
                # Detect crossover (previous vs current comparison)
                crossover_type = detect_crossover(
                    current_short_ma, current_long_ma,
                    prev_short_ma, prev_long_ma
                )
                
                # Apply optional threshold filter
                if self.threshold_bps is not None and crossover_type != "NO_CROSSOVER":
                    separation_pct = abs(current_short_ma - current_long_ma) / current_long_ma
                    threshold_decimal = self.threshold_bps / 10000.0
                    
                    if separation_pct < threshold_decimal:
                        logger.debug(
                            f"{instrument_id} ({symbol}): Crossover detected but below "
                            f"threshold ({separation_pct:.4%} < {threshold_decimal:.4%})"
                        )
                        crossover_type = "NO_CROSSOVER"
            
            # Apply optional cooldown filter
            if self.cooldown_bars is not None and crossover_type != "NO_CROSSOVER":
                current_bar_index = len(bars) - 1
                last_signal_index = self._last_signal_bar_index.get(instrument_id, -999999)
                bars_since_signal = current_bar_index - last_signal_index
                
                if bars_since_signal < self.cooldown_bars:
                    logger.debug(
                        f"{instrument_id} ({symbol}): Crossover detected but in cooldown "
                        f"({bars_since_signal}/{self.cooldown_bars} bars since last signal)"
                    )
                    crossover_type = "COOLDOWN_ACTIVE"
                else:
                    # Update last signal index
                    self._last_signal_bar_index[instrument_id] = current_bar_index
            
            # Generate signal based on crossover
            if crossover_type == "CROSSOVER_UP":
                action = "BUY"
                reason = "SIG_CROSSOVER_UP"
                logger.info(
                    f"{instrument_id} ({symbol}): Golden cross detected - BUY "
                    f"(short_MA={current_short_ma:.2f}, long_MA={current_long_ma:.2f})"
                )
            elif crossover_type == "CROSSOVER_DOWN":
                action = "SELL"
                reason = "SIG_CROSSOVER_DOWN"
                logger.info(
                    f"{instrument_id} ({symbol}): Death cross detected - SELL "
                    f"(short_MA={current_short_ma:.2f}, long_MA={current_long_ma:.2f})"
                )
            elif crossover_type == "COOLDOWN_ACTIVE":
                action = "HOLD"
                reason = "SIG_COOLDOWN_ACTIVE"
                logger.debug(
                    f"{instrument_id} ({symbol}): Signal suppressed (cooldown active)"
                )
            else:
                action = "HOLD"
                reason = "SIG_NO_CROSSOVER"
                logger.debug(
                    f"{instrument_id} ({symbol}): No crossover "
                    f"(short_MA={current_short_ma:.2f}, long_MA={current_long_ma:.2f})"
                )
            
            # Create signal with enhanced schema
            signals[instrument_id] = Signal(
                action=action,
                reason=reason,
                timestamp=wall_clock_timestamp,
                decision_time=decision_time,
                strategy_version="moving_average_v1.0",
                price_ref=last_close_price,
                price_type="close",
                data_time_range=data_time_range,
                metadata={
                    "short_ma": round(current_short_ma, 2),
                    "long_ma": round(current_long_ma, 2),
                    "prev_short_ma": round(prev_short_ma, 2),
                    "prev_long_ma": round(prev_long_ma, 2),
                    "bars_used": len(valid_bars),
                    "short_window": self.short_window,
                    "long_window": self.long_window,
                }
            )
        
        return signals
