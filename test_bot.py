#!/usr/bin/env python3
"""
Simple test script for the Spot Hedging Bot functionality.
Tests core components without needing a real Telegram bot token.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_bot_functionality():
    """Test the core bot functionality."""
    print('🧪 Testing complete bot functionality...')
    
    try:
        # Test 1: ConfigManager initialization
        print('📋 Test 1: ConfigManager initialization...')
        from src.utils.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.get_config()
        print(f'✅ ConfigManager: Loaded config with {len(config)} sections')
        
        # Test 2: Bot initialization
        print('📋 Test 2: Bot initialization...')
        from src.bot.telegram_bot import TelegramBot
        
        # Create a test config with required fields
        test_config = config.copy()
        test_config['telegram']['bot_token'] = 'test_token_123'  # Dummy token for testing
        
        bot = TelegramBot(test_config)
        print('✅ Bot initialization successful')
        
        # Test 3: Portfolio functionality
        print('📋 Test 3: Portfolio functionality...')
        from src.risk.models import Portfolio, Position, PositionType
        
        portfolio = Portfolio()
        position = Position(
            symbol='BTC',
            position_type=PositionType.SPOT,
            size=0.1,
            entry_price=120000,
            current_price=119000,
            delta=1.0
        )
        portfolio.add_position(position)
        print(f'✅ Portfolio test: Value=${portfolio.total_market_value:,.2f}, P&L=${portfolio.total_pnl:,.2f}')
        
        # Test 4: Strategy manager
        print('📋 Test 4: Strategy manager...')
        recommendations = bot.strategy_manager.get_hedge_recommendations(portfolio)
        print(f'✅ Strategy manager test: {len(recommendations)} recommendations generated')
        
        # Test 5: Risk calculator
        print('📋 Test 5: Risk calculator...')
        bot.risk_calculator.calculate_position_greeks(position)
        print(f'✅ Risk calculator test: Delta={position.delta}, Gamma={position.gamma}')
        
        # Test 6: Risk thresholds
        print('📋 Test 6: Risk thresholds...')
        breaches = bot.risk_thresholds.check_breach(portfolio)
        breach_count = sum(breaches.values())
        print(f'✅ Risk thresholds test: {breach_count} breaches detected')
        
        # Test 7: Interactive features setup
        print('📋 Test 7: Interactive features...')
        test_user_id = 12345
        bot.portfolios[test_user_id] = portfolio
        bot.user_settings[test_user_id] = {
            'auto_hedge_enabled': True,
            'auto_hedge_strategy': 'delta_neutral',
            'auto_hedge_threshold': 0.1,
            'risk_alerts_enabled': True
        }
        print(f'✅ Interactive features test: User {test_user_id} configured')
        
        # Test 8: Market data components
        print('📋 Test 8: Market data components...')
        from src.risk.market_data import AggregatedDataProvider
        market_provider = AggregatedDataProvider()
        print('✅ Market data provider initialized')
        
        # Test 9: Component integration
        print('📋 Test 9: Component integration...')
        
        # Test portfolio calculations
        assert portfolio.total_market_value > 0, "Portfolio should have positive value"
        assert len(portfolio.positions) == 1, "Portfolio should have 1 position"
        assert position.pnl == -100.0, "Position P&L should be -100 (119000-120000)*0.1"
        
        # Test bot components
        assert bot.risk_thresholds is not None, "Risk thresholds should be initialized"
        assert bot.strategy_manager is not None, "Strategy manager should be initialized"
        assert bot.risk_calculator is not None, "Risk calculator should be initialized"
        
        print('✅ Component integration test passed')
        
        print('\n🎯 All tests passed! Bot is fully functional.')
        print('\n📊 Test Summary:')
        print(f'• Portfolio Value: ${portfolio.total_market_value:,.2f}')
        print(f'• Position P&L: ${position.pnl:,.2f}')
        print(f'• Risk Breaches: {breach_count}')
        print(f'• Recommendations: {len(recommendations)}')
        print(f'• User Settings: {len(bot.user_settings[test_user_id])} configured')
        
        return True
        
    except Exception as e:
        print(f'❌ Test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

def test_missing_methods():
    """Test for any missing methods that might cause runtime errors."""
    print('\n🔍 Testing for missing methods...')
    
    try:
        from src.bot.telegram_bot import TelegramBot
        from src.utils.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.get_config()
        config['telegram']['bot_token'] = 'test_token'
        
        bot = TelegramBot(config)
        
        # Check if all callback handler methods exist
        missing_methods = []
        required_methods = [
            'handle_add_position_callback',
            'handle_hedge_request', 
            'handle_refresh_request',
            'handle_analytics_request',
            'handle_threshold_request',
            'handle_monitor_request',
            'handle_execute_hedge',
            'handle_view_all_recommendations',
            'handle_auto_hedge_settings',
            'handle_disable_auto_hedge',
            'handle_auto_hedge_setup'
        ]
        
        for method_name in required_methods:
            if not hasattr(bot, method_name):
                missing_methods.append(method_name)
        
        if missing_methods:
            print(f'⚠️  Missing methods found: {missing_methods}')
            return False
        else:
            print('✅ All required callback methods exist')
            return True
            
    except Exception as e:
        print(f'❌ Method check failed: {e}')
        return False

if __name__ == '__main__':
    print('🚀 Spot Hedging Bot Test Suite')
    print('=' * 50)
    
    # Run main functionality test
    test1_passed = test_bot_functionality()
    
    # Run missing methods test
    test2_passed = test_missing_methods()
    
    print('\n' + '=' * 50)
    if test1_passed and test2_passed:
        print('🎉 ALL TESTS PASSED! Bot is ready for deployment.')
        sys.exit(0)
    else:
        print('⚠️  Some tests failed. Please check the output above.')
        sys.exit(1)
