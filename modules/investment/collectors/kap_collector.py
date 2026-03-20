import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

import httpx
from loguru import logger
from sqlalchemy import select, insert, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.database import AsyncSessionLocal as async_session
from modules.investment.ai.llm_client import LLMClient
from modules.investment.models import NewsItem

@dataclass
class KAPDisclosure:
    id: str              # disclosureId
    title: str
    body: str
    url: str
    company_name: str
    disclosure_type: str
    published_at: datetime
    symbols_mentioned: List[str]
    sentiment_score: float | None
    is_high_priority: bool

@dataclass
class CollectionResult:
    total_fetched: int
    new_saved: int
    high_priority_count: int
    duration_seconds: float

# BIST 100 COMPANY -> TICKER MAPPING (Fallback)
COMPANY_TO_TICKER = {
    "Türk Hava Yolları": "THYAO.IS",
    "BİM Birleşik": "BIMAS.IS",
    "Akbank": "AKBNK.IS",
    "Garanti": "GARAN.IS",
    "İş Bankası": "ISCTR.IS",
    "Yapı ve Kredi": "YKBNK.IS",
    "Tüpraş": "TUPRS.IS",
    "Ereğli Demir": "EREGL.IS",
    "Koç Holding": "KCHOL.IS",
    "Sabancı Holding": "SAHOL.IS",
}

class KAPCollector:
    """
    Fetches official company disclosures from KAP via JSON API.
    """

    API_URL = "https://www.kap.org.tr/tr/api/disclosure/list/main"
    DETAIL_URL_BASE = "https://www.kap.org.tr/tr/Bildirim/"

    HIGH_PRIORITY_TYPES = [
        "Özel Durum Açıklaması",
        "İçeriden Öğrenenlerin Ticareti",
        "Temettü Açıklaması",
        "Birleşme",
        "Sermaye Artırımı",
        "ODA",
        "CA"
    ]

    def __init__(self):
        self.llm = LLMClient()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://www.kap.org.tr/tr",
            "Content-Type": "application/json"
        }

    async def fetch_disclosures(self, days_back: int = 1) -> List[KAPDisclosure]:
        """Fetch disclosures from JSON API."""
        now = datetime.now()
        from_date = (now - timedelta(days=days_back)).strftime('%d.%m.%Y')
        to_date = now.strftime('%d.%m.%Y')
        
        payload = {
            "fromDate": from_date,
            "toDate": to_date,
            "disclosureTypes": None,
            "memberTypes": ["DDK", "IGS"],
            "mkkMemberOid": None
        }

        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
            try:
                response = await client.post(self.API_URL, json=payload)
                if response.status_code != 200:
                    logger.error(f"KAP API error: {response.status_code}")
                    return []
                
                data = response.json()
                disclosures = []
                
                for item in data:
                    basic = item.get("disclosureBasic", {})
                    d_id = basic.get("disclosureId")
                    if not d_id: continue
                    
                    # Parse date: "19.03.2026 22:54:01"
                    try:
                        pub_date = datetime.strptime(basic["publishDate"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc)
                    except:
                        pub_date = datetime.now(timezone.utc)
                        
                    stock_code = basic.get("stockCode")
                    symbols = []
                    if stock_code:
                        symbols = [s.strip() + ".IS" for s in stock_code.split(",") if s.strip()]
                    
                    title = basic.get("title", "No Title")
                    summary = basic.get("summary")
                    body = summary if summary else title
                    
                    disclosure_type = basic.get("disclosureType", "")
                    is_high_priority = any(hp in disclosure_type or hp in title for hp in self.HIGH_PRIORITY_TYPES)
                    
                    disclosures.append(KAPDisclosure(
                        id=d_id,
                        title=title,
                        body=body,
                        url=f"{self.DETAIL_URL_BASE}{d_id}",
                        company_name=basic.get("companyTitle", "Unknown"),
                        disclosure_type=disclosure_type,
                        published_at=pub_date,
                        symbols_mentioned=symbols,
                        sentiment_score=None,
                        is_high_priority=is_high_priority
                    ))
                
                return disclosures
            except Exception as e:
                logger.error(f"Error fetching KAP API: {e}")
                return []

    async def extract_symbol_fallback(self, disclosure: KAPDisclosure) -> List[str]:
        """Fallback symbol extraction via LLM if stockCode was missing."""
        if disclosure.symbols_mentioned:
            return disclosure.symbols_mentioned
            
        name = disclosure.company_name
        # 1. Check mapping
        for key, ticker in COMPANY_TO_TICKER.items():
            if key.lower() in name.lower():
                return [ticker]
        
        # 2. LLM Fallback
        try:
            prompt = f"Company: {name}. What is the BIST ticker? Reply with symbol (e.g. THYAO.IS) or 'UNKNOWN'."
            response = await self.llm.generate_flash(prompt)
            symbol = response.strip().upper()
            if symbol != "UNKNOWN" and "." in symbol:
                return [symbol]
        except:
            pass
        return []

    async def score_sentiment(self, disclosure: KAPDisclosure) -> float:
        """Score sentiment of Turkish disclosure."""
        try:
            prompt = f"Rate financial sentiment (-1.0 to 1.0) of this Turkish disclosure: {disclosure.title} - {disclosure.body[:400]}. Single float only."
            response = await self.llm.generate_flash(prompt)
            match = re.search(r"[-+]?\d*\.\d+|\d+", response)
            return float(match.group()) if match else 0.0
        except Exception as e:
            logger.error(f"Sentiment error: {e}")
            return 0.0

    async def save_to_db(self, disclosures: List[KAPDisclosure]) -> int:
        count = 0
        async with async_session() as session:
            for d in disclosures:
                stmt = pg_insert(NewsItem.__table__).values(
                    id=d.id,
                    title=d.title,
                    body=d.body,
                    url=d.url,
                    source="KAP",
                    published_at=d.published_at,
                    symbols_mentioned=d.symbols_mentioned,
                    sentiment_score=d.sentiment_score
                ).on_conflict_do_nothing(index_elements=["id"])
                
                res = await session.execute(stmt)
                if res.rowcount > 0:
                    count += 1
            await session.commit()
        return count

    async def run_collection(self) -> CollectionResult:
        start_time = datetime.now()
        logger.info("Starting KAP API collection...")
        
        disclosures = await self.fetch_disclosures(days_back=1)
        logger.info(f"Fetched {len(disclosures)} disclosures from KAP API.")
        
        # Deduplicate and check for new ones
        new_disclosures = []
        async with async_session() as session:
            for d in disclosures:
                res = await session.execute(select(NewsItem).where(NewsItem.id == d.id))
                if not res.scalar_one_or_none():
                    new_disclosures.append(d)
        
        logger.info(f"Processing {len(new_disclosures)} new disclosures.")
        
        high_priority_count = 0
        for d in new_disclosures:
            if not d.symbols_mentioned:
                d.symbols_mentioned = await self.extract_symbol_fallback(d)
            
            d.sentiment_score = await self.score_sentiment(d)
            if d.is_high_priority:
                high_priority_count += 1
        
        new_saved = await self.save_to_db(new_disclosures)
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"KAP: {new_saved} new saved ({high_priority_count} high priority) in {duration:.2f}s")
        
        return CollectionResult(len(disclosures), new_saved, high_priority_count, duration)

if __name__ == "__main__":
    import asyncio
    async def main():
        c = KAPCollector()
        await c.run_collection()
    asyncio.run(main())
