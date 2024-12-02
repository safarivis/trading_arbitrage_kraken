# Volatility-Adaptive Crypto Arbitrage

A crypto trading system that executes arbitrage trades across exchanges while adapting to market volatility. Features automated data collection, position sizing based on volatility metrics, and built-in risk management rules. Includes backtesting tools and historical data analysis.

# Trading Automation System

A complete trading automation system that executes trades based on TradingView signals across multiple crypto exchanges.

## Supported Exchanges

### Binance
- **API Integration**: Uses REST API
- **Features**:
  - Real-time price data
  - Account balance queries
  - Market/Limit order placement
  - Take Profit and Stop Loss support
- **Setup**:
  1. Add your Binance API credentials to `.env`:
     ```
     BINANCE_API_KEY=your_api_key
     BINANCE_API_SECRET=your_api_secret
     ```
  2. Use `BinanceTrader` class for trading operations:
     ```python
     from binance_trader import BinanceTrader
     
     trader = BinanceTrader()
     balance = trader.get_balance('USD')
     price = trader.get_market_price('BTCUSDT', price_type='last')
     ```
  3. Available price types:
     - 'last': Last trade price
     - 'bid': Current bid price
     - 'ask': Current ask price
     - 'high': 24h high
     - 'low': 24h low
     - 'vwap': Volume weighted average price

### Alpaca
- **API Integration**: Uses REST API
- **Features**:
  - Real-time price data
  - Account balance queries
  - Market/Limit order placement
  - Take Profit and Stop Loss support
- **Setup**:
  1. Add your Alpaca API credentials to `.env`:
     ```
     ALPACA_API_KEY=your_api_key
     ALPACA_API_SECRET=your_api_secret
     ```
  2. Use `AlpacaTrader` class for trading operations:
     ```python
     from alpaca_trader import AlpacaTrader
     
     trader = AlpacaTrader()
     balance = trader.get_balance('USD')
     price = trader.get_market_price('AAPL', price_type='last')
     ```
  3. Available price types:
     - 'last': Last trade price
     - 'bid': Current bid price
     - 'ask': Current ask price
     - 'high': 24h high
     - 'low': 24h low
     - 'vwap': Volume weighted average price

### MetaTrader 5
- **API Integration**: Uses MetaTrader 5 API
- **Features**:
  - Real-time price data
  - Account balance queries
  - Market/Limit order placement
  - Take Profit and Stop Loss support
- **Setup**:
  1. Add your MetaTrader 5 API credentials to `.env`:
     ```
     MT5_API_KEY=your_api_key
     MT5_API_SECRET=your_api_secret
     ```
  2. Use `MT5Trader` class for trading operations:
     ```python
     from mt5_trader import MT5Trader
     
     trader = MT5Trader()
     balance = trader.get_balance('USD')
     price = trader.get_market_price('EURUSD', price_type='last')
     ```
  3. Available price types:
     - 'last': Last trade price
     - 'bid': Current bid price
     - 'ask': Current ask price
     - 'high': 24h high
     - 'low': 24h low
     - 'vwap': Volume weighted average price

### Kraken (Spot Trading)
- **API Integration**: Uses both REST and WebSocket APIs
- **Features**:
  - Real-time price data via WebSocket
  - Account balance queries
  - Market/Limit order placement
  - Take Profit and Stop Loss support
  - Multiple price types (last, bid, ask, high, low, VWAP)
- **Setup**:
  1. Add your Kraken API credentials to `.env`:
     ```
     KRAKEN_API_KEY=your_api_key
     KRAKEN_API_SECRET=your_api_secret
     ```
  2. Use `KrakenTrader` class for trading operations:
     ```python
     from kraken_trader import KrakenTrader
     
     trader = KrakenTrader()
     balance = trader.get_balance('USD')
     price = trader.get_market_price('BTCUSDT', price_type='last')
     ```
  3. Available price types:
     - 'last': Last trade price
     - 'bid': Current bid price
     - 'ask': Current ask price
     - 'high': 24h high
     - 'low': 24h low
     - 'vwap': Volume weighted average price

## Project Structure
- `main.py`: FastAPI server for TradingView webhooks
- `binance_trader.py`: Binance exchange integration
- `alpaca_trader.py`: Alpaca exchange integration
- `mt5_trader.py`: MetaTrader 5 exchange integration
- `kraken_trader.py`: Kraken exchange integration
- `config.py`: Configuration management
- `requirements.txt`: Dependencies
- `.env`: API credentials and settings

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `.env` with your API credentials

3. Start the server:
```bash
python main.py
```

## TradingView Integration
The system receives signals via webhooks from TradingView indicators. Webhook endpoint: `/webhook`

## Risk Management
- Position sizing based on account balance
- Stop loss and take profit functionality
- Maximum position size limits

## Testing
- Use testnet/paper trading accounts for testing
- Binance: Use testnet account with small amounts
- Alpaca: Paper trading is automatically available
- MetaTrader 5: Use demo account with small amounts
- Kraken: Use main account with small amounts

## Error Handling
- Comprehensive error logging
- Automatic WebSocket reconnection
- API error management

## Security
- API key storage in `.env`
- Webhook authentication
- Secure connection handling

I've created a complete trading automation system that integrates with TradingView signals. Here's what I've set up:

Project Structure:
main.py: The main FastAPI server that receives TradingView webhooks
config.py: Configuration management using environment variables
trading/exchanges/: Exchange-specific handlers for Binance, Alpaca, and MT5
requirements.txt: All necessary dependencies
.env.example: Template for your API credentials
README.md: Comprehensive documentation
Key Features:
Webhook endpoint to receive TradingView signals
Support for multiple exchanges (Binance, Alpaca, MT5)
Risk management with position sizing
Secure webhook verification
Proper error handling
Configuration via environment variables
To get started:

