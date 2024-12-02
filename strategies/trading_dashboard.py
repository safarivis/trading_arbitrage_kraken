import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import numpy as np
from typing import Dict, List
import asyncio
from datetime import datetime
import threading
from queue import Queue

class TradingDashboard:
    def __init__(self, update_interval: int = 1000):
        self.root = tk.Tk()
        self.root.title("Perpetual Arbitrage Dashboard")
        self.root.geometry("1200x800")
        self.update_interval = update_interval
        
        # Data storage
        self.price_history = []
        self.pnl_history = []
        self.risk_metrics_history = []
        self.update_queue = Queue()
        
        self._setup_ui()
        self._setup_plots()
        
    def _setup_ui(self):
        """Setup the UI components"""
        # Create main frames
        self.metrics_frame = ttk.LabelFrame(self.root, text="Current Metrics", padding=10)
        self.metrics_frame.pack(fill="x", padx=5, pady=5)
        
        self.risk_frame = ttk.LabelFrame(self.root, text="Risk Metrics", padding=10)
        self.risk_frame.pack(fill="x", padx=5, pady=5)
        
        self.charts_frame = ttk.LabelFrame(self.root, text="Charts", padding=10)
        self.charts_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Setup metrics labels
        self.metrics_labels = {}
        metrics = [
            "Spot Price", "Perp Price", "Spread", "Funding Rate",
            "Position Size", "Current P&L", "ROI"
        ]
        
        for i, metric in enumerate(metrics):
            label = ttk.Label(self.metrics_frame, text=f"{metric}:")
            label.grid(row=i//3, column=(i%3)*2, padx=5, pady=2, sticky="e")
            
            value_label = ttk.Label(self.metrics_frame, text="0.00")
            value_label.grid(row=i//3, column=(i%3)*2+1, padx=5, pady=2, sticky="w")
            self.metrics_labels[metric] = value_label
        
        # Setup risk labels
        self.risk_labels = {}
        risk_metrics = [
            "Volatility", "Margin Ratio", "Liquidation Risk",
            "Max Drawdown", "Sharpe Ratio", "Position Count"
        ]
        
        for i, metric in enumerate(risk_metrics):
            label = ttk.Label(self.risk_frame, text=f"{metric}:")
            label.grid(row=i//3, column=(i%3)*2, padx=5, pady=2, sticky="e")
            
            value_label = ttk.Label(self.risk_frame, text="0.00")
            value_label.grid(row=i//3, column=(i%3)*2+1, padx=5, pady=2, sticky="w")
            self.risk_labels[metric] = value_label
    
    def _setup_plots(self):
        """Setup the matplotlib plots"""
        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 6))
        self.fig.tight_layout(pad=3.0)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.charts_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Initialize subplots
        self.price_line, = self.axes[0,0].plot([], [], 'b-', label='Price')
        self.axes[0,0].set_title('Price Movement')
        self.axes[0,0].legend()
        
        self.spread_line, = self.axes[0,1].plot([], [], 'g-', label='Spread')
        self.axes[0,1].set_title('Spread %')
        self.axes[0,1].legend()
        
        self.pnl_line, = self.axes[1,0].plot([], [], 'r-', label='P&L')
        self.axes[1,0].set_title('P&L ($)')
        self.axes[1,0].legend()
        
        self.risk_line, = self.axes[1,1].plot([], [], 'm-', label='Risk Score')
        self.axes[1,1].set_title('Risk Score')
        self.axes[1,1].legend()
    
    def update_metrics(self, metrics: Dict):
        """Update the metrics display"""
        self.update_queue.put(('metrics', metrics))
    
    def update_risk_metrics(self, risk_metrics: Dict):
        """Update the risk metrics display"""
        self.update_queue.put(('risk', risk_metrics))
    
    def update_charts(self, chart_data: Dict):
        """Update the charts with new data"""
        self.update_queue.put(('charts', chart_data))
    
    def _process_updates(self):
        """Process updates from the queue"""
        while not self.update_queue.empty():
            update_type, data = self.update_queue.get()
            
            if update_type == 'metrics':
                for metric, value in data.items():
                    if metric in self.metrics_labels:
                        self.metrics_labels[metric].config(text=str(value))
            
            elif update_type == 'risk':
                for metric, value in data.items():
                    if metric in self.risk_labels:
                        self.risk_labels[metric].config(text=str(value))
            
            elif update_type == 'charts':
                # Update price chart
                if 'prices' in data:
                    self.price_line.set_data(range(len(data['prices'])), data['prices'])
                    self.axes[0,0].relim()
                    self.axes[0,0].autoscale_view()
                
                # Update spread chart
                if 'spreads' in data:
                    self.spread_line.set_data(range(len(data['spreads'])), data['spreads'])
                    self.axes[0,1].relim()
                    self.axes[0,1].autoscale_view()
                
                # Update P&L chart
                if 'pnl' in data:
                    self.pnl_line.set_data(range(len(data['pnl'])), data['pnl'])
                    self.axes[1,0].relim()
                    self.axes[1,0].autoscale_view()
                
                # Update risk chart
                if 'risk' in data:
                    self.risk_line.set_data(range(len(data['risk'])), data['risk'])
                    self.axes[1,1].relim()
                    self.axes[1,1].autoscale_view()
                
                self.canvas.draw()
        
        # Schedule next update
        self.root.after(self.update_interval, self._process_updates)
    
    def start(self):
        """Start the dashboard"""
        self._process_updates()
        self.root.mainloop()
    
    def stop(self):
        """Stop the dashboard"""
        self.root.quit()

class DashboardManager:
    def __init__(self):
        self.dashboard = None
        self.dashboard_thread = None
    
    def start_dashboard(self):
        """Start the dashboard in a separate thread"""
        def run_dashboard():
            self.dashboard = TradingDashboard()
            self.dashboard.start()
        
        self.dashboard_thread = threading.Thread(target=run_dashboard)
        self.dashboard_thread.daemon = True
        self.dashboard_thread.start()
    
    def update_dashboard(self, metrics: Dict, risk_metrics: Dict, chart_data: Dict):
        """Update all dashboard components"""
        if self.dashboard:
            self.dashboard.update_metrics(metrics)
            self.dashboard.update_risk_metrics(risk_metrics)
            self.dashboard.update_charts(chart_data)
    
    def stop_dashboard(self):
        """Stop the dashboard"""
        if self.dashboard:
            self.dashboard.stop()
            self.dashboard_thread.join()
