import argparse
import asyncio
import httpx
import feedparser
import json
import uuid
import time
from google import genai
from google.genai import types
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from typing import List, Dict
from loguru import logger
from sqlalchemy.dialects.postgresql import insert

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.database import AsyncSessionLocal
from core.config import settings
from modules.investment.models import NewsItem

# Initialize Gemini Client (new google-genai SDK)
client = genai.Client(api_key=settings.gemini_api_key)

# We use gemini-3-flash-preview for cheap, fast batch sentiment parsing.
FLASH_MODEL = "gemini-3-flash-preview"

RSS_FEEDS = {
    "Bloomberg HT": "https://www.bloomberght.com/rss",
    "Reuters": "https://www.reutersagency.com/feed/?best-regions=europe&best-sectors=financial-services",
    "Investing TR": "https://tr.investing.com/rss/news.rss"
}

class NewsCollector:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        
    async def save_to_db(self, news: List[dict]):
        if not news:
            return
            
        if self.dry_run:
            logger.info(f"[DRY RUN] Would save {len(news)} news items.")
            for n in news[:2]:
                logger.debug(f"[DRY RUN] Sample: {n['title']} | Sentiment: {n.get('sentiment_score')} | Symbols: {n.get('symbols_mentioned')}")
            return
            
        async with AsyncSessionLocal() as session:
            try:
                stmt = insert(NewsItem).values(news)
                stmt = stmt.on_conflict_do_nothing(index_elements=['id'])
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Saved {len(news)} news items to DB.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save news: {e}")

    async def enrich_with_gemini_batch(self, raw_news: List[dict]) -> List[dict]:
        """Process news batch with Gemini to extract sentiment and symbols."""
        if not settings.gemini_api_key or not raw_news:
            return raw_news
            
        # We only send titles to keep the prompt small and fast
        payload = [{"id": n["id"], "text": n["title"]} for n in raw_news]
        
        prompt = f"""For each of the following headlines, extract the financial sentiment (a float between -1.0 and 1.0) and a list of mentioned stock/finance companies or symbols (e.g. ["THYAO.IS", "AAPL"]).
Return strictly a JSON array matching the exact IDs provided.
Format:
[
  {{"id": "id-from-input", "sentiment": 0.5, "symbols": ["THYAO.IS"]}}
]

Headlines:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            logger.info(f"Enriching news headlines via Gemini ({FLASH_MODEL})")
            
            response = client.models.generate_content(
                model=FLASH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json'
                )
            )
            
            results = json.loads(response.text)
            enrichment_map = {item["id"]: item for item in results}
            
            for news in raw_news:
                enriched = enrichment_map.get(news["id"])
                if enriched:
                    # Parse explicitly in case the LLM deviates
                    sentiment = enriched.get("sentiment")
                    news["sentiment_score"] = float(sentiment) if sentiment is not None else None
                    news["symbols_mentioned"] = enriched.get("symbols", [])
                    
        except Exception as e:
            logger.error(f"Gemini batch extraction failed: {e}")
            
        return raw_news

    async def fetch_rss(self) -> List[dict]:
        records = []
        for source, url in RSS_FEEDS.items():
            logger.info(f"Fetching RSS feed from {source}...")
            loop = asyncio.get_running_loop()
            try:
                feed = await loop.run_in_executor(None, feedparser.parse, url)
                
                for entry in feed.entries[:15]: # Fetch top 15 from each
                    dt = datetime.now(timezone.utc)
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                    
                    title = entry.title
                    summary = entry.get('summary', '')
                    soup = BeautifulSoup(summary, "html.parser")
                    clean_summary = soup.get_text(strip=True)
                    
                    records.append({
                        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, entry.link)),
                        "title": title[:500],
                        "body": clean_summary,
                        "url": entry.link[:1000],
                        "source": source,
                        "published_at": dt,
                        "symbols_mentioned": [],
                        "sentiment_score": None
                    })
            except Exception as e:
                logger.error(f"Failed to fetch RSS from {source}: {e}")
                
        # Enrich all collected records via single batch LLM call
        if records:
            logger.info(f"Enriching {len(records)} headlines using Gemini batch API...")
            records = await self.enrich_with_gemini_batch(records)
            
        return records

    async def run_collection(self):
        news = await self.fetch_rss()
        await self.save_to_db(news)


async def main():
    parser = argparse.ArgumentParser(description="News Data Collector")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving to DB")
    args = parser.parse_args()

    collector = NewsCollector(dry_run=args.dry_run)
    await collector.run_collection()

if __name__ == "__main__":
    asyncio.run(main())
