import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import AsyncSessionLocal

async def verify():
    query = """
    SELECT symbol, COUNT(*) as records, MIN(timestamp), MAX(timestamp)
    FROM market_prices
    GROUP BY symbol
    ORDER BY COUNT(*) DESC
    LIMIT 10;
    """
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(query))
        rows = result.fetchall()
        
        print("\n=== TOP 10 SEEDED SYMBOLS ===")
        print(f"{'SYMBOL':<15} | {'RECORDS':<10} | {'MIN_DATE':<22} | {'MAX_DATE'}")
        print("-" * 75)
        for row in rows:
            symbol, count, min_dt, max_dt = row
            min_str = min_dt.strftime('%Y-%m-%d %H:%M:%S') if min_dt else 'N/A'
            max_str = max_dt.strftime('%Y-%m-%d %H:%M:%S') if max_dt else 'N/A'
            print(f"{symbol:<15} | {count:<10} | {min_str:<22} | {max_str}")
        print("=============================\n")

if __name__ == "__main__":
    asyncio.run(verify())
