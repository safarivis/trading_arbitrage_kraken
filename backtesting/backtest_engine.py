import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('BacktestEngine')

@dataclass
class Position:
    symbol: str
    side: str
    entry_price: float
    amount: float
    leverage: float
    timestamp: datetime
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None

@dataclass
class Trade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    amount: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    fees: float
    funding_cost: float
    leverage: float

class BacktestEngine:
    def __init__(
        self,
        initial_capital: float,
        trading_fee: float = 0.001,
        slippage: float = 0.0005
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trading_fee = trading_fee
        self.slippage = slippage
        
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.metrics: Dict = {}
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        leverage: float,
        max_position_pct: float
    ) -> float:
        """Calculate safe position size based on capital and leverage"""
        max_position_value = capital * max_position_pct
        return (max_position_value * leverage) / price
    
    def calculate_liquidation_price(
        self,
        position: Position,
        maintenance_margin: float = 0.05
    ) -> float:
        """Calculate liquidation price for a position"""
        if position.side == 'long':
            return position.entry_price * (1 - (1 / position.leverage) + maintenance_margin)
        else:
            return position.entry_price * (1 + (1 / position.leverage) - maintenance_margin)
    
    def open_position(
        self,
        symbol: str,
        side: str,
        price: float,
        amount: float,
        leverage: float,
        timestamp: datetime,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None
    ) -> bool:
        """Open a new position"""
        # Check if we already have a position
        if symbol in self.positions:
            logger.warning(f"Already have position in {symbol}")
            return False
        
        # Calculate required margin
        position_value = price * amount
        required_margin = position_value / leverage
        
        # Check if we have enough capital
        if required_margin > self.capital:
            logger.warning(f"Insufficient capital for position")
            return False
        
        # Apply slippage
        executed_price = price * (1 + self.slippage if side == 'long' else 1 - self.slippage)
        
        # Calculate and apply fees
        fees = position_value * self.trading_fee
        self.capital -= fees
        
        # Create position
        self.positions[symbol] = Position(
            symbol=symbol,
            side=side,
            entry_price=executed_price,
            amount=amount,
            leverage=leverage,
            timestamp=timestamp,
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        
        return True
    
    def close_position(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        funding_cost: float = 0
    ) -> Optional[Trade]:
        """Close an existing position"""
        if symbol not in self.positions:
            logger.warning(f"No position in {symbol} to close")
            return None
        
        position = self.positions[symbol]
        
        # Apply slippage
        executed_price = price * (1 - self.slippage if position.side == 'long' else 1 + self.slippage)
        
        # Calculate P&L
        if position.side == 'long':
            pnl = (executed_price - position.entry_price) * position.amount
        else:
            pnl = (position.entry_price - executed_price) * position.amount
        
        # Calculate fees
        position_value = executed_price * position.amount
        fees = position_value * self.trading_fee
        
        # Update capital
        self.capital += pnl - fees - funding_cost
        
        # Create trade record
        trade = Trade(
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=executed_price,
            amount=position.amount,
            entry_time=position.timestamp,
            exit_time=timestamp,
            pnl=pnl,
            fees=fees,
            funding_cost=funding_cost,
            leverage=position.leverage
        )
        
        self.trades.append(trade)
        del self.positions[symbol]
        
        return trade
    
    def update_equity(self, timestamp: datetime, prices: Dict[str, float]):
        """Update equity curve with unrealized P&L"""
        total_equity = self.capital
        
        # Add unrealized P&L from open positions
        for symbol, position in self.positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                if position.side == 'long':
                    unrealized_pnl = (current_price - position.entry_price) * position.amount
                else:
                    unrealized_pnl = (position.entry_price - current_price) * position.amount
                total_equity += unrealized_pnl
        
        self.equity_curve.append((timestamp, total_equity))
    
    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {}
        
        equity_df = pd.DataFrame(
            self.equity_curve,
            columns=['timestamp', 'equity']
        ).set_index('timestamp')
        
        returns = equity_df['equity'].pct_change()
        
        # Basic metrics
        total_return = (self.capital - self.initial_capital) / self.initial_capital
        num_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t.pnl > 0])
        
        metrics = {
            'total_return': total_return,
            'num_trades': num_trades,
            'win_rate': winning_trades / num_trades if num_trades > 0 else 0,
            'avg_trade_pnl': sum(t.pnl for t in self.trades) / num_trades if num_trades > 0 else 0,
            'max_drawdown': self.calculate_max_drawdown(equity_df['equity']),
            'sharpe_ratio': self.calculate_sharpe_ratio(returns),
            'sortino_ratio': self.calculate_sortino_ratio(returns),
            'profit_factor': self.calculate_profit_factor(),
            'avg_trade_duration': self.calculate_avg_trade_duration()
        }
        
        self.metrics = metrics
        return metrics
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> float:
        """Calculate maximum drawdown"""
        rolling_max = equity_curve.cummax()
        drawdowns = (rolling_max - equity_curve) / rolling_max
        return drawdowns.max()
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0
        excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
        return np.sqrt(252) * excess_returns.mean() / returns.std()
    
    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio"""
        if len(returns) < 2:
            return 0
        excess_returns = returns - risk_free_rate / 252
        downside_returns = returns[returns < 0]
        if len(downside_returns) < 1:
            return np.inf
        return np.sqrt(252) * excess_returns.mean() / downside_returns.std()
    
    def calculate_profit_factor(self) -> float:
        """Calculate profit factor"""
        gross_profits = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_losses = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        return gross_profits / gross_losses if gross_losses != 0 else np.inf
    
    def calculate_avg_trade_duration(self) -> float:
        """Calculate average trade duration in hours"""
        if not self.trades:
            return 0
        durations = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in self.trades]
        return sum(durations) / len(durations)
    
    def save_results(self, filename: str):
        """Save backtest results to a JSON file"""
        results = {
            'metrics': {k: float(v) for k, v in self.metrics.items()},
            'trades': [{
                'symbol': t.symbol,
                'side': t.side,
                'entry_price': float(t.entry_price),
                'exit_price': float(t.exit_price) if hasattr(t, 'exit_price') else None,
                'amount': float(t.amount),
                'entry_time': t.entry_time.isoformat() if hasattr(t, 'entry_time') else None,
                'exit_time': t.exit_time.isoformat() if hasattr(t, 'exit_time') else None,
                'pnl': float(t.pnl) if hasattr(t, 'pnl') else None,
                'fees': float(t.fees) if hasattr(t, 'fees') else None,
                'funding_cost': float(t.funding_cost) if hasattr(t, 'funding_cost') else 0.0,
                'leverage': float(t.leverage) if hasattr(t, 'leverage') else 1.0
            } for t in self.trades],
            'equity_curve': [{
                'timestamp': ts.isoformat() if isinstance(ts, (pd.Timestamp, datetime)) else str(ts),
                'equity': float(eq)
            } for ts, eq in self.equity_curve]
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=4)

def run_backtest(
    data: pd.DataFrame,
    strategy_func: Callable,
    initial_capital: float,
    params: Dict
) -> BacktestEngine:
    """Run a backtest with given data and strategy"""
    engine = BacktestEngine(initial_capital)
    
    for idx, row in data.iterrows():
        # Update strategy
        signals = strategy_func(data.loc[:idx], params)
        
        # Process signals
        for signal in signals:
            if signal['action'] == 'open':
                engine.open_position(
                    symbol=signal['symbol'],
                    side=signal['side'],
                    price=row['close'],
                    amount=signal['amount'],
                    leverage=signal['leverage'],
                    timestamp=idx,
                    take_profit=signal.get('take_profit'),
                    stop_loss=signal.get('stop_loss')
                )
            elif signal['action'] == 'close':
                engine.close_position(
                    symbol=signal['symbol'],
                    price=row['close'],
                    timestamp=idx,
                    funding_cost=signal.get('funding_cost', 0)
                )
        
        # Update equity curve
        engine.update_equity(idx, {'BTC/USD': row['close']})
    
    # Calculate final metrics
    engine.calculate_metrics()
    
    return engine
