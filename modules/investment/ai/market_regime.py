import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Literal
from loguru import logger
import json

from core.database import AsyncSessionLocal
from core.cache import cache
from core.config import settings
from modules.investment.models import MarketPrice, MacroIndicator
from modules.investment.ai.schemas import MarketRegime
from modules.investment.ai.prompts import REGIME_NARRATIVE_PROMPT
from google import genai
from google.genai import types
from sqlalchemy import select, desc

class MarketRegimeDetector:
    """
    Classifies the market into one of the predefined regimes based on quantitative data.
    Uses Gemini only for narrative explanation.
    """

    def __init__(self):
        self.genai_client = genai.Client(api_key=settings.gemini_api_key)
        self.model_id = getattr(settings, "gemini_model_flash", "gemini-3-flash-preview")

    async def _get_latest_price(self, symbol: str, days: int = 5) -> List[float]:
        async with AsyncSessionLocal() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days + 5) # Buffer for weekends
            query = select(MarketPrice.close).where(
                MarketPrice.symbol == symbol,
                MarketPrice.timestamp >= cutoff
            ).order_by(desc(MarketPrice.timestamp)).limit(days + 1)
            
            result = await session.execute(query)
            return [r[0] for r in result.all()]

    async def _get_latest_macro(self, indicator: str, limit: int = 5) -> List[float]:
        async with AsyncSessionLocal() as session:
            query = select(MacroIndicator.value).where(
                MacroIndicator.indicator == indicator
            ).order_by(desc(MacroIndicator.timestamp)).limit(limit)
            
            result = await session.execute(query)
            return [r[0] for r in result.all()]

    async def detect_regime(self) -> MarketRegime:
        logger.info("Detecting current market regime...")
        
        # 1. Gather data
        xu100_prices = await self._get_latest_price("XU100.IS", 5)
        usdtry_prices = await self._get_latest_price("USDTRY=X", 5)
        gold_prices = await self._get_latest_price("GC=F", 5)
        policy_rates = await self._get_latest_macro("TCMB_POLICY_RATE", 3)
        cpi_data = await self._get_latest_macro("FRED_CPIAUCSL", 2) # Example fallback

        signals = []
        regime_label: Literal["risk_on", "risk_off", "rate_tightening", "rate_easing", "fx_pressure", "inflation_driven", "earnings_season"] = "risk_on"
        confidence: Literal["high", "medium", "low"] = "medium"

        # USDTRY check
        if len(usdtry_prices) >= 2:
            change_5d = ((usdtry_prices[0] - usdtry_prices[-1]) / usdtry_prices[-1]) * 100 if len(usdtry_prices) >= 5 else 0
            if change_5d > 3.0:
                regime_label = "fx_pressure"
                signals.append(f"USDTRY +{change_5d:.1f}% 5d")
            
        # Risk Off check (BIST down, Gold up)
        if regime_label == "risk_on" and len(xu100_prices) >= 5 and len(gold_prices) >= 5:
            xu_return = ((xu100_prices[0] - xu100_prices[-1]) / xu100_prices[-1]) * 100
            gold_return = ((gold_prices[0] - gold_prices[-1]) / gold_prices[-1]) * 100
            if xu_return < -4.0 and gold_return > 2.0:
                regime_label = "risk_off"
                signals.append(f"BIST100 {xu_return:.1f}% 5d, Gold +{gold_return:.1f}% 5d")

        # Risk On check
        if regime_label == "risk_on" and len(xu100_prices) >= 5:
            xu_return = ((xu100_prices[0] - xu100_prices[-1]) / xu100_prices[-1]) * 100
            if xu_return > 3.0:
                regime_label = "risk_on"
                signals.append(f"BIST100 +{xu_return:.1f}% 5d")

        # Policy rate check
        if len(policy_rates) >= 2:
            if policy_rates[0] > policy_rates[1]:
                if regime_label == "risk_on":
                    regime_label = "rate_tightening"
                signals.append("TCMB Rate Hike")
            elif policy_rates[0] < policy_rates[1]:
                if regime_label == "risk_on":
                    regime_label = "rate_easing"
                signals.append("TCMB Rate Cut")

        # 2. Generate Narrative with Gemini
        narrative = "Market conditions are relatively stable with standard risk levels."
        try:
            prompt = REGIME_NARRATIVE_PROMPT.format(
                regime=regime_label,
                signals_used=", ".join(signals) if signals else "No significant outliers"
            )
            response = self.genai_client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            if response.text:
                narrative = response.text.strip()
        except Exception as e:
            logger.error(f"Failed to generate regime narrative: {e}")

        result = MarketRegime(
            regime=regime_label,
            narrative=narrative,
            detected_at=datetime.now(timezone.utc),
            confidence=confidence,
            signals_used=signals
        )

        # 3. Cache Result
        try:
            await cache.set("market_regime:current", result.model_dump_json(), ttl=6*3600)
        except Exception as e:
            logger.warning(f"Failed to cache regime: {e}")

        return result

    async def get_current_regime(self) -> MarketRegime:
        try:
            cached = await cache.get("market_regime:current")
            if cached:
                return MarketRegime.model_validate_json(cached)
        except Exception as e:
            logger.warning(f"Failed to read regime from cache: {e}")
            
        return await self.detect_regime()
