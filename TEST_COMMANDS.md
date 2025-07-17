# 🧪 Spot Hedging Bot - Test Commands Guide

## Quick Start Test Sequence

### 1. Bot Initialization
```
/start
```
- Tests: Welcome message, user initialization, interactive buttons

### 2. Add Positions (Test different assets)
```
/add_position BTC 0.1
/add_position ETH 2.0
/add_position AAPL 100 190
/add_position TSLA 50
```
- Tests: Market data fetching, position creation, portfolio management

### 3. View Portfolio
```
/portfolio
```
- Tests: Portfolio overview, P&L calculation, risk metrics display

### 4. Risk Monitoring
```
/monitor_risk BTC 0.1 0.05
/monitor_risk AAPL 100 0.1
```
- Tests: Risk threshold monitoring, background tasks, alert system

### 5. Hedge Analysis
```
/hedge_status
```
- Tests: Risk breach detection, hedge recommendations, strategy engine

### 6. Auto-Hedge Setup
```
/auto_hedge delta_neutral 0.1
/auto_hedge protective_put 0.05
```
- Tests: Auto-hedge configuration, strategy validation

### 7. Analytics and Reporting
```
/analytics
/hedge_history
```
- Tests: Portfolio analytics, performance tracking, detailed metrics

### 8. Settings Management
```
/settings
```
- Tests: Configuration management, user preferences

### 9. Interactive Button Tests
- Click "📊 View Portfolio" button
- Click "⚖️ Hedge Now" button
- Click "📈 View Analytics" button
- Click "⚙️ Settings" button
- Click "🔄 Refresh" buttons

### 10. Edge Cases
```
/add_position INVALID 100
/monitor_risk BTC 0 0.1
/auto_hedge invalid_strategy 0.1
```
- Tests: Error handling, input validation, graceful failures

## Expected Results

### ✅ Successful Tests Should Show:
1. **Portfolio Management**: Real-time P&L calculations, position tracking
2. **Risk Monitoring**: Breach detection, threshold alerts
3. **Hedge Recommendations**: Delta-neutral, protective put, collar strategies
4. **Market Data**: Live price updates for crypto (BTC, ETH) and stocks (AAPL, TSLA)
5. **Interactive UI**: All buttons functional, smooth navigation
6. **Analytics**: Detailed risk metrics, performance breakdown
7. **Auto-Hedge**: Strategy configuration, background monitoring

### 🔧 Performance Metrics to Verify:
- Response time < 3 seconds for most commands
- Market data updates within 5 seconds
- Risk calculations accuracy
- Interactive buttons responsiveness
- Error messages clarity

## Test Scenarios by Feature

### Portfolio Management
```bash
# Basic portfolio operations
/add_position BTC 0.5 120000
/add_position ETH 3.0
/portfolio

# Test mixed portfolio
/add_position AAPL 200 185
/add_position MSFT 100
/analytics
```

### Risk Management
```bash
# Risk monitoring setup
/monitor_risk BTC 0.5 0.08
/hedge_status

# Auto-hedge scenarios
/auto_hedge delta_neutral 0.1
/auto_hedge protective_put 0.03
```

### Interactive Features
```bash
# Test all callback buttons after each command
/start  # Test all start menu buttons
/portfolio  # Test portfolio action buttons
/hedge_status  # Test hedge action buttons
/settings  # Test settings buttons
```

### Error Handling
```bash
# Invalid inputs
/add_position 
/monitor_risk ABC
/auto_hedge 
/add_position XYZ 0 100
```

## Advanced Test Scenarios

### Stress Testing
```bash
# Multiple positions
/add_position BTC 1.0
/add_position ETH 5.0
/add_position AAPL 500
/add_position TSLA 200
/add_position GOOGL 50
/analytics
```

### Risk Breach Simulation
```bash
# Create large position to trigger risk alerts
/add_position BTC 2.0
/monitor_risk BTC 2.0 0.01  # Very low threshold
# Wait for risk alerts and test hedge recommendations
```

### Strategy Testing
```bash
# Test different hedge strategies
/auto_hedge delta_neutral 0.15
/hedge_status
/auto_hedge protective_put 0.05
/hedge_status
/auto_hedge collar 0.08
/hedge_status
```
