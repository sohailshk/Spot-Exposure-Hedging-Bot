"""
Test suite for risk calculation engine.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import asyncio

from src.risk.models import Position, Portfolio, PositionType, RiskThresholds, MarketData
from src.risk.calculator import BlackScholesCalculator, RiskCalculator
from src.risk.market_data import YahooFinanceProvider, AggregatedDataProvider


class TestBlackScholesCalculator:
    """Test Black-Scholes calculations."""
    
    def test_option_price_call(self):
        """Test call option pricing."""
        bs = BlackScholesCalculator()
        
        # Standard test case
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2
        price = bs.option_price(S, K, T, r, sigma, 'call')
        
        # Should be around 4.61 for these parameters (updated based on actual calculation)
        assert 4.0 < price < 5.0
    
    def test_option_price_put(self):
        """Test put option pricing."""
        bs = BlackScholesCalculator()
        
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2
        price = bs.option_price(S, K, T, r, sigma, 'put')
        
        # Should be around 3.37 for these parameters (updated based on actual calculation)
        assert 3.0 < price < 4.0
    
    def test_delta_calculation(self):
        """Test delta calculation."""
        bs = BlackScholesCalculator()
        
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2
        
        call_delta = bs.delta(S, K, T, r, sigma, 'call')
        put_delta = bs.delta(S, K, T, r, sigma, 'put')
        
        # Call delta should be positive, put delta negative
        assert 0 < call_delta < 1
        assert -1 < put_delta < 0
        
        # Put-call parity: call_delta - put_delta should equal 1
        assert abs((call_delta - put_delta) - 1.0) < 0.01
    
    def test_gamma_calculation(self):
        """Test gamma calculation."""
        bs = BlackScholesCalculator()
        
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2
        gamma = bs.gamma(S, K, T, r, sigma)
        
        # Gamma should be positive for both calls and puts
        assert gamma > 0
    
    def test_theta_calculation(self):
        """Test theta calculation."""
        bs = BlackScholesCalculator()
        
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2
        
        call_theta = bs.theta(S, K, T, r, sigma, 'call')
        put_theta = bs.theta(S, K, T, r, sigma, 'put')
        
        # Theta should be negative (time decay)
        assert call_theta < 0
        assert put_theta < 0
    
    def test_vega_calculation(self):
        """Test vega calculation."""
        bs = BlackScholesCalculator()
        
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2
        vega = bs.vega(S, K, T, r, sigma)
        
        # Vega should be positive
        assert vega > 0
    
    def test_expired_option(self):
        """Test calculations for expired options."""
        bs = BlackScholesCalculator()
        
        # Option expired (T = 0)
        S, K, T, r, sigma = 110, 100, 0, 0.05, 0.2
        
        call_price = bs.option_price(S, K, T, r, sigma, 'call')
        put_price = bs.option_price(S, K, T, r, sigma, 'put')
        
        # Call should be worth intrinsic value (S - K = 10)
        assert abs(call_price - 10) < 0.01
        
        # Put should be worthless
        assert put_price == 0
    
    def test_time_to_expiry(self):
        """Test time to expiry calculation."""
        bs = BlackScholesCalculator()
        
        current = datetime(2025, 1, 1, 12, 0, 0)
        expiry = datetime(2025, 4, 1, 12, 0, 0)  # 3 months later
        
        T = bs.time_to_expiry(expiry, current)
        
        # Should be approximately 0.25 years (3 months)
        assert 0.24 < T < 0.26


class TestRiskCalculator:
    """Test risk calculator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.risk_calc = RiskCalculator()
    
    def test_spot_position_greeks(self):
        """Test Greeks calculation for spot positions."""
        position = Position(
            symbol="AAPL",
            position_type=PositionType.SPOT,
            size=100,
            entry_price=150,
            current_price=155
        )
        
        updated_position = self.risk_calc.calculate_position_greeks(position)
        
        # Spot position should have delta = 1, others = 0
        assert updated_position.delta == 1.0
        assert updated_position.gamma == 0.0
        assert updated_position.theta == 0.0
        assert updated_position.vega == 0.0
    
    def test_option_position_greeks(self):
        """Test Greeks calculation for option positions."""
        expiry = datetime.now() + timedelta(days=30)
        
        position = Position(
            symbol="AAPL",
            position_type=PositionType.OPTION_CALL,
            size=10,  # 10 contracts
            entry_price=5.0,
            current_price=150,
            strike_price=150,
            expiry_date=expiry,
            implied_volatility=0.25
        )
        
        updated_position = self.risk_calc.calculate_position_greeks(position)
        
        # Option should have non-zero Greeks
        assert updated_position.delta is not None
        assert updated_position.gamma is not None
        assert updated_position.theta is not None
        assert updated_position.vega is not None
        
        # Delta should be scaled by position size
        assert abs(updated_position.delta) <= abs(position.size)
    
    def test_var_calculation(self):
        """Test VaR calculation."""
        # Generate some sample returns
        np.random.seed(42)
        returns = np.random.normal(0, 0.02, 1000)  # 2% daily volatility
        
        var_95 = self.risk_calc.calculate_var(returns, 0.95)
        var_99 = self.risk_calc.calculate_var(returns, 0.99)
        
        # VaR should be positive (loss)
        assert var_95 > 0
        assert var_99 > 0
        
        # 99% VaR should be higher than 95% VaR
        assert var_99 > var_95
    
    def test_correlation_matrix(self):
        """Test correlation matrix calculation."""
        # Create sample price data
        np.random.seed(42)
        
        # Correlated price series
        base_prices = np.cumsum(np.random.normal(0, 0.01, 100))
        price_data = {
            'AAPL': 150 + base_prices + np.random.normal(0, 0.005, 100),
            'GOOGL': 2800 + base_prices * 18 + np.random.normal(0, 0.01, 100),
            'MSFT': 350 + base_prices * 2 + np.random.normal(0, 0.008, 100)
        }
        
        corr_matrix = self.risk_calc.calculate_correlation_matrix(price_data)
        
        # Should be 3x3 matrix
        assert corr_matrix.shape == (3, 3)
        
        # Diagonal should be 1s (self-correlation)
        np.testing.assert_array_almost_equal(np.diag(corr_matrix), [1, 1, 1], decimal=2)
        
        # Matrix should be symmetric
        np.testing.assert_array_almost_equal(corr_matrix, corr_matrix.T, decimal=10)


