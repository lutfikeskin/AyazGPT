import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Literal, Optional
from loguru import logger
import json

from core.database import AsyncSessionLocal
from core.cache import cache
from core.config import settings
from modules.investment.ai.schemas import (
    MarketRegime, ReturnEstimates, InvestmentRecommendation, 
    AvoidSignal, UniverseScan, BlindSpot
)
from modules.investment.ai.market_regime import MarketRegimeDetector
from modules.investment.ai.pattern_engine import HistoricalPatternMiner
from modules.investment.ai.blind_spot_detector import BlindSpotDetector
from modules.investment.analysis.aggregator import AnalysisAggregator
from modules.investment.ai.report_store import ReportStore
from modules.investment.ai.evidence_graph import EvidenceGraphBuilder
from modules.investment.ai.prompts import RECOMMENDATION_PROMPT
from google import genai
from google.genai import types

class RecommendationEngine:
    BIST100_LIST = [
        "AEFES.IS", "AGESA.IS", "AKBNK.IS", "AKCNS.IS", "AKSA.IS", "AKSEN.IS", "ALARK.IS", "ALBRK.IS",
        "ALFAS.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "ASUZU.IS", "AYDEM.IS", "BAGFS.IS", "BERA.IS",
        "BIMAS.IS", "BRMEN.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CEMTS.IS",
        "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "EGEEN.IS", "EKGYO.IS", "ENJSA.IS", "ENKAI.IS",
        "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GUBRF.IS", "HALKB.IS", "HEKTS.IS",
        "IPEKE.IS", "ISCTR.IS", "ISDMR.IS", "ISGYO.IS", "ISMEN.IS", "IZMDC.IS", "KARDM.IS", "KCHOL.IS",
        "KONTR.IS", "KORDS.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS",
        "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PENTA.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", "SAHOL.IS",
        "SASA.IS", "SISE.IS", "SKBNK.IS", "SMRTG.IS", "SNGYO.IS", "SOKM.IS", "TARKM.IS", "TAVHL.IS",
        "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TMSN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TUPRS.IS",
        "TURSG.IS", "VAKBN.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "ZOREN.IS"
    ]
    GLOBAL_LIST = [
        "SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "NVDA", "META", "AMZN", "TSLA",
        "JPM", "GS", "GC=F", "SI=F", "CL=F", "BTC-USD"
    ]

    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.pattern_miner = HistoricalPatternMiner()
        self.blind_spot_detector = BlindSpotDetector()
        self.aggregator = AnalysisAggregator()
        self.report_store = ReportStore()
        self.genai_client = genai.Client(api_key=settings.gemini_api_key)
        self.model_id = getattr(settings, "gemini_model_pro", "gemini-3.1-pro-preview")
        self._semaphore = asyncio.Semaphore(3)

    async def _calculate_return_estimates(
        self, 
        symbol: str, 
        similar_setups: Any, # SimilarSetupResult
        regime: MarketRegime
    ) -> ReturnEstimates:
        """Deterministic return calculation based on historical data."""
        source = "historical_patterns"
        confidence: Literal["high", "medium", "low"] = "medium"
        
        ret_1m = getattr(similar_setups, "median_1m_return", 0.0)
        ret_3m = getattr(similar_setups, "median_3m_return", 0.0)
        
        # Fallback if low confidence
        if not similar_setups or getattr(similar_setups, "confidence", "low") == "low":
            source = "market_averages_fallback"
            confidence = "low"
            if symbol.endswith(".IS"):
                ret_1m, ret_3m = 1.5, 4.0
            elif symbol in ["GC=F", "SI=F"]:
                ret_1m, ret_3m = 0.5, 1.5
            else:
                ret_1m, ret_3m = 0.8, 2.5
        
        # Extrapolate 1Y
        ret_1y = min(100.0, max(-100.0, ret_3m * 4))
        
        # Regime Adjustment
        regime_adjusted = False
        if regime.regime == "risk_off":
            ret_1m *= 0.6; ret_3m *= 0.6; ret_1y *= 0.6
            regime_adjusted = True
        elif regime.regime == "fx_pressure" and symbol.endswith(".IS"):
            ret_1m *= 0.7; ret_3m *= 0.7; ret_1y *= 0.7
            regime_adjusted = True
        elif regime.regime == "risk_on":
            ret_1m *= 1.1; ret_3m *= 1.1; ret_1y *= 1.1
            regime_adjusted = True
            
        return ReturnEstimates(
            return_1m=round(ret_1m, 2),
            return_3m=round(ret_3m, 2),
            return_1y=round(ret_1y, 2),
            data_source=source,
            regime_adjusted=regime_adjusted,
            confidence=confidence
        )

    async def _quick_score(self, symbol: str, regime: MarketRegime) -> float:
        """Fast quantitative scoring 0-100. No LLM."""
        score = 50.0
        try:
            analysis = await self.aggregator.get_analysis(symbol, "1M")
            if not analysis: return 0.0
            
            # Technical indicators
            rsi = analysis.technical.indicators.get("RSI", 50)
            if rsi < 40: score += 20
            if rsi > 70: score -= 20
            
            # Fundamental
            dcf = analysis.fundamental.dcf_fair_value
            price = analysis.fundamental.metrics.get("current_price", 0)
            if dcf and price > 0:
                if dcf > price * 1.15: score += 25
                if dcf < price * 0.85: score -= 25
                
            # Sentiment
            sent = analysis.sentiment.avg_sentiment if analysis.sentiment else 0
            if sent > 0.3: score += 15
            if sent < -0.3: score -= 15
            
            # Regime and Sector specific
            if regime.regime == "risk_off": score -= 15
            if regime.regime == "fx_pressure" and symbol.endswith(".IS"): score -= 10
            if regime.regime == "risk_on": score += 10
            
        except Exception as e:
            logger.warning(f"Error quick-scoring {symbol}: {e}")
            return 0.0
            
        return max(0, min(100, score))

    async def get_single_recommendation(self, symbol: str, regime: Optional[MarketRegime] = None) -> InvestmentRecommendation:
        if not regime:
            regime = await self.regime_detector.get_current_regime()
            
        async with self._semaphore:
            logger.info(f"Producing deep recommendation for {symbol}")
            
            # 1. Gather all quantitative data
            analysis = await self.aggregator.get_analysis(symbol, "1M")
            patterns = await self.pattern_miner.scan_similar_setups(symbol, analysis.technical.indicators if analysis else {}, regime)
            blind_spots = await self.blind_spot_detector.run_all_checks(symbol, analysis, []) if analysis else []
            
            # 2. Deterministic return estimates
            returns = await self._calculate_return_estimates(symbol, patterns, regime)
            
            # 3. LLM Synthesis
            try:
                prompt = RECOMMENDATION_PROMPT.format(
                    symbol=symbol,
                    regime=regime.regime,
                    regime_narrative=regime.narrative,
                    full_analysis=analysis.model_dump_json() if analysis else "{}",
                    pattern_analysis=patterns.model_dump_json() if patterns else "{}",
                    return_1m=returns.return_1m,
                    return_3m=returns.return_3m,
                    return_1y=returns.return_1y,
                    return_data_source=returns.data_source,
                    blind_spots=json.dumps([bs.model_dump() for bs in blind_spots])
                )
                
                response = self.genai_client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                    )
                )
                
                llm_data = json.loads(response.text or "{}")
                rec_label = llm_data.get("recommendation", "hold")
                
                # Build Evidence Graph
                evidence_builder = EvidenceGraphBuilder()
                evidence_graph = evidence_builder.build(
                    symbol=symbol,
                    analysis=analysis,
                    patterns=patterns,
                    regime=regime,
                    blind_spots=blind_spots,
                    recommendation_label=rec_label
                )
                
                recommendation = InvestmentRecommendation(
                    symbol=symbol,
                    current_price=analysis.fundamental.metrics.get("current_price", 0) if analysis else 0,
                    recommendation=rec_label,
                    confidence=llm_data.get("confidence", 5),
                    returns=returns,
                    primary_thesis=llm_data.get("primary_thesis", "No thesis provided."),
                    key_catalysts=llm_data.get("key_catalysts", []),
                    supporting_data=llm_data.get("supporting_data", []),
                    counter_thesis=llm_data.get("counter_thesis", "Analysis might be biased or based on incomplete historical context."),
                    key_risks=llm_data.get("key_risks", []),
                    invalidation_triggers=llm_data.get("invalidation_triggers", ["Price drops below key support", "Yield curve steepens unexpectedly"]),
                    blind_spots_flagged=blind_spots,
                    data_as_of=datetime.now(timezone.utc),
                    analysis_quality="high" if analysis else "low",
                    market_regime=regime,
                    pattern_support=llm_data.get("pattern_support", "Based on historical setups."),
                    macro_alignment=llm_data.get("macro_alignment", "Neutral alignment."),
                    evidence_graph=evidence_graph
                )
                
                # Auto-save
                report_id = await self.report_store.save_report(
                    symbol=symbol,
                    timeframe="1M",
                    report_type="investment_recommendation",
                    content=recommendation.model_dump(mode='json'),
                    llm_summary=recommendation.primary_thesis,
                    conviction_level=recommendation.confidence,
                    data_as_of=datetime.now(timezone.utc)
                )
                                
                return recommendation
                
            except Exception as e:
                logger.error(f"Failed to generate synthesis for {symbol}: {e}")
                # Return basic fallback instead of failing
                return InvestmentRecommendation(
                    symbol=symbol, current_price=0, recommendation="hold", confidence=1,
                    returns=returns, primary_thesis="Error in analysis.", key_catalysts=[], supporting_data=[],
                    counter_thesis="System failure during synthesis. No reliable data available.", 
                    key_risks=[], invalidation_triggers=["System fix required", "Manual review needed"],
                    market_regime=regime, pattern_support="", macro_alignment="", blind_spots_flagged=[],
                    data_as_of=datetime.now(timezone.utc), analysis_quality="low"
                )

    async def scan_universe(self, watchlist: List[str]) -> UniverseScan:
        start_time = datetime.now(timezone.utc)
        regime = await self.regime_detector.get_current_regime()
        
        full_universe = list(set(self.BIST100_LIST + self.GLOBAL_LIST + watchlist))
        logger.info(f"Starting universe scan for {len(full_universe)} symbols")
        
        # PASS 1: Quick Score
        scores: List[Dict[str, Any]] = []
        for symbol in full_universe:
            score = await self._quick_score(symbol, regime)
            scores.append({"symbol": symbol, "score": score})
            
        scores.sort(key=lambda x: float(x["score"]), reverse=True)
        
        top_10_candidates = [str(s["symbol"]) for s in scores[:10]]
        bottom_3 = [AvoidSignal(symbol=str(s["symbol"]), quick_score=float(s["score"]), main_reason="Poor quantitative metrics in current regime.") 
                   for s in scores[-3:]]
        
        symbols_to_deep_analyze = list(set(top_10_candidates + watchlist))
        
        # PASS 2: Deep Analysis
        tasks = [self.get_single_recommendation(str(s), regime) for s in symbols_to_deep_analyze]
        results = await asyncio.gather(*tasks)
        
        top_opps = [r for r in results if r.symbol in top_10_candidates]
        watchlist_recs = [r for r in results if r.symbol in watchlist]
        
        scan_result = UniverseScan(
            market_regime=regime,
            top_opportunities=top_opps,
            watchlist_recommendations=watchlist_recs,
            symbols_to_avoid=bottom_3,
            scan_timestamp=datetime.now(timezone.utc),
            universe_size=len(full_universe),
            symbols_scanned=len(full_universe),
            scan_duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds()
        )
        
        # Cache Scan result
        await cache.set("market_recommendation:latest", scan_result.model_dump_json(), ttl=6*3600)
        
        return scan_result
