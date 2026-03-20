import argparse
import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
from typing import List
from loguru import logger
from sqlalchemy.dialects.postgresql import insert

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.database import AsyncSessionLocal
from modules.investment.models import MarketPrice

class MarketCollector:
    """Collects OHLCV data from Yahoo Finance for various asset classes."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        
    async def save_to_db(self, prices: List[dict]):
        if not prices:
            return
            
        if self.dry_run:
            logger.info(f"[DRY RUN] Would save {len(prices)} market price records.")
            for p in prices[:3]:
                logger.debug(f"[DRY RUN] Sample: {p['symbol']} at {p['timestamp']}: Close {p['close']}")
            return
            
        async with AsyncSessionLocal() as session:
            try:
                stmt = insert(MarketPrice).values(prices)
                
                # TimescaleDB requires ON CONFLICT for idempotent inserts
                stmt = stmt.on_conflict_do_update(
                    index_elements=['symbol', 'timestamp'],
                    set_={
                        'open': stmt.excluded.open,
                        'high': stmt.excluded.high,
                        'low': stmt.excluded.low,
                        'close': stmt.excluded.close,
                        'volume': stmt.excluded.volume,
                        'source': stmt.excluded.source
                    }
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Saved {len(prices)} records to market_prices.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save market prices: {e}")

    async def _fetch_data(self, symbol: str, period: str) -> List[dict]:
        logger.info(f"Fetching {period} data for {symbol} via yfinance...")
        
        # yfinance operations are blocking, run in executor
        loop = asyncio.get_running_loop()
        
        def fetch():
            ticker = yf.Ticker(symbol)
            return ticker.history(period=period)
            
        try:
            # Exponential backoff could be added here if we hit rate limits heavily
            df = await loop.run_in_executor(None, fetch)
            
            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return []
                
            # Ensure index is UTC aware
            if df.index.tzinfo is None:
                df.index = df.index.tz_localize('UTC')
            else:
                df.index = df.index.tz_convert('UTC')

            records = []
            for dt, row in df.iterrows():
                records.append({
                    "symbol": symbol,
                    "timestamp": dt,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                    "source": "yfinance"
                })
            return records
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return []

    async def fetch_historical(self, symbol: str, period: str = "1y"):
        """Fetch historical data for a given symbol and period."""
        records = await self._fetch_data(symbol, period)
        await self.save_to_db(records)

    async def fetch_latest(self, symbol: str):
        """Fetch the latest available data for a given symbol."""
        # Use 5d to ensure we get the latest trading day even on weekends
        records = await self._fetch_data(symbol, period="5d")
        if records:
            await self.save_to_db(records)


async def main():
    parser = argparse.ArgumentParser(description="Market Data Collector")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving to DB")
    parser.add_argument("--symbol", type=str, default="THYAO.IS", help="Symbol to fetch")
    parser.add_argument("--historical", action="store_true", help="Fetch 1y historical data")
    args = parser.parse_args()

    collector = MarketCollector(dry_run=args.dry_run)
    
    if args.historical:
        await collector.fetch_historical(args.symbol, period="1y")
    else:
        await collector.fetch_latest(args.symbol)

if __name__ == "__main__":
    asyncio.run(main())
