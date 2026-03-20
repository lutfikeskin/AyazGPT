from loguru import logger
from typing import Optional

from modules.investment.analysis.aggregator import AnalysisAggregator
from modules.investment.ai.embeddings import EmbeddingService
from modules.investment.ai.schemas import ContextPackage

class ContextBuilder:
    def __init__(self):
        self.aggregator = AnalysisAggregator()
        self.embeddings = EmbeddingService()
        
    async def build(self, symbol: str, timeframe: str) -> Optional[ContextPackage]:
        logger.info(f"Building context package for {symbol} ({timeframe})")
        
        # 1. Get full analysis payload (prices, basic TA, Fundamentals, Sentiment, Risk)
        analysis_res = await self.aggregator.get_analysis(symbol, timeframe)
        if not analysis_res:
            logger.warning(f"Could not retrieve analysis for {symbol}")
            return None
            
        # 2. Semantic search for highest relevance news
        query = f"Key financial performance catalysts and major risks for {symbol}"
        relevant_news = self.embeddings.search_relevant_context(
            query=query, 
            symbols=[symbol], 
            n=10
        )
        
        # 3. Macro snapshot
        # For a full system, fetch this from DB (MacroIndicator) 
        # using a MacroCollector/Aggregator. Mocked for structural integrity for now.
        macro_indicators = {
            "FEDFUNDS": 5.25,
            "CPI": 3.1,
            "USDTRY": 32.50
        }
        
        # 4. Peer comparison
        # Dummy peers payload (to be integrated with actual DB metrics later)
        peers_comparison = [
            {"symbol": "PEER1", "pe_ratio": 15.0, "return_1y": 0.12},
            {"symbol": "PEER2", "pe_ratio": 18.2, "return_1y": -0.05}
        ]
        
        pkg = ContextPackage(
            symbol=symbol,
            timeframe=timeframe,
            analysis=analysis_res,
            relevant_news=relevant_news,
            macro_indicators=macro_indicators,
            peers_comparison=peers_comparison
        )
        
        return pkg
