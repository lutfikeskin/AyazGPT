import asyncio
import redis
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings

async def check_db():
    try:
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        print("DB: Connected")
    except Exception as e:
        print(f"DB: Failed - {e}")

def check_redis():
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        print("Redis: Connected")
    except Exception as e:
        print(f"Redis: Failed - {e}")

if __name__ == "__main__":
    check_redis()
    asyncio.run(check_db())
