import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional
import time

@dataclass
class RiskMetrics:
    spread: float
    volatility: float
    funding_rate: float
    margin_ratio: float
    liquidation_risk: float
    position_size: float
    leverage: float
    timestamp: float

class RiskManager:
    def __init__(self,
                 initial_capital: float,
                 max_leverage: float = 5,
                 max_position_pct: float = 0.8,
                 max_spread: float = 0.02,
                 max_volatility: float = 0.05,
                 min_funding_rate: float = -0.01,
                 margin_buffer: float = 0.2):
        
        self.initial_capital = initial_capital
        self.max_leverage = max_leverage
        self.max_position_pct = max_position_pct
        self.max_spread = max_spread
        self.max_volatility = max_volatility
        self.min_funding_rate = min_funding_rate
        self.margin_buffer = margin_buffer
        
        self.metrics_history: List[RiskMetrics] = []
        self.current_position: Optional[Dict] = None
        
    def calculate_volatility(self, price_history: List[float], window: int = 20) -> float:
        """Calculate rolling volatility"""
        if len(price_history) < window:
            return 0.0
        
        returns = np.diff(np.log(price_history[-window:]))
        return np.std(returns) * np.sqrt(252)  # Annualized
    
    def calculate_margin_ratio(self, 
                             position_value: float,
                             current_pnl: float) -> float:
        """Calculate current margin ratio"""
        initial_margin = position_value / self.max_leverage
        current_margin = initial_margin + current_pnl
        return current_margin / position_value
    
    def calculate_liquidation_risk(self,
                                 margin_ratio: float,
                                 volatility: float) -> float:
        """Estimate probability of liquidation"""
        # Simple model: higher volatility and lower margin = higher risk
        margin_buffer = margin_ratio - self.margin_buffer
        if margin_buffer <= 0:
            return 1.0
        
        risk_score = (volatility * self.max_leverage) / margin_buffer
        return min(max(risk_score, 0), 1)
    
    def check_risk_limits(self, metrics: RiskMetrics) -> Dict[str, bool]:
        """Check if any risk limits are breached"""
        return {
            'spread_limit': metrics.spread > self.max_spread,
            'volatility_limit': metrics.volatility > self.max_volatility,
            'funding_limit': metrics.funding_rate < self.min_funding_rate,
            'margin_limit': metrics.margin_ratio < self.margin_buffer,
            'liquidation_risk': metrics.liquidation_risk > 0.5
        }
    
    def get_position_size(self,
                         current_price: float,
                         volatility: float) -> float:
        """Calculate safe position size based on market conditions"""
        # Reduce position size when volatility is high
        volatility_factor = max(0, 1 - (volatility / self.max_volatility))
        base_size = self.initial_capital * self.max_leverage * self.max_position_pct
        return base_size * volatility_factor
    
    def should_close_position(self, metrics: RiskMetrics) -> Tuple[bool, str]:
        """Determine if position should be closed"""
        limits = self.check_risk_limits(metrics)
        
        if limits['liquidation_risk']:
            return True, "High liquidation risk"
        if limits['spread_limit']:
            return True, "Spread exceeded limit"
        if limits['volatility_limit']:
            return True, "Volatility too high"
        if limits['funding_limit']:
            return True, "Negative funding rate"
        if limits['margin_limit']:
            return True, "Low margin ratio"
            
        return False, ""
    
    def update_metrics(self,
                      spot_price: float,
                      perp_price: float,
                      funding_rate: float,
                      position_value: float = 0,
                      current_pnl: float = 0) -> RiskMetrics:
        """Update risk metrics"""
        spread = (perp_price - spot_price) / spot_price
        
        # Calculate volatility using recent price history
        self.price_history.append(spot_price)
        volatility = self.calculate_volatility(self.price_history)
        
        # Calculate margin metrics if position is open
        margin_ratio = 1.0
        if position_value > 0:
            margin_ratio = self.calculate_margin_ratio(position_value, current_pnl)
        
        # Calculate liquidation risk
        liquidation_risk = self.calculate_liquidation_risk(margin_ratio, volatility)
        
        metrics = RiskMetrics(
            spread=spread,
            volatility=volatility,
            funding_rate=funding_rate,
            margin_ratio=margin_ratio,
            liquidation_risk=liquidation_risk,
            position_size=position_value,
            leverage=self.max_leverage,
            timestamp=time.time()
        )
        
        self.metrics_history.append(metrics)
        return metrics
    
    def get_risk_summary(self) -> Dict:
        """Get current risk summary"""
        if not self.metrics_history:
            return {}
        
        latest = self.metrics_history[-1]
        return {
            'spread': f"{latest.spread*100:.3f}%",
            'volatility': f"{latest.volatility*100:.2f}%",
            'funding_rate': f"{latest.funding_rate*100:.4f}%",
            'margin_ratio': f"{latest.margin_ratio*100:.2f}%",
            'liquidation_risk': f"{latest.liquidation_risk*100:.2f}%",
            'position_size': f"${latest.position_size:,.2f}",
            'leverage': f"{latest.leverage}x"
        }
    
    def plot_risk_metrics(self):
        """Plot historical risk metrics"""
        if not self.metrics_history:
            return
        
        df = pd.DataFrame([vars(m) for m in self.metrics_history])
        
        fig, axes = plt.subplots(3, 2, figsize=(15, 10))
        
        # Plot spread
        axes[0,0].plot(df['timestamp'], df['spread']*100)
        axes[0,0].set_title('Spread (%)')
        
        # Plot volatility
        axes[0,1].plot(df['timestamp'], df['volatility']*100)
        axes[0,1].set_title('Volatility (%)')
        
        # Plot funding rate
        axes[1,0].plot(df['timestamp'], df['funding_rate']*100)
        axes[1,0].set_title('Funding Rate (%)')
        
        # Plot margin ratio
        axes[1,1].plot(df['timestamp'], df['margin_ratio']*100)
        axes[1,1].set_title('Margin Ratio (%)')
        
        # Plot liquidation risk
        axes[2,0].plot(df['timestamp'], df['liquidation_risk']*100)
        axes[2,0].set_title('Liquidation Risk (%)')
        
        # Plot position size
        axes[2,1].plot(df['timestamp'], df['position_size'])
        axes[2,1].set_title('Position Size ($)')
        
        plt.tight_layout()
        plt.show()
