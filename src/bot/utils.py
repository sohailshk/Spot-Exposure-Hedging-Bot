"""
Bot-specific utilities and helpers.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode


class MessageFormatter:
    """Utility class for formatting Telegram messages."""
    
    @staticmethod
    def format_currency(amount: float) -> str:
        """Format currency with proper commas and signs."""
        if amount >= 0:
            return f"${amount:,.2f}"
        else:
            return f"-${abs(amount):,.2f}"
    
    @staticmethod
    def format_percentage(value: float) -> str:
        """Format percentage with proper sign."""
        if value >= 0:
            return f"+{value:.2%}"
        else:
            return f"{value:.2%}"
    
    @staticmethod
    def format_large_number(value: float) -> str:
        """Format large numbers with K/M/B suffixes."""
        if abs(value) >= 1e9:
            return f"{value/1e9:.1f}B"
        elif abs(value) >= 1e6:
            return f"{value/1e6:.1f}M"
        elif abs(value) >= 1e3:
            return f"{value/1e3:.1f}K"
        else:
            return f"{value:.0f}"
    
    @staticmethod
    def get_risk_emoji(is_breach: bool) -> str:
        """Get appropriate emoji for risk status."""
        return "❌" if is_breach else "✅"
    
    @staticmethod
    def get_pnl_emoji(pnl: float) -> str:
        """Get appropriate emoji for P&L."""
        if pnl > 0:
            return "📈"
        elif pnl < 0:
            return "📉"
        else:
            return "➡️"
    
    @staticmethod
    def get_urgency_emoji(urgency: str) -> str:
        """Get emoji for hedge urgency."""
        urgency_map = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }
        return urgency_map.get(urgency.lower(), '⚪')


class KeyboardBuilder:
    """Utility class for building inline keyboards."""
    
    @staticmethod
    def portfolio_keyboard() -> InlineKeyboardMarkup:
        """Create portfolio action keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("⚖️ Hedge Analysis", callback_data="hedge_status"),
                InlineKeyboardButton("📈 Analytics", callback_data="analytics")
            ],
            [
                InlineKeyboardButton("➕ Add Position", callback_data="add_position"),
                InlineKeyboardButton("🔄 Refresh", callback_data="portfolio")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def hedge_status_keyboard(has_recommendations: bool = False) -> InlineKeyboardMarkup:
        """Create hedge status action keyboard."""
        keyboard = []
        
        if has_recommendations:
            keyboard.append([
                InlineKeyboardButton("⚖️ Execute Top Hedge", callback_data="execute_top_hedge"),
                InlineKeyboardButton("📋 View All Recommendations", callback_data="view_all_recs")
            ])
        
        keyboard.extend([
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_hedge_status"),
                InlineKeyboardButton("📈 View Analytics", callback_data="analytics")
            ],
            [
                InlineKeyboardButton("📊 Portfolio", callback_data="portfolio"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings")
            ]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def position_keyboard(symbol: str) -> InlineKeyboardMarkup:
        """Create position-specific action keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data=f"refresh_{symbol}"),
                InlineKeyboardButton("⚖️ Hedge Now", callback_data=f"hedge_{symbol}")
            ],
            [
                InlineKeyboardButton("📊 View Analytics", callback_data=f"analytics_{symbol}"),
                InlineKeyboardButton("⚙️ Adjust Threshold", callback_data=f"threshold_{symbol}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def risk_alert_keyboard() -> InlineKeyboardMarkup:
        """Create risk alert action keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("⚖️ View Hedge Recommendations", callback_data="hedge_status"),
                InlineKeyboardButton("📊 Portfolio Details", callback_data="portfolio")
            ],
            [
                InlineKeyboardButton("🔄 Enable Auto-Hedge", callback_data="auto_hedge_setup")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def settings_keyboard() -> InlineKeyboardMarkup:
        """Create settings menu keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("⚖️ Risk Thresholds", callback_data="settings_risk"),
                InlineKeyboardButton("🔔 Notifications", callback_data="settings_notifications")
            ],
            [
                InlineKeyboardButton("🤖 Auto-Hedge", callback_data="settings_auto_hedge"),
                InlineKeyboardButton("📊 Display", callback_data="settings_display")
            ],
            [
                InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


class TaskManager:
    """Utility class for managing background tasks."""
    
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
    
    def create_task(self, name: str, coro) -> asyncio.Task:
        """Create and register a new task."""
        if name in self.tasks:
            self.tasks[name].cancel()
        
        task = asyncio.create_task(coro)
        self.tasks[name] = task
        return task
    
    def cancel_task(self, name: str) -> bool:
        """Cancel a specific task."""
        if name in self.tasks:
            self.tasks[name].cancel()
            del self.tasks[name]
            return True
        return False
    
    def cancel_user_tasks(self, user_id: int):
        """Cancel all tasks for a specific user."""
        user_tasks = [name for name in self.tasks.keys() if name.startswith(f"user_{user_id}_")]
        for task_name in user_tasks:
            self.cancel_task(task_name)
    
    def cancel_all_tasks(self):
        """Cancel all tasks."""
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()
    
    def get_task_count(self) -> int:
        """Get number of active tasks."""
        return len([task for task in self.tasks.values() if not task.done()])


class RateLimiter:
    """Simple rate limiter for bot commands."""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[int, List[datetime]] = {}
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to make a request."""
        now = datetime.now()
        
        # Initialize user history
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # Clean old requests
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id] if req_time > cutoff
        ]
        
        # Check limit
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[user_id].append(now)
        return True
    
    def get_reset_time(self, user_id: int) -> Optional[datetime]:
        """Get when the rate limit resets for a user."""
        if user_id not in self.requests or not self.requests[user_id]:
            return None
        
        oldest_request = min(self.requests[user_id])
        return oldest_request + timedelta(seconds=self.window_seconds)


class UserState:
    """Manage user conversation state for multi-step interactions."""
    
    def __init__(self):
        self.states: Dict[int, Dict] = {}
    
    def set_state(self, user_id: int, state: str, data: Dict = None):
        """Set user state."""
        if user_id not in self.states:
            self.states[user_id] = {}
        
        self.states[user_id]['current_state'] = state
        self.states[user_id]['data'] = data or {}
        self.states[user_id]['timestamp'] = datetime.now()
    
    def get_state(self, user_id: int) -> Optional[Tuple[str, Dict]]:
        """Get user state."""
        if user_id not in self.states:
            return None
        
        state_info = self.states[user_id]
        
        # Check if state is expired (older than 10 minutes)
        if datetime.now() - state_info['timestamp'] > timedelta(minutes=10):
            self.clear_state(user_id)
            return None
        
        return state_info['current_state'], state_info['data']
    
    def clear_state(self, user_id: int):
        """Clear user state."""
        if user_id in self.states:
            del self.states[user_id]
    
    def update_data(self, user_id: int, data: Dict):
        """Update state data without changing state."""
        if user_id in self.states:
            self.states[user_id]['data'].update(data)
            self.states[user_id]['timestamp'] = datetime.now()


class ValidationHelpers:
    """Helper functions for input validation."""
    
    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """Validate trading symbol format."""
        if not symbol or len(symbol) < 2:
            return False
        
        # Allow alphanumeric characters, dashes, and underscores
        return symbol.replace('-', '').replace('_', '').isalnum()
    
    @staticmethod
    def validate_size(size_str: str) -> Tuple[bool, Optional[float]]:
        """Validate position size."""
        try:
            size = float(size_str)
            if abs(size) < 0.001:
                return False, None
            return True, size
        except ValueError:
            return False, None
    
    @staticmethod
    def validate_price(price_str: str) -> Tuple[bool, Optional[float]]:
        """Validate price."""
        try:
            price = float(price_str)
            if price <= 0:
                return False, None
            return True, price
        except ValueError:
            return False, None
    
    @staticmethod
    def validate_threshold(threshold_str: str) -> Tuple[bool, Optional[float]]:
        """Validate risk threshold."""
        try:
            threshold = float(threshold_str)
            if not 0.001 <= threshold <= 1.0:
                return False, None
            return True, threshold
        except ValueError:
            return False, None
    
    @staticmethod
    def parse_add_position_args(args: List[str]) -> Tuple[bool, Dict]:
        """Parse arguments for add position command."""
        if len(args) < 3:
            return False, {"error": "Not enough arguments"}
        
        symbol = args[0].upper()
        if not ValidationHelpers.validate_symbol(symbol):
            return False, {"error": "Invalid symbol format"}
        
        size_valid, size = ValidationHelpers.validate_size(args[1])
        if not size_valid:
            return False, {"error": "Invalid position size"}
        
        price_valid, price = ValidationHelpers.validate_price(args[2])
        if not price_valid:
            return False, {"error": "Invalid price"}
        
        return True, {
            "symbol": symbol,
            "size": size,
            "price": price
        }
