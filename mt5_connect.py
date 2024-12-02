import os
import sys
import time
from datetime import datetime

# Get the current user's username
CURRENT_USER = os.getenv('USER')

# Set the WINEPATH environment variable to point to your Wine Python installation
WINE_PYTHON_PATH = os.path.expanduser(f'~/.wine/drive_c/users/{CURRENT_USER}/AppData/Local/Programs/Python/Python39')
MT5_PATH = os.path.expanduser('~/.wine/drive_c/Program Files/MetaTrader 5')

def connect_mt5():
    """
    Connect to MetaTrader 5 terminal
    Returns: bool - True if connection successful, False otherwise
    """
    try:
        # Add Wine Python path to system path
        sys.path.append(WINE_PYTHON_PATH)
        
        # Import MetaTrader5 after setting up the path
        import MetaTrader5 as mt5
        
        # Initialize MT5
        if not mt5.initialize(path=f"{MT5_PATH}/terminal64.exe"):
            print(f"initialize() failed, error code = {mt5.last_error()}")
            return False

        # Connect to the account
        authorized = mt5.login(
            login=81325573,
            password="Joshua2415!",
            server="Zero"
        )
        
        if authorized:
            print("Connected to MT5 successfully")
            account_info = mt5.account_info()
            if account_info is not None:
                print(f"Account: {account_info.login}")
                print(f"Balance: {account_info.balance}")
                print(f"Equity: {account_info.equity}")
        else:
            print(f"Failed to connect to MT5, error code: {mt5.last_error()}")
        
        return authorized

    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def place_market_order(symbol, order_type, volume):
    """
    Place a market order
    Args:
        symbol (str): Trading instrument (e.g., "EURUSD")
        order_type (str): "BUY" or "SELL"
        volume (float): Trade volume in lots
    Returns:
        object: Order result
    """
    try:
        import MetaTrader5 as mt5
        
        if order_type.upper() == "BUY":
            trade_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        else:
            trade_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": trade_type,
            "price": price,
            "deviation": 20,  # maximum price deviation in points
            "magic": 234000,  # EA ID
            "comment": "python script order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Order failed, retcode={result.retcode}")
            print(f"Error: {mt5.last_error()}")
        else:
            print(f"Order successfully placed! Ticket={result.order}")
        
        return result

    except Exception as e:
        print(f"Error placing order: {str(e)}")
        return None

def process_trading_view_signal(signal):
    """
    Process TradingView webhook signal
    Args:
        signal (dict): Signal from TradingView with keys:
            - 'symbol': Trading pair
            - 'action': 'BUY' or 'SELL'
            - 'volume': Trade volume
    """
    if not all(k in signal for k in ['symbol', 'action', 'volume']):
        print("Invalid signal format")
        return False
    
    return place_market_order(
        symbol=signal['symbol'],
        order_type=signal['action'],
        volume=signal['volume']
    )

if __name__ == "__main__":
    if connect_mt5():
        print("Ready to trade!")
        # Example signal from TradingView
        # signal = {
        #     'symbol': 'EURUSD',
        #     'action': 'BUY',
        #     'volume': 0.1
        # }
        # process_trading_view_signal(signal)
    else:
        print("Failed to connect to MT5")
    mt5.shutdown()
