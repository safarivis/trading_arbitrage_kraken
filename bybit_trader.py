from pybit.spot import HTTP
import os
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime
import requests

# Load environment variables
load_dotenv()

class BybitTrader:
    def __init__(self):
        testnet = os.getenv('TESTNET', 'false').lower() == 'true'
        self.testnet = testnet
        self.base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        
        # Initialize spot API client
        self.client = HTTP(
            endpoint=self.base_url + "/spot/v1",
            api_key=os.getenv('BYBIT_API_KEY'),
            api_secret=os.getenv('BYBIT_API_SECRET')
        )
        print("Initialized Bybit client with testnet:", testnet)

    def get_balance(self, coin: str = 'USDT') -> float:
        """Get balance for a specific coin"""
        try:
            url = f"{self.base_url}/spot/v1/account"
            response = requests.get(url, auth=(os.getenv('BYBIT_API_KEY'), os.getenv('BYBIT_API_SECRET')))
            print(f"Full balance response: {response.json()}")
            
            if response.status_code == 200:
                data = response.json()
                balances = data.get('result', {}).get('balances', [])
                for balance in balances:
                    if balance['coin'] == coin:
                        return float(balance['free'])
            return 0.0
        except Exception as e:
            print(f"Error getting balance: {str(e)}")
            return 0.0

    def get_market_price(self, symbol: str) -> float:
        """Get current market price for a symbol"""
        try:
            url = f"{self.base_url}/spot/quote/v1/ticker/price"
            params = {'symbol': symbol}
            response = requests.get(url, params=params, auth=(os.getenv('BYBIT_API_KEY'), os.getenv('BYBIT_API_SECRET')))
            print(f"Price response: {response.json()}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ret_code') == 0:
                    return float(data['result']['price'])
            return 0.0
        except Exception as e:
            print(f"Error getting market price: {str(e)}")
            return 0.0

    def place_order(self, symbol: str, side: str, quantity: float, 
                   price: Optional[float] = None, take_profit: Optional[float] = None, 
                   stop_loss: Optional[float] = None) -> dict:
        """
        Place an order on Bybit
        :param symbol: Trading pair (e.g., 'BTCUSDT')
        :param side: 'Buy' or 'Sell'
        :param quantity: Order quantity
        :param price: Optional limit price (if None, places market order)
        :param take_profit: Optional take profit price
        :param stop_loss: Optional stop loss price
        """
        try:
            order_type = "LIMIT" if price else "MARKET"
            
            params = {
                "symbol": symbol,
                "qty": str(quantity),
                "side": side.upper(),
                "type": order_type,
            }
            
            if price:
                params["price"] = str(price)

            # For spot market, we handle take profit and stop loss as separate orders
            response = self.client.place_active_order(**params)
            print(f"Order placed: {response}")
            
            # If main order successful and we have TP/SL, place them as separate orders
            if response.get('ret_code') == 0 and (take_profit or stop_loss):
                order_id = response['result']['orderId']
                
                if take_profit:
                    tp_params = {
                        "symbol": symbol,
                        "qty": str(quantity),
                        "side": "SELL" if side.upper() == "BUY" else "BUY",
                        "type": "LIMIT",
                        "price": str(take_profit),
                        "orderLinkId": f"tp_{order_id}"
                    }
                    tp_response = self.client.place_active_order(**tp_params)
                    print(f"Take profit order placed: {tp_response}")
                
                if stop_loss:
                    sl_params = {
                        "symbol": symbol,
                        "qty": str(quantity),
                        "side": "SELL" if side.upper() == "BUY" else "BUY",
                        "type": "STOP_LIMIT",
                        "price": str(stop_loss),
                        "orderLinkId": f"sl_{order_id}"
                    }
                    sl_response = self.client.place_active_order(**sl_params)
                    print(f"Stop loss order placed: {sl_response}")
            
            return response

        except Exception as e:
            print(f"Error placing order: {str(e)}")
            return {"error": str(e)}

if __name__ == "__main__":
    # Test the connection
    trader = BybitTrader()
    balance = trader.get_balance()
    print(f"USDT Balance: {balance}")
    btc_price = trader.get_market_price("BTCUSDT")
    print(f"BTC Price: {btc_price}")
