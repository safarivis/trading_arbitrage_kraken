import os
import sys
import asyncio
from typing import Dict, List, Optional
from decimal import Decimal
import time
import pandas as pd
import numpy as np

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kraken_trader import KrakenTrader
from strategies.risk_manager import RiskManager
from strategies.trading_dashboard import DashboardManager

class EnhancedPerpArbitrage:
    def __init__(self, 
                 initial_capital: float = 10000,
                 max_leverage: float = 5,
                 max_position_pct: float = 0.8):
        
        self.trader = KrakenTrader()
        self.risk_manager = RiskManager(
            initial_capital=initial_capital,
            max_leverage=max_leverage,
            max_position_pct=max_position_pct
        )
        self.dashboard_manager = DashboardManager()
        
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.active_positions: Dict[str, Dict] = {}
        
        # History tracking
        self.price_history: List[float] = []
        self.pnl_history: List[float] = []
        self.metrics_history: List[Dict] = []
        
    async def initialize(self):
        """Initialize the strategy"""
        # Start dashboard
        self.dashboard_manager.start_dashboard()
        
        # Initialize price history
        prices = await self.get_recent_prices("BTC/USD")
        self.price_history.extend(prices)
    
    async def get_recent_prices(self, symbol: str, lookback: int = 100) -> List[float]:
        """Get recent price history"""
        # Implement based on your exchange API
        prices = await self.trader.get_recent_trades(symbol, lookback)
        return [float(p) for p in prices]
    
    async def update_metrics(self, 
                           symbol: str,
                           spot_price: float,
                           perp_price: float,
                           funding_rate: float):
        """Update all metrics and dashboard"""
        # Calculate position P&L if exists
        pnl = 0
        position_value = 0
        if symbol in self.active_positions:
            pnl = await self.calculate_position_pnl(symbol)
            position_value = self.active_positions[symbol]['position_size']
        
        # Update risk metrics
        risk_metrics = self.risk_manager.update_metrics(
            spot_price=spot_price,
            perp_price=perp_price,
            funding_rate=funding_rate,
            position_value=position_value,
            current_pnl=pnl
        )
        
        # Prepare dashboard updates
        metrics_update = {
            "Spot Price": f"${spot_price:,.2f}",
            "Perp Price": f"${perp_price:,.2f}",
            "Spread": f"{((perp_price - spot_price) / spot_price) * 100:.3f}%",
            "Funding Rate": f"{funding_rate*100:.4f}%",
            "Position Size": f"${position_value:,.2f}",
            "Current P&L": f"${pnl:,.2f}",
            "ROI": f"{(pnl/self.initial_capital)*100:.2f}%"
        }
        
        risk_update = {
            "Volatility": f"{risk_metrics.volatility*100:.2f}%",
            "Margin Ratio": f"{risk_metrics.margin_ratio*100:.2f}%",
            "Liquidation Risk": f"{risk_metrics.liquidation_risk*100:.2f}%",
            "Max Drawdown": f"{self.calculate_max_drawdown()*100:.2f}%",
            "Sharpe Ratio": f"{self.calculate_sharpe_ratio():.2f}",
            "Position Count": len(self.active_positions)
        }
        
        chart_update = {
            "prices": self.price_history[-100:],
            "spreads": [(p2-p1)/p1 for p1, p2 in zip(self.price_history[-100:], self.price_history[-99:])],
            "pnl": self.pnl_history[-100:],
            "risk": [m.liquidation_risk for m in self.risk_manager.metrics_history[-100:]]
        }
        
        # Update dashboard
        self.dashboard_manager.update_dashboard(
            metrics_update,
            risk_update,
            chart_update
        )
    
    async def execute_arbitrage(self,
                              symbol: str,
                              spot_price: float,
                              perp_price: float,
                              funding_rate: float) -> bool:
        """Execute arbitrage trades with risk management"""
        try:
            # Get position size from risk manager
            volatility = self.risk_manager.calculate_volatility(self.price_history)
            position_size = self.risk_manager.get_position_size(spot_price, volatility)
            
            # Calculate amounts
            spot_amount = position_size / spot_price
            perp_amount = position_size / perp_price
            
            # Check risk limits before execution
            risk_metrics = self.risk_manager.update_metrics(
                spot_price=spot_price,
                perp_price=perp_price,
                funding_rate=funding_rate
            )
            
            should_close, reason = self.risk_manager.should_close_position(risk_metrics)
            if should_close:
                print(f"Risk limit breached: {reason}")
                return False
            
            # Execute trades
            if perp_price > spot_price:
                # Buy spot, sell perp
                spot_order = await self.trader.create_order(
                    symbol=symbol,
                    order_type='market',
                    side='buy',
                    amount=spot_amount
                )
                
                perp_order = await self.trader.create_order(
                    symbol=f"PI_{symbol}",
                    order_type='market',
                    side='sell',
                    amount=perp_amount
                )
            else:
                # Sell spot, buy perp
                spot_order = await self.trader.create_order(
                    symbol=symbol,
                    order_type='market',
                    side='sell',
                    amount=spot_amount
                )
                
                perp_order = await self.trader.create_order(
                    symbol=f"PI_{symbol}",
                    order_type='market',
                    side='buy',
                    amount=perp_amount
                )
            
            # Store position
            self.active_positions[symbol] = {
                'spot_order': spot_order,
                'perp_order': perp_order,
                'entry_time': time.time(),
                'spot_price': spot_price,
                'perp_price': perp_price,
                'position_size': position_size
            }
            
            return True
            
        except Exception as e:
            print(f"Error executing arbitrage: {e}")
            return False
    
    async def monitor_positions(self):
        """Monitor and manage open positions"""
        for symbol in list(self.active_positions.keys()):
            try:
                # Get current prices
                spot_price, perp_price = await self.get_market_prices(symbol)
                funding_rate = await self.get_funding_rate(symbol)
                
                # Update metrics
                await self.update_metrics(symbol, spot_price, perp_price, funding_rate)
                
                # Check risk limits
                risk_metrics = self.risk_manager.update_metrics(
                    spot_price=spot_price,
                    perp_price=perp_price,
                    funding_rate=funding_rate
                )
                
                should_close, reason = self.risk_manager.should_close_position(risk_metrics)
                if should_close:
                    print(f"Closing position: {reason}")
                    await self.close_position(symbol)
                
            except Exception as e:
                print(f"Error monitoring position: {e}")
    
    async def run(self, symbol: str = "BTC/USD"):
        """Main strategy loop"""
        print(f"Starting enhanced perpetual arbitrage for {symbol}")
        await self.initialize()
        
        while True:
            try:
                # Get market data
                spot_price, perp_price = await self.get_market_prices(symbol)
                funding_rate = await self.get_funding_rate(symbol)
                
                # Update price history
                self.price_history.append(spot_price)
                
                # Update metrics and dashboard
                await self.update_metrics(symbol, spot_price, perp_price, funding_rate)
                
                # Check for new opportunities
                if not self.active_positions:
                    spread = (perp_price - spot_price) / spot_price
                    if abs(spread) > self.risk_manager.min_spread:
                        print(f"Found opportunity: {spread*100:.3f}% spread")
                        await self.execute_arbitrage(symbol, spot_price, perp_price, funding_rate)
                
                # Monitor existing positions
                await self.monitor_positions()
                
                # Wait before next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error in main loop: {e}")
                await asyncio.sleep(1)
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from PnL history"""
        if not self.pnl_history:
            return 0.0
        
        cumulative = np.maximum.accumulate(self.pnl_history)
        drawdown = (cumulative - self.pnl_history) / cumulative
        return np.max(drawdown) if len(drawdown) > 0 else 0.0
    
    def calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from PnL history"""
        if len(self.pnl_history) < 2:
            return 0.0
        
        returns = np.diff(self.pnl_history)
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        return np.mean(returns) / np.std(returns) * np.sqrt(252)

async def main():
    strategy = EnhancedPerpArbitrage(
        initial_capital=10000,
        max_leverage=5,
        max_position_pct=0.8
    )
    await strategy.run("BTC/USD")

if __name__ == "__main__":
    asyncio.run(main())
