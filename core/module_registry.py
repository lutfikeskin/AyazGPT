import importlib
import pkgutil
from typing import Dict, List
from core.base_module import BaseModule
from loguru import logger

class ModuleRegistry:
    """Discovers and registers MyMind modules."""
    
    def __init__(self) -> None:
        self._modules: Dict[str, BaseModule] = {}
        
    def register(self, module: BaseModule) -> None:
        if module.name in self._modules:
            logger.warning(f"Module {module.name} already registered. Overwriting.")
        self._modules[module.name] = module
        logger.info(f"Registered module: {module.name} (v{module.version})")
        
    def get_module(self, name: str) -> BaseModule:
        return self._modules[name]
        
    def get_all_modules(self) -> List[BaseModule]:
        return list(self._modules.values())
        
registry = ModuleRegistry()

def discover_modules() -> None:
    """Auto-discover and load modules in the `modules` directory."""
    try:
        import modules
    except ImportError:
        logger.warning("No modules directory found.")
        return
        
    for _, name, ispkg in pkgutil.iter_modules(modules.__path__):
        if ispkg:
            try:
                mod = importlib.import_module(f"modules.{name}.module")
                module_instance = getattr(mod, "get_module")()
                registry.register(module_instance)
            except Exception as e:
                logger.error(f"Failed to load module {name}: {e}")

async def startup_modules() -> None:
    """Run startup hooks for all registered modules."""
    for mod in registry.get_all_modules():
        logger.info(f"Starting module: {mod.name}...")
        try:
            await mod.on_startup()
        except Exception as e:
            logger.error(f"Error starting module {mod.name}: {e}")

async def shutdown_modules() -> None:
    """Run shutdown hooks for all registered modules."""
    for mod in registry.get_all_modules():
        logger.info(f"Shutting down module: {mod.name}...")
        try:
            await mod.on_shutdown()
        except Exception as e:
            logger.error(f"Error shutting down module {mod.name}: {e}")
