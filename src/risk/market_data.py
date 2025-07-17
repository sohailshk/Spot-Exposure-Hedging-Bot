"""
Market data provider for real-time and historical data.
"""

import asyncio
import yfinance as yf
import ccxt
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from abc import ABC, abstractmethod

from .models import MarketData, PositionType


class MarketDataProvider(ABC):
    """Abstract base class for market data providers."""
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get comprehensive market data for a symbol."""
        pass
    
    @abstractmethod
    async def get_historical_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical price data."""
        pass
    
    @abstractmethod
    async def get_options_chain(self, symbol: str) -> Optional[Dict]:
        """Get options chain data."""
        pass


class YahooFinanceProvider(MarketDataProvider):
    """Yahoo Finance data provider for stocks and some crypto."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from Yahoo Finance."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Try different price fields
            price = None
            for field in ['regularMarketPrice', 'currentPrice', 'price', 'bid', 'ask']:
                if field in info and info[field]:
                    price = float(info[field])
                    break
            
            if price is None:
                # Fallback to history
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
            
            if price and price > 0:
                self.logger.debug(f"Yahoo Finance price for {symbol}: ${price:.2f}")
                return price
            else:
                self.logger.warning(f"No valid price found for {symbol}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting Yahoo Finance price for {symbol}: {e}")
            return None
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Try different price fields
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('price')
            return float(price) if price else None
            
        except Exception as e:
            self.logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get comprehensive market data from Yahoo Finance."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Get basic price data with multiple fallbacks
            price = None
            for field in ['regularMarketPrice', 'currentPrice', 'price', 'previousClose']:
                if field in info and info[field]:
                    price = float(info[field])
                    break
            
            # If still no price, try history
            if price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
            
            if price is None or price <= 0:
                self.logger.warning(f"No valid price found for {symbol}")
                return None
            
            # Get other data with safe fallbacks
            bid = info.get('bid')
            ask = info.get('ask')
            volume = info.get('volume')
            implied_vol = info.get('impliedVolatility')
            
            return MarketData(
                symbol=symbol,
                price=float(price),
                bid=float(bid) if bid and bid > 0 else None,
                ask=float(ask) if ask and ask > 0 else None,
                volume=float(volume) if volume and volume > 0 else None,
                implied_volatility=float(implied_vol) if implied_vol and implied_vol > 0 else None,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching market data for {symbol}: {e}")
            # Return a basic MarketData with just price if we can get it
            try:
                price = await self.get_current_price(symbol)
                if price:
                    return MarketData(
                        symbol=symbol,
                        price=price,
                        timestamp=datetime.now()
                    )
            except:
                pass
            return None
    
    async def get_historical_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical price data from Yahoo Finance."""
        try:
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            hist = ticker.history(start=start_date, end=end_date, interval='1d')
            
            if hist.empty:
                return None
            
            # Standardize column names
            hist = hist.rename(columns={
                'Open': 'open',
                'High': 'high', 
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            return hist
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    async def get_options_chain(self, symbol: str) -> Optional[Dict]:
        """Get options chain from Yahoo Finance."""
        try:
            ticker = yf.Ticker(symbol)
            options_dates = ticker.options
            
            if not options_dates:
                return None
            
            options_data = {}
            
            # Get data for next few expiry dates
            for date in options_dates[:5]:  # Limit to first 5 expiries
                try:
                    chain = ticker.option_chain(date)
                    options_data[date] = {
                        'calls': chain.calls.to_dict('records'),
                        'puts': chain.puts.to_dict('records')
                    }
                except Exception as e:
                    self.logger.warning(f"Error fetching options for {date}: {e}")
                    continue
            
            return options_data if options_data else None
            
        except Exception as e:
            self.logger.error(f"Error fetching options chain for {symbol}: {e}")
            return None


class CCXTProvider(MarketDataProvider):
    """CCXT provider for cryptocurrency exchanges."""
    
    def __init__(self, exchange_name: str = 'binance', config: Optional[Dict] = None):
        """
        Initialize CCXT provider.
        
        Args:
            exchange_name: Name of the exchange (e.g., 'binance', 'bybit')
            config: Exchange configuration (API keys, etc.)
        """
        self.exchange_name = exchange_name
        self.logger = logging.getLogger(__name__)
        
        try:
            exchange_class = getattr(ccxt, exchange_name)
            self.exchange = exchange_class(config or {})
        except Exception as e:
            self.logger.error(f"Error initializing {exchange_name}: {e}")
            self.exchange = None
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from crypto exchange."""
        if not self.exchange:
            return None
        
        try:
            ticker = await self._safe_fetch_ticker(symbol)
            return ticker.get('last') if ticker else None
            
        except Exception as e:
            self.logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get comprehensive market data from crypto exchange."""
        if not self.exchange:
            return None
        
        try:
            ticker = await self._safe_fetch_ticker(symbol)
            
            if not ticker:
                return None
            
            return MarketData(
                symbol=symbol,
                price=ticker.get('last', 0),
                bid=ticker.get('bid'),
                ask=ticker.get('ask'),
                volume=ticker.get('baseVolume'),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching market data for {symbol}: {e}")
            return None
    
    async def get_historical_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical OHLCV data from crypto exchange."""
        if not self.exchange:
            return None
        
        try:
            # Calculate timeframe
            since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            # Fetch OHLCV data
            ohlcv = await self._safe_fetch_ohlcv(symbol, '1d', since)
            
            if not ohlcv:
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    async def get_options_chain(self, symbol: str) -> Optional[Dict]:
        """Get options chain (not supported by most crypto exchanges)."""
        self.logger.warning("Options chains not supported for crypto exchanges")
        return None
    
    async def _safe_fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """Safely fetch ticker data."""
        try:
            if hasattr(self.exchange, 'fetch_ticker'):
                return self.exchange.fetch_ticker(symbol)
            return None
        except Exception as e:
            self.logger.error(f"Error in fetch_ticker for {symbol}: {e}")
            return None
    
    async def _safe_fetch_ohlcv(self, symbol: str, timeframe: str, since: int) -> Optional[List]:
        """Safely fetch OHLCV data."""
        try:
            if hasattr(self.exchange, 'fetch_ohlcv'):
                return self.exchange.fetch_ohlcv(symbol, timeframe, since)
            return None
        except Exception as e:
            self.logger.error(f"Error in fetch_ohlcv for {symbol}: {e}")
            return None


class AggregatedDataProvider:
    """Aggregated data provider that combines multiple sources."""
    
    def __init__(self):
        self.providers = {
            'yahoo': YahooFinanceProvider(),
            'binance': CCXTProvider('binance'),
            'bybit': CCXTProvider('bybit')
        }
        self.logger = logging.getLogger(__name__)
        
        # Symbol routing rules
        self.routing_rules = {
            # Crypto symbols typically go to crypto exchanges
            'BTC/USDT': ['binance', 'bybit'],
            'ETH/USDT': ['binance', 'bybit'], 
            'BTC-USD': ['yahoo'],
            'ETH-USD': ['yahoo'],
            
            # Stock symbols go to Yahoo Finance
            'AAPL': ['yahoo'],
            'GOOGL': ['yahoo'],
            'TSLA': ['yahoo'],
            'SPY': ['yahoo'],
            'QQQ': ['yahoo'],
        }
    
    def _get_providers_for_symbol(self, symbol: str) -> List[str]:
        """Determine which providers to use for a symbol."""
        # Check exact match first
        if symbol in self.routing_rules:
            return self.routing_rules[symbol]
        
        # Check patterns
        if '/' in symbol and 'USDT' in symbol:
            return ['binance', 'bybit']
        elif '-USD' in symbol:
            return ['yahoo']
        else:
            # Default to Yahoo Finance for stocks
            return ['yahoo']
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from the best available provider."""
        provider_names = self._get_providers_for_symbol(symbol)
        
        for provider_name in provider_names:
            if provider_name in self.providers:
                try:
                    price = await self.providers[provider_name].get_current_price(symbol)
                    if price is not None:
                        return price
                except Exception as e:
                    self.logger.warning(f"Provider {provider_name} failed for {symbol}: {e}")
                    continue
        
        return None
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get market data from the best available provider."""
        provider_names = self._get_providers_for_symbol(symbol)
        
        for provider_name in provider_names:
            if provider_name in self.providers:
                try:
                    data = await self.providers[provider_name].get_market_data(symbol)
                    if data is not None:
                        return data
                except Exception as e:
                    self.logger.warning(f"Provider {provider_name} failed for {symbol}: {e}")
                    continue
        
        return None
    
    async def get_historical_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical data from the best available provider."""
        provider_names = self._get_providers_for_symbol(symbol)
        
        for provider_name in provider_names:
            if provider_name in self.providers:
                try:
                    data = await self.providers[provider_name].get_historical_data(symbol, days)
                    if data is not None and not data.empty:
                        return data
                except Exception as e:
                    self.logger.warning(f"Provider {provider_name} failed for {symbol}: {e}")
                    continue
        
        return None
    
    async def get_options_chain(self, symbol: str) -> Optional[Dict]:
        """Get options chain (primarily from Yahoo Finance)."""
        provider_names = self._get_providers_for_symbol(symbol)
        
        for provider_name in provider_names:
            if provider_name in self.providers:
                try:
                    data = await self.providers[provider_name].get_options_chain(symbol)
                    if data is not None:
                        return data
                except Exception as e:
                    self.logger.warning(f"Provider {provider_name} failed for {symbol}: {e}")
                    continue
        
        return None
    
    async def update_multiple_symbols(self, symbols: List[str]) -> Dict[str, MarketData]:
        """Update market data for multiple symbols concurrently."""
        tasks = []
        for symbol in symbols:
            task = asyncio.create_task(self.get_market_data(symbol))
            tasks.append((symbol, task))
        
        results = {}
        for symbol, task in tasks:
            try:
                data = await task
                if data:
                    results[symbol] = data
            except Exception as e:
                self.logger.error(f"Error updating {symbol}: {e}")
        
        return results


# Global market data provider instance
market_data_provider = AggregatedDataProvider()
