import json
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any
from pydantic import BaseModel

from core.cache import cache
from modules.investment.ai.insight_engine import InsightEngine
from modules.investment.ai.recommendation_engine import RecommendationEngine
from modules.investment.ai.market_regime import MarketRegimeDetector
from modules.investment.ai.schemas import (
    SymbolReport, PatternAnalysis, WeeklyDigest, ComparisonReport,
    BlindSpot, ReportSummary, HistoricalQAResponse,
    InvestmentRecommendation, MarketRegime, UniverseScan
)
from modules.investment.models import NewsItem
from core.database import AsyncSessionLocal as async_session
from sqlalchemy import select, desc
from datetime import datetime, timedelta

router = APIRouter(tags=["investment"])
insight_engine = InsightEngine()
recommend_engine = RecommendationEngine()
regime_detector = MarketRegimeDetector()

class AskRequest(BaseModel):
    question: str
    symbol: str
    lang: str = "tr"

@router.get("/health")
async def health_check():
    return {"status": "ok", "module": "investment"}

@router.get("/symbols", response_model=List[str])
async def get_symbols():
    data = await cache.get("watchlist_symbols")
    if data:
        return json.loads(data)
    return ["AAPL", "THYAO.IS"]

@router.post("/symbols")
async def add_symbol(payload: dict = Body(...)):
    symbol = payload.get("symbol")
    if not symbol:
        raise HTTPException(status_code=400, detail="Missing symbol")
    current = await get_symbols()
    if symbol not in current:
        current.append(symbol)
        await cache.set("watchlist_symbols", json.dumps(current))
    return {"status": "success", "symbols": current}

@router.get("/analyze/{symbol}", response_model=SymbolReport)
async def analyze_symbol(symbol: str, timeframe: str = "1M", lang: str = "tr"):
    try:
        report = await insight_engine.analyze(symbol, timeframe, lang=lang)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/digest/weekly", response_model=WeeklyDigest)
async def get_weekly_digest(lang: str = "tr"):
    symbols = await get_symbols()
    try:
        digest = await insight_engine.weekly_digest(symbols, lang=lang)
        return digest
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask")
async def ask_question(req: AskRequest):
    try:
        # fetch context first
        ctx = await insight_engine.context_builder.build(req.symbol, "1M")
        if not ctx:
            raise HTTPException(status_code=404, detail="Context not found")
        ans = await insight_engine.llm.answer_question(req.question, ctx, lang=req.lang)
        return {"answer": ans}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask-with-history", response_model=HistoricalQAResponse)
async def ask_with_history(symbol: str, question: str, lang: str = "tr"):
    try:
        return await insight_engine.answer_with_history(symbol, question, lang)
    except Exception as e:
        # Assuming 'logger' is defined elsewhere or needs to be imported
        # from core.logger import logger
        # logger.error(f"Error answering with history for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommend/{symbol}", response_model=InvestmentRecommendation)
async def get_recommendation(symbol: str):
    try:
        return await recommend_engine.get_single_recommendation(symbol)
    except Exception as e:
        # Assuming 'logger' is defined elsewhere or needs to be imported
        # from core.logger import logger
        # logger.error(f"Error getting recommendation for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/regime", response_model=MarketRegime)
async def get_market_regime():
    try:
        return await regime_detector.get_current_regime()
    except Exception as e:
        # Assuming 'logger' is defined elsewhere or needs to be imported
        # from core.logger import logger
        # logger.error(f"Error getting market regime: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scan", response_model=UniverseScan)
async def run_universe_scan(watchlist: List[str]):
    try:
        return await recommend_engine.scan_universe(watchlist)
    except Exception as e:
        # Assuming 'logger' is defined elsewhere or needs to be imported
        # from core.logger import logger
        # logger.error(f"Error running universe scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scan/latest", response_model=UniverseScan)
