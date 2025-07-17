# Production Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Spot Hedging Bot in a production environment. The system is designed to be robust, scalable, and secure for real-world trading operations.

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+ recommended) or Windows Server
- **Python Version**: 3.10 or higher
- **Memory**: Minimum 2GB RAM (4GB+ recommended)
- **Storage**: 10GB free space minimum
- **Network**: Reliable internet connection for market data

### Required Services
- **Telegram Bot Token**: Obtained from @BotFather
- **Market Data Access**: API keys for financial data providers
- **Optional**: Database server (PostgreSQL/MongoDB for persistence)

## Quick Start (Recommended)

### 1. Clone and Setup
```bash
# Clone the repository
git clone <repository-url> spot-hedging-bot
cd spot-hedging-bot

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
```bash
# Copy configuration template
cp config/config.yaml.template config/config.yaml

# Edit configuration file
nano config/config.yaml
```

### 3. Environment Variables
```bash
# Create environment file
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token_here
MARKET_DATA_API_KEY=your_api_key_here
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF

# Load environment variables
export $(cat .env | xargs)
```

### 4. Run the Bot
```bash
# Test configuration
python -m src.bot.telegram_bot --test

# Start the bot
python -m src.bot.telegram_bot
```

## Detailed Configuration

### Core Configuration (config/config.yaml)

```yaml
# Market Data Configuration
market_data:
  default_provider: "yfinance"
  fallback_provider: "mock"
  update_interval: 30
  cache_duration: 300

# Risk Management Settings
risk:
  delta_threshold: 0.1
  gamma_threshold: 0.05
  theta_threshold: 100
  vega_threshold: 50
  max_portfolio_value: 10000000

# Telegram Bot Settings
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  admin_users: []
  rate_limit_requests: 10
  rate_limit_window: 60
  alert_cooldown_minutes: 5
  monitoring_interval: 30

# Logging Configuration
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/hedging_bot.log"
  max_size_mb: 100
  backup_count: 5

# Feature Toggles
bot_features:
  auto_hedge: false
  risk_alerts: true
  portfolio_limits: true
  rate_limiting: true

# Display Settings
display:
  currency_symbol: "$"
  decimal_places: 2
  timezone: "UTC"
```

### Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ENVIRONMENT=production

# Optional
MARKET_DATA_API_KEY=your_api_key
DATABASE_URL=postgresql://user:pass@host:5432/db
LOG_LEVEL=INFO
ADMIN_CHAT_ID=your_telegram_chat_id

# Security
SECRET_KEY=your_secret_key_for_encryption
RATE_LIMIT_REDIS_URL=redis://localhost:6379/0
```

## Production Setup Options

### Option 1: Systemd Service (Linux)

```bash
# Create service file
sudo nano /etc/systemd/system/hedging-bot.service
```

```ini
[Unit]
Description=Spot Hedging Bot
After=network.target

[Service]
Type=simple
User=hedging-bot
Group=hedging-bot
WorkingDirectory=/opt/hedging-bot
Environment=PATH=/opt/hedging-bot/venv/bin
EnvironmentFile=/opt/hedging-bot/.env
ExecStart=/opt/hedging-bot/venv/bin/python -m src.bot.telegram_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable hedging-bot
sudo systemctl start hedging-bot

# Check status
sudo systemctl status hedging-bot

# View logs
sudo journalctl -u hedging-bot -f
```

### Option 2: Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 hedging-bot
USER hedging-bot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

EXPOSE 8080

CMD ["python", "-m", "src.bot.telegram_bot"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  hedging-bot:
    build: .
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=hedging_bot
      - POSTGRES_USER=hedging_bot
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

```bash
# Deploy with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f hedging-bot

# Scale if needed
docker-compose up -d --scale hedging-bot=3
```

### Option 3: Kubernetes Deployment

#### deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hedging-bot
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hedging-bot
  template:
    metadata:
      labels:
        app: hedging-bot
    spec:
      containers:
      - name: hedging-bot
        image: hedging-bot:latest
        env:
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: hedging-bot-secrets
              key: telegram-token
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"
          initialDelaySeconds: 30
          periodSeconds: 30
---
apiVersion: v1
kind: Secret
metadata:
  name: hedging-bot-secrets
stringData:
  telegram-token: "your_telegram_bot_token"
```

## Security Configuration

### 1. Bot Security
```yaml
# In config.yaml
telegram:
  admin_users: [123456789, 987654321]  # Admin Telegram user IDs
  rate_limit_requests: 10
  rate_limit_window: 60
  allowed_commands: ["start", "portfolio", "monitor", "hedge", "help"]
```

### 2. Network Security
```bash
# Firewall rules (Ubuntu/CentOS)
sudo ufw allow ssh
sudo ufw allow 8080  # If using HTTP health checks
sudo ufw enable

# Or with iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
```

### 3. SSL/TLS Configuration
```bash
# Install certbot for Let's Encrypt
sudo apt-get install certbot

# Generate certificate (if exposing HTTP endpoints)
sudo certbot certonly --standalone -d your-domain.com
```

## Monitoring & Logging

### 1. Application Logging
```python
# Logging configuration in config.yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/hedging_bot.log"
  max_size_mb: 100
  backup_count: 5
```

### 2. System Monitoring
```bash
# Install monitoring tools
sudo apt-get install htop iotop nethogs

# Monitor system resources
htop

# Monitor network
sudo nethogs

# Monitor disk I/O
sudo iotop
```

### 3. Log Management
```bash
# Set up log rotation
sudo nano /etc/logrotate.d/hedging-bot
```

```
/opt/hedging-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 hedging-bot hedging-bot
    postrotate
        systemctl reload hedging-bot
    endscript
}
```

## Database Setup (Optional)

### PostgreSQL Setup
```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE hedging_bot;
CREATE USER hedging_bot WITH ENCRYPTED PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE hedging_bot TO hedging_bot;
\q

