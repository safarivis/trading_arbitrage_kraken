from fastapi import FastAPI, Request, HTTPException
from typing import Dict
import uvicorn
from datetime import datetime
from bybit_trader import BybitTrader
from pydantic import BaseModel

app = FastAPI()
trader = BybitTrader()

class TradingViewAlert(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float = None
    take_profit: float = None
    stop_loss: float = None

@app.post("/webhook")
async def webhook(alert: TradingViewAlert):
    try:
        # Place the order on Bybit
        response = trader.place_order(
            symbol=alert.symbol,
            side=alert.side,
            quantity=alert.quantity,
            price=alert.price,
            take_profit=alert.take_profit,
            stop_loss=alert.stop_loss
        )
        
        if "error" in response:
            raise HTTPException(status_code=400, detail=response["error"])
            
        return {
            "status": "success",
            "message": "Order placed successfully",
            "data": response
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/balance")
async def get_balance():
    """Get current USDT balance"""
    balance = trader.get_balance()
    return {"balance": balance}

@app.get("/price/{symbol}")
async def get_price(symbol: str):
    """Get current price for a symbol"""
    price = trader.get_market_price(symbol)
    return {"symbol": symbol, "price": price}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
