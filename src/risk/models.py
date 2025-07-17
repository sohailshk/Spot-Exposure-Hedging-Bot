"""
Risk models and position data structures.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
import numpy as np


class PositionType(Enum):
    """Position type enumeration."""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    OPTION_CALL = "option_call"
    OPTION_PUT = "option_put"


class RiskMetric(Enum):
    """Risk metric enumeration."""
    DELTA = "delta"
    GAMMA = "gamma"
    THETA = "theta"
    VEGA = "vega"
    RHO = "rho"
    VAR = "var"


@dataclass
class Position:
    """Represents a financial position."""
    symbol: str
    position_type: PositionType
    size: float  # Positive for long, negative for short
    entry_price: float
    current_price: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Option-specific fields
    strike_price: Optional[float] = None
    expiry_date: Optional[datetime] = None
    implied_volatility: Optional[float] = None
    
    # Risk metrics (calculated)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    
    @property
    def market_value(self) -> float:
        """Calculate current market value of position."""
        return self.size * self.current_price
    
    @property
    def pnl(self) -> float:
        """Calculate unrealized P&L."""
        return self.size * (self.current_price - self.entry_price)
    
    @property
    def is_option(self) -> bool:
        """Check if position is an option."""
        return self.position_type in [PositionType.OPTION_CALL, PositionType.OPTION_PUT]


@dataclass
class Portfolio:
    """Portfolio containing multiple positions."""
    positions: List[Position] = field(default_factory=list)
    cash: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def total_market_value(self) -> float:
        """Calculate total portfolio market value."""
        return sum(pos.market_value for pos in self.positions) + self.cash
    
    @property
    def total_pnl(self) -> float:
        """Calculate total unrealized P&L."""
        return sum(pos.pnl for pos in self.positions)
    
    @property
    def total_delta(self) -> float:
        """Calculate portfolio delta."""
        return sum(pos.delta or 0.0 for pos in self.positions)
    
    @property
    def total_gamma(self) -> float:
        """Calculate portfolio gamma."""
        return sum(pos.gamma or 0.0 for pos in self.positions)
    
    @property
    def total_theta(self) -> float:
        """Calculate portfolio theta."""
        return sum(pos.theta or 0.0 for pos in self.positions)
    
    @property
    def total_vega(self) -> float:
        """Calculate portfolio vega."""
        return sum(pos.vega or 0.0 for pos in self.positions)
    
    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a specific symbol."""
        return [pos for pos in self.positions if pos.symbol == symbol]
    
    def add_position(self, position: Position) -> None:
        """Add a position to the portfolio."""
        self.positions.append(position)
        self.timestamp = datetime.now()
    
    def remove_position(self, position: Position) -> bool:
        """Remove a position from the portfolio."""
        if position in self.positions:
            self.positions.remove(position)
            self.timestamp = datetime.now()
            return True
        return False


@dataclass
class RiskThresholds:
    """Risk management thresholds configuration."""
    max_delta: float = 0.1
    max_gamma: float = 0.05
    max_vega: float = 0.1
    max_theta: float = 0.05
    max_var_95: float = 0.02  # 2% VaR at 95% confidence
    max_var_99: float = 0.05  # 5% VaR at 99% confidence
    max_position_size: float = 100000  # USD
    max_portfolio_size: float = 500000  # USD
    correlation_threshold: float = 0.8  # High correlation warning
    
    def check_breach(self, portfolio: Portfolio) -> Dict[str, bool]:
        """Check if any thresholds are breached."""
        breaches = {}
        
        # Delta breach
        abs_delta = abs(portfolio.total_delta)
        breaches['delta'] = abs_delta > self.max_delta
        
        # Gamma breach
        abs_gamma = abs(portfolio.total_gamma)
        breaches['gamma'] = abs_gamma > self.max_gamma
        
        # Vega breach
        abs_vega = abs(portfolio.total_vega)
        breaches['vega'] = abs_vega > self.max_vega
        
        # Theta breach
        abs_theta = abs(portfolio.total_theta)
        breaches['theta'] = abs_theta > self.max_theta
        
        # Portfolio size breach
        breaches['portfolio_size'] = abs(portfolio.total_market_value) > self.max_portfolio_size
        
        # Individual position size breach
        breaches['position_size'] = any(
            abs(pos.market_value) > self.max_position_size 
            for pos in portfolio.positions
        )
        
        return breaches


@dataclass
class MarketData:
    """Market data structure."""
    symbol: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Volatility data
    implied_volatility: Optional[float] = None
    historical_volatility: Optional[float] = None
    
    # Options chain (if applicable)
    options_chain: Optional[Dict] = None
    
    @property
    def bid_ask_spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None
    
    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.price


@dataclass
class HedgeRecommendation:
    """Hedge recommendation structure."""
    symbol: str
    action: str  # "BUY", "SELL", "CLOSE"
    size: float
    instrument_type: PositionType = PositionType.SPOT
    strategy: Optional[str] = None  # Strategy that generated this recommendation
    price: Optional[float] = None
    reasoning: str = ""
    urgency: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    estimated_cost: Optional[float] = None
    risk_reduction: Optional[Dict[str, float]] = None  # Expected risk reduction
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""
    total_value: float
    delta: float
    gamma: float
    theta: float
    vega: float
    unrealized_pnl: float
    var: float  # Value at Risk
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def total_greeks(self) -> Dict[str, float]:
        """Return all Greeks as a dictionary."""
        return {
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega
        }
    
    @property
    def pnl_percentage(self) -> float:
        """Calculate P&L as percentage of total value."""
        if self.total_value == 0:
            return 0.0
        return (self.unrealized_pnl / (self.total_value - self.unrealized_pnl)) * 100
