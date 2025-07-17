"""
Main entry point for the Telegram bot.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.bot.telegram_bot import TelegramBot
from src.utils.config_manager import ConfigManager
from src.utils.logging_setup import setup_logging


def main():
    """Main function to run the Telegram bot."""
    # Setup logging
    logger = setup_logging()
    
    try:
        # Load configuration
        config_path = project_root / "config" / "config.yaml"
        config_manager = ConfigManager(config_path)
        config = config_manager.get_config()
        
        # Check for required Telegram configuration
        if not config.get('telegram', {}).get('bot_token'):
            logger.error("Telegram bot token not found in configuration")
            logger.info("Please set TELEGRAM_BOT_TOKEN environment variable or update config.yaml")
            return
        
        # Initialize and run bot
        bot = TelegramBot(config)
        logger.info("Starting Spot Hedging Bot...")
        
        # Run the bot using the synchronous method
        bot.run_sync()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