class TestPortfolio:
    """Test portfolio functionality."""
    
    def test_portfolio_creation(self):
        """Test portfolio creation and basic functionality."""
        portfolio = Portfolio()
        
        assert len(portfolio.positions) == 0
        assert portfolio.cash == 0.0
        assert portfolio.total_market_value == 0.0
        assert portfolio.total_pnl == 0.0
    
    def test_portfolio_with_positions(self):
        """Test portfolio calculations with positions."""
        portfolio = Portfolio(cash=10000)
        
        # Add some positions
        pos1 = Position("AAPL", PositionType.SPOT, 100, 150, 155)
        pos1.delta = 1.0
        pos1.gamma = 0.0
        pos1.theta = 0.0
        pos1.vega = 0.0
        
        pos2 = Position("GOOGL", PositionType.SPOT, 10, 2800, 2850)
        pos2.delta = 1.0
        pos2.gamma = 0.0
        pos2.theta = 0.0
        pos2.vega = 0.0
        
        portfolio.add_position(pos1)
        portfolio.add_position(pos2)
        
        # Check calculations
        expected_market_value = 100 * 155 + 10 * 2850 + 10000  # positions + cash
        assert portfolio.total_market_value == expected_market_value
        
        expected_pnl = 100 * (155 - 150) + 10 * (2850 - 2800)  # 500 + 500
        assert portfolio.total_pnl == expected_pnl
        
        assert portfolio.total_delta == 2.0  # Both positions have delta = 1
    
    def test_risk_thresholds(self):
        """Test risk threshold checking."""
        thresholds = RiskThresholds(
            max_delta=0.5,
            max_gamma=0.1,
            max_position_size=50000
        )
        
        portfolio = Portfolio()
        
        # Add position that breaches delta threshold
        pos = Position("AAPL", PositionType.SPOT, 100, 150, 155)
        pos.delta = 0.8  # Above threshold
        pos.gamma = 0.05
        portfolio.add_position(pos)
        
        breaches = thresholds.check_breach(portfolio)
        
        assert breaches['delta'] == True
        assert breaches['gamma'] == False


