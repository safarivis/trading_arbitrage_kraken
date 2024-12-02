import os
import sys
import time
import asyncio
from decimal import Decimal
from typing import Dict, Tuple
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kraken_trader import KrakenTrader

class KrakenPerpArbitrage:
    def __init__(self):
        self.trader = KrakenTrader()
        self.min_profit_threshold = 0.001  # 0.1% minimum profit
        self.position_size = 100  # Start with $100 worth for testing
        self.max_position_size = 1000  # Maximum position size in USD
        self.active_positions: Dict[str, Dict] = {}
        
    async def get_market_prices(self, symbol: str = "BTC/USD") -> Tuple[float, float]:
        """Get spot and perpetual futures prices for a symbol"""
        # Get spot price (using the last trade price)
        spot_price = await self.trader.get_ticker(f"{symbol}")
        
        # Get perpetual futures price
        perp_symbol = f"PI_{symbol}"  # Kraken's perpetual futures format
        perp_price = await self.trader.get_ticker(perp_symbol)
        
        return float(spot_price), float(perp_price)
    
    async def get_funding_rate(self, symbol: str = "BTC/USD") -> float:
        """Get the current funding rate for the perpetual futures"""
        perp_symbol = f"PI_{symbol}"
        funding_info = await self.trader.get_funding_info(perp_symbol)
        return float(funding_info['rate'])
    
    def calculate_profit_potential(self, spot_price: float, perp_price: float, 
                                 funding_rate: float) -> Dict:
        """Calculate potential profit from the arbitrage"""
        # Price difference as a percentage
        price_diff = (perp_price - spot_price) / spot_price
        
        # Daily funding return (funding occurs every 8 hours)
        daily_funding = funding_rate * 3
        
        # Total potential return
        total_return = price_diff + daily_funding
        
        return {
            'price_difference': price_diff,
            'daily_funding': daily_funding,
            'total_return': total_return,
            'profitable': total_return > self.min_profit_threshold
        }
    
    async def execute_arbitrage(self, symbol: str, spot_price: float, 
                              perp_price: float) -> bool:
        """Execute the arbitrage trades"""
        try:
            # Calculate position sizes
            spot_amount = self.position_size / spot_price
            perp_amount = self.position_size / perp_price
            
            # If perp_price > spot_price:
            # 1. Buy spot
            # 2. Sell perpetual futures
            if perp_price > spot_price:
                # Place spot buy order
                spot_order = await self.trader.create_order(
                    symbol=symbol,
                    order_type='market',
                    side='buy',
                    amount=spot_amount
                )
                
                # Place perpetual futures sell order
                perp_order = await self.trader.create_order(
                    symbol=f"PI_{symbol}",
                    order_type='market',
                    side='sell',
                    amount=perp_amount
                )
            else:
                # Place spot sell order
                spot_order = await self.trader.create_order(
                    symbol=symbol,
                    order_type='market',
                    side='sell',
                    amount=spot_amount
                )
                
                # Place perpetual futures buy order
                perp_order = await self.trader.create_order(
                    symbol=f"PI_{symbol}",
                    order_type='market',
                    side='buy',
                    amount=perp_amount
                )
            
            # Store the position
            self.active_positions[symbol] = {
                'spot_order': spot_order,
                'perp_order': perp_order,
                'entry_time': time.time(),
                'spot_price': spot_price,
                'perp_price': perp_price
            }
            
            return True
            
        except Exception as e:
            print(f"Error executing arbitrage: {e}")
            return False
    
    async def monitor_position(self, symbol: str):
        """Monitor and manage open arbitrage positions"""
        if symbol not in self.active_positions:
            return
        
        position = self.active_positions[symbol]
        current_spot_price, current_perp_price = await self.get_market_prices(symbol)
        
        # Calculate current P&L
        spot_pnl = (current_spot_price - position['spot_price']) * (self.position_size / position['spot_price'])
        perp_pnl = (position['perp_price'] - current_perp_price) * (self.position_size / position['perp_price'])
        total_pnl = spot_pnl + perp_pnl
        
        # Add funding payments/charges
        funding_rate = await self.get_funding_rate(symbol)
        time_held = time.time() - position['entry_time']
        funding_periods = time_held / (8 * 3600)  # 8 hours per funding period
        funding_pnl = funding_rate * funding_periods * self.position_size
        
        total_pnl += funding_pnl
        
        print(f"Position P&L: ${total_pnl:.2f}")
        
        # Close position if profit target reached or stop loss hit
        if total_pnl > self.position_size * 0.01 or total_pnl < -self.position_size * 0.005:
            await self.close_position(symbol)
    
    async def close_position(self, symbol: str):
        """Close both spot and perpetual positions"""
        if symbol not in self.active_positions:
            return
        
        try:
            position = self.active_positions[symbol]
            
            # Close spot position
            await self.trader.create_order(
                symbol=symbol,
                order_type='market',
                side='sell' if position['spot_order']['side'] == 'buy' else 'buy',
                amount=position['spot_order']['amount']
            )
            
            # Close perpetual position
            await self.trader.create_order(
                symbol=f"PI_{symbol}",
                order_type='market',
                side='buy' if position['perp_order']['side'] == 'sell' else 'sell',
                amount=position['perp_order']['amount']
            )
            
            del self.active_positions[symbol]
            
        except Exception as e:
            print(f"Error closing position: {e}")
    
    async def run(self, symbol: str = "BTC/USD"):
        """Main arbitrage loop"""
        print(f"Starting arbitrage monitoring for {symbol}")
        
        while True:
            try:
                # Get current prices
                spot_price, perp_price = await self.get_market_prices(symbol)
                funding_rate = await self.get_funding_rate(symbol)
                
                # Calculate profit potential
                opportunity = self.calculate_profit_potential(
                    spot_price, perp_price, funding_rate
                )
                
                print(f"\nSpot Price: ${spot_price:.2f}")
                print(f"Perp Price: ${perp_price:.2f}")
                print(f"Funding Rate: {funding_rate*100:.4f}%")
                print(f"Total Return: {opportunity['total_return']*100:.4f}%")
                
                # Execute arbitrage if profitable
                if opportunity['profitable'] and not self.active_positions:
                    print("Executing arbitrage...")
                    await self.execute_arbitrage(symbol, spot_price, perp_price)
                
                # Monitor existing positions
                if self.active_positions:
                    await self.monitor_position(symbol)
                
                # Wait before next check
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"Error in arbitrage loop: {e}")
                await asyncio.sleep(5)

async def main():
    arbitrage = KrakenPerpArbitrage()
    await arbitrage.run("BTC/USD")

if __name__ == "__main__":
    asyncio.run(main())