First, install the required dependencies:
bash
CopyInsert in Terminal
pip install -r requirements.txt
Copy the .env.example file to .env and fill in your API credentials:
bash
CopyInsert in Terminal
cp .env.example .env
Start the server:
bash
CopyInsert in Terminal
python main.py
The server will run on port 8000 and be ready to receive TradingView webhook signals.

Would you like me to explain any specific part of the implementation or help you set up your TradingView alerts to work with this system?

Me
does teh above exchangess have demo trading acc in order to test 1st ?

Yes, all three exchanges offer demo/paper trading accounts! Let me explain how to get them for each platform:

Binance Testnet:
Go to testnet.binance.vision
Create a testnet account to get API keys
You'll receive free test USDT to practice trading
In our config.py, you'll use these testnet credentials
No real money involved
Alpaca Paper Trading (Already configured in our code):
Go to app.alpaca.markets/signup
Sign up for a free account
Paper trading is automatically available
Our code already uses paper trading URL by default: https://paper-api.alpaca.markets
You get $100,000 in virtual money to practice
MetaTrader 5 Demo:
Download MT5 platform from www.metatrader5.com
Open MT5
Click "File" → "Open an Account"
Choose any broker that offers demo accounts
Fill in the registration form and select "Demo Account"
You'll receive demo login credentials to use in our code
Kraken Demo:
Go to www.kraken.com
Sign up for a free account
Click on "Funding" and then "Subaccounts"
Create a new subaccount and select "Demo"
You'll receive demo login credentials to use in our code
Let me modify our configuration to make it clearer how to use demo accounts:

# Crypto Trading System

## Overview
A volatility-adaptive arbitrage trading system that exploits price inefficiencies while managing risk through dynamic position sizing and spread-based entry/exit signals.

### Strategy Concept
The strategy combines two profitable approaches:
1. **Arbitrage**: Exploiting price inefficiencies between markets
2. **Volatility Adaptation**: Adjusting position sizes and trading thresholds based on market conditions

## Why This Strategy Works
- Markets remain inefficient due to:
  - Fragmented exchanges with varying liquidity
  - Information and execution speed differences
  - Regional price variations
  - Human error in market making

## Implementation Plan

### Phase 1: Data Collection and Backtesting (Current)
- [x] Implement FastDataCollector for efficient historical data retrieval
- [x] Create BacktestEngine for strategy simulation
- [x] Develop VolatilityAdaptiveStrategy with dynamic position sizing
- [ ] Fine-tune strategy parameters using historical data
- [ ] Validate results across different market conditions

### Phase 2: Live Testing Setup
1. Exchange Integration
   - Primary: Kraken (already integrated)
   - Secondary: Binance, Coinbase Pro
   - Use CCXT library for unified API access

2. Data Pipeline
   - Real-time price feeds from multiple exchanges
   - Funding rate monitoring
   - Volatility calculation engine

3. Execution Engine
   - Order management system
   - Position tracking
   - Risk management rules

### Phase 3: Paper Trading
- Initial capital: $1,000 (virtual)
- Focus on BTC/USDT and ETH/USDT pairs
- Monitor execution quality and latency
- Validate risk management rules

### Phase 4: Live Trading
- Start with $1,000 real capital
- Implement strict position limits
- Monitor and optimize execution costs

## Technical Architecture

### Components
1. Data Collection
   - FastDataCollector: Historical and real-time data
   - APIs: Kraken, Binance, CryptoCompare

2. Strategy Engine
   - VolatilityAdaptiveStrategy: Core trading logic
   - Risk Management: Position sizing, leverage limits
   - Signal Generation: Spread and volatility based

3. Execution
   - Order Management: Entry/exit execution
   - Position Tracking: Real-time P&L monitoring
   - Risk Controls: Automated circuit breakers

### Required APIs
- Kraken API (Primary)
- Binance API (Secondary)
- CryptoCompare (Market Data)
- CCXT (Universal Exchange Interface)

## Risk Management

### Key Risks
1. Execution Risk
   - Mitigation: Conservative spread thresholds
   - Slippage buffers in position sizing

2. Technical Risk
   - Redundant exchange connections
   - Automated error handling
   - Regular system health checks

3. Market Risk
   - Dynamic position sizing
   - Volatility-based leverage limits
   - Maximum drawdown controls

### Risk Parameters
- Max Position Size: 60% of capital
- Max Leverage: 3x (dynamically reduced with volatility)
- Min Required Spread: 0.1% (adjusted for volatility)
- Max Drawdown Limit: 15%

## Expected Returns

### Conservative Scenario
- Win Rate: 55-60%
- Average Trade Profit: 0.1-0.2%
- Monthly Return Target: 3-5%
- Max Drawdown: < 10%

### Optimal Scenario
- Win Rate: 65-70%
- Average Trade Profit: 0.2-0.3%
- Monthly Return Target: 8-12%
- Max Drawdown: < 15%

## Getting Started

### Prerequisites
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration
1. Copy `.env.example` to `.env`
2. Add your API keys and configuration

### Running Backtests
```bash
python backtest_volatility_strategy.py
```

### Running Live System
```bash
python main.py
```

## Development Status
- Currently in Phase 1 (Backtesting)
- Next steps:
  1. Complete strategy parameter optimization
  2. Implement real-time data feeds
  3. Set up paper trading environment

## Contributing
Feel free to submit issues and enhancement requests!

## License
MIT License