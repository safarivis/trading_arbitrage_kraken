import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple
from dataclasses import dataclass
import ccxt
import os
from datetime import datetime, timedelta
import json
from strategies.risk_manager import RiskManager

@dataclass
class BacktestTrade:
    entry_time: datetime
    exit_time: datetime
    spot_entry: float
    perp_entry: float
    spot_exit: float
    perp_exit: float
    position_size: float
    pnl: float
    funding_pnl: float
    total_pnl: float
    roi: float

class ArbitrageBacktester:
    def __init__(self,
                 initial_capital: float = 10000,
                 max_leverage: float = 5,
                 max_position_pct: float = 0.8,
                 min_spread: float = 0.001,
                 trading_fee: float = 0.001):
        
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_leverage = max_leverage
        self.max_position_pct = max_position_pct
        self.min_spread = min_spread
        self.trading_fee = trading_fee
        
        self.risk_manager = RiskManager(
            initial_capital=initial_capital,
            max_leverage=max_leverage,
            max_position_pct=max_position_pct
        )
        
        self.trades: List[BacktestTrade] = []
        self.metrics_history: List[Dict] = []
        self.equity_curve: List[float] = [initial_capital]
    
    async def fetch_historical_data(self,
                                  exchange: str = 'kraken',
                                  symbol: str = 'BTC/USD',
                                  start_date: str = '2024-01-01',
                                  end_date: str = '2024-02-01') -> pd.DataFrame:
        """Fetch historical spot and perpetual futures data"""
        try:
            # Initialize exchange
            exchange_class = getattr(ccxt, exchange)
            ex = exchange_class()
            
            # Convert dates to timestamps
            start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
            
            # Fetch spot data
            spot_ohlcv = await ex.fetch_ohlcv(
                symbol,
                '1h',
                start_ts,
                limit=1000
            )
            
            # Fetch perpetual futures data
            perp_symbol = f"{symbol}:USD"  # Adjust based on exchange
            perp_ohlcv = await ex.fetch_ohlcv(
                perp_symbol,
                '1h',
                start_ts,
                limit=1000
            )
            
            # Create DataFrames
            spot_df = pd.DataFrame(spot_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            perp_df = pd.DataFrame(perp_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Add funding rates (if available)
            funding_rates = await ex.fetch_funding_rates([perp_symbol])
            funding_df = pd.DataFrame(funding_rates).set_index('timestamp')
            
            # Merge data
            df = pd.merge(spot_df, perp_df, on='timestamp', suffixes=('_spot', '_perp'))
            df = pd.merge(df, funding_df, on='timestamp', how='left')
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
            
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            return pd.DataFrame()
    
    def simulate_trade(self,
                      spot_price: float,
                      perp_price: float,
                      funding_rate: float,
                      position_size: float) -> Dict:
        """Simulate a single trade with fees and funding"""
        # Calculate entry costs
        entry_fee = position_size * self.trading_fee * 2  # Both spot and perp
        
        # Calculate funding payment (8-hour rate)
        funding_payment = position_size * funding_rate
        
        # Calculate spread capture
        spread = (perp_price - spot_price) / spot_price
        spread_profit = position_size * spread
        
        # Total P&L
        total_pnl = spread_profit + funding_payment - entry_fee
        
        return {
            'spread_profit': spread_profit,
            'funding_pnl': funding_payment,
            'fees': entry_fee,
            'total_pnl': total_pnl
        }
    
    def run_backtest(self, data: pd.DataFrame) -> Dict:
        """Run backtest on historical data"""
        print("Starting backtest...")
        
        current_position = None
        position_duration = timedelta(hours=8)  # Minimum hold time for funding
        
        for idx, row in data.iterrows():
            timestamp = row['timestamp']
            spot_price = row['close_spot']
            perp_price = row['close_perp']
            funding_rate = row['fundingRate'] if 'fundingRate' in row else 0.001
            
            # Calculate metrics
            spread = (perp_price - spot_price) / spot_price
            volatility = data['close_spot'].pct_change().rolling(24).std() * np.sqrt(24)
            
            # Update risk metrics
            risk_metrics = self.risk_manager.update_metrics(
                spot_price=spot_price,
                perp_price=perp_price,
                funding_rate=funding_rate,
                volatility=volatility.iloc[-1] if not volatility.empty else 0
            )
            
            # Store metrics
            self.metrics_history.append({
                'timestamp': timestamp,
                'spread': spread,
                'funding_rate': funding_rate,
                'volatility': risk_metrics.volatility,
                'liquidation_risk': risk_metrics.liquidation_risk
            })
            
            if current_position is None:
                # Check for new opportunity
                if abs(spread) > self.min_spread and risk_metrics.liquidation_risk < 0.3:
                    position_size = self.risk_manager.get_position_size(spot_price, risk_metrics.volatility)
                    
                    # Open new position
                    current_position = {
                        'entry_time': timestamp,
                        'spot_entry': spot_price,
                        'perp_entry': perp_price,
                        'position_size': position_size,
                        'funding_pnl': 0
                    }
            
            else:
                # Update funding P&L
                current_position['funding_pnl'] += (
                    current_position['position_size'] * funding_rate / 3
                )  # Assuming 8-hour funding periods
                
                # Check exit conditions
                time_held = timestamp - current_position['entry_time']
                should_exit = (
                    time_held >= position_duration or
                    risk_metrics.liquidation_risk > 0.4 or
                    abs(spread) < self.min_spread * 0.5
                )
                
                if should_exit:
                    # Calculate trade P&L
                    trade = BacktestTrade(
                        entry_time=current_position['entry_time'],
                        exit_time=timestamp,
                        spot_entry=current_position['spot_entry'],
                        perp_entry=current_position['perp_entry'],
                        spot_exit=spot_price,
                        perp_exit=perp_price,
                        position_size=current_position['position_size'],
                        pnl=(perp_price - spot_price) * current_position['position_size'],
                        funding_pnl=current_position['funding_pnl'],
                        total_pnl=0,  # Will calculate below
                        roi=0  # Will calculate below
                    )
                    
                    # Add fees
                    total_fees = current_position['position_size'] * self.trading_fee * 4  # Entry and exit, both sides
                    trade.total_pnl = trade.pnl + trade.funding_pnl - total_fees
                    trade.roi = trade.total_pnl / self.initial_capital
                    
                    # Update capital
                    self.current_capital += trade.total_pnl
                    self.equity_curve.append(self.current_capital)
                    
                    # Store trade
                    self.trades.append(trade)
                    
                    # Reset position
                    current_position = None
        
        # Calculate performance metrics
        return self.calculate_performance_metrics()
    
    def calculate_performance_metrics(self) -> Dict:
        """Calculate backtest performance metrics"""
        if not self.trades:
            return {}
        
        # Convert trades to DataFrame for analysis
        trades_df = pd.DataFrame([vars(t) for t in self.trades])
        
        # Calculate metrics
        total_pnl = sum(t.total_pnl for t in self.trades)
        win_rate = len([t for t in self.trades if t.total_pnl > 0]) / len(self.trades)
        
        # Calculate returns
        returns = pd.Series(self.equity_curve).pct_change().dropna()
        
        # Sharpe Ratio (annualized)
        sharpe = np.sqrt(252) * returns.mean() / returns.std() if len(returns) > 1 else 0
        
        # Max Drawdown
        cummax = pd.Series(self.equity_curve).cummax()
        drawdown = (cummax - self.equity_curve) / cummax
        max_drawdown = drawdown.max()
        
        return {
            'total_pnl': total_pnl,
            'return_pct': (self.current_capital / self.initial_capital - 1) * 100,
            'num_trades': len(self.trades),
            'win_rate': win_rate * 100,
            'avg_trade_pnl': total_pnl / len(self.trades),
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown * 100,
            'final_capital': self.current_capital
        }
    
    def plot_results(self):
        """Plot backtest results"""
        # Create figure with subplots
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        
        # Plot equity curve
        equity_series = pd.Series(self.equity_curve)
        equity_series.plot(ax=axes[0], title='Equity Curve')
        axes[0].set_ylabel('Capital ($)')
        
        # Plot trade P&Ls
        trade_pnls = [t.total_pnl for t in self.trades]
        pd.Series(trade_pnls).plot(kind='bar', ax=axes[1], title='Trade P&Ls')
        axes[1].set_ylabel('P&L ($)')
        
        # Plot metrics history
        metrics_df = pd.DataFrame(self.metrics_history)
        metrics_df.set_index('timestamp', inplace=True)
        metrics_df[['spread', 'funding_rate']].plot(ax=axes[2], title='Spread & Funding Rate')
        axes[2].set_ylabel('Rate (%)')
        
        plt.tight_layout()
        plt.show()
    
    def save_results(self, filename: str = 'backtest_results.json'):
        """Save backtest results to file"""
        results = {
            'metrics': self.calculate_performance_metrics(),
            'trades': [vars(t) for t in self.trades],
            'equity_curve': self.equity_curve,
            'parameters': {
                'initial_capital': self.initial_capital,
                'max_leverage': self.max_leverage,
                'max_position_pct': self.max_position_pct,
                'min_spread': self.min_spread,
                'trading_fee': self.trading_fee
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=4, default=str)

async def main():
    # Initialize backtester
    backtester = ArbitrageBacktester(
        initial_capital=10000,
        max_leverage=5,
        max_position_pct=0.8
    )
    
    # Fetch historical data
    data = await backtester.fetch_historical_data(
        start_date='2024-01-01',
        end_date='2024-02-01'
    )
    
    if data.empty:
        print("Failed to fetch historical data")
        return
    
    # Run backtest
    results = backtester.run_backtest(data)
    
    # Print results
    print("\nBacktest Results:")
    for metric, value in results.items():
        print(f"{metric}: {value}")
    
    # Plot results
    backtester.plot_results()
    
    # Save results
    backtester.save_results()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
