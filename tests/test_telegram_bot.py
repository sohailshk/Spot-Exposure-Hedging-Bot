"""
Test suite for the Telegram bot functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import with graceful fallback for missing dependencies
try:
    from src.bot.telegram_bot import TelegramBot
    from src.bot.utils import MessageFormatter, KeyboardBuilder, TaskManager, RateLimiter, ValidationHelpers
    from src.bot.config import BotConfig, create_default_bot_config
    from src.risk.models import Portfolio, Position, PositionType, RiskThresholds
    
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Telegram dependencies not available: {e}")
    TELEGRAM_AVAILABLE = False
    
    # Create mock classes for testing
    class TelegramBot:
        pass
    class MessageFormatter:
        pass
    class KeyboardBuilder:
        pass
    class TaskManager:
        pass
    class RateLimiter:
        pass
    class ValidationHelpers:
        pass
    class BotConfig:
        pass
    def create_default_bot_config():
        return {}


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")
class TestMessageFormatter:
    """Test message formatting utilities."""
    
    def test_format_currency(self):
        """Test currency formatting."""
        assert MessageFormatter.format_currency(1234.56) == "$1,234.56"
        assert MessageFormatter.format_currency(-1234.56) == "-$1,234.56"
        assert MessageFormatter.format_currency(0) == "$0.00"
        assert MessageFormatter.format_currency(1000000) == "$1,000,000.00"
    
    def test_format_percentage(self):
        """Test percentage formatting."""
        assert MessageFormatter.format_percentage(0.1234) == "+12.34%"
        assert MessageFormatter.format_percentage(-0.0567) == "-5.67%"
        assert MessageFormatter.format_percentage(0) == "+0.00%"
    
    def test_format_large_number(self):
        """Test large number formatting."""
        assert MessageFormatter.format_large_number(1234) == "1.2K"
        assert MessageFormatter.format_large_number(1234567) == "1.2M"
        assert MessageFormatter.format_large_number(1234567890) == "1.2B"
        assert MessageFormatter.format_large_number(500) == "500"
    
    def test_get_risk_emoji(self):
        """Test risk status emoji."""
        assert MessageFormatter.get_risk_emoji(True) == "❌"
        assert MessageFormatter.get_risk_emoji(False) == "✅"
    
    def test_get_pnl_emoji(self):
        """Test P&L emoji."""
        assert MessageFormatter.get_pnl_emoji(100) == "📈"
        assert MessageFormatter.get_pnl_emoji(-100) == "📉"
        assert MessageFormatter.get_pnl_emoji(0) == "➡️"
    
    def test_get_urgency_emoji(self):
        """Test urgency emoji."""
        assert MessageFormatter.get_urgency_emoji("high") == "🔴"
        assert MessageFormatter.get_urgency_emoji("medium") == "🟡"
        assert MessageFormatter.get_urgency_emoji("low") == "🟢"
        assert MessageFormatter.get_urgency_emoji("unknown") == "⚪"


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")
class TestKeyboardBuilder:
    """Test inline keyboard builders."""
    
    def test_portfolio_keyboard(self):
        """Test portfolio keyboard creation."""
        keyboard = KeyboardBuilder.portfolio_keyboard()
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 2
        assert len(keyboard.inline_keyboard[0]) == 2
        assert len(keyboard.inline_keyboard[1]) == 2
    
    def test_hedge_status_keyboard(self):
        """Test hedge status keyboard creation."""
        # Without recommendations
        keyboard = KeyboardBuilder.hedge_status_keyboard(False)
        assert len(keyboard.inline_keyboard) == 2
        
        # With recommendations
        keyboard = KeyboardBuilder.hedge_status_keyboard(True)
        assert len(keyboard.inline_keyboard) == 3
    
    def test_position_keyboard(self):
        """Test position-specific keyboard."""
        keyboard = KeyboardBuilder.position_keyboard("AAPL")
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 2
        
        # Check callback data contains symbol
        refresh_button = keyboard.inline_keyboard[0][0]
        assert "AAPL" in refresh_button.callback_data
    
    def test_risk_alert_keyboard(self):
        """Test risk alert keyboard."""
        keyboard = KeyboardBuilder.risk_alert_keyboard()
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 2


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")
class TestTaskManager:
    """Test background task management."""
    
    @pytest.fixture
    def task_manager(self):
        """Create task manager instance."""
        return TaskManager()
    
    @pytest.mark.asyncio
    async def test_create_task(self, task_manager):
        """Test task creation."""
        async def dummy_task():
            await asyncio.sleep(0.1)
        
        task = task_manager.create_task("test_task", dummy_task())
        assert "test_task" in task_manager.tasks
        assert not task.done()
        
        # Test task replacement
        task2 = task_manager.create_task("test_task", dummy_task())
        # Give a moment for cancellation to register
        await asyncio.sleep(0.01)
        assert task.cancelled()
        assert task2 is task_manager.tasks["test_task"]
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, task_manager):
        """Test task cancellation."""
        async def dummy_task():
            await asyncio.sleep(1)
        
        task_manager.create_task("test_task", dummy_task())
        assert task_manager.cancel_task("test_task")
        assert "test_task" not in task_manager.tasks
        
        # Test cancelling non-existent task
        assert not task_manager.cancel_task("non_existent")
    
    @pytest.mark.asyncio
    async def test_cancel_user_tasks(self, task_manager):
        """Test cancelling user-specific tasks."""
        async def dummy_task():
            await asyncio.sleep(1)
        
        task_manager.create_task("user_123_monitor", dummy_task())
        task_manager.create_task("user_123_alert", dummy_task())
        task_manager.create_task("user_456_monitor", dummy_task())
        
        task_manager.cancel_user_tasks(123)
        
        assert "user_123_monitor" not in task_manager.tasks
        assert "user_123_alert" not in task_manager.tasks
        assert "user_456_monitor" in task_manager.tasks
    
    @pytest.mark.asyncio
    async def test_cancel_all_tasks(self, task_manager):
        """Test cancelling all tasks."""
        async def dummy_task():
            await asyncio.sleep(1)
        
        task_manager.create_task("task1", dummy_task())
        task_manager.create_task("task2", dummy_task())
        
        task_manager.cancel_all_tasks()
        assert len(task_manager.tasks) == 0


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")
class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_rate_limiting(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # Should allow first 3 requests
        assert limiter.is_allowed(123)
        assert limiter.is_allowed(123)
        assert limiter.is_allowed(123)
        
        # Should reject 4th request
        assert not limiter.is_allowed(123)
        
        # Different user should be allowed
        assert limiter.is_allowed(456)
    
    def test_rate_limit_reset(self):
        """Test rate limit window reset."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        
        # Use up the limit
        assert limiter.is_allowed(123)
        assert limiter.is_allowed(123)
        assert not limiter.is_allowed(123)
        
        # Wait for window to reset
        import time
        time.sleep(1.1)
        
        # Should be allowed again
        assert limiter.is_allowed(123)
    
    def test_get_reset_time(self):
        """Test getting reset time."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # No requests yet
        assert limiter.get_reset_time(123) is None
        
        # Make a request
        limiter.is_allowed(123)
        reset_time = limiter.get_reset_time(123)
        assert reset_time is not None
        assert reset_time > datetime.now()


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")
class TestValidationHelpers:
    """Test input validation helpers."""
    
    def test_validate_symbol(self):
        """Test symbol validation."""
        assert ValidationHelpers.validate_symbol("AAPL")
        assert ValidationHelpers.validate_symbol("BTC-USD")
        assert ValidationHelpers.validate_symbol("SPY_CALL_420")
        
        assert not ValidationHelpers.validate_symbol("")
        assert not ValidationHelpers.validate_symbol("A")
        assert not ValidationHelpers.validate_symbol("INVALID@SYMBOL")
    
    def test_validate_size(self):
        """Test size validation."""
        valid, size = ValidationHelpers.validate_size("1000")
        assert valid and size == 1000.0
        
        valid, size = ValidationHelpers.validate_size("0.5")
        assert valid and size == 0.5
        
        valid, size = ValidationHelpers.validate_size("-500")
        assert valid and size == -500.0
        
        # Too small
        valid, size = ValidationHelpers.validate_size("0.0001")
        assert not valid
        
        # Invalid format
        valid, size = ValidationHelpers.validate_size("invalid")
        assert not valid
    
    def test_validate_price(self):
        """Test price validation."""
        valid, price = ValidationHelpers.validate_price("150.50")
        assert valid and price == 150.50
        
        valid, price = ValidationHelpers.validate_price("0.01")
        assert valid and price == 0.01
        
        # Negative price
        valid, price = ValidationHelpers.validate_price("-10")
        assert not valid
        
        # Zero price
        valid, price = ValidationHelpers.validate_price("0")
        assert not valid
        
        # Invalid format
        valid, price = ValidationHelpers.validate_price("invalid")
        assert not valid
    
    def test_validate_threshold(self):
        """Test threshold validation."""
        valid, threshold = ValidationHelpers.validate_threshold("0.1")
        assert valid and threshold == 0.1
        
        valid, threshold = ValidationHelpers.validate_threshold("0.001")
        assert valid and threshold == 0.001
        
        valid, threshold = ValidationHelpers.validate_threshold("1.0")
        assert valid and threshold == 1.0
        
        # Too small
        valid, threshold = ValidationHelpers.validate_threshold("0.0001")
        assert not valid
        
        # Too large
        valid, threshold = ValidationHelpers.validate_threshold("1.5")
        assert not valid
        
        # Invalid format
        valid, threshold = ValidationHelpers.validate_threshold("invalid")
        assert not valid
    
    def test_parse_add_position_args(self):
        """Test parsing add position arguments."""
        # Valid arguments
        valid, result = ValidationHelpers.parse_add_position_args(["AAPL", "1000", "150.50"])
        assert valid
        assert result["symbol"] == "AAPL"
        assert result["size"] == 1000.0
        assert result["price"] == 150.50
        
        # Not enough arguments
        valid, result = ValidationHelpers.parse_add_position_args(["AAPL", "1000"])
        assert not valid
        assert "Not enough arguments" in result["error"]
        
        # Invalid symbol
        valid, result = ValidationHelpers.parse_add_position_args(["INVALID@", "1000", "150.50"])
        assert not valid
        assert "Invalid symbol" in result["error"]
        
        # Invalid size
        valid, result = ValidationHelpers.parse_add_position_args(["AAPL", "invalid", "150.50"])
        assert not valid
        assert "Invalid position size" in result["error"]
        
        # Invalid price
        valid, result = ValidationHelpers.parse_add_position_args(["AAPL", "1000", "-10"])
        assert not valid
        assert "Invalid price" in result["error"]


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")
class TestBotConfig:
    """Test bot configuration management."""
    
    def test_default_config_creation(self):
        """Test default configuration creation."""
        config = create_default_bot_config()
        assert 'telegram' in config
        assert 'bot_features' in config
        assert 'display' in config
        assert 'limits' in config
    
    def test_bot_config_validation(self):
        """Test bot configuration validation."""
        # Valid config
        config_data = create_default_bot_config()
        config_data['telegram']['bot_token'] = 'test_token'
        config_data['risk'] = {
            'delta_threshold': 0.1,
            'gamma_threshold': 0.05
        }
        
        bot_config = BotConfig(config_data)
        assert bot_config.bot_token == 'test_token'
        
        # Missing required config
        incomplete_config = {'telegram': {}}
        with pytest.raises(ValueError, match="Missing required configuration"):
            BotConfig(incomplete_config)
    
    def test_config_properties(self):
        """Test configuration property access."""
        config_data = create_default_bot_config()
        config_data['telegram']['bot_token'] = 'test_token'
        config_data['telegram']['admin_users'] = [123, 456]
        config_data['telegram']['chat_id'] = 'test_chat'
        config_data['risk'] = {
            'delta_threshold': 0.1,
            'gamma_threshold': 0.05
        }
        
        bot_config = BotConfig(config_data)
        
        assert bot_config.bot_token == 'test_token'
        assert bot_config.admin_users == [123, 456]
        assert bot_config.chat_id == 'test_chat'
        assert bot_config.rate_limit_requests == 10
        assert bot_config.rate_limit_window == 60
        assert bot_config.alert_cooldown_minutes == 5
        assert bot_config.monitoring_interval == 30


@pytest.mark.skipif(not TELEGRAM_AVAILABLE, reason="Telegram dependencies not available")
class TestTelegramBot:
    """Test main Telegram bot functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = create_default_bot_config()
        config['telegram']['bot_token'] = 'test_token'
        config['risk'] = {
            'delta_threshold': 0.1,
            'gamma_threshold': 0.05,
            'theta_threshold': 100,
            'vega_threshold': 50
        }
        return config
    
    @pytest.fixture
    def bot(self, mock_config):
        """Create bot instance with mock config."""
        return TelegramBot(mock_config)
    
    def test_bot_initialization(self, bot):
        """Test bot initialization."""
        assert bot.bot_token == 'test_token'
        assert bot.admin_users == set()
        assert isinstance(bot.portfolios, dict)
        assert isinstance(bot.user_settings, dict)
        assert isinstance(bot.monitoring_tasks, dict)
    
    @pytest.mark.asyncio
    async def test_start_command(self, bot):
        """Test /start command handling."""
        # Mock update and context
        update = Mock()
        update.effective_user.id = 123
        update.effective_user.first_name = "TestUser"
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        
        await bot.start_command(update, context)
        
        # Check user was initialized
        assert 123 in bot.portfolios
        assert 123 in bot.user_settings
        
        # Check reply was sent
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Welcome to Spot Hedging Bot, TestUser!" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_monitor_risk_command_invalid_args(self, bot):
        """Test monitor risk command with invalid arguments."""
        update = Mock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        context.args = ["AAPL"]  # Missing size and threshold
        
        await bot.monitor_risk_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_portfolio_command_empty(self, bot):
        """Test portfolio command with empty portfolio."""
        update = Mock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        
        await bot.portfolio_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Portfolio is Empty" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_help_command(self, bot):
        """Test help command."""
        update = Mock()
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        
        await bot.help_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "COMMAND REFERENCE" in call_args[0][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
