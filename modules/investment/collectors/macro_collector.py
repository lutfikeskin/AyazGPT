import argparse
import asyncio
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional, Dict
from loguru import logger
from sqlalchemy.dialects.postgresql import insert

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.config import settings
from core.database import AsyncSessionLocal
from modules.investment.models import MacroIndicator, NewsItem
import feedparser
import time

# FRED historical endpoints
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
TCMB_TODAY_XML = "https://www.tcmb.gov.tr/kurlar/today.xml"

# You'll need to add FRED_API_KEY to your .env or Config later for these to work.
FRED_SERIES = [
    "DEXTHUS", "FEDFUNDS", "CPIAUCSL", "T10Y2Y", "UNRATE", "DEXUSEU", "GOLDAMGBD228NLBM"
]

class MacroCollector:
    """Collects Macro indicators from FRED and TCMB."""
    
    def __init__(self, dry_run: bool = False, fred_api_key: Optional[str] = None):
        self.dry_run = dry_run
        self.fred_api_key = fred_api_key or settings.fred_api_key
        
    async def save_to_db(self, indicators: List[dict]):
        if not indicators:
            return
            
        if self.dry_run:
            logger.info(f"[DRY RUN] Would save {len(indicators)} macro records.")
            for i in indicators[:3]:
                logger.debug(f"[DRY RUN] Sample: {i['indicator']} = {i['value']} at {i['timestamp']}")
            return
            
        async with AsyncSessionLocal() as session:
            try:
                stmt = insert(MacroIndicator).values(indicators)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['indicator', 'timestamp'],
                    set_={
                        'value': stmt.excluded.value,
                        'source': stmt.excluded.source
                    }
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Saved {len(indicators)} records to macro_indicators.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save macro indicators: {e}")

    async def fetch_tcmb_daily(self) -> List[dict]:
        """Fetch daily USD/TRY reference rate from TCMB XML."""
        logger.info("Fetching daily TCMB USDTRY rate...")
        records = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(TCMB_TODAY_XML, timeout=10.0)
                response.raise_for_status()
                
            root = ET.fromstring(response.content)
            # Find USD
            for currency in root.findall('Currency'):
                if currency.get('CurrencyCode') == 'USD':
                    forex_elem = currency.find('ForexBuying')
                    forex_buying = forex_elem.text if forex_elem is not None else None
                    
                    if forex_buying:
                        records.append({
                            "indicator": "TCMB_USDTRY",
                            "timestamp": datetime.now(timezone.utc),
                            "value": float(forex_buying),
                            "source": "TCMB"
                        })
                    break
        except Exception as e:
            logger.error(f"Failed to fetch/parse TCMB XML: {e}")
            
        return records

    async def fetch_fred_series(self) -> List[dict]:
        """Fetch macro series from FRED API."""
        if not self.fred_api_key:
            logger.warning("FRED_API_KEY not set! Skipping FRED data collection.")
            return []
            
        records = []
        async with httpx.AsyncClient() as client:
            for series in FRED_SERIES:
                logger.info(f"Fetching FRED series: {series}")
                try:
                    # limit to recent observations for daily runs. 
                    # Set limit=10 unless doing historical bootstrap.
                    params: Dict[str, str | int] = {
                        "series_id": series,
                        "api_key": self.fred_api_key or "",
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 5
                    }
                    response = await client.get(FRED_API_URL, params=params, timeout=10.0)
                    response.raise_for_status()
                    data = response.json()
                    
                    for obs in data.get("observations", []):
                        if obs.get("value") == ".":
                            continue # skip missing data
                        try:
                            val = float(obs["value"])
                            dt = datetime.strptime(obs["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                            records.append({
                                "indicator": f"FRED_{series}",
                                "timestamp": dt,
                                "value": val,
                                "source": "FRED"
                            })
                        except ValueError:
                            pass
                except Exception as e:
                    logger.error(f"Error fetching FRED series {series}: {e}")
                    
        return records

    async def fetch_tcmb_policy_rate(self) -> List[dict]:
        logger.info("Fetching TCMB Policy Rate from EVDS...")
        records = []
        evds_url = "https://evds2.tcmb.gov.tr/service/evds/series=TP.MB.S.M.F&startDate=01-01-2015&endDate=today&type=json"
        
        try:
            async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
                res = await client.get(evds_url, timeout=15.0)
                res.raise_for_status()
                data = res.json()
                
                for item in data.get('items', []):
                    val = item.get('TP_MB_S_M_F')
                    date_str = item.get('Tarih')
                    if val and date_str and str(val).lower() != 'null':
                        try:
                            dt = datetime.strptime(date_str, "%d-%m-%Y").replace(tzinfo=timezone.utc)
                            records.append({
                                "indicator": "TCMB_POLICY_RATE",
                                "timestamp": dt,
                                "value": float(val),
                                "source": "TCMB_EVDS"
                            })
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"Failed EVDS API for TCMB Rate: {e}. Fallback logic skipped for brevity.")

        return records

    async def fetch_resmi_gazete(self):
        logger.info("Fetching Resmi Gazete RSS...")
        rss_url = "https://www.resmigazete.gov.tr/rss/son_dakika.xml"
        keywords = ["faiz", "vergi", "bütçe", "ihracat", "ithalat", "teşvik",
                   "sermaye", "borsa", "SPK", "BDDK", "merkez bankası",
                   "enflasyon", "kur", "döviz", "gümrük", "özelleştirme"]
                   
        try:
            feed = feedparser.parse(rss_url)
            news_records = []
            
            for entry in feed.entries:
                title = entry.get('title', '').lower()
                desc = entry.get('description', '').lower()
                
                if any(k in title or k in desc for k in keywords):
                    dt = datetime.now(timezone.utc)
                    if 'published_parsed' in entry and entry.published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), timezone.utc)
                    
                    news_records.append({
                        "title": entry.get('title', ''),
                        "body": entry.get('description', ''),
                        "url": entry.get('link', ''),
                        "source": "Resmi Gazete",
                        "published_at": dt,
                        "symbols_mentioned": [],
                    })
                    
            if not news_records:
                return

            if self.dry_run:
                logger.info(f"[DRY RUN] Would save {len(news_records)} Resmi Gazete items.")
                return

            async with AsyncSessionLocal() as session:
                stmt = insert(NewsItem).values(news_records)
                stmt = stmt.on_conflict_do_nothing(index_elements=['url'])
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Saved {len(news_records)} Resmi Gazete items.")
                
        except Exception as e:
            logger.error(f"Error fetching Resmi Gazete: {e}")

    async def run_collection(self):
        all_records = []
        
        # 1. TCMB USDTRY
        tcmb_records = await self.fetch_tcmb_daily()
        all_records.extend(tcmb_records)
        
        # 2. TCMB Policy Rate
        policy_records = await self.fetch_tcmb_policy_rate()
        all_records.extend(policy_records)
        
        # 3. FRED
        fred_records = await self.fetch_fred_series()
        all_records.extend(fred_records)
        
        await self.save_to_db(all_records)
        
        # 4. Resmi Gazete News
        await self.fetch_resmi_gazete()


async def main():
    parser = argparse.ArgumentParser(description="Macro Data Collector")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving to DB")
    args = parser.parse_args()

    collector = MacroCollector(dry_run=args.dry_run)
    await collector.run_collection()

if __name__ == "__main__":
    asyncio.run(main())
