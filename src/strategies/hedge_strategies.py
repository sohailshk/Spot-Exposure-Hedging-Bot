"""
Hedging strategies for risk management.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

try:
    from ..risk.models import Position, Portfolio, PositionType, HedgeRecommendation, MarketData
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from risk.models import Position, Portfolio, PositionType, HedgeRecommendation, MarketData


class HedgeStrategy(Enum):
    """Hedging strategy types."""
    DELTA_NEUTRAL = "delta_neutral"
    PROTECTIVE_PUT = "protective_put"
    COVERED_CALL = "covered_call"
    COLLAR = "collar"
    PAIRS_TRADING = "pairs_trading"
    FUTURES_HEDGE = "futures_hedge"


class HedgeUrgency(Enum):
    """Hedge urgency levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class HedgeConfig:
    """Configuration for hedging strategies."""
    strategy: HedgeStrategy
    enabled: bool = True
    
    # Delta hedging parameters
    delta_threshold: float = 0.1
    rebalance_threshold: float = 0.05
    hedge_ratio: float = 1.0
    
    # Options strategy parameters
    protective_put_delta: float = -0.2  # OTM puts
    covered_call_delta: float = 0.3     # OTM calls
    collar_put_delta: float = -0.2
    collar_call_delta: float = 0.3
    
    # Cost thresholds
    max_hedge_cost: float = 0.02  # 2% of position value
    min_cost_improvement: float = 0.001  # 0.1% minimum improvement
    
    # Time parameters
    min_time_to_expiry: int = 7   # Minimum days to expiry
    max_time_to_expiry: int = 60  # Maximum days to expiry
    
    # Risk parameters
    max_slippage: float = 0.001   # 0.1% max slippage
    confidence_level: float = 0.95  # For risk calculations


@dataclass
class ExecutionCost:
    """Execution cost analysis."""
    strategy: HedgeStrategy
    estimated_cost: float
    bid_ask_spread_cost: float
    slippage_cost: float
    commission_cost: float
    market_impact_cost: float
    total_cost: float
    cost_percentage: float
    
    def __post_init__(self):
        """Calculate total cost."""
        self.total_cost = (
            self.estimated_cost + 
            self.bid_ask_spread_cost + 
            self.slippage_cost + 
            self.commission_cost + 
            self.market_impact_cost
        )


class BaseHedgeStrategy(ABC):
    """Abstract base class for hedging strategies."""
    
    def __init__(self, config: HedgeConfig):
        self.config = config
        self.name = config.strategy.value
    
    @abstractmethod
    def analyze_position(self, position: Position, market_data: MarketData) -> Optional[HedgeRecommendation]:
        """Analyze a position and generate hedge recommendation."""
        pass
    
    @abstractmethod
    def analyze_portfolio(self, portfolio: Portfolio, market_data: Dict[str, MarketData]) -> List[HedgeRecommendation]:
        """Analyze portfolio and generate hedge recommendations."""
        pass
    
    @abstractmethod
    def calculate_hedge_size(self, position: Position, target_delta: float = 0.0) -> float:
        """Calculate optimal hedge size."""
        pass
    
    def estimate_execution_cost(self, recommendation: HedgeRecommendation, 
                              market_data: MarketData) -> ExecutionCost:
        """Estimate execution costs for a hedge recommendation."""
        
        # Base cost estimates
        notional_value = abs(recommendation.size * (recommendation.price or market_data.price))
        
        # Bid-ask spread cost
        spread_cost = 0.0
        if market_data.bid and market_data.ask:
            spread = market_data.ask - market_data.bid
            spread_cost = spread * abs(recommendation.size) / 2
        
        # Slippage cost (estimated)
        slippage_cost = notional_value * self.config.max_slippage
        
        # Commission cost (estimated)
        commission_cost = max(notional_value * 0.0001, 1.0)  # Min $1 commission
        
        # Market impact (for large orders)
        market_impact_cost = 0.0
        if notional_value > 100000:  # Large order threshold
            market_impact_cost = notional_value * 0.0005
        
        # Estimated hedge cost (from recommendation)
        estimated_cost = recommendation.estimated_cost or 0.0
        
        cost_percentage = (estimated_cost + spread_cost + slippage_cost + 
                          commission_cost + market_impact_cost) / notional_value
        
        return ExecutionCost(
            strategy=self.config.strategy,
            estimated_cost=estimated_cost,
            bid_ask_spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            commission_cost=commission_cost,
            market_impact_cost=market_impact_cost,
            total_cost=0.0,  # Will be calculated in __post_init__
            cost_percentage=cost_percentage
        )
    
    def _determine_urgency(self, risk_breach_severity: float) -> HedgeUrgency:
        """Determine hedge urgency based on risk breach severity."""
        if risk_breach_severity > 3.0:
            return HedgeUrgency.CRITICAL
        elif risk_breach_severity > 2.0:
            return HedgeUrgency.HIGH
        elif risk_breach_severity > 1.5:
            return HedgeUrgency.MEDIUM
        else:
            return HedgeUrgency.LOW
    
    def _calculate_risk_reduction(self, current_risk: Dict[str, float], 
                                 hedge_delta: float, hedge_gamma: float) -> Dict[str, float]:
        """Calculate expected risk reduction from hedge."""
        return {
            'delta_reduction': abs(hedge_delta),
            'gamma_reduction': abs(hedge_gamma),
            'var_reduction': min(abs(hedge_delta) * 0.1, 0.5)  # Estimated VaR reduction
        }


