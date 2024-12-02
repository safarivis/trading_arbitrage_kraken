import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple
from dataclasses import dataclass
import ccxt
import asyncio
from datetime import datetime, timedelta
import json
from strategies.arbitrage_backtester import ArbitrageBacktester
from concurrent.futures import ThreadPoolExecutor
import itertools
import random

@dataclass
class StrategyConfig:
    name: str
    initial_capital: float
    max_leverage: float
    max_position_pct: float
    min_spread: float
    trading_fee: float
    risk_params: Dict

@dataclass
class ComparisonResult:
    strategy: str
    asset: str
    total_pnl: float
    roi: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    avg_trade_pnl: float
    num_trades: int
    volatility: float

class StrategyComparator:
    def __init__(self):
        self.results: List[ComparisonResult] = []
        self.exchanges = ['kraken', 'binance', 'bybit']  # Add more as needed
        
    async def fetch_exchange_data(self,
                                exchange: str,
                                symbol: str,
                                start_date: str,
                                end_date: str) -> pd.DataFrame:
        """Fetch data from specific exchange"""
        try:
            exchange_class = getattr(ccxt, exchange)
            ex = exchange_class()
            
            # Convert dates
            start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
            
            # Fetch OHLCV data
            ohlcv = await ex.fetch_ohlcv(symbol, '1h', start_ts, limit=1000)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['exchange'] = exchange
            
            return df
            
        except Exception as e:
            print(f"Error fetching data from {exchange} for {symbol}: {e}")
            return pd.DataFrame()
    
    async def get_funding_rates(self,
                              exchange: str,
                              symbol: str,
                              start_date: str,
                              end_date: str) -> pd.DataFrame:
        """Fetch historical funding rates"""
        try:
            exchange_class = getattr(ccxt, exchange)
            ex = exchange_class()
            
            funding_rates = await ex.fetch_funding_rate_history(
                symbol,
                int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000),
                limit=1000
            )
            
            df = pd.DataFrame(funding_rates)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
            
        except Exception as e:
            print(f"Error fetching funding rates from {exchange} for {symbol}: {e}")
            return pd.DataFrame()
    
    def calculate_metrics(self, trades_df: pd.DataFrame) -> ComparisonResult:
        """Calculate performance metrics for a strategy"""
        if trades_df.empty:
            return None
        
        returns = trades_df['total_pnl'].pct_change()
        
        return ComparisonResult(
            strategy=trades_df['strategy'].iloc[0],
            asset=trades_df['symbol'].iloc[0],
            total_pnl=trades_df['total_pnl'].sum(),
            roi=(trades_df['total_pnl'].sum() / trades_df['position_size'].iloc[0]),
            sharpe=np.sqrt(252) * returns.mean() / returns.std() if len(returns) > 1 else 0,
            max_drawdown=self.calculate_max_drawdown(trades_df['total_pnl'].cumsum()),
            win_rate=len(trades_df[trades_df['total_pnl'] > 0]) / len(trades_df),
            avg_trade_pnl=trades_df['total_pnl'].mean(),
            num_trades=len(trades_df),
            volatility=returns.std() * np.sqrt(252)
        )
    
    def calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """Calculate maximum drawdown"""
        rolling_max = equity_curve.cummax()
        drawdowns = (rolling_max - equity_curve) / rolling_max
        return drawdowns.max()
    
    async def compare_strategies(self,
                               strategies: List[StrategyConfig],
                               symbols: List[str],
                               start_date: str,
                               end_date: str) -> pd.DataFrame:
        """Compare multiple strategies across different assets"""
        print("Starting strategy comparison...")
        
        all_results = []
        
        # Create all combinations of strategies and symbols
        combinations = list(itertools.product(strategies, symbols))
        
        for strategy, symbol in combinations:
            print(f"\nTesting {strategy.name} on {symbol}")
            
            # Fetch data from all exchanges
            exchange_data = []
            for exchange in self.exchanges:
                data = await self.fetch_exchange_data(
                    exchange, symbol, start_date, end_date
                )
                if not data.empty:
                    exchange_data.append(data)
            
            if not exchange_data:
                print(f"No data available for {symbol}")
                continue
            
            # Combine data from all exchanges
            combined_data = pd.concat(exchange_data)
            combined_data.sort_values('timestamp', inplace=True)
            
            # Get funding rates
            funding_data = await self.get_funding_rates(
                self.exchanges[0], symbol, start_date, end_date
            )
            
            # Merge price and funding data
            data = pd.merge(combined_data, funding_data, on='timestamp', how='left')
            
            # Run backtest
            backtester = ArbitrageBacktester(
                initial_capital=strategy.initial_capital,
                max_leverage=strategy.max_leverage,
                max_position_pct=strategy.max_position_pct,
                min_spread=strategy.min_spread,
                trading_fee=strategy.trading_fee
            )
            
            results = backtester.run_backtest(data)
            
            # Store results
            if results:
                result = ComparisonResult(
                    strategy=strategy.name,
                    asset=symbol,
                    total_pnl=results['total_pnl'],
                    roi=results['return_pct'],
                    sharpe=results['sharpe_ratio'],
                    max_drawdown=results['max_drawdown_pct'],
                    win_rate=results['win_rate'],
                    avg_trade_pnl=results['avg_trade_pnl'],
                    num_trades=results['num_trades'],
                    volatility=data['close'].pct_change().std() * np.sqrt(252)
                )
                all_results.append(result)
        
        return all_results
    
    def plot_comparison(self, results: List[ComparisonResult]):
        """Plot comparison results"""
        if not results:
            print("No results to plot")
            return
        
        # Convert results to DataFrame
        df = pd.DataFrame([vars(r) for r in results])
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # ROI comparison
        sns.barplot(data=df, x='asset', y='roi', hue='strategy', ax=axes[0,0])
        axes[0,0].set_title('Return on Investment (%)')
        axes[0,0].tick_params(axis='x', rotation=45)
        
        # Sharpe ratio comparison
        sns.barplot(data=df, x='asset', y='sharpe', hue='strategy', ax=axes[0,1])
        axes[0,1].set_title('Sharpe Ratio')
        axes[0,1].tick_params(axis='x', rotation=45)
        
        # Max drawdown comparison
        sns.barplot(data=df, x='asset', y='max_drawdown', hue='strategy', ax=axes[1,0])
        axes[1,0].set_title('Maximum Drawdown (%)')
        axes[1,0].tick_params(axis='x', rotation=45)
        
        # Win rate comparison
        sns.barplot(data=df, x='asset', y='win_rate', hue='strategy', ax=axes[1,1])
        axes[1,1].set_title('Win Rate (%)')
        axes[1,1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.show()
        
        # Create heatmap of strategy performance
        plt.figure(figsize=(12, 8))
        pivot_roi = df.pivot(index='strategy', columns='asset', values='roi')
        sns.heatmap(pivot_roi, annot=True, cmap='RdYlGn', center=0)
        plt.title('Strategy ROI Heatmap (%)')
        plt.show()
    
    def generate_report(self, results: List[ComparisonResult], filename: str = 'comparison_report.html'):
        """Generate HTML report of comparison results"""
        df = pd.DataFrame([vars(r) for r in results])
        
        # Style the DataFrame
        styled_df = df.style\
            .background_gradient(subset=['roi', 'sharpe'], cmap='RdYlGn')\
            .background_gradient(subset=['max_drawdown'], cmap='RdYlGn_r')\
            .format({
                'roi': '{:.2f}%',
                'sharpe': '{:.2f}',
                'max_drawdown': '{:.2f}%',
                'win_rate': '{:.2f}%',
                'avg_trade_pnl': '${:.2f}',
                'total_pnl': '${:.2f}',
                'volatility': '{:.2f}%'
            })
        
        # Generate HTML
        html = f"""
        <html>
        <head>
            <title>Strategy Comparison Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                .summary {{ margin: 20px 0; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f5f6fa; }}
                tr:hover {{ background-color: #f5f5f5; }}
            </style>
        </head>
        <body>
            <h1>Strategy Comparison Report</h1>
            <div class="summary">
                <h2>Summary Statistics</h2>
                <p>Total Strategies: {len(df['strategy'].unique())}</p>
                <p>Total Assets: {len(df['asset'].unique())}</p>
                <p>Best Performing Strategy: {df.loc[df['roi'].idxmax(), 'strategy']} ({df['roi'].max():.2f}% ROI)</p>
                <p>Best Performing Asset: {df.loc[df['roi'].idxmax(), 'asset']}</p>
            </div>
            {styled_df.to_html()}
        </body>
        </html>
        """
        
        with open(filename, 'w') as f:
            f.write(html)
        
        print(f"Report generated: {filename}")
    
    def summary_metrics(self, results: List[ComparisonResult]):
        """Generate a detailed summary of key trading metrics"""
        metrics_df = pd.DataFrame([vars(r) for r in results])
        
        # Group by strategy
        strategy_metrics = metrics_df.groupby('strategy').agg({
            'total_pnl': ['mean', 'sum', 'std'],
            'roi': ['mean', 'min', 'max', 'std'],
            'sharpe': 'mean',
            'max_drawdown': ['mean', 'max'],
            'win_rate': 'mean',
            'num_trades': 'sum',
            'avg_trade_pnl': 'mean',
            'volatility': 'mean'
        }).round(4)
        
        # Calculate additional metrics
        strategy_metrics['risk_adjusted_return'] = (
            strategy_metrics[('roi', 'mean')] / strategy_metrics[('max_drawdown', 'max')]
        ).round(4)
        
        strategy_metrics['consistency_score'] = (
            strategy_metrics[('roi', 'mean')] / strategy_metrics[('roi', 'std')]
        ).round(4)
        
        # Print summary
        print("\n=== Strategy Performance Summary ===\n")
        for strategy in strategy_metrics.index:
            print(f"\n{strategy} Performance Metrics:")
            print("-" * 50)
            print(f"Total P&L: ${strategy_metrics.loc[strategy, ('total_pnl', 'sum')]:,.2f}")
            print(f"Average ROI: {strategy_metrics.loc[strategy, ('roi', 'mean')]*100:.2f}%")
            print(f"ROI Range: {strategy_metrics.loc[strategy, ('roi', 'min')]*100:.2f}% to {strategy_metrics.loc[strategy, ('roi', 'max')]*100:.2f}%")
            print(f"Sharpe Ratio: {strategy_metrics.loc[strategy, ('sharpe', 'mean')]:.2f}")
            print(f"Max Drawdown: {strategy_metrics.loc[strategy, ('max_drawdown', 'max')]*100:.2f}%")
            print(f"Win Rate: {strategy_metrics.loc[strategy, ('win_rate', 'mean')]*100:.2f}%")
            print(f"Total Trades: {strategy_metrics.loc[strategy, ('num_trades', 'sum')]:,.0f}")
            print(f"Avg Trade P&L: ${strategy_metrics.loc[strategy, ('avg_trade_pnl', 'mean']):,.2f}")
            print(f"Annualized Volatility: {strategy_metrics.loc[strategy, ('volatility', 'mean')]*100:.2f}%")
            print(f"Risk-Adjusted Return: {strategy_metrics.loc[strategy, 'risk_adjusted_return']:.2f}")
            print(f"Consistency Score: {strategy_metrics.loc[strategy, 'consistency_score']:.2f}")
        
        return strategy_metrics
    
    def generate_mock_results(self):
        """Generate mock results for demonstration"""
        strategies = [
            "Volatility_Adaptive",
            "Hybrid_Adaptive",
            "Mean_Reversion_Heavy",
            "Trend_Following_Dynamic",
            "Range_Breakout"
        ]
        
        assets = ["BTC/USD", "ETH/USD", "SOL/USD"]
        results = []
        
        # Mock data based on realistic backtesting results
        data = {
            "Volatility_Adaptive": {
                "roi_range": (0.15, 0.45),
                "sharpe": (1.8, 2.5),
                "max_dd": (0.12, 0.18),
                "win_rate": (0.58, 0.65)
            },
            "Hybrid_Adaptive": {
                "roi_range": (0.12, 0.38),
                "sharpe": (1.6, 2.2),
                "max_dd": (0.15, 0.22),
                "win_rate": (0.55, 0.62)
            },
            "Mean_Reversion_Heavy": {
                "roi_range": (0.10, 0.32),
                "sharpe": (1.4, 2.0),
                "max_dd": (0.10, 0.15),
                "win_rate": (0.60, 0.68)
            },
            "Trend_Following_Dynamic": {
                "roi_range": (0.08, 0.40),
                "sharpe": (1.3, 1.9),
                "max_dd": (0.18, 0.25),
                "win_rate": (0.52, 0.58)
            },
            "Range_Breakout": {
                "roi_range": (0.05, 0.35),
                "sharpe": (1.2, 1.8),
                "max_dd": (0.20, 0.28),
                "win_rate": (0.50, 0.56)
            }
        }
        
        for strategy in strategies:
            for asset in assets:
                roi = random.uniform(*data[strategy]["roi_range"])
                sharpe = random.uniform(*data[strategy]["sharpe"])
                max_dd = random.uniform(*data[strategy]["max_dd"])
                win_rate = random.uniform(*data[strategy]["win_rate"])
                
                results.append(ComparisonResult(
                    strategy=strategy,
                    asset=asset,
                    total_pnl=roi * 10000,  # Based on $10,000 initial capital
                    roi=roi,
                    sharpe=sharpe,
                    max_drawdown=max_dd,
                    win_rate=win_rate,
                    avg_trade_pnl=roi * 10000 / 500,  # Assuming ~500 trades
                    num_trades=random.randint(400, 600),
                    volatility=max_dd * 1.5  # Approximate relationship
                ))
        
        return results

async def main():
    # Generate mock results
    comparator = StrategyComparator()
    results = comparator.generate_mock_results()
    
    # Analyze results
    comparator.summary_metrics(results)

if __name__ == "__main__":
    asyncio.run(main())
