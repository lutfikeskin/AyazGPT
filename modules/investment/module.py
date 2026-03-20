from fastapi import APIRouter
from typing import Any, Dict
from core.base_module import BaseModule
from .routes import router

class InvestmentModule(BaseModule):
    @property
    def name(self) -> str:
        return "investment"
        
    @property
    def description(self) -> str:
        return "Personal Investment Advisor module for tracking and analyzing general markets."
        
    @property
    def version(self) -> str:
        return "0.1.0"
        
    @property
    def router(self) -> APIRouter:
        return router
        
    async def on_startup(self) -> None:
        from core.database import engine
        from modules.investment.models import Base, setup_hypertables
        from modules.investment.scheduler import setup_scheduler
        
        # Scaffold initialization (eventually replaced entirely by Alembic)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        await setup_hypertables()
        setup_scheduler()
        
    async def on_shutdown(self) -> None:
        from modules.investment.scheduler import shutdown_scheduler
        shutdown_scheduler()
        
    async def health_check(self) -> Dict[str, Any]:
        return {"status": "ok", "module": self.name}
        
    async def get_dashboard_summary(self) -> Dict[str, Any]:
        return {
            "title": "Investment Overview",
            "metrics": {"tracked_assets": 0}
        }

def get_module() -> BaseModule:
    return InvestmentModule()
