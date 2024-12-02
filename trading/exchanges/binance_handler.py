from binance.client import Client
from binance.enums import *
from typing import Dict
import logging
import time
import math
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class BinanceHandler:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """Initialize Binance client with API credentials"""
        self.logger = logging.getLogger(__name__)
        
        # Configure proxy settings
        proxies = {
            'http': 'http://api.allorigins.win/raw?url=',
            'https': 'https://api.allorigins.win/raw?url='
        }
        
        # Use alternative testnet URL
        if testnet:
            self.client = Client(api_key, api_secret, testnet=True)
            # Use proxy for testnet
            self.client.API_URL = 'https://api.allorigins.win/raw?url=https://testnet.binance.vision/api'
            self.client.session.proxies = proxies
        else:
            self.client = Client(api_key, api_secret, testnet=False)
            
        self.testnet = testnet
        
        # Test connection
        try:
            account_info = self.client.get_account()
            self.logger.info(f"Connected to {'Binance Testnet' if testnet else 'Binance'}")
            self.logger.info(f"Account Status: {account_info['accountType']}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {str(e)}")
            raise
    
    def get_symbol_info(self, symbol: str) -> dict:
        """Get trading rules and precision for a symbol"""
        info = self.client.get_symbol_info(symbol)
        if not info:
            raise ValueError(f"Symbol {symbol} not found")
        return info
    
    def get_balance(self, asset: str) -> float:
        """Get free balance for a specific asset"""
        account = self.client.get_account()
        for balance in account['balances']:
            if balance['asset'] == asset:
                return float(balance['free'])
        return 0.0
    
    def calculate_position_size(self, symbol: str, price: float, risk_percentage: float = 1.0) -> float:
        """Calculate position size based on account balance and risk percentage"""
        try:
            # Get symbol information for precision
            symbol_info = self.get_symbol_info(symbol)
            
            # Get quote asset (e.g., USDT from BTCUSDT)
            quote_asset = symbol_info['quoteAsset']
            
            # Get available balance in quote asset
            balance = self.get_balance(quote_asset)
            
            # Calculate risk amount
            risk_amount = balance * (risk_percentage / 100)
            
            # Calculate quantity
            quantity = risk_amount / price
            
            # Round to symbol's lot size
            lot_size_filter = next(filter(lambda x: x['filterType'] == 'LOT_SIZE', symbol_info['filters']))
            step_size = float(lot_size_filter['stepSize'])
            precision = int(round(-math.log10(step_size)))
            
            # Round down to meet lot size requirements
            quantity = math.floor(quantity * (10 ** precision)) / (10 ** precision)
            
            self.logger.info(f"Calculated position size: {quantity} {symbol} (Risk: {risk_percentage}% of {balance} {quote_asset})")
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            raise
    
    async def execute_trade(self, signal: Dict) -> Dict:
        """Execute trade based on TradingView signal"""
        try:
            symbol = signal['symbol']
            action = signal['action'].upper()
            price = float(signal['price'])
            
            # Validate action
            if action not in ['BUY', 'SELL']:
                raise ValueError(f"Invalid action: {action}. Must be 'BUY' or 'SELL'")
            
            # Calculate position size
            quantity = self.calculate_position_size(
                symbol=symbol,
                price=price,
                risk_percentage=1.0  # Default risk percentage
            )
            
            # Get symbol trading rules
            symbol_info = self.get_symbol_info(symbol)
            
            # Prepare order parameters
            order_params = {
                'symbol': symbol,
                'side': SIDE_BUY if action == 'BUY' else SIDE_SELL,
                'type': ORDER_TYPE_LIMIT,
                'timeInForce': TIME_IN_FORCE_GTC,
                'quantity': quantity,
                'price': price
            }
            
            # Log order details
            self.logger.info(f"Placing order: {order_params}")
            
            # Place the order
            order = self.client.create_order(**order_params)
            
            # Log success
            self.logger.info(f"Order placed successfully: {order['orderId']}")
            
            return {
                'order_id': order['orderId'],
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': price,
                'status': order['status'],
                'testnet': self.testnet
            }
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {str(e)}")
            raise
    
    def get_order_status(self, symbol: str, order_id: int) -> dict:
        """Get the status of a specific order"""
        try:
            order = self.client.get_order(symbol=symbol, orderId=order_id)
            return {
                "order_id": order["orderId"],
                "symbol": order["symbol"],
                "status": order["status"],
                "price": float(order["price"]),
                "quantity": float(order["origQty"]),
                "executed_quantity": float(order["executedQty"]),
                "side": order["side"],
                "type": order["type"],
                "time": datetime.fromtimestamp(order["time"] / 1000).isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting order status: {str(e)}")
            raise
