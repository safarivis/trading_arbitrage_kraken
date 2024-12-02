import MetaTrader5 as mt5
from typing import Dict
import config

class MT5Handler:
    def __init__(self, login: int, password: str, server: str):
        self.login = login
        self.password = password
        self.server = server
        self._initialize()
    
    def _initialize(self):
        """Initialize MT5 connection"""
        if not mt5.initialize():
            raise Exception("MT5 initialization failed")
        
        # Connect to MT5
        if not mt5.login(self.login, password=self.password, server=self.server):
            mt5.shutdown()
            raise Exception("MT5 login failed")
    
    async def execute_trade(self, signal: Dict):
        """Execute trade on MT5 based on the signal"""
        try:
            symbol = signal['symbol']
            action = signal['action'].upper()
            price = signal['price']
            
            # Get account info
            account_info = mt5.account_info()
            if account_info is None:
                raise Exception("Failed to get account info")
            
            balance = account_info.balance
            
            # Calculate position size based on risk percentage
            risk_amount = balance * (config.DEFAULT_RISK_PERCENTAGE / 100)
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                raise Exception(f"Symbol {symbol} not found")
            
            # Calculate lot size (standard lot is usually 100,000 units)
            lot_size = risk_amount / (100000 * symbol_info.point)
            
            # Round lot size to broker's requirements
            lot_size = round(lot_size, 2)  # Most brokers use 2 decimal places for lots
            
            # Prepare trade request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "deviation": 20,  # max deviation from requested price
                "magic": 234000,  # magic number to identify trades
                "comment": "TradingView signal",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send trade request
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise Exception(f"Order failed, return code: {result.retcode}")
            
            return {
                "order_id": result.order,
                "symbol": symbol,
                "action": action,
                "volume": lot_size,
                "price": price
            }
            
        except Exception as e:
            raise Exception(f"MT5 trade execution failed: {str(e)}")
    
    def __del__(self):
        """Cleanup MT5 connection"""
        mt5.shutdown()
