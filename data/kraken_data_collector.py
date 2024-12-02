import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
import os
import json
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('KrakenDataCollector')

class KrakenDataCollector:
    def __init__(self, cache_dir: str = 'data/cache/kraken'):
        """Initialize the Kraken data collector"""
        self.exchange = ccxt.kraken({
            'enableRateLimit': True,
            'rateLimit': 2000  # Be conservative with rate limits
        })
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol"""
        cache_file = self.cache_dir / f"{symbol.replace('/', '_')}_{timeframe}_ohlcv.csv"
        
        # Check cache first
        if use_cache and cache_file.exists():
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Check if we need to fetch more recent data
            if df['timestamp'].max() < end_date:
                new_start = df['timestamp'].max()
                new_df = await self._fetch_ohlcv_chunk(symbol, timeframe, new_start, end_date)
                if not new_df.empty:
                    df = pd.concat([df, new_df]).drop_duplicates(subset=['timestamp'])
                    df.to_csv(cache_file, index=False)
            return df
        
        return await self._fetch_ohlcv_chunk(symbol, timeframe, start_date, end_date)
    
    async def _fetch_ohlcv_chunk(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch OHLCV data in chunks to handle rate limits"""
        try:
            all_candles = []
            current_date = start_date
            
            while current_date < end_date:
                logger.info(f"Fetching {symbol} data from {current_date}")
                
                since = int(current_date.timestamp() * 1000)
                candles = await asyncio.to_thread(
                    self.exchange.fetch_ohlcv,
                    symbol,
                    timeframe,
                    since=since,
                    limit=1000
                )
                
                if not candles:
                    break
                    
                all_candles.extend(candles)
                
                # Update current_date based on last candle
                last_candle_time = datetime.fromtimestamp(candles[-1][0] / 1000)
                if last_candle_time <= current_date:
                    break
                current_date = last_candle_time
                
                # Rate limiting
                await asyncio.sleep(2)
            
            if not all_candles:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(
                all_candles,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Save to cache
            cache_file = self.cache_dir / f"{symbol.replace('/', '_')}_{timeframe}_ohlcv.csv"
            df.to_csv(cache_file, index=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV data for {symbol}: {str(e)}")
            return pd.DataFrame()
    
    async def fetch_funding_rates(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """Fetch funding rate history"""
        cache_file = self.cache_dir / f"{symbol.replace('/', '_')}_funding.csv"
        
        if use_cache and cache_file.exists():
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            if df['timestamp'].max() < end_date:
                new_start = df['timestamp'].max()
                new_df = await self._fetch_funding_chunk(symbol, new_start, end_date)
                if not new_df.empty:
                    df = pd.concat([df, new_df]).drop_duplicates(subset=['timestamp'])
                    df.to_csv(cache_file, index=False)
            return df
        
        return await self._fetch_funding_chunk(symbol, start_date, end_date)
    
    async def _fetch_funding_chunk(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch funding rate data in chunks"""
        try:
            all_rates = []
            current_date = start_date
            
            while current_date < end_date:
                logger.info(f"Fetching funding rates for {symbol} from {current_date}")
                
                since = int(current_date.timestamp() * 1000)
                rates = await asyncio.to_thread(
                    self.exchange.fetch_funding_rate_history,
                    symbol,
                    since=since,
                    limit=1000
                )
                
                if not rates:
                    break
                    
                all_rates.extend(rates)
                
                # Update current_date
                last_rate_time = datetime.fromtimestamp(rates[-1]['timestamp'] / 1000)
                if last_rate_time <= current_date:
                    break
                current_date = last_rate_time
                
                await asyncio.sleep(2)
            
            if not all_rates:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(all_rates)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Save to cache
            cache_file = self.cache_dir / f"{symbol.replace('/', '_')}_funding.csv"
            df.to_csv(cache_file, index=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching funding rates for {symbol}: {str(e)}")
            return pd.DataFrame()
    
    async def fetch_trades(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """Fetch historical trades"""
        cache_file = self.cache_dir / f"{symbol.replace('/', '_')}_trades.csv"
        
        if use_cache and cache_file.exists():
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            if df['timestamp'].max() < end_date:
                new_start = df['timestamp'].max()
                new_df = await self._fetch_trades_chunk(symbol, new_start, end_date)
                if not new_df.empty:
                    df = pd.concat([df, new_df]).drop_duplicates(subset=['timestamp', 'id'])
                    df.to_csv(cache_file, index=False)
            return df
        
        return await self._fetch_trades_chunk(symbol, start_date, end_date)
    
    async def _fetch_trades_chunk(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch trade data in chunks"""
        try:
            all_trades = []
            current_date = start_date
            
            while current_date < end_date:
                logger.info(f"Fetching trades for {symbol} from {current_date}")
                
                since = int(current_date.timestamp() * 1000)
                trades = await asyncio.to_thread(
                    self.exchange.fetch_trades,
                    symbol,
                    since=since,
                    limit=1000
                )
                
                if not trades:
                    break
                    
                all_trades.extend(trades)
                
                # Update current_date
                last_trade_time = datetime.fromtimestamp(trades[-1]['timestamp'] / 1000)
                if last_trade_time <= current_date:
                    break
                current_date = last_trade_time
                
                await asyncio.sleep(2)
            
            if not all_trades:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame([{
                'timestamp': trade['timestamp'],
                'id': trade['id'],
                'price': trade['price'],
                'amount': trade['amount'],
                'side': trade['side'],
                'cost': trade['cost']
            } for trade in all_trades])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Save to cache
            cache_file = self.cache_dir / f"{symbol.replace('/', '_')}_trades.csv"
            df.to_csv(cache_file, index=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching trades for {symbol}: {str(e)}")
            return pd.DataFrame()

async def main():
    # Example usage
    collector = KrakenDataCollector()
    
    # Define parameters
    symbol = "BTC/USD"
    timeframe = "1h"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    # Fetch OHLCV data
    ohlcv_data = await collector.fetch_ohlcv(symbol, timeframe, start_date, end_date)
    print(f"\nFetched {len(ohlcv_data)} OHLCV records")
    
    # Fetch funding rates
    funding_data = await collector.fetch_funding_rates(symbol, start_date, end_date)
    print(f"\nFetched {len(funding_data)} funding rate records")
    
    # Fetch trades
    trades_data = await collector.fetch_trades(symbol, start_date, end_date)
    print(f"\nFetched {len(trades_data)} trade records")

if __name__ == "__main__":
    asyncio.run(main())
