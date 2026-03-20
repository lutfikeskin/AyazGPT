import asyncio
import json
from core.database import AsyncSessionLocal
from core.cache import cache
from modules.investment.models import NewsItem
from sqlalchemy import select

async def main():
    print("--- CACHE WATCHLIST ---")
    wl = await cache.get("watchlist_symbols")
    print(f"Cache 'watchlist_symbols': {wl}")
    
    print("\n--- DB NEWS ITEMS ---")
    async with AsyncSessionLocal() as session:
        # Check KAP sources
        stmt = select(NewsItem).where(NewsItem.source == "KAP").limit(5)
        res = await session.execute(stmt)
        items = res.scalars().all()
        for i in items:
            print(f"ID: {i.id} | Title: {i.title[:50]} | Symbols: {i.symbols_mentioned}")
            
    print("\n--- DB THYAO.IS SPECIFIC ---")
    async with AsyncSessionLocal() as session:
        stmt = select(NewsItem).where(NewsItem.symbols_mentioned.contains(['THYAO.IS']))
        res = await session.execute(stmt)
        items = res.scalars().all()
        print(f"THYAO.IS items found: {len(items)}")

if __name__ == "__main__":
    asyncio.run(main())
