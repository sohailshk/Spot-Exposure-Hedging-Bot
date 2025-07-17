"""
Test suite for hedging strategies.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.strategies.hedge_strategies import (
    HedgeStrategy, HedgeConfig, DeltaNeutralStrategy, 
    ProtectivePutStrategy, CollarStrategy
)
from src.strategies.strategy_manager import StrategyManager
from src.risk.models import (
    Position, Portfolio, PositionType, MarketData, RiskThresholds
)


class TestDeltaNeutralStrategy:
    """Test delta neutral hedging strategy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = HedgeConfig(
            strategy=HedgeStrategy.DELTA_NEUTRAL,
            delta_threshold=0.1,
            rebalance_threshold=0.05
        )
        self.strategy = DeltaNeutralStrategy(self.config)
    
    def test_analyze_position_no_hedge_needed(self):
        """Test position that doesn't need hedging."""
        position = Position(
            symbol="AAPL",
            position_type=PositionType.SPOT,
            size=100,
            entry_price=150,
            current_price=155
        )
        position.delta = 0.05  # Below threshold
        
        market_data = MarketData(symbol="AAPL", price=155)
        
        recommendation = self.strategy.analyze_position(position, market_data)
        assert recommendation is None
    
    def test_analyze_position_hedge_needed(self):
        """Test position that needs delta hedging."""
        position = Position(
            symbol="AAPL",
            position_type=PositionType.SPOT,
            size=1000,  # Large position
            entry_price=150,
            current_price=155
        )
        position.delta = 1.0  # Spot delta
        
        market_data = MarketData(symbol="AAPL", price=155)
        
        recommendation = self.strategy.analyze_position(position, market_data)
        
        assert recommendation is not None
        assert recommendation.symbol == "QQQ"  # Tech ETF hedge
        assert recommendation.action in ["BUY", "SELL"]
        assert recommendation.size > 0
        assert "delta hedge" in recommendation.reasoning.lower()
    
    def test_portfolio_analysis(self):
        """Test portfolio-level delta hedging."""
        portfolio = Portfolio()
        
        # Add positions with net delta exposure
        pos1 = Position("AAPL", PositionType.SPOT, 500, 150, 155)
        pos1.delta = 1.0
        
        pos2 = Position("GOOGL", PositionType.SPOT, 50, 2800, 2850)
        pos2.delta = 1.0
        
        portfolio.add_position(pos1)
        portfolio.add_position(pos2)
        
        market_data = {
            "AAPL": MarketData(symbol="AAPL", price=155),
            "GOOGL": MarketData(symbol="GOOGL", price=2850),
            "QQQ": MarketData(symbol="QQQ", price=400)
        }
        
        recommendations = self.strategy.analyze_portfolio(portfolio, market_data)
        
        assert len(recommendations) >= 1  # Should generate hedge recommendations
        
        # Check that recommendations address delta exposure
        total_hedge_delta = sum(
            rec.size if rec.action == "BUY" else -rec.size 
            for rec in recommendations
        )
        assert abs(total_hedge_delta) > 0


class TestProtectivePutStrategy:
    """Test protective put strategy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = HedgeConfig(
            strategy=HedgeStrategy.PROTECTIVE_PUT,
            protective_put_delta=-0.2,
            max_hedge_cost=0.05  # Increased to 5% to allow for realistic option costs
        )
        self.strategy = ProtectivePutStrategy(self.config)
    
    def test_analyze_position_long_position(self):
        """Test protective put for long position."""
        position = Position(
            symbol="AAPL",
            position_type=PositionType.SPOT,
            size=1000,  # Long position (increased to meet minimum threshold)
            entry_price=150,
            current_price=155
        )
        
        market_data = MarketData(symbol="AAPL", price=155)
        
        recommendation = self.strategy.analyze_position(position, market_data)
        
        assert recommendation is not None
        assert "PUT" in recommendation.symbol
        assert recommendation.action == "BUY"
        assert recommendation.size == position.size
        assert recommendation.instrument_type == PositionType.OPTION_PUT
        assert "protective put" in recommendation.reasoning.lower()
    
    def test_analyze_position_short_position(self):
        """Test that short positions don't get protective puts."""
        position = Position(
            symbol="AAPL",
            position_type=PositionType.SPOT,
            size=-500,  # Short position
            entry_price=150,
            current_price=155
        )
        
        market_data = MarketData(symbol="AAPL", price=155)
        
        recommendation = self.strategy.analyze_position(position, market_data)
        assert recommendation is None
    
    def test_analyze_position_small_position(self):
        """Test that small positions don't get protective puts."""
        position = Position(
            symbol="AAPL",
            position_type=PositionType.SPOT,
            size=10,  # Small position
            entry_price=150,
            current_price=155
        )
        
        market_data = MarketData(symbol="AAPL", price=155)
        
        recommendation = self.strategy.analyze_position(position, market_data)
        assert recommendation is None  # Position too small


