from alpaca_trade_api.rest import REST
from typing import Dict
import config

class AlpacaHandler:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.api = REST(api_key, api_secret, base_url)
    
    async def execute_trade(self, signal: Dict):
        """Execute trade on Alpaca based on the signal"""
        try:
            symbol = signal['symbol']
            action = signal['action'].upper()
            price = signal['price']
            
            # Get account equity
            account = self.api.get_account()
            equity = float(account.equity)
            
            # Calculate position size based on risk percentage
            risk_amount = equity * (config.DEFAULT_RISK_PERCENTAGE / 100)
            quantity = int(risk_amount / price)  # Round down to nearest whole share
            
            # Place order
            order = self.api.submit_order(
                symbol=symbol,
                qty=quantity,
                side=action,
                type='limit',
                time_in_force='gtc',
                limit_price=price
            )
            
            return {
                "order_id": order.id,
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "price": price
            }
            
        except Exception as e:
            raise Exception(f"Alpaca trade execution failed: {str(e)}")
