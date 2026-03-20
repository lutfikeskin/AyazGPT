import sys
from loguru import logger
from .config import settings

# Configure loguru logger based on environment
logger.remove()
if settings.environment == "dev":
    logger.add(sys.stderr, level="DEBUG")
else:
    logger.add(sys.stderr, level="INFO", serialize=True)

logger.info("Logger initialized.")
