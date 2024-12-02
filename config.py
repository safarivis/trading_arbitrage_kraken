import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Trading platforms configuration
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')  # Use paper trading by default

MT5_LOGIN = os.getenv('MT5_LOGIN')
MT5_PASSWORD = os.getenv('MT5_PASSWORD')
MT5_SERVER = os.getenv('MT5_SERVER')

# Webhook configuration
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-secret-key')  # Used to verify TradingView signals

# Trading parameters
DEFAULT_RISK_PERCENTAGE = float(os.getenv('DEFAULT_RISK_PERCENTAGE', '1.0'))  # Risk per trade
MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', '5'))  # Maximum number of open positions