class TestCollarStrategy:
    """Test collar strategy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = HedgeConfig(
            strategy=HedgeStrategy.COLLAR,
            collar_put_delta=-0.2,
            collar_call_delta=0.3,
            max_hedge_cost=0.015
        )
        self.strategy = CollarStrategy(self.config)
    
    def test_analyze_position_large_position(self):
        """Test collar for large position."""
        position = Position(
            symbol="AAPL",
            position_type=PositionType.SPOT,
            size=1000,  # Large position
            entry_price=150,
            current_price=155
        )
        
        market_data = MarketData(symbol="AAPL", price=155)
        
        recommendation = self.strategy.analyze_position(position, market_data)
        
        assert recommendation is not None
        assert "COLLAR" in recommendation.symbol
        assert recommendation.action == "COLLAR"
        assert recommendation.size == position.size
        assert "collar strategy" in recommendation.reasoning.lower()
        
        # Check risk reduction information
        assert recommendation.risk_reduction is not None
        assert "downside_protection" in recommendation.risk_reduction
        assert "upside_cap" in recommendation.risk_reduction


class TestStrategyManager:
    """Test strategy manager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.risk_thresholds = RiskThresholds(
            max_delta=0.1,
            max_position_size=100000
        )
        self.strategy_manager = StrategyManager(self.risk_thresholds)
    
    def test_initialization(self):
        """Test strategy manager initialization."""
        assert len(self.strategy_manager.strategies) > 0
        assert HedgeStrategy.DELTA_NEUTRAL in self.strategy_manager.strategies
        assert HedgeStrategy.PROTECTIVE_PUT in self.strategy_manager.strategies
        assert HedgeStrategy.COLLAR in self.strategy_manager.strategies
    
    def test_enable_disable_strategy(self):
        """Test enabling and disabling strategies."""
        # Disable delta neutral strategy
        self.strategy_manager.enable_strategy(HedgeStrategy.DELTA_NEUTRAL, False)
        assert not self.strategy_manager.strategy_configs[HedgeStrategy.DELTA_NEUTRAL].enabled
        
        # Re-enable it
        self.strategy_manager.enable_strategy(HedgeStrategy.DELTA_NEUTRAL, True)
        assert self.strategy_manager.strategy_configs[HedgeStrategy.DELTA_NEUTRAL].enabled
    
    def test_analyze_portfolio_no_breach(self):
        """Test portfolio analysis with no risk breaches."""
        portfolio = Portfolio()
        
        # Small position that doesn't breach thresholds
        pos = Position("AAPL", PositionType.SPOT, 10, 150, 155)
        pos.delta = 0.01  # Very small delta
        portfolio.add_position(pos)
        
        market_data = {
            "AAPL": MarketData(symbol="AAPL", price=155)
        }
        
        recommendations = self.strategy_manager.analyze_portfolio(portfolio, market_data)
        assert len(recommendations) == 0  # No hedging needed
    
    def test_analyze_portfolio_with_breach(self):
        """Test portfolio analysis with risk breaches."""
        portfolio = Portfolio()
        
        # Large position that breaches delta threshold
        pos = Position("AAPL", PositionType.SPOT, 1000, 150, 155)
        pos.delta = 1.0  # Large delta exposure
        portfolio.add_position(pos)
        
        market_data = {
            "AAPL": MarketData(symbol="AAPL", price=155),
            "QQQ": MarketData(symbol="QQQ", price=400)
        }
        
        recommendations = self.strategy_manager.analyze_portfolio(portfolio, market_data)
        assert len(recommendations) > 0  # Should generate recommendations
        
        # Check that recommendations have strategy names in reasoning
        for rec in recommendations:
            assert any(strategy.value in rec.reasoning for strategy in HedgeStrategy)
    
    def test_rank_recommendations(self):
        """Test recommendation ranking."""
        portfolio = Portfolio()
        pos = Position("AAPL", PositionType.SPOT, 1000, 150, 155)
        pos.delta = 1.0
        portfolio.add_position(pos)
        
        market_data = {
            "AAPL": MarketData(symbol="AAPL", price=155),
            "QQQ": MarketData(symbol="QQQ", price=400)
        }
        
        recommendations = self.strategy_manager.analyze_portfolio(portfolio, market_data)
        
        if recommendations:
            rankings = self.strategy_manager.rank_recommendations(
                recommendations, portfolio, market_data
            )
            
            assert len(rankings) == len(recommendations)
            
            # Check that rankings are sorted by score
            scores = [ranking.total_score for ranking in rankings]
            assert scores == sorted(scores, reverse=True)
            
            # Check ranking components
            for ranking in rankings:
                assert 0 <= ranking.effectiveness_score <= 1
                assert 0 <= ranking.urgency_score <= 1
                assert 0 <= ranking.cost_score <= 1
                assert ranking.total_score > 0
    
    def test_select_optimal_hedges(self):
        """Test optimal hedge selection."""
        portfolio = Portfolio()
        
        # Create portfolio with multiple positions
        pos1 = Position("AAPL", PositionType.SPOT, 1000, 150, 155)
        pos1.delta = 1.0
        pos2 = Position("GOOGL", PositionType.SPOT, 100, 2800, 2850)
        pos2.delta = 1.0
        
        portfolio.add_position(pos1)
        portfolio.add_position(pos2)
        
        market_data = {
            "AAPL": MarketData(symbol="AAPL", price=155),
            "GOOGL": MarketData(symbol="GOOGL", price=2850),
            "QQQ": MarketData(symbol="QQQ", price=400)
        }
        
        # Get all recommendations
        all_recommendations = self.strategy_manager.analyze_portfolio(portfolio, market_data)
        
        if all_recommendations:
            # Select optimal hedges with cost constraint
            max_cost = 10000  # $10k max
            optimal_hedges = self.strategy_manager.select_optimal_hedges(
                all_recommendations, portfolio, market_data, max_cost
            )
            
            assert len(optimal_hedges) <= len(all_recommendations)
            
            # Calculate total cost
            total_cost = 0
            for hedge in optimal_hedges:
                if hedge.estimated_cost:
                    total_cost += hedge.estimated_cost
            
            assert total_cost <= max_cost
    
    def test_strategy_performance_tracking(self):
        """Test strategy performance tracking."""
        strategy_type = HedgeStrategy.DELTA_NEUTRAL
        
        # Update performance metrics
        self.strategy_manager.update_strategy_performance(
            strategy_type=strategy_type,
            executed=True,
            cost=1000.0,
            risk_reduction=0.5,
            execution_time=2.5
        )
        
        performance = self.strategy_manager.strategy_performance[strategy_type]
        
        assert performance.executed_recommendations == 1
        assert performance.total_cost == 1000.0
        assert performance.total_risk_reduction == 0.5
        assert performance.avg_execution_time == 2.5
        assert performance.last_execution is not None
    
    def test_performance_report(self):
        """Test performance report generation."""
        report = self.strategy_manager.get_strategy_performance_report()
        
        assert isinstance(report, dict)
        assert len(report) > 0
        
        for strategy_name, performance in report.items():
            assert hasattr(performance, 'total_recommendations')
            assert hasattr(performance, 'execution_rate')
            assert hasattr(performance, 'cost_efficiency')


