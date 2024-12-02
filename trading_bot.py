from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from typing import Dict, List
import uvicorn
import hmac
import hashlib
import json
from datetime import datetime
import logging

from trading.exchanges.binance_handler import BinanceHandler
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Security
API_KEY_HEADER = APIKeyHeader(name="X-API-KEY")

# Initialize exchange handler
binance_handler = BinanceHandler(
    api_key=config.BINANCE_API_KEY,
    api_secret=config.BINANCE_SECRET_KEY,
    testnet=True
)

# Store recent orders in memory
recent_orders = []

async def verify_api_key(api_key: str = Depends(API_KEY_HEADER)):
    """Verify the API key from TradingView"""
    if api_key != config.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return api_key

@app.post("/webhook")
async def webhook(request: Request, api_key: str = Depends(verify_api_key)):
    """Handle incoming webhook signals from TradingView"""
    try:
        signal = await request.json()
        logger.info(f"Received signal: {signal}")
        
        # Validate required fields
        required_fields = ['exchange', 'symbol', 'action', 'price']
        if not all(field in signal for field in required_fields):
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields. Required: {required_fields}"
            )
        
        # Execute trade based on the signal
        if signal['exchange'].lower() == 'binance':
            result = await binance_handler.execute_trade(signal)
            
            # Store order in recent orders
            order_info = {
                "time": datetime.utcnow().isoformat(),
                "order_id": result['order_id'],
                "symbol": result['symbol'],
                "action": result['action'],
                "quantity": result['quantity'],
                "price": result['price'],
                "status": result['status']
            }
            recent_orders.append(order_info)
            
            # Keep only last 10 orders
            if len(recent_orders) > 10:
                recent_orders.pop(0)
            
            return {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "trade_result": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported exchange: {signal['exchange']}"
            )
            
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/order/{order_id}")
async def get_order_status(order_id: int, symbol: str, api_key: str = Depends(verify_api_key)):
    """Get the status of a specific order"""
    try:
        status = binance_handler.get_order_status(symbol, order_id)
        return {
            "status": "success",
            "order": status
        }
    except Exception as e:
        logger.error(f"Error getting order status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders")
async def get_recent_orders(api_key: str = Depends(verify_api_key)):
    """Get list of recent orders"""
    return {
        "status": "success",
        "orders": recent_orders
    }

@app.get("/balance")
async def get_balance(asset: str = "USDT", api_key: str = Depends(verify_api_key)):
    """Get balance for a specific asset"""
    try:
        balance = binance_handler.get_balance(asset)
        return {
            "status": "success",
            "asset": asset,
            "free_balance": balance
        }
    except Exception as e:
        logger.error(f"Error getting balance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    logger.info("Starting trading bot server...")
    uvicorn.run(
        "trading_bot:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
