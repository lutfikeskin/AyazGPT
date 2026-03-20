import json
import asyncio
import uuid
from loguru import logger
from typing import List

from core.database import AsyncSessionLocal
from modules.investment.ai.schemas import SymbolReport, PatternAnalysis, WeeklyDigest, ComparisonReport, BlindSpot, HistoricalQAResponse, ReportSummary
from modules.investment.ai.context_builder import ContextBuilder
from modules.investment.ai.llm_client import LLMClient
from modules.investment.ai.pattern_engine import HistoricalPatternMiner
from modules.investment.ai.blind_spot_detector import BlindSpotDetector
from modules.investment.ai.report_store import ReportStore
from datetime import datetime

class InsightEngine:
    def __init__(self):
        self.context_builder = ContextBuilder()
        self.llm = LLMClient()
        self.pattern_miner = HistoricalPatternMiner()
        self.blind_spot_detector = BlindSpotDetector()
        self.report_store = ReportStore()
        
    async def analyze(self, symbol: str, timeframe: str, lang: str = "tr") -> SymbolReport:
        logger.info(f"InsightEngine analyzing {symbol} {timeframe} (lang={lang})")
        context = await self.context_builder.build(symbol, timeframe)
        if not context:
            raise ValueError(f"Could not build context package for {symbol}")
            
        report = await self.llm.analyze_symbol(symbol, timeframe, context, lang=lang)
        
        # Auto-save & Embed
        try:
            report_id = await self.report_store.save_report(
                symbol=symbol,
                timeframe=timeframe,
                report_type="symbol_analysis",
                content=json.loads(report.model_dump_json()),
                llm_summary=report.executive_summary,
                conviction_level=report.conviction_level,
                data_as_of=datetime.fromisoformat(report.data_as_of.replace("Z", "+00:00")) if report.data_as_of else datetime.now()
            )
            await self.report_store.embed_and_index(
                report_id=report_id,
                text=f"{report.executive_summary} Catalysts: {', '.join(report.key_catalysts)}. Risks: {', '.join(report.risks)}",
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "report_type": "symbol_analysis",
                    "created_at": datetime.now().isoformat(),
                    "conviction_level": report.conviction_level
                }
            )
        except Exception as e:
            logger.error(f"Failed to auto-save report: {e}")
            
        return report

    async def get_pattern_analysis(self, symbol: str, watchlist: List[str], lang: str = "tr") -> PatternAnalysis:
        """
        Runs historical mining, blind spot detection, and synthesizes results via LLM.
        """
        logger.info(f"InsightEngine generating pattern analysis for {symbol}")
        
        # 1. Gather all quantitative data
        context = await self.context_builder.build(symbol, "1M")
        if not context:
            raise ValueError(f"Context build failed for {symbol}")

        indicators = {
            "rsi": context.analysis.technical.indicators.get("RSI", 50),
            "trend": context.analysis.technical.trend,
            "volume_avg_20": context.analysis.technical.indicators.get("Volume_SMA", 0),
        }
        
        # Run miners concurrently
        similar_setups_task = self.pattern_miner.scan_similar_setups(symbol, indicators)
        macro_triggers_task = self.pattern_miner.detect_macro_triggers(symbol, "1Y")
        sector_div_task = self.pattern_miner.find_sector_divergence(symbol)
        blind_spots_task = self.blind_spot_detector.run_all_checks(symbol, context.analysis, watchlist)
        
        similar_setups, macro_triggers, sector_div, blind_spots = await asyncio.gather(
            similar_setups_task, macro_triggers_task, sector_div_task, blind_spots_task
        )
        
        # 2. Get LLM Synthesis
        synthesis = await self.llm.synthesize_patterns(
            symbol=symbol,
            similar_setups=similar_setups,
            macro_triggers=macro_triggers,
            sector_divergence=sector_div,
            blind_spots=blind_spots,
            lang=lang
        )
        
        pattern_report = PatternAnalysis(
            similar_setups=similar_setups,
            macro_triggers=macro_triggers,
            sector_divergence=sector_div,
            blind_spots=blind_spots,
            llm_synthesis=synthesis
        )
        
        # Auto-save & Embed
        try:
            report_id = await self.report_store.save_report(
                symbol=symbol,
                timeframe="1M",
                report_type="pattern_analysis",
                content=json.loads(pattern_report.model_dump_json()),
                llm_summary=synthesis[:500],
                conviction_level=5,
                data_as_of=datetime.now()
            )
            await self.report_store.embed_and_index(
                report_id=report_id,
                text=synthesis,
                metadata={
                    "symbol": symbol,
                    "timeframe": "1M",
                    "report_type": "pattern_analysis",
                    "created_at": datetime.now().isoformat(),
                    "conviction_level": 5
                }
            )
        except Exception as e:
            logger.error(f"Failed to auto-save pattern report: {e}")
            
        return pattern_report

    async def get_blind_spots(self, symbol: str, watchlist: List[str], lang: str = "tr") -> List[BlindSpot]:
        """Convenience method - returns detailed blind spot models."""
        logger.info(f"InsightEngine fetching blind spots for {symbol}")
        context = await self.context_builder.build(symbol, "1M")
        if not context: return []
        
        return await self.blind_spot_detector.run_all_checks(symbol, context.analysis, watchlist)

    async def compare(self, symbols: List[str], lang: str = "tr") -> ComparisonReport:
        logger.info(f"InsightEngine comparing symbols: {symbols} (lang={lang})")
        contexts = {}
        for sym in symbols:
            ctx = await self.context_builder.build(sym, "1Y")
            if ctx:
                contexts[sym] = json.loads(ctx.model_dump_json())
                
        context_str = json.dumps(contexts)
        return await self.llm.compare_symbols(context_str, lang=lang)

    async def weekly_digest(self, symbols: List[str], lang: str = "tr") -> WeeklyDigest:
        logger.info(f"InsightEngine generating weekly digest for symbols: {symbols} (lang={lang})")
        contexts = {}
        for sym in symbols:
            ctx = await self.context_builder.build(sym, "1W")
            if ctx:
                contexts[sym] = ctx
                
        digest = await self.llm.generate_weekly_digest(contexts, lang=lang)
        return digest

    async def answer_with_history(self, question: str, symbol: str, watchlist: List[str], lang: str = "tr") -> HistoricalQAResponse:
        """Q&A that uses both live data AND saved reports as context."""
        logger.info(f"InsightEngine answering with history for {symbol}")
        
        # 1. Search past reports
        past_hits = await self.report_store.search_relevant_reports(question, symbols=[symbol], n=3)
        
        # 2. Get live context
        context = await self.context_builder.build(symbol, "1M")
        if not context:
            raise ValueError(f"Context build failed for {symbol}")
            
        # 3. Format history
        history_text = ""
        referenced_ids = []
        for hit in past_hits:
            history_text += f"\n[Date: {hit['created_at']}] {hit['relevant_excerpt']}\n"
            referenced_ids.append(hit['report_id'])
            
        # 4. LLM Synthesis
        raw_answer = await self.llm.answer_with_history(
            question=question,
            symbol=symbol,
            history_text=history_text if history_text else "No past reports found.",
            current_context=context,
            lang=lang
        )
        
        # 5. Build response objects (simplified for now)
        sources = []
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from modules.investment.models import AnalysisReport
            stmt = select(AnalysisReport).where(AnalysisReport.id.in_([uuid.UUID(rid) for rid in referenced_ids]))
            res = await session.execute(stmt)
            for r in res.scalars():
                sources.append(ReportSummary(
                    id=str(r.id),
                    symbol=r.symbol,
                    timeframe=r.timeframe,
                    report_type=r.report_type,
                    llm_summary=r.llm_summary,
                    conviction_level=r.conviction_level,
                    created_at=r.created_at,
                    data_as_of=r.data_as_of
                ))

        return HistoricalQAResponse(
            answer=raw_answer,
            sources_used=sources,
            has_view_changed="view has changed" in raw_answer.lower() or "değişti" in raw_answer.lower(),
            past_prediction_outcome=None # Future: let LLM determine this
        )
