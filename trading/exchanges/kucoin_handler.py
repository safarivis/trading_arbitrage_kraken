"""
KuCoin exchange handler for executing trades based on TradingView signals.
Supports both spot and futures trading.
"""

import logging
from typing import Dict
from kucoin.client import Market, Trade, User
from kucoin.futures.client import FuturesClient
import math
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class KuCoinHandler:
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str, 
                 testnet: bool = True):
        """Initialize KuCoin client with API credentials"""
        self.logger = logging.getLogger(__name__)
        
        # Set API URL based on environment
        api_url = 'https://openapi-sandbox.kucoin.com' if testnet else 'https://api.kucoin.com'
        
        # Initialize clients
        self.market_client = Market(url=api_url)
        self.trade_client = Trade(key=api_key, secret=api_secret, 
                                passphrase=api_passphrase, is_sandbox=testnet, url=api_url)
        self.user_client = User(key=api_key, secret=api_secret, 
                              passphrase=api_passphrase, is_sandbox=testnet, url=api_url)
        
        # Initialize futures client if needed
        self.futures_client = FuturesClient(key=api_key, secret=api_secret,
                                          passphrase=api_passphrase, is_sandbox=testnet)
        
        self.testnet = testnet
        
        # Test connection
        try:
            account_info = self.user_client.get_account_list()[0]
            self.logger.info(f"Connected to {'KuCoin Sandbox' if testnet else 'KuCoin'}")
            self.logger.info(f"Account Type: {account_info['type']}")
        except Exception as e:
            self.logger.error(f"Failed to connect to KuCoin: {str(e)}")
            raise

    def get_symbol_info(self, symbol: str) -> dict:
        """Get trading information for a symbol"""
        try:
            return self.market_client.get_symbol_detail(symbol)
        except Exception as e:
            self.logger.error(f"Error getting symbol info: {str(e)}")
            raise

    def calculate_position_size(self, symbol: str, entry_price: float, 
                              risk_percentage: float = 1.0) -> float:
        """Calculate position size based on risk percentage"""
        try:
            # Get account balance
            accounts = self.user_client.get_account_list()
            quote_asset = symbol.split('-')[1]  # KuCoin uses BTC-USDT format
            balance = next(
                (acc for acc in accounts if acc['currency'] == quote_asset 
                 and acc['type'] == 'trade'),
                None
            )
            
            if not balance:
                raise ValueError(f"No trading account found for {quote_asset}")
                
            available_balance = float(balance['available'])
            
            # Calculate quantity based on risk
            risk_amount = available_balance * (risk_percentage / 100)
            quantity = risk_amount / entry_price
            
            # Get symbol precision
            symbol_info = self.get_symbol_info(symbol)
            precision = int(symbol_info['baseIncrement'].find('1') - 1)
            
            # Round down to meet lot size requirements
            quantity = math.floor(quantity * (10 ** precision)) / (10 ** precision)
            
            self.logger.info(f"Calculated position size: {quantity} {symbol} (Risk: {risk_percentage}% of {available_balance} {quote_asset})")
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            raise

    async def execute_trade(self, signal: Dict) -> Dict:
        """Execute a trade based on TradingView signal"""
        try:
            symbol = signal['symbol'].replace('/', '-')  # Convert BTCUSDT to BTC-USDT
            side = signal['action'].lower()
            price = str(signal['price'])
            
            # Calculate position size
            quantity = self.calculate_position_size(
                symbol=symbol,
                entry_price=float(price),
                risk_percentage=signal.get('risk_percentage', 1.0)
            )
            
            # Place order
            order = self.trade_client.create_limit_order(
                symbol=symbol,
                side=side,
                price=price,
                size=str(quantity)
            )
            
            self.logger.info(f"Order placed successfully: {order['orderId']}")
            
            # Get order details
            order_details = self.trade_client.get_order_details(order['orderId'])
            
            return {
                'order_id': order_details['id'],
                'symbol': symbol,
                'action': side,
                'quantity': float(order_details['size']),
                'price': float(order_details['price']),
                'status': order_details['status'],
                'testnet': self.testnet
            }
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {str(e)}")
            raise

    def get_order_status(self, order_id: str) -> dict:
        """Get the status of a specific order"""
        try:
            order = self.trade_client.get_order_details(order_id)
            return {
                "order_id": order['id'],
                "symbol": order['symbol'],
                "status": order['status'],
                "price": float(order['price']),
                "quantity": float(order['size']),
                "executed_quantity": float(order['dealSize']),
                "side": order['side'],
                "type": order['type'],
                "time": datetime.fromtimestamp(
                    float(order['createdAt']) / 1000
                ).isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting order status: {str(e)}")
            raise
