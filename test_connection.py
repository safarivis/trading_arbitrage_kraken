from binance.client import Client
import os
from dotenv import load_dotenv
import requests
import certifi
import urllib3
import hmac
import hashlib
import time

def get_signed_params(api_secret: str, params: dict) -> dict:
    """Sign parameters with API secret"""
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params['signature'] = signature
    return params

def test_binance_connection():
    # Load environment variables
    load_dotenv()
    
    # Get API credentials
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_SECRET_KEY')
    
    if not api_key or not api_secret:
        print("Error: Please add your Binance Testnet API keys to the .env file")
        return
    
    # Use system CA certificates
    session = requests.Session()
    session.verify = True
    
    base_url = 'https://testnet.binance.vision'
    
    try:
        print(f"Connecting to Binance Testnet ({base_url})...")
        
        # Test basic endpoint
        response = session.get(f"{base_url}/api/v3/ping", timeout=10)
        print(f"Basic endpoint test successful! Status code: {response.status_code}")
        
        # Test account endpoint
        print("\nTesting account access...")
        
        # Prepare parameters
        params = {
            'timestamp': int(time.time() * 1000)  # Current timestamp in milliseconds
        }
        
        # Sign the parameters
        signed_params = get_signed_params(api_secret, params)
        
        headers = {
            'X-MBX-APIKEY': api_key
        }
        
        account_response = session.get(
            f"{base_url}/api/v3/account",
            headers=headers,
            params=signed_params,
            timeout=10
        )
        
        if account_response.status_code == 200:
            print("Account access successful!")
            account = account_response.json()
            print("\nAccount balances:")
            for asset in account['balances']:
                if float(asset['free']) > 0 or float(asset['locked']) > 0:
                    print(f"{asset['asset']}: Free={asset['free']}, Locked={asset['locked']}")
        else:
            print(f"Account access failed. Status code: {account_response.status_code}")
            print(f"Response: {account_response.text}")
        
        # Get BTC price
        print("\nGetting current BTC price...")
        price_response = session.get(f"{base_url}/api/v3/ticker/price", params={'symbol': 'BTCUSDT'})
        if price_response.status_code == 200:
            price_data = price_response.json()
            print(f"Current BTC price: ${float(price_data['price']):.2f}")
        
    except requests.exceptions.RequestException as e:
        print(f"\nError connecting to Binance Testnet: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Since you can access the site via Firefox, try:")
        print("   - Copying Firefox proxy settings to the script")
        print("   - Using system CA certificates")
        print("2. Check if you need to configure proxy settings")
        print("3. Try setting up environment variables:")
        print("   export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt")
        print(f"\nDetailed error: {str(e)}")

if __name__ == "__main__":
    test_binance_connection()
