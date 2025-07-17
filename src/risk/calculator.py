"""
Black-Scholes and Greeks calculation engine.
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from typing import Tuple, Optional
from datetime import datetime, timedelta
import math
import logging

from .models import Position, PositionType, PortfolioRiskMetrics


class BlackScholesCalculator:
    """Black-Scholes option pricing and Greeks calculator."""
    
    @staticmethod
    def time_to_expiry(expiry_date: datetime, current_date: Optional[datetime] = None) -> float:
        """Calculate time to expiry in years."""
        if current_date is None:
            current_date = datetime.now()
        
        time_diff = expiry_date - current_date
        return max(time_diff.total_seconds() / (365.25 * 24 * 3600), 0.0)
    
    @staticmethod
    def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 parameter for Black-Scholes."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    
    @staticmethod
    def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d2 parameter for Black-Scholes."""
        if T <= 0:
            return 0.0
        return BlackScholesCalculator.d1(S, K, T, r, sigma) - sigma * np.sqrt(T)
    
    @classmethod
    def option_price(cls, S: float, K: float, T: float, r: float, sigma: float, 
                    option_type: str = 'call') -> float:
        """
        Calculate Black-Scholes option price.
        
        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
        """
        if T <= 0:
            if option_type.lower() == 'call':
                return max(S - K, 0)
            else:
                return max(K - S, 0)
        
        d1_val = cls.d1(S, K, T, r, sigma)
        d2_val = cls.d2(S, K, T, r, sigma)
        
        if option_type.lower() == 'call':
            price = S * norm.cdf(d1_val) - K * np.exp(-r * T) * norm.cdf(d2_val)
        else:  # put
            price = K * np.exp(-r * T) * norm.cdf(-d2_val) - S * norm.cdf(-d1_val)
        
        return max(price, 0.0)
    
    @classmethod
    def delta(cls, S: float, K: float, T: float, r: float, sigma: float, 
              option_type: str = 'call') -> float:
        """Calculate option delta."""
        if T <= 0:
            if option_type.lower() == 'call':
                return 1.0 if S > K else 0.0
            else:
                return -1.0 if S < K else 0.0
        
        d1_val = cls.d1(S, K, T, r, sigma)
        
        if option_type.lower() == 'call':
            return norm.cdf(d1_val)
        else:  # put
            return norm.cdf(d1_val) - 1.0
    
    @classmethod
    def gamma(cls, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate option gamma (same for calls and puts)."""
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1_val = cls.d1(S, K, T, r, sigma)
        return norm.pdf(d1_val) / (S * sigma * np.sqrt(T))
    
    @classmethod
    def theta(cls, S: float, K: float, T: float, r: float, sigma: float, 
              option_type: str = 'call') -> float:
        """Calculate option theta (time decay)."""
        if T <= 0:
            return 0.0
        
        d1_val = cls.d1(S, K, T, r, sigma)
        d2_val = cls.d2(S, K, T, r, sigma)
        
        theta_part1 = -(S * norm.pdf(d1_val) * sigma) / (2 * np.sqrt(T))
        
        if option_type.lower() == 'call':
            theta_part2 = -r * K * np.exp(-r * T) * norm.cdf(d2_val)
            return (theta_part1 + theta_part2) / 365.25  # Convert to daily
        else:  # put
            theta_part2 = r * K * np.exp(-r * T) * norm.cdf(-d2_val)
            return (theta_part1 + theta_part2) / 365.25  # Convert to daily
    
    @classmethod
    def vega(cls, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate option vega (sensitivity to volatility)."""
        if T <= 0:
            return 0.0
        
        d1_val = cls.d1(S, K, T, r, sigma)
        return S * norm.pdf(d1_val) * np.sqrt(T) / 100  # Convert to 1% vol change
    
    @classmethod
    def rho(cls, S: float, K: float, T: float, r: float, sigma: float, 
            option_type: str = 'call') -> float:
        """Calculate option rho (sensitivity to interest rate)."""
        if T <= 0:
            return 0.0
        
        d2_val = cls.d2(S, K, T, r, sigma)
        
        if option_type.lower() == 'call':
            return K * T * np.exp(-r * T) * norm.cdf(d2_val) / 100
        else:  # put
            return -K * T * np.exp(-r * T) * norm.cdf(-d2_val) / 100
    
    @classmethod
    def implied_volatility(cls, market_price: float, S: float, K: float, T: float, 
                          r: float, option_type: str = 'call', 
                          max_iterations: int = 100, tolerance: float = 1e-6) -> Optional[float]:
        """
        Calculate implied volatility using Brent's method.
        """
        if T <= 0:
            return None
        
        def objective(sigma):
            try:
                theoretical_price = cls.option_price(S, K, T, r, sigma, option_type)
                return theoretical_price - market_price
            except:
                return float('inf')
        
        try:
            # Try to find implied volatility between 0.01% and 1000%
            iv = brentq(objective, 0.0001, 10.0, maxiter=max_iterations, xtol=tolerance)
            return iv
        except:
            return None


class RiskCalculator:
    """Portfolio risk calculation engine."""
    
    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize risk calculator.
        
        Args:
            risk_free_rate: Risk-free interest rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.logger = logging.getLogger(__name__)
    
    def calculate_position_greeks(self, position: Position) -> Position:
        """
        Calculate Greeks for a position and update the position object.
        """
        if not position.is_option:
            # For non-options, delta = 1 for long, -1 for short
            position.delta = 1.0 if position.size > 0 else -1.0
            position.gamma = 0.0
            position.theta = 0.0
            position.vega = 0.0
            position.rho = 0.0
            return position
        
        # Option calculations
        if position.strike_price is None or position.expiry_date is None:
            raise ValueError("Options must have strike price and expiry date")
        
        S = position.current_price
        K = position.strike_price
        T = self.bs_calc.time_to_expiry(position.expiry_date)
        r = self.risk_free_rate
        sigma = position.implied_volatility or 0.2  # Default 20% vol if not provided
        
        option_type = 'call' if position.position_type == PositionType.OPTION_CALL else 'put'
        
        # Calculate Greeks per unit
        delta_per_unit = self.bs_calc.delta(S, K, T, r, sigma, option_type)
        gamma_per_unit = self.bs_calc.gamma(S, K, T, r, sigma)
        theta_per_unit = self.bs_calc.theta(S, K, T, r, sigma, option_type)
        vega_per_unit = self.bs_calc.vega(S, K, T, r, sigma)
        rho_per_unit = self.bs_calc.rho(S, K, T, r, sigma, option_type)
        
        # Scale by position size
        position.delta = delta_per_unit * position.size
        position.gamma = gamma_per_unit * position.size
        position.theta = theta_per_unit * position.size
        position.vega = vega_per_unit * position.size
        position.rho = rho_per_unit * position.size
        
        return position
    
    def calculate_var(self, returns: np.ndarray, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk using historical simulation.
        
        Args:
            returns: Array of historical returns
            confidence_level: Confidence level (default 95%)
        
        Returns:
            VaR value
        """
        if len(returns) == 0:
            return 0.0
        
        sorted_returns = np.sort(returns)
        index = int((1 - confidence_level) * len(sorted_returns))
        return -sorted_returns[index] if index < len(sorted_returns) else 0.0
    
    def calculate_correlation_matrix(self, price_data: dict) -> np.ndarray:
        """
        Calculate correlation matrix for portfolio assets.
        
        Args:
            price_data: Dictionary of symbol -> price array
        
        Returns:
            Correlation matrix
        """
        if not price_data:
            return np.array([])
        
        # Convert to returns
        returns_data = {}
        for symbol, prices in price_data.items():
            if len(prices) > 1:
                returns = np.diff(np.log(prices))
                returns_data[symbol] = returns
        
        if not returns_data:
            return np.array([])
        
        # Create returns matrix
        symbols = list(returns_data.keys())
        min_length = min(len(returns) for returns in returns_data.values())
        
        returns_matrix = np.array([
            returns_data[symbol][-min_length:] for symbol in symbols
        ])
        
        return np.corrcoef(returns_matrix)
    
    def calculate_portfolio_var(self, positions: list, price_history: dict, 
                               confidence_level: float = 0.95, 
                               lookback_days: int = 252) -> float:
        """
        Calculate portfolio VaR using Monte Carlo simulation.
        
        Args:
            positions: List of positions
            price_history: Historical price data
            confidence_level: Confidence level
            lookback_days: Days of history to use
        
        Returns:
            Portfolio VaR
        """
        # This is a simplified VaR calculation
        
        portfolio_values = []
        
        for symbol in set(pos.symbol for pos in positions):
            symbol_positions = [pos for pos in positions if pos.symbol == symbol]
            if symbol in price_history:
                prices = price_history[symbol][-lookback_days:]
                if len(prices) > 1:
                    returns = np.diff(np.log(prices))
                    total_exposure = sum(pos.market_value for pos in symbol_positions)
                    
                    # Simulate portfolio value changes
                    simulated_returns = np.random.choice(returns, size=10000)
                    value_changes = total_exposure * simulated_returns
                    portfolio_values.extend(value_changes)
        
        if portfolio_values:
            return self.calculate_var(np.array(portfolio_values), confidence_level)
        return 0.0

    def calculate_portfolio_risk(self, portfolio, market_data) -> PortfolioRiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics.
        
        Args:
            portfolio: Portfolio object containing positions
            market_data: MarketData object with current market information
            
        Returns:
            PortfolioRiskMetrics object with calculated metrics
        """
        try:
            total_value = 0
            total_delta = 0
            total_gamma = 0
            total_theta = 0
            total_vega = 0
            unrealized_pnl = 0
            
            # Calculate metrics for each position
            for position in portfolio.positions:
                if position.symbol == market_data.symbol:
                    # Update position current price
                    position.current_price = market_data.price
                
                # Calculate position value
                position_value = position.size * position.current_price
                total_value += position_value
                
                # Calculate unrealized P&L
                position_pnl = position.size * (position.current_price - position.entry_price)
                unrealized_pnl += position_pnl
                
                # Calculate Greeks for this position
                self.calculate_position_greeks(position)
                
                # Sum up Greeks (weighted by position size)
                total_delta += position.delta * position.size
                total_gamma += position.gamma * position.size if position.gamma else 0
                total_theta += position.theta * position.size if position.theta else 0
                total_vega += position.vega * position.size if position.vega else 0
            
            # Normalize by portfolio value if non-zero
            if total_value > 0:
                delta = total_delta / total_value
                gamma = total_gamma / total_value
                theta = total_theta / total_value
                vega = total_vega / total_value
            else:
                delta = gamma = theta = vega = 0.0
            
            return PortfolioRiskMetrics(
                total_value=total_value,
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                unrealized_pnl=unrealized_pnl,
                var=0.0,  # Simplified - would need historical data for proper VaR
                timestamp=market_data.timestamp
            )
            
        except Exception as e:
            # Return basic metrics if calculation fails
            self.logger.error(f"Error calculating portfolio risk: {e}")
            return PortfolioRiskMetrics(
                total_value=0.0,
                delta=0.0,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                unrealized_pnl=0.0,
                var=0.0,
                timestamp=market_data.timestamp if market_data else datetime.now()
            )