class DeltaNeutralStrategy(BaseHedgeStrategy):
    """Delta-neutral hedging using futures or ETFs."""
    
    def analyze_position(self, position: Position, market_data: MarketData) -> Optional[HedgeRecommendation]:
        """Analyze individual position for delta hedging."""
        if not self.config.enabled:
            return None
        
        # Check if position needs hedging
        current_delta = position.delta or 0.0
        abs_delta = abs(current_delta)
        
        if abs_delta < self.config.delta_threshold:
            return None  # No hedging needed
        
        # Calculate hedge size to neutralize delta
        hedge_size = self._calculate_hedge_size_for_delta(position, target_delta=0.0)
        
        if abs(hedge_size) < 1:  # Minimum hedge size
            return None
        
        # Determine hedge instrument (futures, perpetuals, or ETF)
        hedge_instrument = self._select_hedge_instrument(position.symbol)
        
        # Calculate hedge cost
        hedge_cost = abs(hedge_size) * market_data.price * 0.001  # Estimated 0.1% cost
        
        # Determine urgency
        risk_severity = abs_delta / self.config.delta_threshold
        urgency = self._determine_urgency(risk_severity)
        
        # Calculate risk reduction
        risk_reduction = self._calculate_risk_reduction(
            {'delta': current_delta},
            -current_delta,  # Hedge delta opposite to position
            0.0
        )
        
        return HedgeRecommendation(
            symbol=hedge_instrument,
            action="SELL" if hedge_size > 0 else "BUY",
            size=abs(hedge_size),
            instrument_type=PositionType.FUTURES,
            price=market_data.price,
            reasoning=f"Delta hedge: neutralizing {current_delta:.3f} delta exposure",
            urgency=urgency.value,
            estimated_cost=hedge_cost,
            risk_reduction=risk_reduction
        )
    
    def analyze_portfolio(self, portfolio: Portfolio, market_data: Dict[str, MarketData]) -> List[HedgeRecommendation]:
        """Analyze portfolio for delta hedging opportunities."""
        recommendations = []
        
        total_delta = portfolio.total_delta
        abs_total_delta = abs(total_delta)
        
        if abs_total_delta < self.config.delta_threshold:
            return recommendations
        
        # Group positions by underlying asset
        asset_deltas = {}
        for position in portfolio.positions:
            base_symbol = self._extract_base_symbol(position.symbol)
            if base_symbol not in asset_deltas:
                asset_deltas[base_symbol] = 0.0
            asset_deltas[base_symbol] += position.delta or 0.0
        
        # Generate hedge recommendations for each asset
        for symbol, net_delta in asset_deltas.items():
            if abs(net_delta) > self.config.delta_threshold:
                if symbol in market_data:
                    # Create a synthetic position for hedging calculation
                    synthetic_position = Position(
                        symbol=symbol,
                        position_type=PositionType.SPOT,
                        size=net_delta,  # Use delta as size
                        entry_price=market_data[symbol].price,
                        current_price=market_data[symbol].price
                    )
                    synthetic_position.delta = net_delta
                    
                    hedge_rec = self.analyze_position(synthetic_position, market_data[symbol])
                    if hedge_rec:
                        recommendations.append(hedge_rec)
        
        return recommendations
    
    def calculate_hedge_size(self, position: Position, target_delta: float = 0.0) -> float:
        """Calculate hedge size to achieve target delta."""
        return self._calculate_hedge_size_for_delta(position, target_delta)
    
    def _calculate_hedge_size_for_delta(self, position: Position, target_delta: float) -> float:
        """Calculate hedge size to achieve target delta."""
        current_delta = position.delta or 0.0
        delta_to_hedge = current_delta - target_delta
        
        # For futures/perpetuals, hedge ratio is typically 1:1
        hedge_size = -delta_to_hedge * self.config.hedge_ratio
        
        return hedge_size
    
    def _select_hedge_instrument(self, symbol: str) -> str:
        """Select appropriate hedge instrument for a symbol."""
        # Map symbols to their hedge instruments
        hedge_mapping = {
            'AAPL': 'QQQ',      # Tech ETF for AAPL
            'GOOGL': 'QQQ',     # Tech ETF for GOOGL
            'MSFT': 'QQQ',      # Tech ETF for MSFT
            'TSLA': 'QQQ',      # Tech ETF for TSLA
            'SPY': 'ES=F',      # S&P 500 futures
            'QQQ': 'NQ=F',      # NASDAQ futures
            'BTC-USD': 'BTC/USDT',  # BTC perpetual
            'ETH-USD': 'ETH/USDT',  # ETH perpetual
        }
        
        return hedge_mapping.get(symbol, f"{symbol}-PERP")
    
    def _extract_base_symbol(self, symbol: str) -> str:
        """Extract base symbol from option or derivative symbol."""
        # Remove option suffixes, dates, etc.
        base = symbol.split('_')[0].split('-')[0].split('/')[0]
        return base