class TestMarketData:
    """Test market data functionality."""
    
    def test_market_data_creation(self):
        """Test MarketData object creation."""
        data = MarketData(
            symbol="AAPL",
            price=155.50,
            bid=155.45,
            ask=155.55,
            volume=1000000
        )
        
        assert data.symbol == "AAPL"
        assert data.price == 155.50
        assert abs(data.bid_ask_spread - 0.10) < 0.001  # Allow for floating point precision
        assert data.mid_price == 155.50
    
    @pytest.mark.asyncio
    async def test_aggregated_provider_routing(self):
        """Test symbol routing in aggregated provider."""
        provider = AggregatedDataProvider()
        
        # Test crypto symbol routing
        crypto_providers = provider._get_providers_for_symbol("BTC/USDT")
        assert 'binance' in crypto_providers or 'bybit' in crypto_providers
        
        # Test stock symbol routing
        stock_providers = provider._get_providers_for_symbol("AAPL")
        assert 'yahoo' in stock_providers


def test_integration_portfolio_risk():
    """Integration test for portfolio risk calculation."""
    # Create a sample portfolio
    portfolio = Portfolio(cash=50000)
    
    # Add mixed positions
    expiry = datetime.now() + timedelta(days=30)
    
    # Spot position
    spot_pos = Position("AAPL", PositionType.SPOT, 100, 150, 155)
    
    # Option position
    option_pos = Position(
        "AAPL", PositionType.OPTION_CALL, 10, 5.0, 155,
        strike_price=150, expiry_date=expiry, implied_volatility=0.25
    )
    
    portfolio.add_position(spot_pos)
    portfolio.add_position(option_pos)
    
    # Calculate risk
    risk_calc = RiskCalculator()
    
    # Update Greeks
    risk_calc.calculate_position_greeks(spot_pos)
    risk_calc.calculate_position_greeks(option_pos)
    
    # Check that portfolio has meaningful risk metrics
    assert portfolio.total_delta != 0
    assert abs(portfolio.total_market_value) > 0
    assert portfolio.total_pnl != 0  # Should have some P&L
    
    # Test risk thresholds
    thresholds = RiskThresholds()
    breaches = thresholds.check_breach(portfolio)
    
    # Should return a dictionary with risk checks
    assert isinstance(breaches, dict)
    assert 'delta' in breaches
    assert 'gamma' in breaches


if __name__ == "__main__":
    # Run a quick test
    print("🧪 Running Risk Engine Tests...")
    
    # Test Black-Scholes
    bs = BlackScholesCalculator()
    call_price = bs.option_price(100, 100, 0.25, 0.05, 0.2, 'call')
    print(f"✅ Black-Scholes Call Price: ${call_price:.2f}")
    
    # Test portfolio
    portfolio = Portfolio()
    pos = Position("AAPL", PositionType.SPOT, 100, 150, 155)
    portfolio.add_position(pos)
    print(f"✅ Portfolio Value: ${portfolio.total_market_value:.2f}")
    print(f"✅ Portfolio P&L: ${portfolio.total_pnl:.2f}")
    
    print("🚀 Risk Engine Tests Completed!")
