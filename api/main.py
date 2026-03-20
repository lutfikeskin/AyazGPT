from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

from core.logger import logger
from core.database import engine
from core.module_registry import discover_modules, startup_modules, shutdown_modules, registry
from typing import Any, AsyncGenerator

# Discover modules before creating the app so we can mount routers safely
discover_modules()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting MyMind backend...")
    
    await startup_modules()
    
    yield
    
    logger.info("Shutting down MyMind backend...")
    await shutdown_modules()
    await engine.dispose()
    logger.info("Database engine disposed.")

app = FastAPI(
    title="MyMind - Modular Personal AI Assistant",
    description="Backend API for MyMind.",
    version="0.1.0",
    lifespan=lifespan
)

# Mount module routers dynamically
for mod in registry.get_all_modules():
    app.include_router(mod.router, prefix=f"/api/{mod.name}")
    logger.info(f"Mounted router for module: {mod.name} at /api/{mod.name}")

@app.get("/health")
async def health_check() -> dict[str, str | bool | int | list[dict[str, Any]]]:
    """
    Comprehensive health check.
    Checks Redis, Database, and all registered Modules.
    """
    from core.cache import cache
    from sqlalchemy import text
    from core.database import AsyncSessionLocal
    
    # 1. Check Redis (Cache)
    redis_alive = await cache.ping()
    
    # 2. Check Database
    db_alive = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_alive = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        
    # 3. Check Modules
    module_statuses = []
    for mod in registry.get_all_modules():
        try:
            status = await mod.health_check()
            module_statuses.append(status)
        except Exception as e:
            logger.error(f"Module {mod.name} health check failed: {e}")
            module_statuses.append({"module": mod.name, "status": "error", "error": str(e)})

    return {
        "status": "ok" if (redis_alive and db_alive) else "degraded",
        "database_connected": db_alive,
        "cache_connected": redis_alive,
        "modules_loaded": len(registry.get_all_modules()),
        "module_details": module_statuses
    }