def test_integration_strategy_workflow():
    """Integration test for complete strategy workflow."""
    # Set up portfolio with risk breach
    portfolio = Portfolio(cash=50000)
    
    # Large AAPL position
    aapl_pos = Position("AAPL", PositionType.SPOT, 1500, 150, 155)
    aapl_pos.delta = 1.0
    portfolio.add_position(aapl_pos)
    
    # Market data
    market_data = {
        "AAPL": MarketData(symbol="AAPL", price=155, bid=154.95, ask=155.05),
        "QQQ": MarketData(symbol="QQQ", price=400, bid=399.90, ask=400.10)
    }
    
    # Risk thresholds that will be breached
    risk_thresholds = RiskThresholds(
        max_delta=0.5,  # Will be breached by 1.0 delta
        max_position_size=200000  # Will be breached by $232.5k position
    )
    
    # Strategy manager
    strategy_manager = StrategyManager(risk_thresholds)
    
    # 1. Analyze portfolio
    recommendations = strategy_manager.analyze_portfolio(portfolio, market_data)
    assert len(recommendations) > 0
    
    # 2. Rank recommendations
    rankings = strategy_manager.rank_recommendations(recommendations, portfolio, market_data)
    assert len(rankings) > 0
    
    # 3. Select optimal hedges
    optimal_hedges = strategy_manager.select_optimal_hedges(
        recommendations, portfolio, market_data, max_hedge_cost=5000
    )
    assert len(optimal_hedges) > 0
    
    # 4. Verify hedge quality
    for hedge in optimal_hedges:
        assert hedge.size > 0
        assert hedge.price is not None
        assert hedge.estimated_cost is not None
        assert hedge.urgency in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


if __name__ == "__main__":
    # Run a quick test
    print("🧪 Running Hedging Strategy Tests...")
    
    # Test delta neutral strategy
    config = HedgeConfig(strategy=HedgeStrategy.DELTA_NEUTRAL)
    strategy = DeltaNeutralStrategy(config)
    
    pos = Position("AAPL", PositionType.SPOT, 1000, 150, 155)
    pos.delta = 1.0
    market_data = MarketData(symbol="AAPL", price=155)
    
    recommendation = strategy.analyze_position(pos, market_data)
    if recommendation:
        print(f"✅ Generated hedge recommendation: {recommendation.action} {recommendation.size} {recommendation.symbol}")
    
    # Test strategy manager
    risk_thresholds = RiskThresholds(max_delta=0.1)
    manager = StrategyManager(risk_thresholds)
    print(f"✅ Strategy manager initialized with {len(manager.strategies)} strategies")
    
    print("🚀 Hedging Strategy Tests Completed!")
