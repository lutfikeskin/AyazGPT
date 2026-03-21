from loguru import logger
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, desc
from core.database import AsyncSessionLocal
from modules.investment.models import MacroIndicator, MarketPrice
from modules.investment.analysis.aggregator import AnalysisAggregator
from modules.investment.ai.embeddings import EmbeddingService
from modules.investment.ai.schemas import ContextPackage, SourceRef

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
        
        available_sources = []
        
        # News Sources
        for news in relevant_news:
            available_sources.append(SourceRef(
                id=news['id'],
                type="news",
                label=news['title'],
                date=datetime.fromisoformat(news['published_at'].replace("Z", "+00:00")) if isinstance(news['published_at'], str) else news['published_at']
            ))

        # 3. Macro snapshot from DB
        macro_indicators = {}
        target_macros = ["TCMB_USDTRY", "TCMB_POLICY_RATE", "FRED_FEDFUNDS", "FRED_CPIAUCSL"]
        
        async with AsyncSessionLocal() as session:
            for m_code in target_macros:
                stmt = select(MacroIndicator).where(MacroIndicator.indicator == m_code).order_by(desc(MacroIndicator.timestamp)).limit(1)
                res = await session.execute(stmt)
                m_obj = res.scalar_one_or_none()
                if m_obj:
                    macro_indicators[m_code.replace("TCMB_", "").replace("FRED_", "")] = m_obj.value
                    available_sources.append(SourceRef(
                        id=f"macro_{m_code}",
                        type="macro",
                        label=f"{m_code} Indicator",
                        date=m_obj.timestamp
                    ))
        
        # 4. Price Data Provenance
        if analysis_res.technical.indicators:
            # We use the analysis_res directly as it contains technical data derived from prices
            async with AsyncSessionLocal() as session:
                p_stmt = select(MarketPrice.timestamp).where(MarketPrice.symbol == symbol).order_by(desc(MarketPrice.timestamp)).limit(1)
                p_res = await session.execute(p_stmt)
                latest_ts = p_res.scalar()
                if latest_ts:
                    available_sources.append(SourceRef(
                        id=f"price_{symbol}_latest",
                        type="price",
                        label=f"Latest Price Data for {symbol}",
                        date=latest_ts
                    ))

        # 5. Peer comparison
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
            peers_comparison=peers_comparison,
            available_sources=available_sources
        )
        
        return pkg
