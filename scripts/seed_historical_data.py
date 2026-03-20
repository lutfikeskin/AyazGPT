import argparse
import asyncio
import yfinance as yf
import pandas as pd
from loguru import logger
from tqdm import tqdm
from typing import List
import time
import sys
import os
from sqlalchemy.dialects.postgresql import insert

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal
from modules.investment.models import MarketPrice

DEFAULT_SYMBOLS = [
    # BIST 100
    "AEFES.IS", "AGESA.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKGRT.IS", "AKSA.IS",
    "AKSEN.IS", "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ALKIM.IS", "ANACM.IS", "ANELE.IS",
    "ARCLK.IS", "ARDYZ.IS", "ASELS.IS", "ASUZU.IS", "AYDEM.IS", "BERA.IS", "BIMAS.IS",
    "BIOEN.IS", "BRISA.IS", "BRYAT.IS", "BUCIM.IS", "CEMTS.IS", "CIMSA.IS", "CLEBI.IS",
    "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "EGEEN.IS", "EKGYO.IS", "ENERY.IS",
    "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FMIZP.IS", "FROTO.IS", "GARAN.IS",
    "GESAN.IS", "GOLTS.IS", "GUBRF.IS", "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS",
    "ISCTR.IS", "ISGYO.IS", "ISMEN.IS", "ITTFH.IS", "IZMDC.IS", "KARSN.IS", "KCHOL.IS",
    "KERVT.IS", "KLNMA.IS", "KMPUR.IS", "KONTR.IS", "KONYA.IS", "KORDS.IS", "KOZAA.IS",
    "KOZAL.IS", "KRDMD.IS", "LOGO.IS", "MAVI.IS", "MGROS.IS", "MPARK.IS", "NETAS.IS",
    "NTHOL.IS", "NUGYO.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PETKM.IS", "PGSUS.IS",
    "PKART.IS", "PNSUT.IS", "QUAGR.IS", "SAHOL.IS", "SASA.IS", "SELEC.IS", "SISE.IS",
    "SKBNK.IS", "SMRTG.IS", "SNGYO.IS", "SODSN.IS", "SOKM.IS", "TAVHL.IS", "TCELL.IS",
    "THYAO.IS", "TKFEN.IS", "TKNSA.IS", "TMSN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS",
    "TUPRS.IS", "TURSG.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YKBNK.IS",
    "YYLGD.IS", "ZOREN.IS", "XU100.IS",
    
    # GLOBAL ENDEKSLER
    "SPY", "QQQ", "DIA", "EEM", "VT", "XLF", "XLE", "XLK",
    
    # GLOBAL HİSSELER
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B",
    "JPM", "GS", "BAC", "XOM", "CVX",
    
    # EMTİA
    "GC=F", "SI=F", "CL=F", "NG=F", "HG=F", "PL=F",
    
    # DÖVİZ
    "USDTRY=X", "EURUSD=X", "GBPUSD=X", "USDJPY=X",
    "EURTRY=X", "GBPTRY=X", "XAUUSD=X",
    
    # KRIPTO
    "BTC-USD", "ETH-USD"
]

async def save_batch(records: List[dict]) -> bool:
    if not records:
        return True
    async with AsyncSessionLocal() as session:
        try:
            stmt = insert(MarketPrice).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol', 'timestamp'],
                set_={
                    'open': stmt.excluded.open,
                    'high': stmt.excluded.high,
                    'low': stmt.excluded.low,
                    'close': stmt.excluded.close,
                    'volume': stmt.excluded.volume,
                }
            )
            await session.execute(stmt)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to save batch: {e}")
            return False

async def run_seed(symbols: List[str], period: str):
    logger.info(f"Starting historical data seed for {len(symbols)} symbols. Period: {period}")
    
    batch_size = 10
    total_saved = 0
    
    for i in tqdm(range(0, len(symbols), batch_size), desc="Batch Process"):
        batch = symbols[i:i+batch_size]
        try:
            # Download using threads
            data = yf.download(batch, period=period, interval="1d", group_by='ticker', threads=True, progress=False)
            
            if data.empty:
                continue

            # Ensure index is UTC aware
            if data.index.tzinfo is None:
                data.index = data.index.tz_localize('UTC')
            else:
                data.index = data.index.tz_convert('UTC')
            
            records_to_save = []
            
            if len(batch) == 1:
                # single ticker dict structure is slightly different
                ticker = batch[0]
                df = data.dropna(subset=['Close'])
                if not df.empty:
                    for dt, row in df.iterrows():
                        # dt is now UTC-aware from the centralized fix above
                        vol_val = row.get('Volume', 0)
                        vol = int(vol_val) if pd.notna(vol_val) else 0
                        records_to_save.append({
                            "symbol": ticker,
                            "timestamp": dt,
                            "open": float(row['Open']),
                            "high": float(row['High']),
                            "low": float(row['Low']),
                            "close": float(row['Close']),
                            "volume": vol,
                            "source": "yfinance"
                        })
                    logger.info(f"Loaded {len(df)} records for {ticker}")
            else:
                for ticker in batch:
                    if ticker not in data.columns.levels[0]:
                        logger.warning(f"No data returned for {ticker}")
                        continue
                        
                    df = data[ticker].dropna(subset=['Close'])
                    if df.empty:
                        logger.warning(f"Empty data for {ticker}")
                        continue
                        
                    for dt, row in df.iterrows():
                        # dt is now UTC-aware
                        vol_val = row.get('Volume', 0)
                        vol = int(vol_val) if pd.notna(vol_val) else 0
                        records_to_save.append({
                            "symbol": ticker,
                            "timestamp": dt,
                            "open": float(row['Open']),
                            "high": float(row['High']),
                            "low": float(row['Low']),
                            "close": float(row['Close']),
                            "volume": vol,
                            "source": "yfinance"
                        })
                    logger.info(f"Loaded {len(df)} records for {ticker}")
            
            if records_to_save:
                db_chunk_size = 500
                for j in range(0, len(records_to_save), db_chunk_size):
                    chunk = records_to_save[j:j+db_chunk_size]
                    success = await save_batch(chunk)
                    if success:
                        total_saved += len(chunk)
                
        except Exception as e:
            logger.error(f"Error processing batch {batch}: {e}")
            
        time.sleep(2) # rate limit prevention

    logger.info(f"Seed complete. Total records saved: {total_saved}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Historical Market Data")
    parser.add_argument("--symbols", nargs="+", help="Specific symbols to seed", default=DEFAULT_SYMBOLS)
    parser.add_argument("--period", type=str, default="10y", help="Period to fetch (e.g., 1y, 5y, 10y)")
    
    args = parser.parse_args()
    asyncio.run(run_seed(args.symbols, args.period))