class ProtectivePutStrategy(BaseHedgeStrategy):
    """Protective put hedging strategy."""
    
    def analyze_position(self, position: Position, market_data: MarketData) -> Optional[HedgeRecommendation]:
        """Analyze position for protective put opportunity."""
        if not self.config.enabled or position.size <= 0:  # Only for long positions
            return None
        
        # Check if position needs protection
        position_value = position.market_value
        if position_value < 10000:  # Minimum position size for options
            return None
        
        # Calculate put strike (OTM)
        current_price = market_data.price
        put_strike = current_price * (1 + self.config.protective_put_delta)  # OTM put strike
        
        # Estimate put premium (simplified)
        put_premium = self._estimate_put_premium(current_price, put_strike, 30)  # 30 days
        total_cost = put_premium * position.size
        
        # Check cost threshold
        if total_cost > position_value * self.config.max_hedge_cost:
            return None
        
        # Calculate risk reduction
        max_loss_without_hedge = position_value  # Could lose everything
        max_loss_with_hedge = max(0, (current_price - put_strike) * position.size + total_cost)
        risk_reduction_value = max_loss_without_hedge - max_loss_with_hedge
        
        risk_reduction = {
            'downside_protection': risk_reduction_value,
            'max_loss_reduction': risk_reduction_value / position_value,
            'cost_ratio': total_cost / position_value
        }
        
        return HedgeRecommendation(
            symbol=f"{position.symbol}_PUT_{put_strike:.0f}",
            action="BUY",
            size=position.size,
            instrument_type=PositionType.OPTION_PUT,
            price=put_premium,
            reasoning=f"Protective put for ${position_value:,.0f} long position",
            urgency=HedgeUrgency.MEDIUM.value,
            estimated_cost=total_cost,
            risk_reduction=risk_reduction
        )
    
    def analyze_portfolio(self, portfolio: Portfolio, market_data: Dict[str, MarketData]) -> List[HedgeRecommendation]:
        """Analyze portfolio for protective put opportunities."""
        recommendations = []
        
        # Group long positions by symbol
        long_positions = {}
        for position in portfolio.positions:
            if position.size > 0 and not position.is_option:
                symbol = position.symbol
                if symbol not in long_positions:
                    long_positions[symbol] = []
                long_positions[symbol].append(position)
        
        # Analyze each symbol group
        for symbol, positions in long_positions.items():
            if symbol in market_data:
                # Aggregate positions
                total_size = sum(pos.size for pos in positions)
                avg_price = sum(pos.entry_price * pos.size for pos in positions) / total_size
                
                # Create aggregate position
                aggregate_position = Position(
                    symbol=symbol,
                    position_type=PositionType.SPOT,
                    size=total_size,
                    entry_price=avg_price,
                    current_price=market_data[symbol].price
                )
                
                hedge_rec = self.analyze_position(aggregate_position, market_data[symbol])
                if hedge_rec:
                    recommendations.append(hedge_rec)
        
        return recommendations
    
    def calculate_hedge_size(self, position: Position, target_delta: float = 0.0) -> float:
        """Calculate protective put size (typically 1:1 with position)."""
        return position.size if position.size > 0 else 0.0
    
    def _estimate_put_premium(self, spot_price: float, strike_price: float, days_to_expiry: int) -> float:
        """Estimate put option premium (simplified Black-Scholes)."""
        # Simplified premium calculation
        # In practice, you'd use the full Black-Scholes calculator
        
        time_value = days_to_expiry / 365.0
        volatility = 0.25  # Assumed 25% volatility
        risk_free_rate = 0.05
        
        # Intrinsic value
        intrinsic = max(strike_price - spot_price, 0)
        
        # Time value (simplified)
        time_val = spot_price * volatility * np.sqrt(time_value) * 0.4
        
        return intrinsic + time_val


