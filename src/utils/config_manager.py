"""
Configuration management utilities.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages application configuration from files and environment variables."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager."""
        self.config_path = config_path or Path("config.yaml")
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file and environment."""
        # Start with default configuration
        self._config = self._get_default_config()
        
        # Load from file if it exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        self._merge_configs(self._config, file_config)
            except Exception as e:
                print(f"Warning: Could not load config file {self.config_path}: {e}")
        
        # Override with environment variables
        self._apply_env_overrides()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'risk': {
                'delta_threshold': 0.1,
                'gamma_threshold': 0.05,
                'theta_threshold': 100,
                'vega_threshold': 50,
                'max_position_size': 1000000,
                'max_portfolio_value': 10000000
            },
            'market_data': {
                'provider': 'yfinance',
                'update_interval': 30,
                'cache_timeout': 300,
                'symbols': []
            },
            'strategies': {
                'delta_neutral': {
                    'enabled': True,
                    'cost_threshold': 0.02
                },
                'protective_put': {
                    'enabled': True,
                    'cost_threshold': 0.05
                },
                'collar': {
                    'enabled': True,
                    'cost_threshold': 0.03
                }
            },
            'telegram': {
                'bot_token': None,
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
            'logging': {
                'level': 'INFO',
                'file': 'logs/spot_hedging.log',
                'max_size': '10MB',
                'backup_count': 5
            },
            'database': {
                'url': 'sqlite:///spot_hedging.db',
                'echo': False
            }
        }
    
    def _merge_configs(self, base: Dict[str, Any], update: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        env_mappings = {
            'TELEGRAM_BOT_TOKEN': 'telegram.bot_token',
            'TELEGRAM_CHAT_ID': 'telegram.chat_id',
            'TELEGRAM_WEBHOOK_URL': 'telegram.webhook_url',
            'TELEGRAM_WEBHOOK_PORT': 'telegram.webhook_port',
            'LOG_LEVEL': 'logging.level',
            'DATABASE_URL': 'database.url',
            'RISK_DELTA_THRESHOLD': 'risk.delta_threshold',
            'RISK_GAMMA_THRESHOLD': 'risk.gamma_threshold',
            'MARKET_DATA_PROVIDER': 'market_data.provider',
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                self._set_nested_value(config_path, env_value)
    
    def _set_nested_value(self, key_path: str, value: Any):
        """Set nested configuration value using dot notation."""
        keys = key_path.split('.')
        current = self._config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Convert string values to appropriate types
        final_key = keys[-1]
        if isinstance(value, str):
            # Try to convert to appropriate type
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif '.' in value and value.replace('.', '').isdigit():
                value = float(value)
        
        current[final_key] = value
    
    def get_config(self) -> Dict[str, Any]:
        """Get the complete configuration."""
        return self._config.copy()
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key_path.split('.')
        current = self._config
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        """Set configuration value using dot notation."""
        self._set_nested_value(key_path, value)
    
    def save_config(self, path: Optional[Path] = None):
        """Save current configuration to file."""
        save_path = path or self.config_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False, indent=2)
    
    def reload_config(self):
        """Reload configuration from file."""
        self._load_config()
    
    def validate_config(self) -> bool:
        """Validate configuration for required fields."""
        required_fields = [
            'risk.delta_threshold',
            'risk.gamma_threshold',
            'market_data.provider'
        ]
        
        for field in required_fields:
            if self.get(field) is None:
                raise ValueError(f"Required configuration field missing: {field}")
        
        return True
