import redis.asyncio as redis
from core.config import settings
from loguru import logger

class CacheClient:
    """Redis client wrapper for MyMind."""
    
    def __init__(self, url: str):
        self._client = redis.from_url(url, decode_responses=True)
        
    async def get(self, key: str) -> str | None:
        return await self._client.get(key)
        
    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self._client.set(key, value, ex=ttl)
        
    async def delete(self, key: str) -> None:
        await self._client.delete(key)
        
    async def ping(self) -> bool:
        """Check if the Redis connection is alive."""
        try:
            # Cast to Awaitable to satisfy mypy's expectation of await
            from typing import cast, Awaitable
            res = await cast(Awaitable[bool], self._client.ping())
            return bool(res)
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

cache = CacheClient(settings.redis_url)
