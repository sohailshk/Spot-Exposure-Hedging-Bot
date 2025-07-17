# validation_test.py - Test the fixed Telegram bot components
import sys
import os
import asyncio
import logging

# Set up path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test if all required imports work."""
    print("🧪 Testing imports...")
    
    # Test CCXT
    try:
        import ccxt
        exchange = ccxt.binance()
        print("✅ CCXT import successful")
        CCXT_OK = True
    except ImportError:
        print("❌ CCXT not available")
        CCXT_OK = False
    
    # Test Telegram
    try:
        from telegram import Update
        print("✅ Telegram import successful")
        TELEGRAM_OK = True
    except ImportError:
        print("❌ Telegram not available")
        TELEGRAM_OK = False
    
    # Test our components
    try:
        from src.risk.models import Portfolio, Position, RiskThresholds
        from src.risk.calculator import RiskCalculator
        from src.risk.market_data import market_data_provider
        print("✅ Risk management components import successful")
        COMPONENTS_OK = True
    except ImportError as e:
        print(f"❌ Risk components import failed: {e}")
        COMPONENTS_OK = False
    
    return CCXT_OK, TELEGRAM_OK, COMPONENTS_OK

async def test_price_fetching():
    """Test price fetching functionality."""
    print("\n🧪 Testing price fetching...")
    
    # Test CCXT directly
    try:
        import ccxt
        exchange = ccxt.binance()
        ticker = exchange.fetch_ticker('BTC/USDT')
        btc_price = ticker['last']
        print(f"✅ CCXT BTC price: ${btc_price:,.2f}")
    except Exception as e:
        print(f"❌ CCXT price fetch failed: {e}")
        return False
    
    # Test our market data provider
    try:
        from src.risk.market_data import market_data_provider
        price = await market_data_provider.get_current_price('BTC-USD')
        if price:
            print(f"✅ Market data provider BTC price: ${price:,.2f}")
        else:
            print("⚠️ Market data provider returned None")
    except Exception as e:
        print(f"❌ Market data provider failed: {e}")
    
    return True

def test_risk_calculator():
    """Test risk calculation components."""
    print("\n🧪 Testing risk calculator...")
    
    try:
        from src.risk.calculator import RiskCalculator
        from src.risk.models import Portfolio, Position, PositionType, MarketData
        from datetime import datetime
        
        # Create test portfolio
        portfolio = Portfolio()
        position = Position(
            symbol="BTC",
            size=10000,
            entry_price=45000,
            current_price=118000,  # Add current_price
            position_type=PositionType.SPOT  # Use SPOT instead of LONG
        )
        portfolio.add_position(position)
        
        # Create market data
        market_data = MarketData(
            symbol="BTC",
            price=118000,  # Current price from your test
            timestamp=datetime.now()
        )
        
        # Calculate risk
        calc = RiskCalculator()
        risk_metrics = calc.calculate_portfolio_risk(portfolio, market_data)
        
        print(f"✅ Risk calculation successful:")
        print(f"   Total Value: ${risk_metrics.total_value:,.2f}")
        print(f"   Unrealized P&L: ${risk_metrics.unrealized_pnl:,.2f}")
        print(f"   Delta: {risk_metrics.delta:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Risk calculation failed: {e}")
        return False

def test_strategy_manager():
    """Test strategy manager."""
    print("\n🧪 Testing strategy manager...")
    
    try:
        from src.strategies.strategy_manager import StrategyManager
        from src.risk.models import RiskThresholds, Portfolio
        
        # Create strategy manager
        thresholds = RiskThresholds()
        strategy_manager = StrategyManager(thresholds)
        
        # Test with empty portfolio
        portfolio = Portfolio()
        recommendations = strategy_manager.get_hedge_recommendations(portfolio)
        
        print(f"✅ Strategy manager created successfully")
        print(f"   Recommendations for empty portfolio: {len(recommendations) if recommendations else 0}")
        
        # Test with a position
        from src.risk.models import Position, PositionType
        position = Position(
            symbol="BTC",
            size=1000,
            entry_price=45000,
            current_price=118000,
            position_type=PositionType.SPOT
        )
        portfolio.add_position(position)
        recommendations = strategy_manager.get_hedge_recommendations(portfolio)
        print(f"   Recommendations with BTC position: {len(recommendations) if recommendations else 0}")
        
        return True
        
    except Exception as e:
        print(f"❌ Strategy manager test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting validation tests for improved Telegram bot...\n")
    
    # Test 1: Imports
    ccxt_ok, telegram_ok, components_ok = test_imports()
    
    # Test 2: Price fetching
    if ccxt_ok:
        price_ok = await test_price_fetching()
    else:
        price_ok = False
        print("⏭️ Skipping price test (CCXT not available)")
    
    # Test 3: Risk calculator
    if components_ok:
        risk_ok = test_risk_calculator()
        strategy_ok = test_strategy_manager()
    else:
        risk_ok = False
        strategy_ok = False
        print("⏭️ Skipping component tests (imports failed)")
    
    # Summary
    print(f"\n📊 Test Results Summary:")
    print(f"   CCXT Integration: {'✅' if ccxt_ok else '❌'}")
    print(f"   Telegram Bot: {'✅' if telegram_ok else '❌'}")
    print(f"   Risk Components: {'✅' if components_ok else '❌'}")
    print(f"   Price Fetching: {'✅' if price_ok else '❌'}")
    print(f"   Risk Calculator: {'✅' if risk_ok else '❌'}")
    print(f"   Strategy Manager: {'✅' if strategy_ok else '❌'}")
    
    total_tests = 6
    passed_tests = sum([ccxt_ok, telegram_ok, components_ok, price_ok, risk_ok, strategy_ok])
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests >= 4:
        print("\n✅ System ready for testing! The bot should work with real data.")
        print("\nNext steps:")
        print("1. Run: python teltest.py")
        print("2. Test commands: /start, /monitor_risk BTC 10000 0.1")
        print("3. Click the interactive buttons")
        print("4. Verify real prices are shown")
    else:
        print("\n❌ System needs more fixes before testing.")
        print("Please install missing dependencies:")
        if not ccxt_ok:
            print("   pip install ccxt")
        if not telegram_ok:
            print("   pip install python-telegram-bot")

if __name__ == "__main__":
    asyncio.run(main())
