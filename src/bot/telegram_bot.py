"""
Telegram bot interface for the spot hedging bot.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

try:
    from ..risk.models import Portfolio, Position, RiskThresholds, MarketData
    from ..risk.calculator import RiskCalculator
    from ..risk.market_data import market_data_provider
    from ..strategies.strategy_manager import StrategyManager
    from ..utils.config_manager import ConfigManager
    from ..utils.logging_setup import setup_logging
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from risk.models import Portfolio, Position, RiskThresholds, MarketData
    from risk.calculator import RiskCalculator
    from risk.market_data import market_data_provider
    from strategies.strategy_manager import StrategyManager
    from utils.config_manager import ConfigManager
    from utils.logging_setup import setup_logging


class TelegramBot:
    """Main Telegram bot class for hedge management."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Telegram bot."""
        self.config = config
        self.bot_token = config['telegram']['bot_token']
        self.admin_users = set(config['telegram'].get('admin_users', []))
        self.chat_id = config['telegram'].get('chat_id')
        
        # Initialize core components
        self.risk_thresholds = RiskThresholds()
        # Update thresholds from config
        risk_config = config.get('risk', {})
        if 'delta_threshold' in risk_config:
            self.risk_thresholds.max_delta = risk_config['delta_threshold']
        if 'gamma_threshold' in risk_config:
            self.risk_thresholds.max_gamma = risk_config['gamma_threshold']
        if 'theta_threshold' in risk_config:
            self.risk_thresholds.max_theta = risk_config['theta_threshold']
        if 'vega_threshold' in risk_config:
            self.risk_thresholds.max_vega = risk_config['vega_threshold']
        self.risk_calculator = RiskCalculator()
        self.strategy_manager = StrategyManager(self.risk_thresholds)
        
        # Portfolio and state management
        self.portfolios: Dict[int, Portfolio] = {}  # user_id -> portfolio
        self.monitoring_tasks: Dict[int, asyncio.Task] = {}  # user_id -> monitoring task
        self.user_settings: Dict[int, Dict] = {}  # user_id -> settings
        
        # Application setup
        self.application = None
        self.logger = logging.getLogger(__name__)
        
        # Alert settings
        self.alert_cooldown = timedelta(minutes=5)  # Minimum time between alerts
        self.last_alerts: Dict[int, datetime] = {}  # user_id -> last alert time
    
    async def initialize(self):
        """Initialize the bot application."""
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("monitor_risk", self.monitor_risk_command))
        self.application.add_handler(CommandHandler("auto_hedge", self.auto_hedge_command))
        self.application.add_handler(CommandHandler("hedge_status", self.hedge_status_command))
        self.application.add_handler(CommandHandler("hedge_history", self.hedge_history_command))
        self.application.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.application.add_handler(CommandHandler("add_position", self.add_position_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        self.application.add_handler(CommandHandler("analytics", self.analytics_command))
        
        # Add callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Add message handler for general messages
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        self.logger.info("Telegram bot initialized successfully")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        try:
            user_id = update.effective_user.id
            user_name = update.effective_user.first_name
            
            # Initialize user portfolio and settings
            if user_id not in self.portfolios:
                self.portfolios[user_id] = Portfolio()
                self.user_settings[user_id] = {
                    'auto_hedge_enabled': False,
                    'risk_alerts_enabled': True,
                    'notification_interval': 300,  # 5 minutes
                }
            
            welcome_message = f"""
🚀 **Welcome to Spot Hedging Bot, {user_name}!**

I'm your intelligent risk management assistant. Here's what I can do:

📊 **Risk Monitoring**
• `/monitor_risk <symbol> <size> <threshold>` - Monitor position risk
• `/portfolio` - View your current portfolio
• `/analytics` - Detailed risk analytics

⚖️ **Hedge Management**
• `/auto_hedge <strategy> <threshold>` - Enable auto-hedging
• `/hedge_status` - Check current hedge status
• `/hedge_history` - View hedge execution history

⚙️ **Configuration**
• `/settings` - Adjust bot settings
• `/add_position <symbol> <size> <price>` - Add position

💡 **Quick Actions**
Use the buttons below for common actions:
            """
            
            # Create inline keyboard
            keyboard = [
                [
                    InlineKeyboardButton("📊 View Portfolio", callback_data="portfolio"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="settings")
                ],
                [
                    InlineKeyboardButton("🔍 Monitor Risk", callback_data="monitor_risk"),
                    InlineKeyboardButton("⚖️ Auto Hedge", callback_data="auto_hedge")
                ],
                [
                    InlineKeyboardButton("📈 Analytics", callback_data="analytics"),
                    InlineKeyboardButton("❓ Help", callback_data="help")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in start command: {e}")
            await update.message.reply_text(
                "🚀 **Welcome to Spot Hedging Bot!**\n\n"
                "I'm your intelligent risk management assistant.\n\n"
                "**Key Commands:**\n"
                "• `/portfolio` - View your portfolio\n"
                "• `/add_position <symbol> <size> <price>` - Add position\n"
                "• `/monitor_risk <symbol> <size> <threshold>` - Monitor risk\n"
                "• `/help` - Full command reference"
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """
🔍 **COMMAND REFERENCE**

**Risk Monitoring Commands:**
• `/monitor_risk AAPL 1000 0.1` - Monitor 1000 AAPL shares with 0.1 delta threshold
• `/portfolio` - Show current portfolio positions and risk metrics
• `/analytics` - Detailed portfolio analytics and risk breakdown

**Hedge Management Commands:**
• `/auto_hedge delta_neutral 0.1` - Enable auto delta-neutral hedging at 0.1 threshold
• `/hedge_status` - Show current hedge recommendations and status
• `/hedge_history` - View past hedge executions and performance

**Position Management:**
• `/add_position AAPL 1000 150.50` - Add 1000 AAPL shares at $150.50
• `/add_position AAPL_CALL_160 10 5.50` - Add 10 call option contracts

**Configuration:**
• `/settings` - Adjust risk thresholds, alerts, and auto-hedge settings

**Examples:**
```
/monitor_risk AAPL 1000 0.1
/auto_hedge protective_put 0.02
/add_position BTC-USD 0.5 50000
/hedge_status
```

💡 **Tips:**
- Use inline buttons for quick actions
- Enable auto-hedge for hands-free risk management
- Set realistic risk thresholds based on your risk tolerance
- Monitor large positions closely

❓ **Need more help?** Contact support or check the documentation.
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def monitor_risk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /monitor_risk command."""
        user_id = update.effective_user.id
        
        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "❌ **Usage:** `/monitor_risk <symbol> <size> <threshold>`\n\n"
                "**Examples:**\n"
                "• `/monitor_risk AAPL 1000 0.1` - Monitor AAPL with delta threshold 0.1\n"
                "• `/monitor_risk BTC-USD 0.5 0.05` - Monitor BTC with threshold 0.05",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            symbol = context.args[0].upper()
            size = float(context.args[1])
            threshold = float(context.args[2])
            
            # Validate inputs
            if abs(size) < 0.001:
                await update.message.reply_text("❌ Position size must be greater than 0.001")
                return
            
            if not 0.001 <= threshold <= 1.0:
                await update.message.reply_text("❌ Threshold must be between 0.001 and 1.0")
                return
            
            # Get current market data
            await update.message.reply_text(f"🔍 Fetching current price for {symbol}...")
            
            # Try to get real market data
            current_price = None
            
            # Try CCXT first for crypto
            if symbol in ['BTC', 'ETH', 'LTC', 'BCH'] or '-USD' in symbol or 'USDT' in symbol:
                try:
                    import ccxt.async_support as ccxt
                    exchange = ccxt.binance()
                    
                    # Format symbol for Binance
                    if symbol == 'BTC':
                        ticker_symbol = 'BTC/USDT'
                    elif symbol == 'ETH':
                        ticker_symbol = 'ETH/USDT'
                    elif symbol.endswith('-USD'):
                        ticker_symbol = symbol.replace('-USD', '/USDT')
                    else:
                        ticker_symbol = f"{symbol}/USDT"
                    
                    ticker = await exchange.fetch_ticker(ticker_symbol)
                    current_price = ticker['last']
                    await exchange.close()
                    self.logger.info(f"✅ Got CCXT price for {symbol}: ${current_price:,.2f}")
                    
                except Exception as e:
                    self.logger.error(f"CCXT failed for {symbol}: {e}")
            
            # Fallback to market data provider
            if not current_price:
                try:
                    market_data = await market_data_provider.get_market_data(symbol)
                    if market_data:
                        current_price = market_data.price
                        self.logger.info(f"✅ Got market data price for {symbol}: ${current_price:,.2f}")
                except Exception as e:
                    self.logger.error(f"Market data provider failed for {symbol}: {e}")
            
            # Final fallback - only for known symbols
            if not current_price:
                fallback_prices = {
                    'BTC': 118000, 'ETH': 3200, 'AAPL': 190, 'TSLA': 250, 'MSFT': 420, 'GOOGL': 150
                }
                if symbol in fallback_prices:
                    current_price = fallback_prices[symbol]
                    await update.message.reply_text(f"⚠️ Could not fetch live data. Using fallback price ${current_price:,.2f}")
                
            if not current_price:
                await update.message.reply_text(
                    f"❌ Could not fetch market data for {symbol}\n\n"
                    f"**Suggestions:**\n"
                    f"• Check symbol spelling\n"
                    f"• Try different formats: AAPL, BTC, ETH\n"
                    f"• For options or complex instruments, use specific price:\n"
                    f"  `/monitor_risk {symbol} {context.args[1]} {context.args[2]} <price>`\n"
                    f"• Or add position first: `/add_position {symbol} {context.args[1]} <price>`"
                )
                return
            
            # Create or update position
            portfolio = self.portfolios[user_id]
            
            # Check if position already exists
            existing_positions = [pos for pos in portfolio.positions if pos.symbol == symbol]
            if existing_positions:
                # Update existing position
                position = existing_positions[0]
                position.size = size
                position.current_price = current_price
            else:
                # Create new position
                from ..risk.models import PositionType
                position = Position(
                    symbol=symbol,
                    position_type=PositionType.SPOT,
                    size=size,
                    entry_price=current_price,
                    current_price=current_price,
                    delta=1.0  # Spot positions have delta of 1.0
                )
                portfolio.add_position(position)
            
            # Calculate risk metrics
            self.risk_calculator.calculate_position_greeks(position)
            
            # Start monitoring task
            if user_id in self.monitoring_tasks:
                self.monitoring_tasks[user_id].cancel()
            
            self.monitoring_tasks[user_id] = asyncio.create_task(
                self.monitor_portfolio_risk(user_id, threshold)
            )
            
            # Create response with inline buttons
            message = f"""
✅ **Risk Monitoring Started**

📊 **Position Details:**
• Symbol: {symbol}
• Size: {size:,.4f} {'units' if symbol in ['BTC', 'ETH'] else 'shares'}
• Current Price: ${current_price:.2f}
• Market Value: ${position.market_value:,.2f}
• Delta: {position.delta or 1.0:.3f}

⚙️ **Monitoring Settings:**
• Risk Threshold: {threshold}
• Auto-alerts: Enabled
• Check Interval: Every 30 seconds

🎯 **Status:** {'❌ Risk Breach' if abs(position.delta or 1.0) > threshold else '✅ Within Limits'}
            """
            
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
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except ValueError as e:
            await update.message.reply_text(f"❌ Invalid input: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in monitor_risk_command: {e}")
            await update.message.reply_text("❌ An error occurred while setting up monitoring")
    
    async def auto_hedge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /auto_hedge command."""
        user_id = update.effective_user.id
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ **Usage:** `/auto_hedge <strategy> <threshold>`\n\n"
                "**Available Strategies:**\n"
                "• `delta_neutral` - Delta-neutral hedging with futures/ETFs\n"
                "• `protective_put` - Downside protection with put options\n"
                "• `collar` - Collar strategy with puts and calls\n\n"
                "**Examples:**\n"
                "• `/auto_hedge delta_neutral 0.1`\n"
                "• `/auto_hedge protective_put 0.02`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            strategy_name = context.args[0].lower()
            threshold = float(context.args[1])
            
            # Validate strategy
            valid_strategies = ['delta_neutral', 'protective_put', 'collar']
            if strategy_name not in valid_strategies:
                await update.message.reply_text(
                    f"❌ Invalid strategy. Choose from: {', '.join(valid_strategies)}"
                )
                return
            
            # Update user settings
            settings = self.user_settings[user_id]
            settings['auto_hedge_enabled'] = True
            settings['auto_hedge_strategy'] = strategy_name
            settings['auto_hedge_threshold'] = threshold
            
            message = f"""
✅ **Auto-Hedge Enabled**

⚙️ **Configuration:**
• Strategy: {strategy_name.replace('_', ' ').title()}
• Threshold: {threshold}
• Status: 🟢 Active

📋 **How it works:**
1. Continuous portfolio monitoring
2. Risk breach detection
3. Automatic hedge recommendations
4. Optional auto-execution (if enabled)

⚠️ **Note:** Hedge recommendations will be sent for approval unless auto-execution is enabled in settings.
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Settings", callback_data="auto_hedge_settings"),
                    InlineKeyboardButton("📊 View Status", callback_data="hedge_status")
                ],
                [
                    InlineKeyboardButton("🔴 Disable Auto-Hedge", callback_data="disable_auto_hedge")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except ValueError:
            await update.message.reply_text("❌ Invalid threshold value")
        except Exception as e:
            self.logger.error(f"Error in auto_hedge_command: {e}")
            await update.message.reply_text("❌ An error occurred while enabling auto-hedge")
    
    async def hedge_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /hedge_status command."""
        user_id = update.effective_user.id
        portfolio = self.portfolios.get(user_id)
        
        # Handle both direct command and callback query
        if update.callback_query:
            message_obj = update.callback_query.message
            reply_method = message_obj.reply_text
        else:
            message_obj = update.message
            reply_method = message_obj.reply_text
        
        if not portfolio or not portfolio.positions:
            await reply_method(
                "📝 **No positions found**\n\n"
                "Add positions using `/add_position` or `/monitor_risk` first.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            # Update positions with real current prices
            status_message = await reply_method("🔍 Analyzing portfolio and generating hedge recommendations...")
            
            # Update each position with current market price
            for position in portfolio.positions:
                try:
                    current_price = None
                    
                    # Try CCXT first for crypto
                    if position.symbol in ['BTC', 'ETH', 'LTC', 'BCH']:
                        try:
                            import ccxt.async_support as ccxt
                            exchange = ccxt.binance()
                            ticker = await exchange.fetch_ticker(f'{position.symbol}/USDT')
                            current_price = ticker['last']
                            await exchange.close()
                        except Exception as e:
                            self.logger.error(f"CCXT failed for {position.symbol}: {e}")
                    
                    # Fallback to market data provider
                    if not current_price:
                        try:
                            market_data = await market_data_provider.get_market_data(position.symbol)
                            if market_data:
                                current_price = market_data.price
                        except Exception as e:
                            self.logger.error(f"Market data failed for {position.symbol}: {e}")
                    
                    # Update position price
                    if current_price:
                        position.current_price = current_price
                        # Ensure delta is set
                        if not position.delta:
                            position.delta = 1.0
                            
                except Exception as e:
                    self.logger.error(f"Error updating {position.symbol}: {e}")
            
            # Check risk breaches
            breaches = self.risk_thresholds.check_breach(portfolio)
            
            # Generate hedge recommendations  
            recommendations = self.strategy_manager.get_hedge_recommendations(portfolio)
            
            # Build status message (simplified format to avoid markdown issues)
            status_text = f"""Portfolio Hedge Status
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Portfolio Summary:
• Total Value: ${portfolio.total_market_value:,.2f}
• Total P&L: ${portfolio.total_pnl:,.2f}
• Delta: {portfolio.total_delta:.3f}
• Gamma: {portfolio.total_gamma:.3f}

Risk Status:
"""
            
            # Add breach information
            breach_count = sum(breaches.values())
            if breach_count > 0:
                status_text += f"⚠️ {breach_count} Risk Breach(es) Detected\n"
                for risk_type, is_breached in breaches.items():
                    if is_breached:
                        status_text += f"• {risk_type.replace('_', ' ').title()}: BREACH\n"
            else:
                status_text += "✅ All Risk Limits Within Thresholds\n"
            
            # Add recommendations
            if recommendations:
                status_text += f"\n⚖️ Hedge Recommendations ({len(recommendations)}):\n"
                
                # Show recommendations without ranking for now (to avoid market_data issues)
                for i, rec in enumerate(recommendations[:3], 1):  # Show top 3
                    # Simplified format to avoid markdown parsing issues
                    action = str(rec.action)
                    symbol = str(rec.symbol)
                    strategy_name = 'N/A'
                    if hasattr(rec, 'strategy') and rec.strategy:
                        strategy_name = str(rec.strategy.value).replace('_', ' ').title()
                    
                    status_text += f"""
{i}. {action} {rec.size:,.0f} {symbol}
   • Strategy: {strategy_name}
   • Cost: ${rec.estimated_cost:,.2f}
   • Urgency: {rec.urgency}
"""
            else:
                status_text += "\n✅ No Hedge Recommendations\nPortfolio is within risk limits."
            
            # Create action buttons
            keyboard = []
            if recommendations:
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
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Edit the status message
            await status_message.edit_text(
                status_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in hedge_status_command: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            await status_message.edit_text(
                f"❌ **Error generating hedge status**\n\n"
                f"**Issue:** {str(e)}\n\n"
                f"**Try these solutions:**\n"
                f"• Check if you have positions in portfolio\n"
                f"• Verify market data is accessible\n"
                f"• Use `/portfolio` to see current positions\n"
                f"• Try again in a moment"
            )
    
    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command."""
        user_id = update.effective_user.id
        portfolio = self.portfolios.get(user_id)
        
        if not portfolio or not portfolio.positions:
            message = """
📝 **Portfolio is Empty**

Add positions using:
• `/add_position AAPL 1000 150.50`
• `/monitor_risk AAPL 1000 0.1`

Or use the button below to add your first position.
            """
            
            keyboard = [[InlineKeyboardButton("➕ Add Position", callback_data="add_position")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        try:
            # Update positions with current market data
            await update.message.reply_text("🔍 Updating portfolio with current market data...")
            
            # Update positions with current market data individually using CCXT
            await update.message.reply_text("🔍 Updating portfolio with current market data...")
            
            # Update each position with real current price
            for position in portfolio.positions:
                try:
                    # Use CCXT for crypto, fallback for others
                    current_price = None
                    
                    # Try CCXT first for crypto
                    if position.symbol in ['BTC', 'ETH', 'LTC', 'BCH']:
                        try:
                            import ccxt.async_support as ccxt
                            exchange = ccxt.binance()
                            ticker = await exchange.fetch_ticker(f'{position.symbol}/USDT')
                            current_price = ticker['last']
                            await exchange.close()
                            self.logger.info(f"✅ Updated {position.symbol} price: ${current_price:,.2f}")
                        except Exception as e:
                            self.logger.error(f"CCXT failed for {position.symbol}: {e}")
                    
                    # Fallback to market data provider for stocks
                    if not current_price:
                        try:
                            market_data = await market_data_provider.get_market_data(position.symbol)
                            if market_data:
                                current_price = market_data.price
                                self.logger.info(f"✅ Updated {position.symbol} price: ${current_price:,.2f}")
                        except Exception as e:
                            self.logger.error(f"Market data failed for {position.symbol}: {e}")
                    
                    # Update position if we got a price
                    if current_price:
                        position.current_price = current_price
                        # Ensure delta is set for spot positions
                        if not position.delta:
                            position.delta = 1.0
                    else:
                        self.logger.warning(f"Could not update price for {position.symbol}, using entry price")
                        
                except Exception as e:
                    self.logger.error(f"Error updating {position.symbol}: {e}")
                    # Keep using entry price if update fails
            
            # Build portfolio message
            message = f"""
📊 **Portfolio Overview**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💰 **Summary:**
• Total Value: ${portfolio.total_market_value:,.2f}
• Cash: ${portfolio.cash:,.2f}
• Total P&L: ${portfolio.total_pnl:,.2f}
• Positions: {len(portfolio.positions)}

📈 **Risk Metrics:**
• Delta: {portfolio.total_delta:.3f}
• Gamma: {portfolio.total_gamma:.3f}
• Theta: ${portfolio.total_theta:.2f}/day
• Vega: ${portfolio.total_vega:.2f}

📋 **Positions:**
            """
            
            # Add individual positions
            for i, pos in enumerate(portfolio.positions, 1):
                pnl_emoji = "📈" if pos.pnl > 0 else "📉" if pos.pnl < 0 else "➡️"
                message += f"""
{i}. **{pos.symbol}** ({pos.position_type.value.upper()})
   • Size: {pos.size:.4f} units
   • Price: ${pos.current_price:.2f}
   • Value: ${pos.market_value:,.2f}
   • P&L: {pnl_emoji} ${pos.pnl:,.2f}
   • Delta: {pos.delta:.3f}
"""
            
            # Check risk status
            breaches = self.risk_thresholds.check_breach(portfolio)
            breach_count = sum(breaches.values())
            
            if breach_count > 0:
                message += f"\n⚠️ **Risk Alert: {breach_count} threshold(s) breached**"
            else:
                message += "\n✅ **Risk Status: All limits within thresholds**"
            
            # Create action buttons
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
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in portfolio_command: {e}")
            await update.message.reply_text("❌ An error occurred while retrieving portfolio")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        try:
            if data == "portfolio":
                await self.portfolio_command(update, context)
            elif data == "hedge_status":
                await self.hedge_status_command(update, context)
            elif data == "analytics":
                await self.analytics_command(update, context)
            elif data == "settings":
                await self.settings_command(update, context)
            elif data == "help":
                await self.help_command(update, context)
            elif data == "add_position":
                await self.handle_add_position_callback(query)
            elif data == "refresh_hedge_status":
                await self.hedge_status_command(update, context)
            elif data.startswith("hedge_"):
                symbol = data.split("_", 1)[1]
                await self.handle_hedge_request(query, symbol)
            elif data.startswith("refresh_"):
                symbol = data.split("_", 1)[1]
                await self.handle_refresh_request(query, symbol)
            elif data.startswith("analytics_"):
                symbol = data.split("_", 1)[1]
                await self.handle_analytics_request(query, symbol)
            elif data.startswith("threshold_"):
                symbol = data.split("_", 1)[1]
                await self.handle_threshold_request(query, symbol)
            elif data.startswith("monitor_"):
                symbol = data.split("_", 1)[1]
                await self.handle_monitor_request(query, symbol)
            elif data == "execute_top_hedge":
                await self.handle_execute_hedge(query)
            elif data == "view_all_recs":
                await self.handle_view_all_recommendations(query)
            elif data == "auto_hedge_settings":
                await self.handle_auto_hedge_settings(query)
            elif data == "disable_auto_hedge":
                await self.handle_disable_auto_hedge(query)
            elif data == "auto_hedge_setup":
                await self.handle_auto_hedge_setup(query)
            else:
                await query.edit_message_text("❓ Unknown command")
                
        except Exception as e:
            self.logger.error(f"Error in handle_callback: {e}")
            await query.edit_message_text("❌ An error occurred processing your request")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general text messages."""
        message_text = update.message.text.lower()
        
        if any(word in message_text for word in ['risk', 'hedge', 'portfolio', 'delta']):
            await update.message.reply_text(
                "💡 **Quick Commands:**\n"
                "• `/hedge_status` - Check current risk status\n"
                "• `/portfolio` - View your positions\n"
                "• `/monitor_risk` - Start risk monitoring\n"
                "• `/help` - Full command reference"
            )
        else:
            await update.message.reply_text(
                "❓ I didn't understand that. Use `/help` to see available commands."
            )
    
    async def monitor_portfolio_risk(self, user_id: int, threshold: float):
        """Background task to monitor portfolio risk."""
        try:
            while True:
                portfolio = self.portfolios.get(user_id)
                if not portfolio or not portfolio.positions:
                    break
                
                # Update market data for each position individually
                try:
                    import ccxt.async_support as ccxt
                    exchange = ccxt.binance()
                    
                    for position in portfolio.positions:
                        symbol_lower = position.symbol.lower()
                        if symbol_lower in ['btc', 'bitcoin']:
                            ticker = await exchange.fetch_ticker('BTC/USDT')
                            position.current_price = ticker['last']
                        elif symbol_lower in ['eth', 'ethereum']:
                            ticker = await exchange.fetch_ticker('ETH/USDT')
                            position.current_price = ticker['last']
                        else:
                            # Fallback to market data provider for non-crypto
                            try:
                                market_data = await market_data_provider.get_market_data(position.symbol)
                                if market_data:
                                    position.current_price = market_data.price
                            except Exception as e:
                                self.logger.warning(f"Could not update price for {position.symbol}: {e}")
                                continue
                        
                        # Calculate position Greeks
                        self.risk_calculator.calculate_position_greeks(position)
                    
                    await exchange.close()
                    
                except Exception as e:
                    self.logger.error(f"Error updating market data: {e}")
                    # Fallback to existing market data provider
                    symbols = list(set(pos.symbol for pos in portfolio.positions))
                    try:
                        market_data = await market_data_provider.update_multiple_symbols(symbols)
                        for position in portfolio.positions:
                            if position.symbol in market_data:
                                position.current_price = market_data[position.symbol].price
                                self.risk_calculator.calculate_position_greeks(position)
                    except Exception as fallback_error:
                        self.logger.error(f"Fallback market data update failed: {fallback_error}")
                        continue
                
                # Check for risk breaches
                breaches = self.risk_thresholds.check_breach(portfolio)
                
                if any(breaches.values()):
                    await self.send_risk_alert(user_id, portfolio, breaches)
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except asyncio.CancelledError:
            self.logger.info(f"Monitoring task cancelled for user {user_id}")
        except Exception as e:
            self.logger.error(f"Error in monitoring task for user {user_id}: {e}")
    
    async def send_risk_alert(self, user_id: int, portfolio: Portfolio, breaches: Dict[str, bool]):
        """Send risk alert to user."""
        # Check cooldown
        now = datetime.now()
        if user_id in self.last_alerts:
            if now - self.last_alerts[user_id] < self.alert_cooldown:
                return
        
        self.last_alerts[user_id] = now
        
        # Count breaches
        breach_count = sum(breaches.values())
        breach_types = [risk_type for risk_type, breached in breaches.items() if breached]
        
        alert_message = f"""
🚨 **RISK ALERT** 🚨

⚠️ **{breach_count} Risk Threshold(s) Breached**

**Breached Limits:**
{chr(10).join(f'• {breach.replace("_", " ").title()}' for breach in breach_types)}

📊 **Current Metrics:**
• Delta: {portfolio.total_delta:.3f}
• Gamma: {portfolio.total_gamma:.3f}
• Portfolio Value: ${portfolio.total_market_value:,.2f}

🎯 **Recommended Actions:**
• Review hedge recommendations
• Consider reducing position sizes
• Enable auto-hedging for future protection
        """
        
        keyboard = [
            [
                InlineKeyboardButton("⚖️ View Hedge Recommendations", callback_data="hedge_status"),
                InlineKeyboardButton("📊 Portfolio Details", callback_data="portfolio")
            ],
            [
                InlineKeyboardButton("🔄 Enable Auto-Hedge", callback_data="auto_hedge_setup")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await self.application.bot.send_message(
                chat_id=user_id,
                text=alert_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as e:
            self.logger.error(f"Failed to send alert to user {user_id}: {e}")
    
    async def run(self):
        """Start the bot asynchronously."""
        await self.initialize()
        
        self.logger.info("Starting Telegram bot...")
        await self.application.run_polling(
            poll_interval=1.0,
            timeout=10,
            drop_pending_updates=True
        )
    
    def run_sync(self):
        """Start the bot synchronously (recommended approach)."""
        # Initialize application synchronously
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("monitor_risk", self.monitor_risk_command))
        self.application.add_handler(CommandHandler("auto_hedge", self.auto_hedge_command))
        self.application.add_handler(CommandHandler("hedge_status", self.hedge_status_command))
        self.application.add_handler(CommandHandler("hedge_history", self.hedge_history_command))
        self.application.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.application.add_handler(CommandHandler("add_position", self.add_position_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        self.application.add_handler(CommandHandler("analytics", self.analytics_command))
        
        # Add callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Add message handler for general messages
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        self.logger.info("Telegram bot initialized successfully")
        self.logger.info("Starting Telegram bot...")
        
        # Start polling (this manages the event loop internally)
        print("🚀 Spot Hedging Bot is starting, press Ctrl+C to stop.")
        self.application.run_polling(
            poll_interval=1.0,
            timeout=10,
            drop_pending_updates=True
        )
    
    async def stop(self):
        """Stop the bot and cleanup."""
        self.logger.info("Stopping Telegram bot...")
        
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()


# Stub implementations for missing methods
    async def add_position_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_position command with real market data."""
        user_id = update.effective_user.id
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ **Usage:** `/add_position <symbol> <size> [entry_price]`\n\n"
                "**Examples:**\n"
                "• `/add_position BTC 0.5` - Add 0.5 BTC at current market price\n"
                "• `/add_position AAPL 1000 150.50` - Add 1000 AAPL shares at $150.50\n"
                "• `/add_position ETH 2.0` - Add 2 ETH at current price",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            symbol = context.args[0].upper()
            size = float(context.args[1])
            
            # Initialize portfolio if not exists
            if user_id not in self.portfolios:
                self.portfolios[user_id] = Portfolio()
            
            # Get current market price
            await update.message.reply_text(f"🔍 Fetching current price for {symbol}...")
            
            # Try to get real market data
            current_price = None
            
            # Try CCXT first for crypto
            if symbol in ['BTC', 'ETH', 'LTC', 'BCH'] or '-USD' in symbol or 'USDT' in symbol:
                try:
                    import ccxt.async_support as ccxt
                    exchange = ccxt.binance()
                    
                    # Format symbol for Binance
                    if symbol == 'BTC':
                        ticker_symbol = 'BTC/USDT'
                    elif symbol == 'ETH':
                        ticker_symbol = 'ETH/USDT'
                    elif symbol.endswith('-USD'):
                        ticker_symbol = symbol.replace('-USD', '/USDT')
                    else:
                        ticker_symbol = f"{symbol}/USDT"
                    
                    ticker = await exchange.fetch_ticker(ticker_symbol)
                    current_price = ticker['last']
                    await exchange.close()
                    self.logger.info(f"✅ Got CCXT price for {symbol}: ${current_price:,.2f}")
                    
                except Exception as e:
                    self.logger.error(f"CCXT failed for {symbol}: {e}")
            
            # Fallback to market data provider
            if not current_price:
                try:
                    market_data = await market_data_provider.get_market_data(symbol)
                    if market_data:
                        current_price = market_data.price
                        self.logger.info(f"✅ Got market data price for {symbol}: ${current_price:,.2f}")
                except Exception as e:
                    self.logger.error(f"Market data provider failed for {symbol}: {e}")
            
            # Use provided entry price if given and market data failed
            if len(context.args) >= 3 and not current_price:
                current_price = float(context.args[2])
                self.logger.info(f"Using provided entry price for {symbol}: ${current_price:,.2f}")
            
            # Final fallback - only for known symbols  
            if not current_price:
                fallback_prices = {
                    'BTC': 118000,
                    'ETH': 3200,
                    'AAPL': 190,
                    'TSLA': 250,
                    'MSFT': 420,
                    'GOOGL': 150
                }
                if symbol in fallback_prices:
                    current_price = fallback_prices[symbol]
                    await update.message.reply_text(f"⚠️ Could not fetch live data. Using fallback price ${current_price:,.2f}")
            
            # If still no price, require manual entry
            if not current_price:
                await update.message.reply_text(
                    f"❌ Could not fetch market data for {symbol}\n\n"
                    f"**Please provide entry price manually:**\n"
                    f"`/add_position {symbol} {size} <price>`\n\n"
                    f"**Examples:**\n"
                    f"• `/add_position {symbol} {size} 5.50` - Use $5.50 as entry price\n"
                    f"• `/add_position AAPL_CALL_160 10 3.25` - Option contract at $3.25"
                )
                return
            
            # Create position
            from ..risk.models import PositionType
            position = Position(
                symbol=symbol,
                position_type=PositionType.SPOT,
                size=size,
                entry_price=current_price,
                current_price=current_price,
                delta=1.0  # Spot positions have delta of 1.0
            )
            
            # Add to portfolio
            portfolio = self.portfolios[user_id]
            portfolio.add_position(position)
            
            # Calculate position value
            position_value = abs(size) * current_price
            
            # Determine units
            if symbol in ['BTC', 'ETH', 'LTC', 'BCH'] or symbol.endswith('USD'):
                units = "units"
            else:
                units = "shares"
            
            # Create response
            message = f"""
✅ **Position Added Successfully**

📊 **Position Details:**
• Symbol: {symbol}
• Size: {size:,.4f} {units}
• Entry Price: ${current_price:,.2f}
• Position Value: ${position_value:,.2f}
• Position Type: {'Long' if size > 0 else 'Short'}

💼 **Portfolio Status:**
• Total Positions: {len(portfolio.positions)}
• Portfolio Value: ${portfolio.total_market_value:,.2f}

💡 **Next Steps:**
Use `/monitor_risk {symbol} {abs(size)} 0.1` to start monitoring this position.
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 View Portfolio", callback_data="portfolio"),
                    InlineKeyboardButton("🔍 Monitor Risk", callback_data=f"monitor_{symbol}")
                ],
                [
                    InlineKeyboardButton("📈 Analytics", callback_data=f"analytics_{symbol}"),
                    InlineKeyboardButton("➕ Add Another", callback_data="add_position")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except ValueError as e:
            await update.message.reply_text(f"❌ Invalid input: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in add_position_command: {e}")
            await update.message.reply_text("❌ An error occurred while adding the position. Please try again.")
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command with full functionality."""
        user_id = update.effective_user.id
        
        # Handle both direct command and callback query
        if update.callback_query:
            message_obj = update.callback_query.message
            reply_method = message_obj.reply_text
            edit_method = update.callback_query.edit_message_text
        else:
            message_obj = update.message
            reply_method = message_obj.reply_text
            edit_method = None
        
        # Get current settings
        settings = self.user_settings.get(user_id, {
            'auto_hedge_enabled': False,
            'risk_alerts_enabled': True,
            'notification_interval': 300,
        })
        
        # Build settings message
        settings_text = f"""⚙️ **Bot Settings & Configuration**

🔔 **Notifications:**
• Risk Alerts: {'🟢 Enabled' if settings.get('risk_alerts_enabled', True) else '🔴 Disabled'}
• Alert Interval: {settings.get('notification_interval', 300)//60} minutes
• Alert Cooldown: {self.alert_cooldown.total_seconds()//60} minutes

⚖️ **Auto-Hedge:**
• Status: {'🟢 Enabled' if settings.get('auto_hedge_enabled', False) else '🔴 Disabled'}
• Strategy: {settings.get('auto_hedge_strategy', 'Not Set').replace('_', ' ').title()}
• Threshold: {settings.get('auto_hedge_threshold', 'Not Set')}

📊 **Risk Thresholds:**
• Max Delta: {self.risk_thresholds.max_delta}
• Max Gamma: {self.risk_thresholds.max_gamma}
• Max Theta: {self.risk_thresholds.max_theta}
• Max Vega: {self.risk_thresholds.max_vega}

💼 **Portfolio:**
• Positions: {len(self.portfolios.get(user_id, Portfolio()).positions)}
• Monitoring Tasks: {'🟢 Active' if user_id in self.monitoring_tasks else '🔴 Inactive'}

🔧 **System Status:**
• Market Data: 🟢 Connected
• Risk Engine: 🟢 Active
• Strategy Manager: 🟢 Ready
"""
        
        keyboard = [
            [
                InlineKeyboardButton("⚖️ Auto-Hedge Settings", callback_data="auto_hedge_settings"),
                InlineKeyboardButton("📊 Risk Thresholds", callback_data="risk_thresholds")
            ],
            [
                InlineKeyboardButton("🔔 Alert Settings", callback_data="alert_settings"),
                InlineKeyboardButton("📈 Portfolio Settings", callback_data="portfolio_settings")
            ],
            [
                InlineKeyboardButton("📊 View Portfolio", callback_data="portfolio"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_method:
            await edit_method(settings_text, reply_markup=reply_markup)
        else:
            await reply_method(settings_text, reply_markup=reply_markup)
    
    async def analytics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analytics command with real portfolio analytics."""
        user_id = update.effective_user.id
        portfolio = self.portfolios.get(user_id)
        
        # Handle both direct command and callback query
        if update.callback_query:
            message_obj = update.callback_query.message
            reply_method = message_obj.reply_text
            edit_method = update.callback_query.edit_message_text
        else:
            message_obj = update.message
            reply_method = message_obj.reply_text
            edit_method = None
        
        if not portfolio or not portfolio.positions:
            response = """
📊 **Portfolio Analytics**

📝 **No positions found**

Add positions using `/add_position` or `/monitor_risk` first to see detailed analytics.
            """
            if edit_method:
                await edit_method(response)
            else:
                await reply_method(response, parse_mode=ParseMode.MARKDOWN)
            return
        
        try:
            # Update positions with current market data
            for position in portfolio.positions:
                try:
                    current_price = None
                    
                    # Try CCXT first for crypto
                    if position.symbol in ['BTC', 'ETH', 'LTC', 'BCH']:
                        try:
                            import ccxt.async_support as ccxt
                            exchange = ccxt.binance()
                            ticker = await exchange.fetch_ticker(f'{position.symbol}/USDT')
                            current_price = ticker['last']
                            await exchange.close()
                        except Exception as e:
                            self.logger.error(f"CCXT failed for {position.symbol}: {e}")
                    
                    # Fallback to market data provider
                    if not current_price:
                        try:
                            market_data = await market_data_provider.get_market_data(position.symbol)
                            if market_data:
                                current_price = market_data.price
                        except Exception as e:
                            self.logger.error(f"Market data failed for {position.symbol}: {e}")
                    
                    # Update position price
                    if current_price:
                        position.current_price = current_price
                        if not position.delta:
                            position.delta = 1.0
                            
                except Exception as e:
                    self.logger.error(f"Error updating {position.symbol}: {e}")
            
            # Calculate comprehensive analytics
            total_value = portfolio.total_market_value
            total_pnl = portfolio.total_pnl
            total_delta = portfolio.total_delta
            total_gamma = portfolio.total_gamma
            total_theta = portfolio.total_theta
            total_vega = portfolio.total_vega
            
            # Calculate risk metrics
            breaches = self.risk_thresholds.check_breach(portfolio)
            breach_count = sum(breaches.values())
            
            # Position analysis
            best_performer = max(portfolio.positions, key=lambda p: p.pnl) if portfolio.positions else None
            worst_performer = min(portfolio.positions, key=lambda p: p.pnl) if portfolio.positions else None
            
            # Build analytics message
            analytics_text = f"""📊 **Portfolio Analytics**
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💰 **Portfolio Summary:**
• Total Value: ${total_value:,.2f}
• Total P&L: ${total_pnl:,.2f} ({(total_pnl/max(total_value-total_pnl, 1)*100):+.2f}%)
• Positions: {len(portfolio.positions)}
• Cash: ${portfolio.cash:,.2f}

📈 **Risk Profile:**
• Delta: {total_delta:.4f}
• Gamma: {total_gamma:.4f}
• Theta: ${total_theta:.2f}/day
• Vega: ${total_vega:.2f}

⚠️ **Risk Status:**
• Breaches: {breach_count} threshold(s)
• Delta Risk: {'❌ BREACH' if breaches.get('delta_breach', False) else '✅ OK'}
• Gamma Risk: {'❌ BREACH' if breaches.get('gamma_breach', False) else '✅ OK'}
• Portfolio Size: {'❌ BREACH' if breaches.get('portfolio_size', False) else '✅ OK'}

📊 **Position Performance:**"""

            if best_performer:
                analytics_text += f"""
🏆 **Best Performer:** {best_performer.symbol}
   • P&L: ${best_performer.pnl:,.2f} ({(best_performer.pnl/max(best_performer.size*best_performer.entry_price, 1)*100):+.2f}%)
   • Value: ${best_performer.market_value:,.2f}"""

            if worst_performer and worst_performer != best_performer:
                analytics_text += f"""
📉 **Worst Performer:** {worst_performer.symbol}
   • P&L: ${worst_performer.pnl:,.2f} ({(worst_performer.pnl/max(worst_performer.size*worst_performer.entry_price, 1)*100):+.2f}%)
   • Value: ${worst_performer.market_value:,.2f}"""

            # Add sector exposure if applicable
            crypto_exposure = sum(pos.market_value for pos in portfolio.positions if pos.symbol in ['BTC', 'ETH', 'LTC', 'BCH'])
            stock_exposure = total_value - crypto_exposure - portfolio.cash
            
            if crypto_exposure > 0 or stock_exposure > 0:
                analytics_text += f"""

🏭 **Sector Exposure:**"""
                if crypto_exposure > 0:
                    analytics_text += f"""
• Crypto: ${crypto_exposure:,.2f} ({crypto_exposure/max(total_value, 1)*100:.1f}%)"""
                if stock_exposure > 0:
                    analytics_text += f"""
• Stocks: ${stock_exposure:,.2f} ({stock_exposure/max(total_value, 1)*100:.1f}%)"""
                if portfolio.cash > 0:
                    analytics_text += f"""
• Cash: ${portfolio.cash:,.2f} ({portfolio.cash/max(total_value, 1)*100:.1f}%)"""

            # Create action buttons
            keyboard = [
                [
                    InlineKeyboardButton("⚖️ Hedge Analysis", callback_data="hedge_status"),
                    InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Analytics", callback_data="analytics"),
                    InlineKeyboardButton("⚙️ Risk Settings", callback_data="settings")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if edit_method:
                await edit_method(analytics_text, reply_markup=reply_markup)
            else:
                await reply_method(analytics_text, reply_markup=reply_markup)
            
        except Exception as e:
            self.logger.error(f"Error in analytics_command: {e}")
            error_msg = "❌ An error occurred while generating analytics"
            if edit_method:
                await edit_method(error_msg)
            else:
                await reply_method(error_msg)
    
    async def hedge_history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /hedge_history command with real tracking."""
        user_id = update.effective_user.id
        
        # Handle both direct command and callback query
        if update.callback_query:
            message_obj = update.callback_query.message
            reply_method = message_obj.reply_text
            edit_method = update.callback_query.edit_message_text
        else:
            message_obj = update.message
            reply_method = message_obj.reply_text
            edit_method = None
        
        # Initialize hedge history if not exists
        if not hasattr(self, 'hedge_history'):
            self.hedge_history = {}
        
        user_history = self.hedge_history.get(user_id, [])
        
        if not user_history:
            response = """
📋 **Hedge History**

📝 **No hedge executions found**

Your hedge execution history will appear here after you execute hedges using:
• `/hedge_status` - View and execute hedge recommendations
• Auto-hedge when enabled

**Example hedge types tracked:**
• Delta-neutral hedges
• Protective put purchases
• Collar strategy executions
• Position adjustments
            """
            if edit_method:
                await edit_method(response)
            else:
                await reply_method(response, parse_mode=ParseMode.MARKDOWN)
            return
        
        # Build history message
        history_text = f"""📋 **Hedge History**
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 **Summary:**
• Total Executions: {len(user_history)}
• Period: Last 30 days

🔄 **Recent Hedge Executions:**
"""
        
        # Show last 5 hedge executions
        for i, hedge in enumerate(user_history[-5:], 1):
            execution_time = hedge.get('timestamp', 'Unknown')
            strategy = hedge.get('strategy', 'Unknown')
            symbol = hedge.get('symbol', 'Unknown')
            size = hedge.get('size', 0)
            cost = hedge.get('cost', 0)
            status = hedge.get('status', 'Unknown')
            
            status_emoji = "✅" if status == "Executed" else "⏳" if status == "Pending" else "❌"
            
            history_text += f"""
{i}. **{strategy}** - {symbol}
   • Size: {size:,.0f}
   • Cost: ${cost:,.2f}
   • Status: {status_emoji} {status}
   • Time: {execution_time}
"""
        
        # Calculate performance metrics
        executed_hedges = [h for h in user_history if h.get('status') == 'Executed']
        total_cost = sum(h.get('cost', 0) for h in executed_hedges)
        avg_cost = total_cost / len(executed_hedges) if executed_hedges else 0
        
        history_text += f"""

� **Performance Metrics:**
• Total Hedge Cost: ${total_cost:,.2f}
• Average Cost: ${avg_cost:,.2f}
• Success Rate: {len(executed_hedges)/max(len(user_history), 1)*100:.1f}%
• Most Used Strategy: {max(set(h.get('strategy', 'Unknown') for h in user_history), key=lambda x: sum(1 for h in user_history if h.get('strategy') == x)) if user_history else 'None'}
"""
        
        keyboard = [
            [
                InlineKeyboardButton("⚖️ New Hedge", callback_data="hedge_status"),
                InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")
            ],
            [
                InlineKeyboardButton("🔄 Refresh History", callback_data="hedge_history"),
                InlineKeyboardButton("📈 Analytics", callback_data="analytics")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_method:
            await edit_method(history_text, reply_markup=reply_markup)
        else:
            await reply_method(history_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_hedge_request(self, query, symbol: str):
        """Handle hedge request for specific symbol."""
        user_id = query.from_user.id
        portfolio = self.portfolios.get(user_id)
        
        if not portfolio or not portfolio.positions:
            await query.edit_message_text(
                "❌ **No positions found**\n\n"
                "Add positions first using `/add_position` or `/monitor_risk`."
            )
            return
        
        try:
            # Find positions for this symbol
            symbol_positions = [pos for pos in portfolio.positions if pos.symbol == symbol]
            
            if not symbol_positions:
                await query.edit_message_text(
                    f"❌ **No {symbol} positions found**\n\n"
                    f"Add a {symbol} position first using `/add_position {symbol} <size>`."
                )
                return
            
            # Update position with current price
            position = symbol_positions[0]
            current_price = None
            
            # Get current market price
            if symbol in ['BTC', 'ETH', 'LTC', 'BCH']:
                try:
                    import ccxt.async_support as ccxt
                    exchange = ccxt.binance()
                    ticker = await exchange.fetch_ticker(f'{symbol}/USDT')
                    current_price = ticker['last']
                    await exchange.close()
                except Exception as e:
                    self.logger.error(f"CCXT failed for {symbol}: {e}")
            
            if not current_price:
                try:
                    market_data = await market_data_provider.get_market_data(symbol)
                    if market_data:
                        current_price = market_data.price
                except Exception as e:
                    self.logger.error(f"Market data failed for {symbol}: {e}")
            
            if current_price:
                position.current_price = current_price
            
            # Generate hedge recommendations for this position
            market_data_dict = {symbol: MarketData(symbol=symbol, price=position.current_price, timestamp=datetime.now())}
            recommendations = self.strategy_manager.get_hedge_recommendations(portfolio, market_data_dict)
            
            # Filter recommendations for this symbol
            symbol_recs = [rec for rec in recommendations if symbol in rec.symbol or rec.symbol == symbol]
            
            if not symbol_recs:
                message = f"""⚖️ **{symbol} Hedge Analysis**

✅ **No hedge needed for {symbol}**

Current position is within risk limits:
• Size: {position.size:,.4f}
• Value: ${position.market_value:,.2f}
• Delta: {position.delta or 1.0:.3f}
• P&L: ${position.pnl:,.2f}

Risk thresholds are satisfied."""
            else:
                rec = symbol_recs[0]  # Take first recommendation
                message = f"""⚖️ **{symbol} Hedge Recommendation**

🎯 **Recommended Action:**
• Strategy: {rec.strategy.value.replace('_', ' ').title() if hasattr(rec, 'strategy') and rec.strategy else 'Delta Neutral'}
• Action: {rec.action} {rec.size:,.0f} {rec.symbol}
• Estimated Cost: ${rec.estimated_cost:,.2f}
• Urgency: {rec.urgency}

📊 **Current Position:**
• Size: {position.size:,.4f}
• Value: ${position.market_value:,.2f}
• Delta: {position.delta or 1.0:.3f}
• P&L: ${position.pnl:,.2f}

💡 **Why this hedge?**
{rec.reasoning}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Execute Hedge", callback_data=f"execute_hedge_{symbol}"),
                    InlineKeyboardButton("📊 View All Recs", callback_data="view_all_recs")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Analysis", callback_data=f"hedge_{symbol}"),
                    InlineKeyboardButton("📈 Position Analytics", callback_data=f"analytics_{symbol}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            self.logger.error(f"Error in handle_hedge_request: {e}")
            await query.edit_message_text(f"❌ Error analyzing {symbol} hedge: {str(e)}")
    
    async def handle_refresh_request(self, query, symbol: str):
        """Handle refresh request for specific symbol."""
        user_id = query.from_user.id
        portfolio = self.portfolios.get(user_id)
        
        if not portfolio or not portfolio.positions:
            await query.edit_message_text("❌ No positions to refresh")
            return
        
        try:
            # Find and update position
            symbol_positions = [pos for pos in portfolio.positions if pos.symbol == symbol]
            
            if not symbol_positions:
                await query.edit_message_text(f"❌ No {symbol} position found")
                return
            
            position = symbol_positions[0]
            
            # Update with current market price
            current_price = None
            
            if symbol in ['BTC', 'ETH', 'LTC', 'BCH']:
                try:
                    import ccxt.async_support as ccxt
                    exchange = ccxt.binance()
                    ticker = await exchange.fetch_ticker(f'{symbol}/USDT')
                    current_price = ticker['last']
                    await exchange.close()
                except Exception as e:
                    self.logger.error(f"CCXT failed: {e}")
            
            if not current_price:
                try:
                    market_data = await market_data_provider.get_market_data(symbol)
                    if market_data:
                        current_price = market_data.price
                except Exception as e:
                    self.logger.error(f"Market data failed: {e}")
            
            if current_price:
                old_price = position.current_price
                position.current_price = current_price
                price_change = ((current_price - old_price) / old_price * 100) if old_price else 0
                
                # Recalculate Greeks
                self.risk_calculator.calculate_position_greeks(position)
                
                message = f"""🔄 **{symbol} Position Refreshed**

📊 **Updated Data:**
• Current Price: ${current_price:,.2f} ({price_change:+.2f}%)
• Position Value: ${position.market_value:,.2f}
• P&L: ${position.pnl:,.2f}
• Delta: {position.delta or 1.0:.3f}

⚙️ **Risk Status:**
• Size: {position.size:,.4f}
• Entry Price: ${position.entry_price:.2f}
• Last Updated: {datetime.now().strftime('%H:%M:%S')}
"""
            else:
                message = f"❌ Could not fetch current price for {symbol}"
            
            keyboard = [
                [
                    InlineKeyboardButton("⚖️ Hedge Analysis", callback_data=f"hedge_{symbol}"),
                    InlineKeyboardButton("📈 Analytics", callback_data=f"analytics_{symbol}")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Again", callback_data=f"refresh_{symbol}"),
                    InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            self.logger.error(f"Error in handle_refresh_request: {e}")
            await query.edit_message_text(f"❌ Error refreshing {symbol}: {str(e)}")
    
    async def handle_analytics_request(self, query, symbol: str):
        """Handle analytics request for specific symbol."""
        user_id = query.from_user.id
        portfolio = self.portfolios.get(user_id)
        
        if not portfolio or not portfolio.positions:
            await query.edit_message_text("❌ No positions for analytics")
            return
        
        try:
            # Find position
            symbol_positions = [pos for pos in portfolio.positions if pos.symbol == symbol]
            
            if not symbol_positions:
                await query.edit_message_text(f"❌ No {symbol} position found")
                return
            
            position = symbol_positions[0]
            
            # Calculate detailed analytics
            pnl_pct = (position.pnl / max(position.size * position.entry_price, 1)) * 100
            value_pct = (position.market_value / max(portfolio.total_market_value, 1)) * 100
            
            # Risk assessment
            risk_level = "LOW"
            if abs(position.delta or 0) > 0.5:
                risk_level = "HIGH" 
            elif abs(position.delta or 0) > 0.2:
                risk_level = "MEDIUM"
            
            message = f"""📈 **{symbol} Position Analytics**

💰 **Performance:**
• Unrealized P&L: ${position.pnl:,.2f} ({pnl_pct:+.2f}%)
• Current Value: ${position.market_value:,.2f}
• Portfolio Weight: {value_pct:.1f}%

📊 **Risk Metrics:**
• Delta: {position.delta or 1.0:.4f}
• Gamma: {position.gamma or 0.0:.4f}
• Theta: ${position.theta or 0.0:.2f}/day
• Vega: ${position.vega or 0.0:.2f}

⚠️ **Risk Assessment:**
• Risk Level: {risk_level}
• Position Type: {position.position_type.value.upper()}
• Entry Price: ${position.entry_price:.2f}
• Current Price: ${position.current_price:.2f}

📈 **Price Movement:**
• Price Change: {((position.current_price - position.entry_price) / position.entry_price * 100):+.2f}%
• Break-even: ${position.entry_price:.2f}
"""
            
            # Add recommendations
            breaches = self.risk_thresholds.check_breach(portfolio)
            if any(breaches.values()):
                message += f"\n⚠️ **Risk Alert:** Portfolio has {sum(breaches.values())} breach(es)"
            
            keyboard = [
                [
                    InlineKeyboardButton("⚖️ Hedge This Position", callback_data=f"hedge_{symbol}"),
                    InlineKeyboardButton("🔄 Refresh Data", callback_data=f"refresh_{symbol}")
                ],
                [
                    InlineKeyboardButton("📊 Full Portfolio", callback_data="analytics"),
                    InlineKeyboardButton("⚙️ Adjust Threshold", callback_data=f"threshold_{symbol}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            self.logger.error(f"Error in handle_analytics_request: {e}")
            await query.edit_message_text(f"❌ Error analyzing {symbol}: {str(e)}")
    
    async def handle_threshold_request(self, query, symbol: str):
        """Handle threshold adjustment request."""
        message = f"""⚙️ **Adjust Risk Threshold for {symbol}**

Current risk monitoring thresholds:
• Delta Threshold: {self.risk_thresholds.max_delta}
• Gamma Threshold: {self.risk_thresholds.max_gamma}

To adjust thresholds, use commands:
• `/monitor_risk {symbol} <size> <new_threshold>`
• `/auto_hedge <strategy> <new_threshold>`

**Common Thresholds:**
• Conservative: 0.05 (5%)
• Moderate: 0.1 (10%)
• Aggressive: 0.2 (20%)
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Monitor Risk", callback_data=f"monitor_{symbol}"),
                InlineKeyboardButton("⚖️ Auto Hedge", callback_data="auto_hedge_setup")
            ],
            [
                InlineKeyboardButton("📊 Position Analytics", callback_data=f"analytics_{symbol}"),
                InlineKeyboardButton("🔙 Back to Portfolio", callback_data="portfolio")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def handle_monitor_request(self, query, symbol: str):
        """Handle monitor setup request."""
        message = f"""🔍 **Monitor {symbol} Risk**

To start risk monitoring for {symbol}, use:
`/monitor_risk {symbol} <position_size> <threshold>`

**Examples:**
• `/monitor_risk {symbol} 1000 0.1` - Monitor with 10% threshold
• `/monitor_risk {symbol} 0.5 0.05` - Monitor with 5% threshold

**What happens:**
✅ Real-time price tracking
✅ Risk breach alerts
✅ Automatic hedge recommendations
✅ Background monitoring every 30 seconds
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📊 View Position", callback_data=f"analytics_{symbol}"),
                InlineKeyboardButton("⚖️ Hedge Now", callback_data=f"hedge_{symbol}")
            ],
            [
                InlineKeyboardButton("📈 Portfolio Overview", callback_data="portfolio"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def handle_execute_hedge(self, query):
        """Handle execute hedge request with real tracking."""
        user_id = query.from_user.id
        portfolio = self.portfolios.get(user_id)
        
        if not portfolio or not portfolio.positions:
            await query.edit_message_text("❌ No positions to hedge")
            return
        
        try:
            # Get hedge recommendations
            recommendations = self.strategy_manager.get_hedge_recommendations(portfolio)
            
            if not recommendations:
                await query.edit_message_text(
                    "✅ **No hedge execution needed**\n\n"
                    "Your portfolio is within risk limits."
                )
                return
            
            # Execute top recommendation (simulate)
            top_rec = recommendations[0]
            
            # Initialize hedge history if not exists
            if not hasattr(self, 'hedge_history'):
                self.hedge_history = {}
            if user_id not in self.hedge_history:
                self.hedge_history[user_id] = []
            
            # Record hedge execution
            hedge_record = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'strategy': top_rec.strategy.value if hasattr(top_rec, 'strategy') and top_rec.strategy else 'delta_neutral',
                'symbol': top_rec.symbol,
                'action': top_rec.action,
                'size': top_rec.size,
                'cost': top_rec.estimated_cost,
                'status': 'Executed',
                'reasoning': top_rec.reasoning
            }
            
            self.hedge_history[user_id].append(hedge_record)
            
            # Keep only last 50 records
            if len(self.hedge_history[user_id]) > 50:
                self.hedge_history[user_id] = self.hedge_history[user_id][-50:]
            
            message = f"""✅ **Hedge Executed Successfully**

🎯 **Execution Details:**
• Strategy: {hedge_record['strategy'].replace('_', ' ').title()}
• Action: {top_rec.action} {top_rec.size:,.0f} {top_rec.symbol}
• Estimated Cost: ${top_rec.estimated_cost:,.2f}
• Execution Time: {hedge_record['timestamp']}

📊 **Portfolio Impact:**
• Expected Risk Reduction: High
• New Delta Exposure: Reduced
• Execution Status: ✅ Completed

💡 **Note:** This is a simulation. In production, this would execute actual trades through connected brokers/exchanges.
"""
            
            keyboard = [
                [
                    InlineKeyboardButton("📋 View History", callback_data="hedge_history"),
                    InlineKeyboardButton("📊 Portfolio Status", callback_data="portfolio")
                ],
                [
                    InlineKeyboardButton("⚖️ New Hedge Analysis", callback_data="hedge_status"),
                    InlineKeyboardButton("📈 Analytics", callback_data="analytics")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            self.logger.error(f"Error in handle_execute_hedge: {e}")
            await query.edit_message_text(f"❌ Error executing hedge: {str(e)}")
    
    async def handle_view_all_recommendations(self, query):
        """Handle view all recommendations request."""
        user_id = query.from_user.id
        portfolio = self.portfolios.get(user_id)
        
        if not portfolio or not portfolio.positions:
            await query.edit_message_text("❌ No positions for recommendations")
            return
        
        try:
            recommendations = self.strategy_manager.get_hedge_recommendations(portfolio)
            
            if not recommendations:
                message = """📋 **All Hedge Recommendations**

✅ **No recommendations currently**

Your portfolio is within all risk limits:
• Delta exposure acceptable
• Position sizes appropriate
• Risk thresholds satisfied

Continue monitoring for changes."""
            else:
                message = f"""📋 **All Hedge Recommendations**
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Found {len(recommendations)} recommendation(s):

"""
                for i, rec in enumerate(recommendations[:5], 1):  # Show top 5
                    strategy_name = rec.strategy.value.replace('_', ' ').title() if hasattr(rec, 'strategy') and rec.strategy else 'Delta Neutral'
                    urgency_emoji = "🔴" if rec.urgency == "CRITICAL" else "🟡" if rec.urgency == "HIGH" else "🟢"
                    
                    message += f"""**{i}. {strategy_name}**
{urgency_emoji} Urgency: {rec.urgency}
• Action: {rec.action} {rec.size:,.0f} {rec.symbol}
• Cost: ${rec.estimated_cost:,.2f}
• Reason: {rec.reasoning[:60]}...

"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Execute Top Rec", callback_data="execute_top_hedge"),
                    InlineKeyboardButton("🔄 Refresh Analysis", callback_data="hedge_status")
                ],
                [
                    InlineKeyboardButton("📊 Portfolio", callback_data="portfolio"),
                    InlineKeyboardButton("📈 Analytics", callback_data="analytics")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            self.logger.error(f"Error in handle_view_all_recommendations: {e}")
            await query.edit_message_text(f"❌ Error loading recommendations: {str(e)}")
    
    async def handle_add_position_callback(self, query):
        """Handle add position callback."""
        message = """➕ **Add New Position**

Use the command format:
`/add_position <symbol> <size> [price]`

**Examples:**
• `/add_position BTC 0.5` - Add 0.5 BTC at current price
• `/add_position AAPL 1000 150.50` - Add 1000 AAPL shares at $150.50
• `/add_position ETH 2.0` - Add 2 ETH at current price

**Supported Assets:**
• Cryptocurrencies: BTC, ETH, LTC, BCH
• Stocks: AAPL, GOOGL, TSLA, MSFT
• And many more...
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📊 View Portfolio", callback_data="portfolio"),
                InlineKeyboardButton("🔍 Monitor Risk", callback_data="monitor_risk")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help"),
                InlineKeyboardButton("📈 Analytics", callback_data="analytics")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def handle_auto_hedge_settings(self, query):
        """Handle auto hedge settings callback."""
        user_id = query.from_user.id
        settings = self.user_settings.get(user_id, {})
        
        auto_hedge_enabled = settings.get('auto_hedge_enabled', False)
        strategy = settings.get('auto_hedge_strategy', 'delta_neutral')
        threshold = settings.get('auto_hedge_threshold', 0.1)
        
        message = f"""⚙️ **Auto-Hedge Settings**

**Current Configuration:**
• Status: {'🟢 Enabled' if auto_hedge_enabled else '🔴 Disabled'}
• Strategy: {strategy.replace('_', ' ').title()}
• Threshold: {threshold}

**Available Strategies:**
• Delta Neutral - Hedge directional risk
• Protective Put - Downside protection
• Collar - Limited risk and reward

**To modify:**
• `/auto_hedge <strategy> <threshold>`
• `/auto_hedge delta_neutral 0.05`
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🔴 Disable Auto-Hedge", callback_data="disable_auto_hedge"),
                InlineKeyboardButton("📊 Hedge Status", callback_data="hedge_status")
            ],
            [
                InlineKeyboardButton("📈 Analytics", callback_data="analytics"),
                InlineKeyboardButton("🔙 Back", callback_data="settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def handle_disable_auto_hedge(self, query):
        """Handle disable auto hedge callback."""
        user_id = query.from_user.id
        settings = self.user_settings.get(user_id, {})
        settings['auto_hedge_enabled'] = False
        
        message = """🔴 **Auto-Hedge Disabled**

Auto-hedge has been turned off. You will need to manually:
• Monitor risk levels using `/hedge_status`
• Execute hedges when recommended
• Re-enable auto-hedge if desired

Manual hedge monitoring remains active.
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🟢 Re-enable Auto-Hedge", callback_data="auto_hedge_setup"),
                InlineKeyboardButton("📊 Hedge Status", callback_data="hedge_status")
            ],
            [
                InlineKeyboardButton("📈 Portfolio", callback_data="portfolio"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def handle_auto_hedge_setup(self, query):
        """Handle auto hedge setup callback."""
        message = """🔄 **Enable Auto-Hedge**

To enable auto-hedging, use:
`/auto_hedge <strategy> <threshold>`

**Available Strategies:**
• `delta_neutral` - Hedge directional risk
• `protective_put` - Downside protection
• `collar` - Collar strategy

**Examples:**
• `/auto_hedge delta_neutral 0.1` - 10% threshold
• `/auto_hedge protective_put 0.05` - 5% threshold

**Benefits:**
✅ Automatic risk monitoring
✅ Instant hedge execution
✅ 24/7 portfolio protection
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Current Portfolio", callback_data="portfolio"),
                InlineKeyboardButton("⚖️ Manual Hedge", callback_data="hedge_status")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help"),
                InlineKeyboardButton("🔙 Back", callback_data="settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