async def get_latest_scan():
    from core.cache import cache
    try:
        cached = await cache.get("market_recommendation:latest")
        if not cached:
            raise HTTPException(status_code=404, detail="No scan run yet.")
        return UniverseScan.model_validate_json(cached)
    except HTTPException:
        raise
    except Exception as e:
        # Assuming 'logger' is defined elsewhere or needs to be imported
        # from core.logger import logger
        # logger.error(f"Error getting latest scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{symbol}", response_model=List[ReportSummary])
async def get_reports(symbol: str, limit: int = 10, report_type: str | None = None):
    try:
        return await insight_engine.report_store.get_recent_reports(symbol, limit, report_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{symbol}/{report_id}")
async def get_report_content(symbol: str, report_id: str):
    try:
        content = await insight_engine.report_store.get_report_by_id(report_id)
        if not content:
            raise HTTPException(status_code=404, detail="Report not found")
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/search/query")
async def search_reports(query: str = Query(...), symbols: str | None = None, n: int = 5):
    try:
        sym_list = [s.strip() for s in symbols.split(",")] if symbols else None
        return await insight_engine.report_store.search_relevant_reports(query, sym_list, n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/patterns/{symbol}", response_model=PatternAnalysis)
async def get_patterns(symbol: str, watchlist: str = "", lang: str = "tr"):
    watchlist_list = [s.strip() for s in watchlist.split(",") if s.strip()]
    if not watchlist_list:
        watchlist_list = await get_symbols()
        
    try:
        patterns = await insight_engine.get_pattern_analysis(symbol, watchlist_list, lang=lang)
        return patterns
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/blind-spots/{symbol}", response_model=List[BlindSpot])
async def get_blind_spots(symbol: str, watchlist: str = "", lang: str = "tr"):
    watchlist_list = [s.strip() for s in watchlist.split(",") if s.strip()]
    if not watchlist_list:
        watchlist_list = await get_symbols()
        
    try:
        blind_spots = await insight_engine.get_blind_spots(symbol, watchlist_list, lang=lang)
        return blind_spots
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compare", response_model=ComparisonReport)
async def compare_symbols(symbols: str, lang: str = "tr"):
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if len(sym_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 symbols separated by comma")
    try:
        report = await insight_engine.compare(sym_list, lang=lang)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/macro/snapshot")
async def macro_snapshot():
    return {
        "FEDFUNDS": 5.25,
        "CPI": 3.1,
        "USDTRY": 32.50
    }

@router.get("/prices/{symbol}")
async def get_prices(symbol: str, timeframe: str = "1Y"):
    from modules.investment.analysis.technical import TechnicalAnalyzer
    ta = TechnicalAnalyzer()
    df = await ta.get_price_data(symbol, timeframe)
    if df.empty:
        return {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
    
    return {
        "dates": [d.isoformat() for d in df.index],
        "open": df['open'].fillna(0).tolist(),
        "high": df['high'].fillna(0).tolist(),
        "low": df['low'].fillna(0).tolist(),
        "close": df['close'].fillna(0).tolist(),
        "volume": df['volume'].fillna(0).tolist()
    }

@router.get("/disclosures/recent")
async def get_recent_disclosures(hours: int = 24, high_priority_only: bool = False):
    """Fetch recent disclosures from the database."""
    cutoff = datetime.now() - timedelta(hours=hours)
    async with async_session() as session:
        stmt = select(NewsItem).where(
            NewsItem.source == "KAP",
            NewsItem.published_at >= cutoff
        ).order_by(desc(NewsItem.published_at))
        
        # Note: high_priority filter would need the 'metadata' column which we found is missing
        # For now, we return all recent KAP news
        res = await session.execute(stmt)
        return res.scalars().all()

@router.get("/disclosures/{symbol}")
async def get_symbol_disclosures(symbol: str, limit: int = 10):
    """Fetch recent disclosures for a specific symbol."""
    async with async_session() as session:
        # Search in JSONB array
        # In PostgreSQL: symbols_mentioned @> '["TUPRS.IS"]'
        stmt = select(NewsItem).where(
            NewsItem.source == "KAP",
            NewsItem.symbols_mentioned.contains([symbol])
        ).order_by(desc(NewsItem.published_at)).limit(limit)
        
        res = await session.execute(stmt)
        return res.scalars().all()
