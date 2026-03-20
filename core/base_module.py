from abc import ABC, abstractmethod
from fastapi import APIRouter
from typing import Any, Dict

class BaseModule(ABC):
    """
    Abstract base class for all MyMind modules.
    Every module must implement this interface.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the module."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A short description of the module's purpose."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Module version string."""
        pass
        
    @property
    @abstractmethod
    def router(self) -> APIRouter:
        """FastAPI APIRouter for the module endpoints."""
        pass
        
    @abstractmethod
    async def on_startup(self) -> None:
        """Lifecycle hook called when application starts."""
        pass
        
    @abstractmethod
    async def on_shutdown(self) -> None:
        """Lifecycle hook called when application shuts down."""
        pass
        
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check module dependencies and status."""
        pass
        
    @abstractmethod
    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """Return a summary intended for the UI dashboard."""
        pass