class CollarStrategy(BaseHedgeStrategy):
    """Collar strategy (protective put + covered call)."""
    
    def analyze_position(self, position: Position, market_data: MarketData) -> Optional[HedgeRecommendation]:
        """Analyze position for collar strategy."""
        if not self.config.enabled or position.size <= 0:
            return None
        
        position_value = position.market_value
        if position_value < 25000:  # Higher minimum for collar
            return None
        
        current_price = market_data.price
        
        # Calculate strikes
        put_strike = current_price * (1 + self.config.collar_put_delta / 10)
        call_strike = current_price * (1 + self.config.collar_call_delta / 10)
        
        # Estimate premiums
        put_premium = self._estimate_put_premium(current_price, put_strike, 30)
        call_premium = self._estimate_call_premium(current_price, call_strike, 30)
        
        # Net cost (put cost - call premium received)
        net_cost = (put_premium - call_premium) * position.size
        
        # Check if net cost is acceptable
        if net_cost > position_value * self.config.max_hedge_cost:
            return None
        
        # Calculate risk reduction
        max_loss = max(0, (current_price - put_strike) * position.size + net_cost)
        max_gain = (call_strike - current_price) * position.size - net_cost
        
        risk_reduction = {
            'downside_protection': (current_price - put_strike) * position.size,
            'upside_cap': max_gain,
            'net_cost': net_cost,
            'cost_ratio': net_cost / position_value
        }
        
        return HedgeRecommendation(
            symbol=f"{position.symbol}_COLLAR_{put_strike:.0f}_{call_strike:.0f}",
            action="COLLAR",
            size=position.size,
            instrument_type=PositionType.OPTION_CALL,  # Placeholder
            price=(put_premium + call_premium) / 2,
            reasoning=f"Collar strategy for ${position_value:,.0f} position",
            urgency=HedgeUrgency.MEDIUM.value,
            estimated_cost=abs(net_cost),
            risk_reduction=risk_reduction
        )
    
    def analyze_portfolio(self, portfolio: Portfolio, market_data: Dict[str, MarketData]) -> List[HedgeRecommendation]:
        """Analyze portfolio for collar opportunities."""
        recommendations = []
        
        # Similar to protective put but for larger positions
        long_positions = {}
        for position in portfolio.positions:
            if position.size > 0 and not position.is_option and position.market_value > 25000:
                symbol = position.symbol
                if symbol not in long_positions:
                    long_positions[symbol] = []
                long_positions[symbol].append(position)
        
        for symbol, positions in long_positions.items():
            if symbol in market_data:
                total_size = sum(pos.size for pos in positions)
                avg_price = sum(pos.entry_price * pos.size for pos in positions) / total_size
                
                aggregate_position = Position(
                    symbol=symbol,
                    position_type=PositionType.SPOT,
                    size=total_size,
                    entry_price=avg_price,
                    current_price=market_data[symbol].price
                )
                
                hedge_rec = self.analyze_position(aggregate_position, market_data[symbol])
                if hedge_rec:
                    recommendations.append(hedge_rec)
        
        return recommendations
    
    def calculate_hedge_size(self, position: Position, target_delta: float = 0.0) -> float:
        """Calculate collar size (1:1 with position)."""
        return position.size if position.size > 0 else 0.0
    
    def _estimate_call_premium(self, spot_price: float, strike_price: float, days_to_expiry: int) -> float:
        """Estimate call option premium."""
        time_value = days_to_expiry / 365.0
        volatility = 0.25
        
        # Intrinsic value
        intrinsic = max(spot_price - strike_price, 0)
        
        # Time value (simplified)
        time_val = spot_price * volatility * np.sqrt(time_value) * 0.4
        
        return intrinsic + time_val
    
    def _estimate_put_premium(self, spot_price: float, strike_price: float, days_to_expiry: int) -> float:
        """Estimate put option premium."""
        time_value = days_to_expiry / 365.0
        volatility = 0.25
        
        # Intrinsic value
        intrinsic = max(strike_price - spot_price, 0)
        
        # Time value (simplified)
        time_val = spot_price * volatility * np.sqrt(time_value) * 0.4
        
        return intrinsic + time_val
