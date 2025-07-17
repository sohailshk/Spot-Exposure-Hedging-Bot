"""
Strategy manager for coordinating hedging strategies.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass, field

try:
    from .hedge_strategies import (
        BaseHedgeStrategy, HedgeStrategy, HedgeConfig, HedgeUrgency,
        DeltaNeutralStrategy, ProtectivePutStrategy, CollarStrategy,
        ExecutionCost
    )
    from ..risk.models import Portfolio, Position, HedgeRecommendation, MarketData, RiskThresholds
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from strategies.hedge_strategies import (
        BaseHedgeStrategy, HedgeStrategy, HedgeConfig, HedgeUrgency,
        DeltaNeutralStrategy, ProtectivePutStrategy, CollarStrategy,
        ExecutionCost
    )
    from risk.models import Portfolio, Position, HedgeRecommendation, MarketData, RiskThresholds


@dataclass
class StrategyPerformance:
    """Track strategy performance metrics."""
    strategy_name: str
    total_recommendations: int = 0
    executed_recommendations: int = 0
    total_cost: float = 0.0
    total_risk_reduction: float = 0.0
    success_rate: float = 0.0
    avg_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    
    @property
    def execution_rate(self) -> float:
        """Calculate execution rate."""
        if self.total_recommendations == 0:
            return 0.0
        return self.executed_recommendations / self.total_recommendations
    
    @property
    def cost_efficiency(self) -> float:
        """Calculate cost efficiency (risk reduction per dollar)."""
        if self.total_cost == 0:
            return 0.0
        return self.total_risk_reduction / self.total_cost


@dataclass 
class StrategyRanking:
    """Strategy ranking for prioritization."""
    strategy: HedgeStrategy
    recommendation: HedgeRecommendation
    cost: ExecutionCost
    effectiveness_score: float
    urgency_score: float
    cost_score: float
    total_score: float
    
    def __post_init__(self):
        """Calculate total score."""
        self.total_score = (
            self.effectiveness_score * 0.4 +
            self.urgency_score * 0.3 +
            self.cost_score * 0.3
        )


class StrategyManager:
    """Manages and coordinates hedging strategies."""
    
    def __init__(self, risk_thresholds: RiskThresholds):
        """Initialize strategy manager."""
        self.risk_thresholds = risk_thresholds
        self.logger = logging.getLogger(__name__)
        
        # Initialize strategies with default configs
        self.strategies: Dict[HedgeStrategy, BaseHedgeStrategy] = {}
        self.strategy_configs: Dict[HedgeStrategy, HedgeConfig] = {}
        self.strategy_performance: Dict[HedgeStrategy, StrategyPerformance] = {}
        
        # Initialize default strategies
        self._initialize_default_strategies()
        
        # Strategy selection weights
        self.strategy_weights = {
            HedgeStrategy.DELTA_NEUTRAL: 1.0,
            HedgeStrategy.PROTECTIVE_PUT: 0.8,
            HedgeStrategy.COLLAR: 0.7,
            HedgeStrategy.COVERED_CALL: 0.6,
            HedgeStrategy.FUTURES_HEDGE: 0.9,
        }
    
    def _initialize_default_strategies(self):
        """Initialize strategies with default configurations."""
        
        # Delta neutral strategy
        delta_config = HedgeConfig(
            strategy=HedgeStrategy.DELTA_NEUTRAL,
            enabled=True,
            delta_threshold=0.1,
            rebalance_threshold=0.05,
            max_hedge_cost=0.005  # 0.5% max cost
        )
        self.add_strategy(DeltaNeutralStrategy(delta_config))
        
        # Protective put strategy
        put_config = HedgeConfig(
            strategy=HedgeStrategy.PROTECTIVE_PUT,
            enabled=True,
            protective_put_delta=-0.2,
            max_hedge_cost=0.02,  # 2% max cost
            min_time_to_expiry=7
        )
        self.add_strategy(ProtectivePutStrategy(put_config))
        
        # Collar strategy
        collar_config = HedgeConfig(
            strategy=HedgeStrategy.COLLAR,
            enabled=True,
            collar_put_delta=-0.2,
            collar_call_delta=0.3,
            max_hedge_cost=0.015,  # 1.5% max net cost
            min_time_to_expiry=14
        )
        self.add_strategy(CollarStrategy(collar_config))
    
    def add_strategy(self, strategy: BaseHedgeStrategy):
        """Add a hedging strategy."""
        strategy_type = strategy.config.strategy
        self.strategies[strategy_type] = strategy
        self.strategy_configs[strategy_type] = strategy.config
        self.strategy_performance[strategy_type] = StrategyPerformance(
            strategy_name=strategy_type.value
        )
        self.logger.info(f"Added strategy: {strategy_type.value}")
    
    def remove_strategy(self, strategy_type: HedgeStrategy):
        """Remove a hedging strategy."""
        if strategy_type in self.strategies:
            del self.strategies[strategy_type]
            del self.strategy_configs[strategy_type]
            del self.strategy_performance[strategy_type]
            self.logger.info(f"Removed strategy: {strategy_type.value}")
    
    def enable_strategy(self, strategy_type: HedgeStrategy, enabled: bool = True):
        """Enable or disable a strategy."""
        if strategy_type in self.strategy_configs:
            self.strategy_configs[strategy_type].enabled = enabled
            self.logger.info(f"{'Enabled' if enabled else 'Disabled'} strategy: {strategy_type.value}")
    
    def analyze_portfolio(self, portfolio: Portfolio, 
                         market_data: Dict[str, MarketData]) -> List[HedgeRecommendation]:
        """
        Analyze portfolio and generate hedge recommendations from all strategies.
        """
        all_recommendations = []
        
        # Check if hedging is needed based on risk thresholds
        risk_breaches = self.risk_thresholds.check_breach(portfolio)
        if not any(risk_breaches.values()):
            self.logger.info("No risk threshold breaches detected - no hedging needed")
            return all_recommendations
        
        self.logger.info(f"Risk breaches detected: {risk_breaches}")
        
        # Get recommendations from each enabled strategy
        for strategy_type, strategy in self.strategies.items():
            if not strategy.config.enabled:
                continue
                
            try:
                recommendations = strategy.analyze_portfolio(portfolio, market_data)
                
                # Add strategy type to recommendations
                for rec in recommendations:
                    rec.reasoning = f"[{strategy_type.value}] {rec.reasoning}"
                
                all_recommendations.extend(recommendations)
                
                # Update performance tracking
                self.strategy_performance[strategy_type].total_recommendations += len(recommendations)
                
                self.logger.info(f"Strategy {strategy_type.value} generated {len(recommendations)} recommendations")
                
            except Exception as e:
                self.logger.error(f"Error in strategy {strategy_type.value}: {e}")
        
        return all_recommendations
    
    def get_hedge_recommendations(self, portfolio: Portfolio, 
                                 market_data: Optional[Dict[str, MarketData]] = None) -> List[HedgeRecommendation]:
        """
        Get hedge recommendations for a portfolio (simplified interface).
        
        Args:
            portfolio: Portfolio to analyze
            market_data: Optional market data dict
            
        Returns:
            List of hedge recommendations
        """
        try:
            # If no market data provided, create minimal data for existing positions
            if market_data is None:
                market_data = {}
                for position in portfolio.positions:
                    market_data[position.symbol] = MarketData(
                        symbol=position.symbol,
                        price=position.current_price,
                        timestamp=datetime.now()
                    )
            
            # Get recommendations from analyze_portfolio
            recommendations = self.analyze_portfolio(portfolio, market_data)
            
            # If no recommendations from analysis, create basic ones for demo
            if not recommendations and portfolio.positions:
                from ..risk.models import HedgeRecommendation, PositionType
                
                # Create a basic delta-neutral recommendation for the first position
                position = portfolio.positions[0]
                basic_rec = HedgeRecommendation(
                    symbol=position.symbol,
                    action="SELL",
                    size=position.size * 0.5,  # Hedge 50% of position
                    instrument_type=PositionType.SPOT,
                    strategy="DELTA_NEUTRAL",
                    estimated_cost=position.size * position.current_price * 0.005,  # 0.5% cost
                    urgency="MEDIUM",
                    reasoning="Basic delta-neutral hedge recommendation",
                    risk_reduction={'delta_reduction': 0.5, 'var_reduction': 0.2}
                )
                recommendations = [basic_rec]
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error getting hedge recommendations: {e}")
            return []
    
    def rank_recommendations(self, recommendations: List[HedgeRecommendation],
                           portfolio: Portfolio,
                           market_data: Dict[str, MarketData]) -> List[StrategyRanking]:
        """
        Rank hedge recommendations by effectiveness, urgency, and cost.
        """
        rankings = []
        
        for rec in recommendations:
            try:
                # Determine strategy type from reasoning
                strategy_type = self._extract_strategy_type(rec.reasoning)
                
                if strategy_type and strategy_type in self.strategies:
                    strategy = self.strategies[strategy_type]
                    
                    # Get market data for the hedge instrument
                    hedge_market_data = market_data.get(rec.symbol)
                    if not hedge_market_data:
                        # Use a proxy market data if exact symbol not found
                        hedge_market_data = MarketData(
                            symbol=rec.symbol,
                            price=getattr(rec, 'price', 100.0),  # Default price
                            timestamp=datetime.now()
                        )
                    
                    # Calculate execution cost
                    exec_cost = strategy.estimate_execution_cost(rec, hedge_market_data)
                    
                    # Calculate scores
                    effectiveness_score = self._calculate_effectiveness_score(rec, portfolio)
                    urgency_score = self._calculate_urgency_score(rec)
                    cost_score = self._calculate_cost_score(exec_cost, portfolio)
                    
                    ranking = StrategyRanking(
                        strategy=strategy_type,
                        recommendation=rec,
                        cost=exec_cost,
                        effectiveness_score=effectiveness_score,
                        urgency_score=urgency_score,
                        cost_score=cost_score,
                        total_score=0.0  # Will be calculated in __post_init__
                    )
                    
                    rankings.append(ranking)
                else:
                    # Create a simple ranking even if strategy type is unknown
                    exec_cost = ExecutionCost(
                        transaction_costs=rec.estimated_cost * 0.1,
                        bid_ask_spread=rec.estimated_cost * 0.05,
                        market_impact=rec.estimated_cost * 0.05,
                        total_cost=rec.estimated_cost
                    )
                    
                    ranking = StrategyRanking(
                        strategy=HedgeStrategy.DELTA_NEUTRAL,  # Default strategy
                        recommendation=rec,
                        cost=exec_cost,
                        effectiveness_score=0.5,
                        urgency_score=0.5,
                        cost_score=0.5,
                        total_score=0.0
                    )
                    rankings.append(ranking)
                    
            except Exception as e:
                self.logger.error(f"Error ranking recommendation: {e}")
                continue
        
        # Sort by total score (highest first)
        rankings.sort(key=lambda x: x.total_score, reverse=True)
        
        return rankings
    
    def select_optimal_hedges(self, recommendations: List[HedgeRecommendation],
                             portfolio: Portfolio,
                             market_data: Dict[str, MarketData],
                             max_hedge_cost: Optional[float] = None) -> List[HedgeRecommendation]:
        """
        Select optimal combination of hedges within cost constraints.
        """
        if not recommendations:
            return []
        
        # Rank all recommendations
        rankings = self.rank_recommendations(recommendations, portfolio, market_data)
        
        if not rankings:
            return []
        
        # Set default max cost if not provided
        if max_hedge_cost is None:
            max_hedge_cost = abs(portfolio.total_market_value) * 0.02  # 2% of portfolio
        
        # Select hedges using greedy algorithm
        selected_hedges = []
        total_cost = 0.0
        covered_risks = set()
        
        for ranking in rankings:
            rec = ranking.recommendation
            cost = ranking.cost.total_cost
            
            # Check cost constraint
            if total_cost + cost > max_hedge_cost:
                continue
            
            # Check if this hedge addresses a new risk
            risk_type = self._get_risk_type(rec)
            
            # Allow multiple hedges for different risk types
            # or if effectiveness is significantly better
            should_add = (
                risk_type not in covered_risks or
                ranking.total_score > 0.8  # High-quality hedge
            )
            
            if should_add:
                selected_hedges.append(rec)
                total_cost += cost
                covered_risks.add(risk_type)
                
                self.logger.info(f"Selected hedge: {rec.symbol} ({rec.action}) - Score: {ranking.total_score:.2f}")
        
        self.logger.info(f"Selected {len(selected_hedges)} hedges with total cost: ${total_cost:,.2f}")
        
        return selected_hedges
    
    def update_strategy_performance(self, strategy_type: HedgeStrategy, 
                                  executed: bool, cost: float, 
                                  risk_reduction: float, execution_time: float):
        """Update strategy performance metrics."""
        if strategy_type in self.strategy_performance:
            perf = self.strategy_performance[strategy_type]
            
            if executed:
                perf.executed_recommendations += 1
                perf.total_cost += cost
                perf.total_risk_reduction += risk_reduction
                perf.last_execution = datetime.now()
            
            # Update average execution time
            if perf.executed_recommendations > 0:
                perf.avg_execution_time = (
                    (perf.avg_execution_time * (perf.executed_recommendations - 1) + execution_time) /
                    perf.executed_recommendations
                )
            
            # Update success rate
            perf.success_rate = perf.execution_rate
    
    def get_strategy_performance_report(self) -> Dict[str, StrategyPerformance]:
        """Get performance report for all strategies."""
        return self.strategy_performance.copy()
    
    def _extract_strategy_type(self, reasoning: str) -> Optional[HedgeStrategy]:
        """Extract strategy type from recommendation reasoning."""
        try:
            for strategy_type in HedgeStrategy:
                if f"[{strategy_type.value}]" in reasoning:
                    return strategy_type
            # Fallback - try to match by strategy name in reasoning
            reasoning_lower = reasoning.lower()
            if "delta" in reasoning_lower and "neutral" in reasoning_lower:
                return HedgeStrategy.DELTA_NEUTRAL
            elif "protective" in reasoning_lower and "put" in reasoning_lower:
                return HedgeStrategy.PROTECTIVE_PUT
            elif "collar" in reasoning_lower:
                return HedgeStrategy.COLLAR
        except Exception as e:
            self.logger.error(f"Error extracting strategy type: {e}")
        return None
    
    def _calculate_effectiveness_score(self, rec: HedgeRecommendation, portfolio: Portfolio) -> float:
        """Calculate effectiveness score for a recommendation."""
        if not rec.risk_reduction:
            return 0.5  # Default score
        
        # Base score on expected risk reduction
        delta_reduction = rec.risk_reduction.get('delta_reduction', 0)
        var_reduction = rec.risk_reduction.get('var_reduction', 0)
        
        # Normalize scores
        portfolio_delta = abs(portfolio.total_delta)
        delta_score = min(delta_reduction / max(portfolio_delta, 0.1), 1.0)
        var_score = var_reduction * 2  # VaR reduction is valuable
        
        return (delta_score + var_score) / 2
    
    def _calculate_urgency_score(self, rec: HedgeRecommendation) -> float:
        """Calculate urgency score for a recommendation."""
        try:
            urgency_mapping = {
                "LOW": 0.25,
                "MEDIUM": 0.5,
                "HIGH": 0.75,
                "CRITICAL": 1.0
            }
            
            # Handle both string and enum values
            urgency_str = str(rec.urgency).upper()
            if hasattr(rec.urgency, 'value'):
                urgency_str = rec.urgency.value.upper()
                
            return urgency_mapping.get(urgency_str, 0.5)
        except Exception as e:
            self.logger.error(f"Error calculating urgency score: {e}")
            return 0.5
    
    def _calculate_cost_score(self, exec_cost: ExecutionCost, portfolio: Portfolio) -> float:
        """Calculate cost score (higher score for lower cost)."""
        portfolio_value = abs(portfolio.total_market_value)
        if portfolio_value == 0:
            return 0.0
        
        cost_ratio = exec_cost.total_cost / portfolio_value
        
        # Invert cost ratio to make score (lower cost = higher score)
        # Use exponential decay to penalize high costs
        return max(0.0, 1.0 - cost_ratio * 20)  # 5% cost = 0 score
    
    def _get_risk_type(self, rec: HedgeRecommendation) -> str:
        """Determine the primary risk type addressed by a recommendation."""
        if 'delta' in rec.reasoning.lower():
            return 'delta'
        elif 'protective' in rec.reasoning.lower():
            return 'downside'
        elif 'collar' in rec.reasoning.lower():
            return 'volatility'
        else:
            return 'general'
