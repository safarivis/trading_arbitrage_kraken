import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Tuple

from data.fast_data_collector import FastDataCollector
from strategies.volatility_adaptive_strategy import VolatilityAdaptiveStrategy
from backtesting.backtest_engine import BacktestEngine

async def run_backtest(
    symbol: str = "BTC/USDT",
    start_date: datetime = datetime(2023, 1, 1),
    end_date: datetime = datetime(2024, 1, 1),
    initial_capital: float = 100000,
    params: Optional[Dict] = None
) -> Tuple[BacktestEngine, pd.DataFrame, pd.DataFrame]:
    """Run backtest for the volatility adaptive strategy"""
    
    # Default strategy parameters
    default_params = {
        'lookback_period': 24,
        'vol_threshold': 0.02,
        'min_spread': 0.001,
        'max_spread': 0.005,
        'funding_threshold': 0.0001,
        'max_position_pct': 0.6,
        'max_leverage': 3.0
    }
    
    # Update with provided params
    if params:
        default_params.update(params)
    
    # Fetch data
    collector = FastDataCollector()
    
    print("Fetching market data...")
    market_data = await collector.get_binance_klines(
        symbol=symbol,
        interval='1h',
        start_date=start_date,
        end_date=end_date
    )
    
    # Print sample of market data
    print("\nSample of market data:")
    print(market_data.head())
    print("\nMarket data shape:", market_data.shape)
    
    # Ensure market_data has a datetime index
    if 'timestamp' in market_data.columns:
        market_data.set_index('timestamp', inplace=True)
    market_data.index = pd.to_datetime(market_data.index)
    
    print("\nFetching funding rates...")
    funding_data = await collector.get_funding_rates(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print sample of funding data
    print("\nSample of funding data:")
    print(funding_data.head())
    print("\nFunding data shape:", funding_data.shape)
    
    # Ensure funding_data has a datetime index
    if 'timestamp' in funding_data.columns:
        funding_data.set_index('timestamp', inplace=True)
    funding_data.index = pd.to_datetime(funding_data.index)
    
    # Initialize strategy and backtest engine
    strategy = VolatilityAdaptiveStrategy(**default_params)
    engine = BacktestEngine(
        initial_capital=initial_capital,
        trading_fee=0.001,  # 0.1% trading fee
        slippage=0.0005    # 0.05% slippage
    )
    
    # Generate signals
    print("Generating trading signals...")
    signals = strategy.generate_signals(
        data=market_data,
        capital=initial_capital,
        funding_data=funding_data
    )
    
    # Process signals through backtest engine
    print("Processing signals...")
    for signal in signals:
        if signal['action'] == 'open':
            engine.open_position(
                symbol=signal['symbol'],
                side=signal['side'],
                price=signal['price'],
                amount=signal['amount'],
                leverage=signal['leverage'],
                timestamp=signal['timestamp']
            )
        elif signal['action'] == 'close':
            engine.close_position(
                symbol=signal['symbol'],
                price=signal['price'],
                timestamp=signal['timestamp'],
                funding_cost=signal.get('funding_cost', 0)
            )
    
    # Calculate metrics
    print("Calculating performance metrics...")
    metrics = engine.calculate_metrics()
    
    # Get strategy metrics
    strategy_metrics = strategy.get_metrics_df()
    
    return engine, market_data, strategy_metrics

def plot_results(
    engine: BacktestEngine,
    market_data: pd.DataFrame,
    strategy_metrics: pd.DataFrame,
    save_path: Optional[str] = None
):
    """Plot backtest results"""
    
    # Create figure with subplots
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), height_ratios=[2, 1, 1])
    fig.suptitle('Volatility Adaptive Strategy Backtest Results', fontsize=14)
    
    # Plot 1: Price and Equity Curve
    ax1 = axes[0]
    ax1.plot(market_data.index, market_data['close'], label='BTC Price', color='gray', alpha=0.5)
    ax1.set_ylabel('Price ($)', color='gray')
    
    ax1_twin = ax1.twinx()
    equity_df = pd.DataFrame(
        engine.equity_curve,
        columns=['timestamp', 'equity']
    ).set_index('timestamp')
    ax1_twin.plot(equity_df.index, equity_df['equity'], label='Portfolio Value', color='blue')
    ax1_twin.set_ylabel('Portfolio Value ($)', color='blue')
    
    # Plot 2: Volatility and Position Count
    ax2 = axes[1]
    ax2.plot(strategy_metrics['timestamp'], strategy_metrics['volatility'], label='Volatility', color='orange')
    ax2.set_ylabel('Volatility', color='orange')
    
    ax2_twin = ax2.twinx()
    ax2_twin.plot(strategy_metrics['timestamp'], strategy_metrics['position_count'], label='Position Count', color='green')
    ax2_twin.set_ylabel('Position Count', color='green')
    
    # Plot 3: Spreads
    ax3 = axes[2]
    ax3.plot(strategy_metrics['timestamp'], strategy_metrics['actual_spread'], label='Actual Spread', color='purple')
    ax3.plot(strategy_metrics['timestamp'], strategy_metrics['required_spread'], label='Required Spread', color='red', linestyle='--')
    ax3.set_ylabel('Spread')
    ax3.legend()
    
    # Format and save
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
    plt.show()

async def main():
    # Run backtest
    print("Starting backtest...")
    engine, market_data, strategy_metrics = await run_backtest()
    
    # Print metrics
    print("\nBacktest Results:")
    print("-" * 40)
    for metric, value in engine.metrics.items():
        print(f"{metric}: {value:.4f}")
    
    # Plot results
    plot_results(engine, market_data, strategy_metrics, "backtest_results.png")
    
    # Save detailed results
    engine.save_results("backtest_detailed_results.json")

if __name__ == "__main__":
    asyncio.run(main())
