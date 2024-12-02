import os
import time
import json
import hmac
import base64
import hashlib
import websockets
import requests
import asyncio
from typing import Optional, Dict, Any
from urllib.parse import urlencode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class KrakenTrader:
    def __init__(self):
        self.api_key = os.getenv('KRAKEN_API_KEY')
        self.api_secret = os.getenv('KRAKEN_API_SECRET')
        self.api_url = "https://api.kraken.com"
        self.ws_url = "wss://ws.kraken.com"
        self.session = requests.Session()
        self.websocket = None
        self.last_prices = {}

    def _get_kraken_signature(self, urlpath: str, data: Dict[str, Any]) -> str:
        """Generate Kraken API signature"""
        post_data = urlencode(data)
        encoded = (str(data['nonce']) + post_data).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.api_secret),
                           message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    def _make_request(self, uri_path: str, data: Dict[str, Any]) -> Dict:
        """Make an authenticated request to Kraken REST API"""
        headers = {
            'API-Key': self.api_key,
            'API-Sign': self._get_kraken_signature(uri_path, data)
        }
        
        response = self.session.post(
            self.api_url + uri_path,
            headers=headers,
            data=data
        )
        
        if response.status_code != 200:
            raise Exception(f'Kraken API request failed: {response.text}')
            
        result = response.json()
        
        if result.get('error'):
            raise Exception(f'Kraken API error: {result["error"]}')
            
        return result.get('result', {})

    def get_balance(self, asset: str = 'USD') -> float:
        """Get balance for a specific asset"""
        data = {
            'nonce': str(int(time.time() * 1000))
        }
        
        try:
            print("Fetching balance...")
            print(f"Using API Key: {self.api_key[:10]}...")
            result = self._make_request('/0/private/Balance', data)
            print(f"Full balance response: {json.dumps(result, indent=2)}")
            
            # Kraken asset code mapping
            kraken_assets = {
                'USD': 'ZUSD',
                'EUR': 'ZEUR',
                'BTC': 'XXBT',
                'ETH': 'XETH',
                'XBT': 'XXBT',  # Alternative name for Bitcoin
            }
            
            # Try both original and Kraken asset name
            kraken_asset = kraken_assets.get(asset, asset)
            balance = result.get(kraken_asset, result.get(asset, 0.0))
            print(f"Looking for asset: {asset} (Kraken: {kraken_asset})")
            print(f"Found balance: {balance}")
            
            return float(balance)
        except Exception as e:
            print(f"Error getting balance: {str(e)}")
            print(f"Error type: {type(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
            return 0.0

    def get_trading_pairs(self):
        """Get available trading pairs from Kraken"""
        try:
            response = requests.get(f"{self.api_url}/0/public/AssetPairs")
            if response.status_code == 200:
                result = response.json()
                if not result.get('error'):
                    print("Available pairs:", json.dumps(result['result'], indent=2))
                    return result['result']
            return {}
        except Exception as e:
            print(f"Error getting trading pairs: {str(e)}")
            return {}

    def get_market_price(self, symbol: str, price_type: str = 'last') -> float:
        """
        Get market price for a symbol
        :param symbol: Trading pair symbol (e.g., 'BTCUSDT')
        :param price_type: Type of price to return ('last', 'bid', 'ask', 'high', 'low')
        :return: Price as float
        """
        try:
            # First get all available pairs
            pairs = self.get_trading_pairs()
            print("\nLooking for matching pairs for:", symbol)
            
            # Try to find the best match for our symbol
            base = symbol[:3]
            quote = 'USD' if symbol[3:] == 'USDT' else symbol[3:]
            
            # Look for matching pairs
            matching_pairs = []
            for pair_name, pair_info in pairs.items():
                if (base.lower() in pair_info.get('base', '').lower() and 
                    quote.lower() in pair_info.get('quote', '').lower()):
                    matching_pairs.append(pair_name)
            
            if not matching_pairs:
                print(f"No matching pairs found for {symbol}")
                return 0.0
                
            # Use the first matching pair
            pair = matching_pairs[0]
            print(f"Using Kraken pair: {pair}")
            
            response = requests.get(
                f"{self.api_url}/0/public/Ticker",
                params={'pair': pair}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Price response: {json.dumps(result, indent=2)}")
                if not result.get('error'):
                    pair_data = list(result['result'].values())[0]
                    
                    # Extract all price types
                    prices = {
                        'last': float(pair_data['c'][0]),  # Last trade closed price
                        'ask': float(pair_data['a'][0]),   # Ask price
                        'bid': float(pair_data['b'][0]),   # Bid price
                        'high': float(pair_data['h'][0]),  # 24h high
                        'low': float(pair_data['l'][0]),   # 24h low
                        'vwap': float(pair_data['p'][0]),  # Volume weighted avg price
                        'volume': float(pair_data['v'][0]) # Volume
                    }
                    
                    print("\nAll prices:")
                    for k, v in prices.items():
                        print(f"{k.capitalize()}: {v}")
                    
                    return prices.get(price_type.lower(), prices['last'])
                    
            return 0.0
        except Exception as e:
            print(f"Error getting market price: {str(e)}")
            print(f"Error type: {type(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
            return 0.0

    def place_order(self, symbol: str, side: str, quantity: float,
                   price: Optional[float] = None, take_profit: Optional[float] = None,
                   stop_loss: Optional[float] = None) -> dict:
        """
        Place an order on Kraken
        :param symbol: Trading pair (e.g., 'BTCUSDT')
        :param side: 'buy' or 'sell'
        :param quantity: Order quantity
        :param price: Optional limit price (if None, places market order)
        :param take_profit: Optional take profit price
        :param stop_loss: Optional stop loss price
        """
        try:
            # Format symbol for Kraken (e.g., 'BTCUSDT' -> 'XBT/USDT')
            formatted_symbol = symbol.replace('BTC', 'XBT')
            formatted_symbol = '/'.join([formatted_symbol[:3], formatted_symbol[3:]])
            
            data = {
                'nonce': str(int(time.time() * 1000)),
                'ordertype': 'limit' if price else 'market',
                'type': side.lower(),
                'volume': str(quantity),
                'pair': formatted_symbol,
            }
            
            if price:
                data['price'] = str(price)
                
            if take_profit:
                data['take_profit'] = str(take_profit)
                
            if stop_loss:
                data['stop_loss'] = str(stop_loss)
            
            result = self._make_request('/0/private/AddOrder', data)
            print(f"Order placed: {result}")
            return result
            
        except Exception as e:
            print(f"Error placing order: {str(e)}")
            return {"error": str(e)}

    async def _connect_websocket(self):
        """Establish WebSocket connection"""
        self.websocket = await websockets.connect(self.ws_url)

    async def subscribe_to_ticker(self, symbol: str, callback):
        """Subscribe to real-time ticker data"""
        if not self.websocket:
            await self._connect_websocket()

        # Format symbol for Kraken WebSocket
        formatted_symbol = symbol.replace('BTC', 'XBT')
        formatted_symbol = formatted_symbol[:3] + '/' + formatted_symbol[3:]

        subscribe_message = {
            "event": "subscribe",
            "pair": [formatted_symbol],
            "subscription": {
                "name": "ticker"
            }
        }

        await self.websocket.send(json.dumps(subscribe_message))

        while True:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                # Handle ticker data
                if isinstance(data, list) and len(data) >= 2:
                    ticker_data = data[1]
                    if 'c' in ticker_data:  # 'c' contains the last trade closed price
                        price = float(ticker_data['c'][0])
                        self.last_prices[symbol] = price
                        await callback(symbol, price)
                        
            except Exception as e:
                print(f"WebSocket error: {str(e)}")
                await asyncio.sleep(1)  # Wait before reconnecting
                await self._connect_websocket()

if __name__ == "__main__":
    # Test the connection
    trader = KrakenTrader()
    balance = trader.get_balance()
    print(f"USD Balance: {balance}")
    
    # Get different types of prices
    for price_type in ['last', 'bid', 'ask', 'high', 'low']:
        price = trader.get_market_price("BTCUSDT", price_type)
        print(f"BTC {price_type.capitalize()} Price: {price}")
    
    # Test WebSocket connection
    async def price_callback(symbol, price):
        print(f"Real-time {symbol} price: {price}")

    async def main():
        await trader.subscribe_to_ticker("BTCUSDT", price_callback)

    # Run WebSocket test
    asyncio.run(main())
