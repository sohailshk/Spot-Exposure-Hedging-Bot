# Telegram Bot Setup Guide

## 🤖 Creating Your Telegram Bot

### Step 1: Create Bot with BotFather

1. **Start a chat with BotFather:**
   - Open Telegram and search for `@BotFather`
   - Start a conversation

2. **Create a new bot:**
   ```
   /newbot
   ```

3. **Choose bot name:**
   ```
   Spot Hedging Bot
   ```

4. **Choose username (must end with 'bot'):**
   ```
   spot_hedging_bot
   ```

5. **Save your bot token:**
   - BotFather will give you a token like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
   - Keep this secure!

### Step 2: Configure Bot Settings

6. **Set bot description:**
   ```
   /setdescription
   ```
   Then send:
   ```
   🚀 Intelligent spot exposure hedging bot with real-time risk monitoring and automated hedge recommendations. Features portfolio tracking, risk alerts, and multiple hedging strategies.
   ```

7. **Set bot commands:**
   ```
   /setcommands
   ```
   Then send:
   ```
   start - Welcome message and setup
   help - Command reference and examples
   portfolio - View current portfolio positions
   monitor_risk - Start risk monitoring for position
   auto_hedge - Enable automatic hedging
   hedge_status - Check current hedge recommendations
   hedge_history - View past hedge executions
   add_position - Add new position to portfolio
   settings - Adjust bot settings and thresholds
   analytics - View detailed portfolio analytics
   ```

### Step 3: Environment Setup

8. **Set environment variable:**

   **Windows (PowerShell):**
   ```powershell
   $env:TELEGRAM_BOT_TOKEN="your_bot_token_here"
   ```

   **Windows (Command Prompt):**
   ```cmd
   set TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

   **Linux/Mac:**
   ```bash
   export TELEGRAM_BOT_TOKEN="your_bot_token_here"
   ```

### Step 4: Update Configuration

9. **Edit config.yaml** (optional, if not using environment variables):
   ```yaml
   telegram:
     bot_token: "your_bot_token_here"
     admin_users: [your_telegram_user_id]  # Optional
     chat_id: null  # Will be auto-detected
     rate_limit:
       max_requests: 10
       window_seconds: 60
     alert_cooldown_minutes: 5
     monitoring_interval_seconds: 30
     max_positions_per_user: 50
     enable_notifications: true
     enable_auto_hedge: false
   ```

## 🚀 Running the Bot

### Option 1: Run Directly
```bash
cd spot-hedging-bot
python src/bot/main.py
```

### Option 2: Run Demo (Test Components)
```bash
python demo_telegram_bot.py
```

### Option 3: Run Tests
```bash
pytest tests/test_telegram_bot.py -v
```

## 💬 Using Your Bot

### Basic Commands

1. **Start the bot:**
   ```
   /start
   ```

2. **Add a position:**
   ```
   /add_position AAPL 1000 150.50
   ```

3. **Monitor risk:**
   ```
   /monitor_risk AAPL 1000 0.1
   ```

4. **Check portfolio:**
   ```
   /portfolio
   ```

5. **Enable auto-hedging:**
   ```
   /auto_hedge delta_neutral 0.1
   ```

6. **Check hedge status:**
   ```
   /hedge_status
   ```

### Interactive Features

- **Inline Buttons:** Use the buttons that appear with messages for quick actions
- **Real-time Alerts:** Get notified when risk thresholds are breached
- **Auto-refresh:** Portfolio and risk data updates automatically

## 🔧 Advanced Configuration

### Webhook Mode (Production)

For production deployment, you can use webhook mode instead of polling:

```yaml
telegram:
  webhook_url: "https://yourdomain.com/webhook"
  webhook_port: 8443
```

### Rate Limiting

Adjust rate limiting to prevent spam:

```yaml
telegram:
  rate_limit:
    max_requests: 20  # requests per window
    window_seconds: 60  # window duration
```

### Admin Features

Set admin users for special privileges:

```yaml
telegram:
  admin_users: [123456789, 987654321]
```

## 🛡️ Security Best Practices

1. **Keep your bot token secret**
   - Never commit it to version control
   - Use environment variables or secure config files

2. **Validate all inputs**
   - The bot includes input validation
   - Monitor for unusual activity

3. **Set reasonable limits**
   - Configure max positions per user
   - Set appropriate rate limits

4. **Monitor bot usage**
   - Review logs regularly
   - Track user activity

## 🐛 Troubleshooting

### Common Issues

1. **"Bot token not found"**
   - Check environment variable is set
   - Verify token format is correct

2. **"Permission denied"**
   - Make sure bot token is valid
   - Check bot hasn't been deleted

3. **"Rate limit exceeded"**
   - Wait for rate limit window to reset
   - Adjust rate limit settings if needed

4. **"Market data not found"**
   - Check symbol format (e.g., "AAPL", "BTC-USD")
   - Verify market data provider is working

### Debug Mode

Enable debug logging by setting:
```bash
export LOG_LEVEL=DEBUG
```

### Getting Help

- Check logs in `logs/` directory
- Run tests to verify functionality
- Use `/help` command in bot for usage examples

## 📈 Features Overview

### ✅ Implemented Features

- **Portfolio Management:** Add, view, and track positions
- **Risk Monitoring:** Real-time delta, gamma tracking
- **Hedge Recommendations:** Multiple strategy support
- **Interactive Interface:** Inline keyboards and commands
- **Rate Limiting:** Prevent spam and abuse
- **Input Validation:** Secure input handling
- **Async Operations:** Non-blocking background tasks

### 🚧 Future Enhancements

- **Settings Panel:** GUI for threshold adjustment
- **Analytics Dashboard:** Advanced portfolio analytics
- **Hedge History:** Detailed execution tracking
- **Export Features:** CSV/PDF portfolio reports
- **Multi-language:** Internationalization support
