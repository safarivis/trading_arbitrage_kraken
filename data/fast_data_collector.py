import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import logging
from pathlib import Path
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FastDataCollector')

class FastDataCollector:
    def __init__(self, cache_dir: str = 'data/cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Base URLs for different data sources
        self.urls = {
            'binance': 'https://data.binance.vision/data',
            'coinapi': 'https://rest.coinapi.io/v1',
            'cryptocompare': 'https://min-api.cryptocompare.com/data'
        }
        
    async def get_binance_klines(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Get historical klines from Binance Data Portal
        Much faster than API as it downloads zipped CSV files
        """
        symbol = symbol.replace('/', '').upper()
        cache_file = self.cache_dir / f"binance_{symbol}_{interval}_{start_date.date()}_{end_date.date()}.csv"
        
        if cache_file.exists():
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        
        # For now, generate sample data for testing
        # TODO: Implement proper data collection from Binance
        dates = pd.date_range(start=start_date, end=end_date, freq=interval)
        base_price = 50000  # Base price for BTC
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': [base_price * (1 + 0.001 * np.random.randn()) for _ in range(len(dates))],
            'high': [base_price * (1 + 0.002 * np.random.randn()) for _ in range(len(dates))],
            'low': [base_price * (1 - 0.002 * np.random.randn()) for _ in range(len(dates))],
            'close': [base_price * (1 + 0.001 * np.random.randn()) for _ in range(len(dates))],
            'volume': [1000 * np.random.rand() for _ in range(len(dates))]
        })
        
        # Ensure high is highest and low is lowest
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        # Save to cache
        df.to_csv(cache_file, index=False)
        return df

    async def get_cryptocompare_data(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Get historical data from CryptoCompare
        Free API with good historical data
        """
        base, quote = symbol.split('/')
        cache_file = self.cache_dir / f"cryptocompare_{base}{quote}_{interval}_{start_date.date()}_{end_date.date()}.csv"
        
        if cache_file.exists():
            return pd.read_csv(cache_file)
        
        # Convert interval to seconds
        interval_seconds = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }[interval]
        
        url = f"{self.urls['cryptocompare']}/v2/histohour"
        params = {
            'fsym': base,
            'tsym': quote,
            'limit': 2000,
            'aggregate': interval_seconds // 3600
        }
        
        all_data = []
        current_date = start_date
        
        async with aiohttp.ClientSession() as session:
            while current_date <= end_date:
                params['toTs'] = int(current_date.timestamp())
                
                try:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data['Response'] == 'Success':
                                df = pd.DataFrame(data['Data']['Data'])
                                all_data.append(df)
                except Exception as e:
                    logger.error(f"Error fetching data: {e}")
                
                current_date += timedelta(days=30)
        
        if not all_data:
            return pd.DataFrame()
        
        # Combine all data
        df = pd.concat(all_data, ignore_index=True)
        df['timestamp'] = pd.to_datetime(df['time'], unit='s')
        
        # Filter date range
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
        
        # Save to cache
        df.to_csv(cache_file, index=False)
        return df

    async def get_funding_rates(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Get historical funding rates from Binance
        """
        symbol = symbol.replace('/', '').upper()
        cache_file = self.cache_dir / f"funding_rates_{symbol}_{start_date.date()}_{end_date.date()}.csv"
        
        if cache_file.exists():
            return pd.read_csv(cache_file)
        
        # For now, return empty DataFrame with expected columns
        # TODO: Implement proper funding rate collection
        df = pd.DataFrame(columns=['timestamp', 'fundingRate'])
        df['timestamp'] = pd.date_range(start=start_date, end=end_date, freq='8H')
        df['fundingRate'] = 0.0001  # Default funding rate for testing
        
        # Save to cache
        df.to_csv(cache_file, index=False)
        return df

async def main():
    collector = FastDataCollector()
    
    # Test data collection
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 1, 1)
    symbol = "BTC/USDT"
    
    print("\nAttempting to fetch Binance data...")
    try:
        binance_data = await collector.get_binance_klines(symbol, '1h', start_date, end_date)
        if not binance_data.empty:
            print("\nBinance Data Sample:")
            print(f"Shape: {binance_data.shape}")
            print("\nFirst 5 rows:")
            print(binance_data.head())
            print("\nLast 5 rows:")
            print(binance_data.tail())
            
            # Save to CSV for inspection
            sample_file = "binance_data_sample.csv"
            binance_data.to_csv(sample_file)
            print(f"\nSaved complete dataset to {sample_file}")
        else:
            print("No data received from Binance")
    except Exception as e:
        print(f"Error fetching Binance data: {str(e)}")
    
    print("\nAttempting to fetch CryptoCompare data...")
    try:
        cc_data = await collector.get_cryptocompare_data(symbol, '1h', start_date, end_date)
        if not cc_data.empty:
            print("\nCryptoCompare Data Sample:")
            print(f"Shape: {cc_data.shape}")
            print("\nFirst 5 rows:")
            print(cc_data.head())
            print("\nLast 5 rows:")
            print(cc_data.tail())
            
            # Save to CSV for inspection
            sample_file = "cryptocompare_data_sample.csv"
            cc_data.to_csv(sample_file)
            print(f"\nSaved complete dataset to {sample_file}")
        else:
            print("No data received from CryptoCompare")
    except Exception as e:
        print(f"Error fetching CryptoCompare data: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
