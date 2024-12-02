from bybit_trader import BybitTrader

def test_connection():
    trader = BybitTrader()
    
    # Test 1: Get Balance
    print("\n=== Testing Balance ===")
    balance = trader.get_balance('USDT')
    print(f"USDT Balance: {balance}")
    
    # Test 2: Get Market Price
    print("\n=== Testing Market Price ===")
    btc_price = trader.get_market_price("BTCUSDT")
    print(f"BTC Price: {btc_price}")
    
    # Test 3: Place a small test order (commented out for safety)
    """
    print("\n=== Testing Order Placement ===")
    order = trader.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.001,  # Very small amount for testing
        price=None  # Market order
    )
    print(f"Order result: {order}")
    """

if __name__ == "__main__":
    test_connection()
