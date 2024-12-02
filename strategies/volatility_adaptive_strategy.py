import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('VolatilityAdaptiveStrategy')

class VolatilityAdaptiveStrategy:
    def __init__(
        self,
        lookback_period: int = 24,  # hours
        vol_threshold: float = 0.02,
        min_spread: float = 0.001,
        max_spread: float = 0.005,
        funding_threshold: float = 0.0001,
        max_position_pct: float = 0.6,
        max_leverage: float = 3.0
    ):
        self.lookback_period = lookback_period
        self.vol_threshold = vol_threshold
        self.min_spread = min_spread
        self.max_spread = max_spread
        self.funding_threshold = funding_threshold
        self.max_position_pct = max_position_pct
        self.max_leverage = max_leverage
        
        # Track positions and metrics
        self.positions = {}
        self.metrics = []
    
    def calculate_volatility(self, data: pd.DataFrame, window: int = 24) -> pd.Series:
        """Calculate rolling volatility"""
        returns = np.log(data['close'] / data['close'].shift(1))
        volatility = returns.rolling(window=window).std() * np.sqrt(24)  # Annualized
        return volatility
    
    def calculate_funding_impact(self, funding_rate: float, position_size: float) -> float:
        """Calculate the impact of funding rate on position"""
        return position_size * funding_rate * 3  # 3x for 8-hour funding periods
    
    def calculate_dynamic_spread(self, volatility: float) -> float:
        """Calculate required spread based on volatility"""
        spread = self.min_spread + (volatility * 2)  # Increase spread with volatility
        return min(spread, self.max_spread)
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        volatility: float
    ) -> Tuple[float, float]:
        """Calculate safe position size based on volatility"""
        # Reduce position size when volatility is high
        vol_scalar = max(0.2, 1 - (volatility / self.vol_threshold))
        
        # Calculate base position size with more conservative sizing
        max_position_value = capital * self.max_position_pct * vol_scalar * 0.5  # Added 0.5 factor for safety
        leverage = min(self.max_leverage, 2 / volatility)  # More conservative leverage
        
        position_size = (max_position_value * leverage) / price
        return position_size, leverage
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        capital: float,
        funding_data: Optional[pd.DataFrame] = None
    ) -> List[Dict]:
        """Generate trading signals based on market conditions"""
        signals = []
        
        # Calculate volatility
        volatility = self.calculate_volatility(data, self.lookback_period)
        data['volatility'] = volatility
        
        # Calculate required spread for each period
        data['required_spread'] = data['volatility'].apply(self.calculate_dynamic_spread)
        
        # Calculate actual spreads (using high-low as proxy)
        data['actual_spread'] = (data['high'] - data['low']) / data['close']
        
        # Print some statistics for debugging
        print("\nStrategy Statistics:")
        print(f"Average Volatility: {data['volatility'].mean():.4f}")
        print(f"Average Required Spread: {data['required_spread'].mean():.4f}")
        print(f"Average Actual Spread: {data['actual_spread'].mean():.4f}")
        print(f"Number of periods with high spread: {len(data[data['actual_spread'] > data['required_spread'] * 1.3])}")
        print(f"Number of periods with low volatility: {len(data[data['volatility'] < self.vol_threshold * 0.8])}")
        
        # Track active symbols to avoid duplicate signals
        active_symbols = set()
        
        for idx in range(len(data)):
            current_row = data.iloc[idx]
            timestamp = current_row.name if isinstance(current_row.name, datetime) else pd.to_datetime(current_row.name)
            
            # Skip if not enough lookback data
            if idx < self.lookback_period:
                continue
            
            # Get current market conditions
            current_price = current_row['close']
            current_vol = current_row['volatility']
            current_spread = current_row['actual_spread']
            required_spread = current_row['required_spread']
            
            # Check funding rate if available
            funding_rate = 0
            if funding_data is not None:
                # Get the nearest funding rate before current timestamp
                nearest_funding = funding_data.asof(timestamp)
                if nearest_funding is not None:
                    funding_rate = nearest_funding['fundingRate'] if isinstance(nearest_funding, pd.Series) else 0
            
            # Generate signals based on conditions
            positions_to_close = []
            for symbol in list(self.positions.keys()):
                if symbol in active_symbols:
                    continue
                    
                position = self.positions[symbol]
                
                # Check exit conditions
                if position['side'] == 'long':
                    # Exit long if spread narrows or volatility too high
                    if (current_spread < required_spread * 0.8 or  # More conservative exit
                        current_vol > self.vol_threshold * 1.3 or  # More conservative volatility threshold
                        funding_rate > self.funding_threshold * 0.8):  # More conservative funding threshold
                        
                        signals.append({
                            'action': 'close',
                            'symbol': symbol,
                            'price': current_price,
                            'timestamp': timestamp,
                            'reason': 'spread_narrowing' if current_spread < required_spread * 0.8 else 'high_volatility',
                            'funding_cost': self.calculate_funding_impact(
                                funding_rate, position['size']
                            ) if funding_data is not None else 0
                        })
                        positions_to_close.append(symbol)
                        active_symbols.add(symbol)
                
                elif position['side'] == 'short':
                    # Exit short if spread narrows or volatility too high
                    if (current_spread < required_spread * 0.8 or
                        current_vol > self.vol_threshold * 1.3 or
                        funding_rate < -self.funding_threshold * 0.8):
                        
                        signals.append({
                            'action': 'close',
                            'symbol': symbol,
                            'price': current_price,
                            'timestamp': timestamp,
                            'reason': 'spread_narrowing' if current_spread < required_spread * 0.8 else 'high_volatility',
                            'funding_cost': self.calculate_funding_impact(
                                funding_rate, position['size']
                            ) if funding_data is not None else 0
                        })
                        positions_to_close.append(symbol)
                        active_symbols.add(symbol)
            
            # Close positions after iteration
            for symbol in positions_to_close:
                if symbol in self.positions:  # Double check position still exists
                    del self.positions[symbol]
            
            # Check entry conditions
            if not self.positions and len(active_symbols) == 0:  # Only enter if no positions open and no recent activity
                # Calculate position size based on current conditions
                position_size, leverage = self.calculate_position_size(
                    capital, current_price, current_vol
                )
                
                # Long entry conditions
                if (current_spread > required_spread * 1.3 and  # More conservative entry
                    current_vol < self.vol_threshold * 0.8 and  # More conservative volatility threshold
                    funding_rate < self.funding_threshold * 0.5):  # More conservative funding threshold
                    
                    symbol = data.iloc[idx].name
                    if symbol not in active_symbols:
                        signals.append({
                            'action': 'open',
                            'symbol': symbol,
                            'side': 'long',
                            'price': current_price,
                            'amount': position_size,
                            'leverage': leverage,
                            'timestamp': timestamp,
                            'reason': 'spread_widening'
                        })
                        
                        self.positions[symbol] = {
                            'side': 'long',
                            'entry_price': current_price,
                            'size': position_size,
                            'leverage': leverage,
                            'entry_time': timestamp
                        }
                        active_symbols.add(symbol)
                
                # Short entry conditions
                elif (current_spread > required_spread * 1.3 and
                      current_vol < self.vol_threshold * 0.8 and
                      funding_rate > -self.funding_threshold * 0.5):
                    
                    symbol = data.iloc[idx].name
                    if symbol not in active_symbols:
                        signals.append({
                            'action': 'open',
                            'symbol': symbol,
                            'side': 'short',
                            'price': current_price,
                            'amount': position_size,
                            'leverage': leverage,
                            'timestamp': timestamp,
                            'reason': 'spread_widening'
                        })
                        
                        self.positions[symbol] = {
                            'side': 'short',
                            'entry_price': current_price,
                            'size': position_size,
                            'leverage': leverage,
                            'entry_time': timestamp
                        }
                        active_symbols.add(symbol)
            
            # Track metrics
            self.metrics.append({
                'timestamp': timestamp,
                'price': current_price,
                'volatility': current_vol,
                'actual_spread': current_spread,
                'required_spread': required_spread,
                'funding_rate': funding_rate,
                'position_count': len(self.positions)
            })
        
        return signals

    def get_metrics_df(self) -> pd.DataFrame:
        """Get metrics as DataFrame"""
        return pd.DataFrame(self.metrics)
