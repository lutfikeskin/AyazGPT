import json
import asyncio
from loguru import logger
from typing import Optional

from core.cache import cache
from modules.investment.analysis.schemas import AnalysisResult
from modules.investment.analysis.technical import TechnicalAnalyzer
from modules.investment.analysis.fundamental import FundamentalAnalyzer
from modules.investment.analysis.sentiment import SentimentAnalyzer
from modules.investment.analysis.risk import RiskAnalyzer

class AnalysisAggregator:
    def __init__(self):
        self.technical = TechnicalAnalyzer()
        self.fundamental = FundamentalAnalyzer()
        self.sentiment = SentimentAnalyzer()
        self.risk = RiskAnalyzer()

    async def get_analysis(self, symbol: str, timeframe: str) -> Optional[AnalysisResult]:
        redis = cache
        cache_key = f"analysis:{symbol}:{timeframe}"
        
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.info(f"Returning cached analysis for {symbol} {timeframe}")
                return AnalysisResult.model_validate_json(cached)
        except Exception as e:
            logger.warning(f"Failed to read from cache (redis unavailable?): {e}")

        logger.info(f"Computing full analysis for {symbol} {timeframe}")
        
        tech_task = asyncio.create_task(self.technical.analyze(symbol, timeframe))
        fund_task = asyncio.create_task(self.fundamental.analyze(symbol))
        sent_task = asyncio.create_task(self.sentiment.get_aggregated_sentiment(symbol, timeframe))
        risk_task = asyncio.create_task(self.risk.analyze(symbol, timeframe))
        
        tech_res, fund_res, sent_res, risk_res = await asyncio.gather(
            tech_task, fund_task, sent_task, risk_task
        )
        
        result = AnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            technical=tech_res,
            fundamental=fund_res,
            sentiment=sent_res,
            risk=risk_res
        )
        
        try:
            # 1 hour TTL
            await redis.set(cache_key, result.model_dump_json(), ttl=3600)
        except Exception as e:
            logger.warning(f"Failed to write to cache: {e}")
            
        return result
