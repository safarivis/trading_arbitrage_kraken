# Setting Up TradingView Alerts

This guide explains how to set up TradingView alerts to work with your trading bot.

## Alert Setup

1. In TradingView, open your indicator or strategy
2. Click the "Create Alert" button
3. In the alert dialog:
   - Set your condition
   - Enable "Webhook URL"
   - Set the webhook URL to: `http://your-server:8000/webhook`
   - Set "Message" to the following format:

```json
{
    "exchange": "binance",
    "symbol": "{{ticker}}",
    "action": "{{strategy.order.action}}",
    "price": {{close}},
    "time": "{{time}}"
}
```

## Example Pine Script

Here's a simple example of a TradingView Pine Script that generates alerts:

```pinescript
//@version=5
strategy("Simple MACD Strategy", overlay=true)

// MACD Parameters
fastLength = input(12)
slowLength = input(26)
signalLength = input(9)

[macdLine, signalLine, _] = ta.macd(close, fastLength, slowLength, signalLength)

// Trading Logic
longCondition = ta.crossover(macdLine, signalLine)
shortCondition = ta.crossunder(macdLine, signalLine)

if (longCondition)
    strategy.entry("Long", strategy.long)

if (shortCondition)
    strategy.entry("Short", strategy.short)

// Alerts
alertcondition(longCondition, title="Buy Signal", message="BUY")
alertcondition(shortCondition, title="Sell Signal", message="SELL")
```

## Testing

1. Start your trading bot:
```bash
python trading_bot.py
```

2. Create a test alert in TradingView with this message:
```json
{
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "action": "buy",
    "price": 50000
}
```

3. Trigger the alert manually to test

## Important Notes

1. The bot uses 1% risk management by default
2. All orders are limit orders
3. The bot is configured to use Binance Testnet by default
4. Make sure your server is accessible from TradingView's IP addresses
5. Keep your API keys secure and never share them

## Troubleshooting

If alerts aren't working:
1. Check the bot's logs for errors
2. Verify the webhook URL is correct
3. Make sure your server is publicly accessible
4. Verify the alert message format is correct JSON
5. Check that the symbol exists on Binance