# Configure connection
export DATABASE_URL="postgresql://hedging_bot:your_password@localhost:5432/hedging_bot"
```

### Redis Setup (for Caching)
```bash
# Install Redis
sudo apt-get install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf

# Set password
requirepass your_redis_password

# Restart Redis
sudo systemctl restart redis-server

# Test connection
redis-cli ping
```

## Health Checks & Monitoring

### 1. Application Health Check
```python
# Add to src/bot/telegram_bot.py
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
```

### 2. External Monitoring
```bash
# Simple health check script
#!/bin/bash
# health_check.sh

HEALTH_URL="http://localhost:8080/health"
TELEGRAM_BOT_TOKEN="your_token"

# Check HTTP health endpoint
if curl -f $HEALTH_URL > /dev/null 2>&1; then
    echo "Health check passed"
else
    echo "Health check failed"
    # Send alert to Telegram
    curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
         -d "chat_id=your_admin_chat_id" \
         -d "text=🚨 Hedging Bot Health Check Failed!"
fi
```

### 3. Process Monitoring
```bash
# Monitor with supervisord
sudo apt-get install supervisor

# Create supervisor config
sudo nano /etc/supervisor/conf.d/hedging-bot.conf
```

```ini
[program:hedging-bot]
command=/opt/hedging-bot/venv/bin/python -m src.bot.telegram_bot
directory=/opt/hedging-bot
user=hedging-bot
autostart=true
autorestart=true
stderr_logfile=/var/log/hedging-bot/error.log
stdout_logfile=/var/log/hedging-bot/out.log
```

## Backup & Recovery

### 1. Configuration Backup
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/hedging-bot"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz config/

# Backup logs
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz logs/

# Keep only last 30 backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

### 2. Database Backup (if using)
```bash
# PostgreSQL backup
pg_dump hedging_bot > /backups/hedging-bot/db_$(date +%Y%m%d_%H%M%S).sql

# Automated daily backup
echo "0 2 * * * /opt/hedging-bot/backup.sh" | sudo crontab -
```

## Troubleshooting

### Common Issues

#### 1. Bot Not Responding
```bash
# Check if process is running
ps aux | grep python

# Check logs
tail -f logs/hedging_bot.log

# Test bot token
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"
```

#### 2. Market Data Issues
```bash
# Test market data connectivity
python -c "import yfinance as yf; print(yf.Ticker('AAPL').info['regularMarketPrice'])"

# Check API rate limits
grep "rate limit" logs/hedging_bot.log
```

#### 3. High Memory Usage
```bash
# Monitor memory usage
python -m memory_profiler src/bot/telegram_bot.py

# Adjust cache settings in config.yaml
market_data:
  cache_duration: 60  # Reduce cache time
```

#### 4. Performance Issues
```bash
# Profile performance
python -m cProfile -o profile.stats src/bot/telegram_bot.py

# Analyze with snakeviz
pip install snakeviz
snakeviz profile.stats
```

### Log Analysis
```bash
# Common log analysis commands
grep "ERROR" logs/hedging_bot.log
grep "WARNING" logs/hedging_bot.log | tail -20
grep "rate limit" logs/hedging_bot.log | wc -l

# Monitor real-time
tail -f logs/hedging_bot.log | grep -E "(ERROR|WARNING|CRITICAL)"
```

## Scaling Considerations

### Horizontal Scaling
```yaml
# Multiple bot instances with load balancing
version: '3.8'
services:
  hedging-bot:
    build: .
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
```

### Performance Optimization
```python
# Async optimizations in config
bot_features:
  async_market_data: true
  connection_pooling: true
  batch_processing: true

# Resource limits
limits:
  max_concurrent_users: 100
  max_positions_per_user: 50
  market_data_cache_size: 1000
```

## Maintenance

### Regular Maintenance Tasks
```bash
# Weekly maintenance script
#!/bin/bash
# maintenance.sh

# Update market data cache
python -c "from src.utils.market_data import MarketDataProvider; MarketDataProvider().refresh_cache()"

# Clean old logs
find logs/ -name "*.log.*" -mtime +7 -delete

# Update dependencies (test environment first)
pip list --outdated

# Restart service
sudo systemctl restart hedging-bot
```

### Update Procedure
```bash
# 1. Backup current version
cp -r /opt/hedging-bot /opt/hedging-bot.backup

# 2. Pull updates
git pull origin main

# 3. Update dependencies
pip install -r requirements.txt

# 4. Test configuration
python -m src.bot.telegram_bot --test

# 5. Restart service
sudo systemctl restart hedging-bot

# 6. Verify deployment
python -c "from src.bot.telegram_bot import TelegramBot; print('Import successful')"
```

## Support & Maintenance

### Getting Help
- **Documentation**: Check TECHNICAL_REPORT.md for detailed system information
- **Logs**: Application logs are in logs/hedging_bot.log
- **Testing**: Run `pytest tests/` to validate system functionality
- **Configuration**: Validate config with `python -m src.bot.telegram_bot --test`

### Monitoring Checklist
- [ ] Bot responds to `/start` command
- [ ] Market data is updating
- [ ] Risk calculations are accurate
- [ ] Alerts are being sent
- [ ] System resources are within limits
- [ ] Logs show no critical errors

---

**Deployment Guide Version**: 1.0  
**Last Updated**: July 15, 2025  
**Compatibility**: Python 3.10+, Linux/Windows  
**Support**: Check logs and test suite for troubleshooting
