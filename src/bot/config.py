"""
Configuration management for the Telegram bot.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional


class BotConfig:
    """Bot-specific configuration management."""
    
    def __init__(self, base_config: Dict[str, Any]):
        """Initialize with base configuration."""
        self.base_config = base_config
        self._validate_config()
    
    def _validate_config(self):
        """Validate required configuration parameters."""
        required_keys = [
            'telegram.bot_token',
            'risk.delta_threshold',
            'risk.gamma_threshold',
        ]
        
        for key in required_keys:
            if not self._get_nested_value(key):
                raise ValueError(f"Missing required configuration: {key}")
    
    def _get_nested_value(self, key_path: str) -> Any:
        """Get nested configuration value using dot notation."""
        keys = key_path.split('.')
        value = self.base_config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    @property
    def bot_token(self) -> str:
        """Get Telegram bot token."""
        token = (
            os.getenv('TELEGRAM_BOT_TOKEN') or 
            self._get_nested_value('telegram.bot_token')
        )
        if not token:
            raise ValueError("Telegram bot token not configured")
        return token
    
    @property
    def admin_users(self) -> list:
        """Get list of admin user IDs."""
        return self._get_nested_value('telegram.admin_users') or []
    
    @property
    def chat_id(self) -> Optional[str]:
        """Get default chat ID."""
        return (
            os.getenv('TELEGRAM_CHAT_ID') or 
            self._get_nested_value('telegram.chat_id')
        )
    
    @property
    def webhook_url(self) -> Optional[str]:
        """Get webhook URL for production deployment."""
        return (
            os.getenv('TELEGRAM_WEBHOOK_URL') or 
            self._get_nested_value('telegram.webhook_url')
        )
    
    @property
    def webhook_port(self) -> int:
        """Get webhook port."""
        return int(
            os.getenv('TELEGRAM_WEBHOOK_PORT') or 
            self._get_nested_value('telegram.webhook_port') or 
            8443
        )
    
    @property
    def rate_limit_requests(self) -> int:
        """Get rate limit max requests."""
        return int(
            self._get_nested_value('telegram.rate_limit.max_requests') or 10
        )
    
    @property
    def rate_limit_window(self) -> int:
        """Get rate limit window in seconds."""
        return int(
            self._get_nested_value('telegram.rate_limit.window_seconds') or 60
        )
    
    @property
    def alert_cooldown_minutes(self) -> int:
        """Get alert cooldown in minutes."""
        return int(
            self._get_nested_value('telegram.alert_cooldown_minutes') or 5
        )
    
    @property
    def monitoring_interval(self) -> int:
        """Get monitoring interval in seconds."""
        return int(
            self._get_nested_value('telegram.monitoring_interval_seconds') or 30
        )
    
    @property
    def max_positions_per_user(self) -> int:
        """Get maximum positions per user."""
        return int(
            self._get_nested_value('telegram.max_positions_per_user') or 50
        )
    
    @property
    def enable_notifications(self) -> bool:
        """Check if notifications are enabled."""
        return bool(
            self._get_nested_value('telegram.enable_notifications') != False
        )
    
    @property
    def enable_auto_hedge(self) -> bool:
        """Check if auto-hedge is enabled by default."""
        return bool(
            self._get_nested_value('telegram.enable_auto_hedge') == True
        )
    
    def get_risk_config(self) -> Dict[str, Any]:
        """Get risk configuration."""
        return self._get_nested_value('risk') or {}
    
    def get_market_data_config(self) -> Dict[str, Any]:
        """Get market data configuration."""
        return self._get_nested_value('market_data') or {}
    
    def get_strategy_config(self) -> Dict[str, Any]:
        """Get strategy configuration."""
        return self._get_nested_value('strategies') or {}


def create_default_bot_config() -> Dict[str, Any]:
    """Create default bot configuration."""
    return {
        'telegram': {
            'bot_token': None,  # Must be set via environment or config
            'admin_users': [],
            'chat_id': None,
            'webhook_url': None,
            'webhook_port': 8443,
            'rate_limit': {
                'max_requests': 10,
                'window_seconds': 60
            },
            'alert_cooldown_minutes': 5,
            'monitoring_interval_seconds': 30,
            'max_positions_per_user': 50,
            'enable_notifications': True,
            'enable_auto_hedge': False
        },
        'bot_features': {
            'enable_portfolio_management': True,
            'enable_risk_monitoring': True,
            'enable_auto_hedging': True,
            'enable_analytics': True,
            'enable_history': True,
            'enable_settings': True
        },
        'display': {
            'currency_symbol': '$',
            'decimal_places': 2,
            'use_emoji': True,
            'compact_mode': False,
            'timezone': 'UTC'
        },
        'limits': {
            'max_message_length': 4000,
            'max_portfolio_value': 10000000,  # $10M
            'min_position_size': 0.001,
            'max_hedge_cost_ratio': 0.1  # 10% of position value
        }
    }


def load_bot_config(config_path: Optional[Path] = None) -> BotConfig:
    """Load bot configuration from file and environment."""
    try:
        # Try to load from main config manager first
        from ..utils.config_manager import ConfigManager
        config_manager = ConfigManager(config_path)
        base_config = config_manager.get_config()
    except ImportError:
        # Fallback to default configuration
        base_config = create_default_bot_config()
    
    return BotConfig(base_config)
