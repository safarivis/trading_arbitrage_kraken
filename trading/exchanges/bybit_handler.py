"""
Bybit exchange handler for executing trades based on TradingView signals.
Supports both USDT Perpetual Futures and USDC Options trading.
"""

import logging
from typing import Dict
from pybit.unified_trading import HTTP
import math
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class BybitHandler:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """Initialize Bybit client with API credentials"""
        self.logger = logging.getLogger(__name__)
        
        # Initialize client
        self.client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        
        self.testnet = testnet
        
        # Test connection
        try:
            account_info = self.client.get_wallet_balance(accountType="UNIFIED")
            self.logger.info(f"Connected to {'Bybit Testnet' if testnet else 'Bybit'}")
            self.logger.info(f"Account Type: UNIFIED")
        except Exception as e:
            self.logger.error(f"Failed to connect to Bybit: {str(e)}")
            raise

    def get_symbol_info(self, symbol: str) -> dict:
        """Get trading information for a symbol"""
        try:
            instruments = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            return instruments['result']
        except Exception as e:
            self.logger.error(f"Error getting symbol info: {str(e)}")
            raise

    def calculate_position_size(self, symbol: str, entry_price: float, 
                              risk_percentage: float = 1.0) -> float:
        """Calculate position size based on risk percentage"""
        try:
            # Get account balance
            balance = self.client.get_wallet_balance(accountType="UNIFIED")
            quote_asset = symbol.replace('USDT', '')
            available_balance = float(balance['result']['list'][0]['totalWalletBalance'])
            
            # Calculate quantity based on risk
            risk_amount = available_balance * (risk_percentage / 100)
            quantity = risk_amount / entry_price
            
            # Get symbol precision
            symbol_info = self.get_symbol_info(symbol)
            precision = symbol_info['list'][0]['lotSizeFilter']['qtyStep'].count('0')
            
            # Round down to meet lot size requirements
            quantity = math.floor(quantity * (10 ** precision)) / (10 ** precision)
            
            self.logger.info(f"Calculated position size: {quantity} {symbol} (Risk: {risk_percentage}% of {available_balance} USDT)")
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            raise

    async def execute_trade(self, signal: Dict) -> Dict:
        """Execute a trade based on TradingView signal"""
        try:
            symbol = signal['symbol']
            side = "Buy" if signal['action'].lower() == 'buy' else "Sell"
            price = float(signal['price'])
            
            # Calculate position size
            quantity = self.calculate_position_size(
                symbol=symbol,
                entry_price=price,
                risk_percentage=signal.get('risk_percentage', 1.0)
            )
            
            # Prepare order parameters
            order_params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": "Limit",
                "qty": str(quantity),
                "price": str(price),
                "timeInForce": "GTC",
                "positionIdx": 0,  # 0: One-Way Mode
                "reduceOnly": False
            }
            
            # Log order details
            self.logger.info(f"Placing order: {order_params}")
            
            # Place the order
            order = self.client.place_order(**order_params)
            
            # Log success
            self.logger.info(f"Order placed successfully: {order['result']['orderId']}")
            
            return {
                'order_id': order['result']['orderId'],
                'symbol': symbol,
                'action': side,
                'quantity': quantity,
                'price': price,
                'status': order['result']['orderStatus'],
                'testnet': self.testnet
            }
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {str(e)}")
            raise

    def get_order_status(self, symbol: str, order_id: str) -> dict:
        """Get the status of a specific order"""
        try:
            order = self.client.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            return {
                "order_id": order['result']['list'][0]['orderId'],
                "symbol": order['result']['list'][0]['symbol'],
                "status": order['result']['list'][0]['orderStatus'],
                "price": float(order['result']['list'][0]['price']),
                "quantity": float(order['result']['list'][0]['qty']),
                "executed_quantity": float(order['result']['list'][0]['cumExecQty']),
                "side": order['result']['list'][0]['side'],
                "type": order['result']['list'][0]['orderType'],
                "time": datetime.fromtimestamp(
                    order['result']['list'][0]['createdTime'] / 1000
                ).isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting order status: {str(e)}")
            raise
