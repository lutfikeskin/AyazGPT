import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from sqlalchemy import select, update
from transformers import pipeline
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from langdetect import detect, LangDetectException
from google import genai
from google.genai import types

from core.database import AsyncSessionLocal
from modules.investment.models import NewsItem
from modules.investment.analysis.schemas import AggregatedSentiment
from core.config import settings

def detect_language(text: str) -> str:
    """Detects the language of a given text. Defaults to English."""
    try:
        # Take first 200 chars for faster detection
        lang = detect(text[:200])
        return str(lang)
    except LangDetectException:
        return 'en'

class SentimentAnalyzer:
    _instance = None
    _pipeline = None
    _executor = ThreadPoolExecutor(max_workers=2)
    _genai_client = genai.Client(api_key=settings.gemini_api_key)
    _model_id = getattr(settings, "gemini_model_flash", "gemini-3-flash-preview")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SentimentAnalyzer, cls).__new__(cls)
        return cls._instance

    def _get_pipeline(self):
        """Lazy loads the FinBERT pipeline for English news."""
        if self._pipeline is None:
            logger.info("Loading FinBERT pipeline for sentiment analysis...")
            self._pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        return self._pipeline

    def _analyze_texts_sync(self, texts: List[str]) -> List[float]:
        """Synchronous FinBERT inference for English texts."""
        if not texts:
            return []
        
        pipe = self._get_pipeline()
        results = pipe(texts)
        scores = []
        for res in results:
            label = res['label']
            if label == 'positive':
                scores.append(1.0)
            elif label == 'negative':
                scores.append(-1.0)
            else:
                scores.append(0.0)
        return scores

    async def _analyze_turkish_batch(self, texts: List[str]) -> List[float]:
        """Sends Turkish headlines to Gemini Flash for sentiment scoring."""
        if not texts:
            return []
            
        numbered_headlines = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
        prompt = f"""Rate each headline's financial sentiment from -1.0 (very bearish) 
to 1.0 (very bullish). Consider Turkish financial market context. 
Return a JSON array of numbers only, same order as input.
Headlines:
{numbered_headlines}"""

        try:
            logger.info(f"Calling Gemini Flash for {len(texts)} Turkish headlines")
            response = self._genai_client.models.generate_content(
                model=self._model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                )
            )
            
            scores = json.loads(response.text or "[]")
            if isinstance(scores, list) and len(scores) == len(texts):
                return [float(s) for s in scores]
            else:
                logger.warning(f"Gemini returned mismatched scores length: {len(scores)} vs {len(texts)}")
                return [0.0] * len(texts)
        except Exception as e:
            logger.error(f"Error in Gemini Turkish sentiment analysis: {e}")
            return [0.0] * len(texts)

    async def batch_analyze_unscored_news(self):
        """Hybrid batch analysis: Turkish -> Gemini, English -> FinBERT."""
        async with AsyncSessionLocal() as session:
            query = select(NewsItem).where(NewsItem.sentiment_score == None).limit(100)
            result = await session.execute(query)
            items = result.scalars().all()
            
            if not items:
                return

            # 1. Split by language
            tr_items = []
            en_items = []
            for item in items:
                lang = detect_language(item.title)
                if lang == 'tr':
                    tr_items.append(item)
                else:
                    en_items.append(item)

            # 2. Process concurrently
            loop = asyncio.get_event_loop()
            tasks = []
            
            if tr_items:
                tr_titles = [it.title for it in tr_items]
                tasks.append(self._analyze_turkish_batch(tr_titles))
            else:
                tasks.append(asyncio.sleep(0, result=[])) # Dummy

            if en_items:
                en_titles = [it.title + " " + (it.body or "") for it in en_items]
                tasks.append(loop.run_in_executor(
                    self._executor, 
                    self._analyze_texts_sync, 
                    en_titles
                ))
            else:
                tasks.append(asyncio.sleep(0, result=[])) # Dummy

            tr_scores, en_scores = await asyncio.gather(*tasks)

            # 3. Apply scores
            for it, score in zip(tr_items, tr_scores):
                it.sentiment_score = score
            for it, score in zip(en_items, en_scores):
                it.sentiment_score = score
            
            await session.commit()
            logger.info(f"Processed {len(tr_items)} Turkish (Gemini) + {len(en_items)} English (FinBERT) news items.")

    async def get_aggregated_sentiment(self, symbol: str, timeframe: str) -> AggregatedSentiment:
        """Reads pre-computed scores from DB and aggregates into a report."""
        # Note: This trigger remains so we always have recent data scored
        await self.batch_analyze_unscored_news()
        
        async with AsyncSessionLocal() as session:
            days_map = {'1W': 7, '1M': 30, '3M': 90, '1Y': 365, '5Y': 1825}
            days = days_map.get(timeframe, 30)
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = select(NewsItem).where(
                NewsItem.symbols_mentioned.contains([symbol]),
                NewsItem.published_at >= cutoff,
                NewsItem.sentiment_score != None
            ).order_by(NewsItem.published_at.desc())
            
            result = await session.execute(query)
            items = result.scalars().all()
            
            if not items:
                return AggregatedSentiment(
                    symbol=symbol, timeframe=timeframe,
                    avg_sentiment=0.0, sentiment_trend="neutral",
                    top_bullish_headlines=[], top_bearish_headlines=[]
                )
                
            scores = [i.sentiment_score for i in items if i.sentiment_score is not None]
            avg_sentiment = sum(scores) / len(scores) if scores else 0.0
            
            half = len(scores) // 2
            if half > 0:
                recent_avg = sum(scores[:half]) / half
                older_avg = sum(scores[half:]) / (len(scores) - half)
                if recent_avg - older_avg > 0.1: # Tighter threshold
                    trend = "improving"
                elif older_avg - recent_avg > 0.1:
                    trend = "worsening"
                else:
                    trend = "stable"
            else:
                trend = "stable"
                
            bullish = sorted([i for i in items if i.sentiment_score is not None and i.sentiment_score > 0.3], 
                            key=lambda x: x.published_at, reverse=True)[:3]
            bearish = sorted([i for i in items if i.sentiment_score is not None and i.sentiment_score < -0.3], 
                            key=lambda x: x.published_at, reverse=True)[:3]
            
            return AggregatedSentiment(
                symbol=symbol, timeframe=timeframe,
                avg_sentiment=avg_sentiment, sentiment_trend=trend,
                top_bullish_headlines=[b.title for b in bullish],
                top_bearish_headlines=[b.title for b in bearish]
            )
