import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Dict, List, Tuple
import asyncio
import random
import time

@dataclass
class MarketState:
    spot_price: float
    perp_price: float
    funding_rate: float
    timestamp: float
    spread: float = 0.0
    volatility: float = 0.0

@dataclass
class Position:
    entry_spot_price: float
    entry_perp_price: float
    size: float
    entry_time: float
    leverage: float
    initial_margin: float

class ArbitrageRiskSimulator:
    def __init__(self, 
                 initial_capital: float = 10000,
                 leverage: float = 5,
                 position_size_pct: float = 0.8):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        self.position_size_pct = position_size_pct
        self.max_position_size = initial_capital * leverage * position_size_pct
        self.positions: List[Position] = []
        self.history: List[Dict] = []
        self.liquidation_threshold = 0.8  # 80% of initial margin
        
    def simulate_market_shock(self, 
                            base_price: float = 95000, 
                            shock_size: float = 0.05,
                            duration_seconds: int = 60) -> List[MarketState]:
        """Simulate a market shock scenario"""
        states = []
        start_time = time.time()
        
        # Generate shock pattern
        for i in range(duration_seconds):
            current_time = start_time + i
            # Shock intensity follows a bell curve
            shock_intensity = shock_size * np.exp(-(((i-duration_seconds/2)/(duration_seconds/4))**2))
            
            # Spot and perp prices diverge temporarily
            spot_shock = -shock_intensity * base_price
            perp_shock = shock_intensity * base_price
            
            # Add some random noise
            spot_noise = np.random.normal(0, base_price * 0.0001)
            perp_noise = np.random.normal(0, base_price * 0.0001)
            
            state = MarketState(
                spot_price=base_price + spot_shock + spot_noise,
                perp_price=base_price + perp_shock + perp_noise,
                funding_rate=0.01 * (1 - shock_intensity),  # Funding rate affected by shock
                timestamp=current_time,
                spread=(perp_shock - spot_shock) / base_price,
                volatility=shock_intensity
            )
            states.append(state)
            
        return states
    
    def simulate_execution_risk(self, 
                              intended_spot_price: float,
                              intended_perp_price: float,
                              market_volatility: float = 0.001) -> Tuple[float, float]:
        """Simulate execution slippage based on market conditions"""
        # Higher volatility = higher slippage
        spot_slippage = np.random.normal(0, intended_spot_price * market_volatility)
        perp_slippage = np.random.normal(0, intended_perp_price * market_volatility)
        
        actual_spot_price = intended_spot_price + spot_slippage
        actual_perp_price = intended_perp_price + perp_slippage
        
        return actual_spot_price, actual_perp_price
    
    def calculate_position_pnl(self, 
                             position: Position,
                             current_spot: float,
                             current_perp: float,
                             current_time: float) -> Dict:
        """Calculate unrealized P&L for a position"""
        spot_pnl = (current_spot - position.entry_spot_price) * position.size
        perp_pnl = (position.entry_perp_price - current_perp) * position.size
        
        # Calculate funding payments
        hours_held = (current_time - position.entry_time) / 3600
        funding_periods = hours_held / 8  # Funding every 8 hours
        funding_pnl = position.size * current_perp * 0.01 * funding_periods  # Assuming 0.01% funding rate
        
        total_pnl = spot_pnl + perp_pnl + funding_pnl
        return {
            'spot_pnl': spot_pnl,
            'perp_pnl': perp_pnl,
            'funding_pnl': funding_pnl,
            'total_pnl': total_pnl,
            'roi': total_pnl / position.initial_margin
        }
    
    def check_liquidation(self, 
                         position: Position,
                         current_pnl: float) -> bool:
        """Check if position should be liquidated"""
        remaining_margin = position.initial_margin + current_pnl
        return remaining_margin < (position.initial_margin * self.liquidation_threshold)
    
    async def run_simulation(self, 
                           scenario: str = 'market_shock',
                           duration_seconds: int = 60):
        """Run a full simulation scenario"""
        print(f"\nRunning {scenario} simulation...")
        print(f"Initial capital: ${self.initial_capital:,.2f}")
        print(f"Leverage: {self.leverage}x")
        print(f"Max position size: ${self.max_position_size:,.2f}")
        
        base_price = 95000
        states = []
        
        if scenario == 'market_shock':
            states = self.simulate_market_shock(base_price, 0.05, duration_seconds)
        elif scenario == 'execution_risk':
            # Simulate rapid small price changes
            states = self.simulate_market_shock(base_price, 0.01, duration_seconds)
        
        # Open a position
        initial_state = states[0]
        position_size = self.max_position_size / initial_state.spot_price
        
        # Simulate execution slippage
        actual_spot, actual_perp = self.simulate_execution_risk(
            initial_state.spot_price,
            initial_state.perp_price,
            initial_state.volatility
        )
        
        position = Position(
            entry_spot_price=actual_spot,
            entry_perp_price=actual_perp,
            size=position_size,
            entry_time=initial_state.timestamp,
            leverage=self.leverage,
            initial_margin=self.max_position_size / self.leverage
        )
        
        self.positions.append(position)
        
        # Run through market states
        for state in states:
            pnl = self.calculate_position_pnl(
                position,
                state.spot_price,
                state.perp_price,
                state.timestamp
            )
            
            # Check for liquidation
            if self.check_liquidation(position, pnl['total_pnl']):
                print(f"\n🚨 LIQUIDATION at timestamp {state.timestamp - states[0].timestamp:.1f}s")
                print(f"Spot Price: ${state.spot_price:,.2f}")
                print(f"Perp Price: ${state.perp_price:,.2f}")
                print(f"Total Loss: ${pnl['total_pnl']:,.2f}")
                print(f"ROI: {pnl['roi']*100:.2f}%")
                break
            
            self.history.append({
                'timestamp': state.timestamp,
                'spot_price': state.spot_price,
                'perp_price': state.perp_price,
                'spread': state.spread,
                'volatility': state.volatility,
                'total_pnl': pnl['total_pnl'],
                'roi': pnl['roi']
            })
            
            # Print updates every 10 seconds
            if len(self.history) % 10 == 0:
                print(f"\nTimestamp: {state.timestamp - states[0].timestamp:.1f}s")
                print(f"Spread: {state.spread*100:.3f}%")
                print(f"P&L: ${pnl['total_pnl']:,.2f}")
                print(f"ROI: {pnl['roi']*100:.2f}%")
        
        # Plot results
        self.plot_simulation_results()
    
    def plot_simulation_results(self):
        """Plot the simulation results"""
        df = pd.DataFrame(self.history)
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
        
        # Plot prices
        ax1.plot(df['timestamp'], df['spot_price'], label='Spot Price')
        ax1.plot(df['timestamp'], df['perp_price'], label='Perp Price')
        ax1.set_title('Price Movement')
        ax1.legend()
        
        # Plot spread
        ax2.plot(df['timestamp'], df['spread'] * 100)
        ax2.set_title('Spread (%)')
        
        # Plot P&L
        ax3.plot(df['timestamp'], df['total_pnl'])
        ax3.set_title('P&L ($)')
        
        plt.tight_layout()
        plt.show()

async def main():
    # Run market shock scenario
    simulator = ArbitrageRiskSimulator(
        initial_capital=10000,
        leverage=5,
        position_size_pct=0.8
    )
    await simulator.run_simulation('market_shock', 60)
    
    # Run execution risk scenario
    simulator2 = ArbitrageRiskSimulator(
        initial_capital=10000,
        leverage=5,
        position_size_pct=0.8
    )
    await simulator2.run_simulation('execution_risk', 60)

if __name__ == "__main__":
    asyncio.run(main())
