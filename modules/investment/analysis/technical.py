import pandas as pd
import pandas_ta as ta # type: ignore
from sqlalchemy import select
from loguru import logger
from datetime import datetime, timedelta, timezone

from core.database import AsyncSessionLocal
from modules.investment.models import MarketPrice
from modules.investment.analysis.schemas import TechnicalAnalysisResult

class TechnicalAnalyzer:
    def __init__(self):
        pass

    async def get_price_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        async with AsyncSessionLocal() as session:
            # Timeframes: '1W','1M','3M','1Y','5Y'
            days_map = {'1W': 7, '1M': 30, '3M': 90, '1Y': 365, '5Y': 1825}
            days = days_map.get(timeframe, 30)
            
            # Since we need rolling metrics (EMA200), fetch more data
            fetch_days = max(days, 300) 
            cutoff = datetime.now(timezone.utc) - timedelta(days=fetch_days)
            
            query = select(MarketPrice).where(
                MarketPrice.symbol == symbol,
                MarketPrice.timestamp >= cutoff
            ).order_by(MarketPrice.timestamp.asc())
            
            result = await session.execute(query)
            rows = result.scalars().all()
            
            if not rows:
                return pd.DataFrame()
                
            df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'open': r.open,
                'high': r.high,
                'low': r.low,
                'close': r.close,
                'volume': r.volume
            } for r in rows])
            df.set_index('timestamp', inplace=True)
            return df
            
    async def analyze(self, symbol: str, timeframe: str) -> TechnicalAnalysisResult:
        df = await self.get_price_data(symbol, timeframe)
        if df.empty or len(df) < 50:
            return TechnicalAnalysisResult(
                symbol=symbol, timeframe=timeframe,
                indicators={}, signals=[], trend="neutral"
            )
            
        try:
            # Calculate indicators using pandas_ta
            df.ta.rsi(length=14, append=True)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            df.ta.bbands(length=20, append=True)
            df.ta.ema(length=20, append=True)
            df.ta.ema(length=50, append=True)
            df.ta.ema(length=200, append=True)
            df.ta.atr(length=14, append=True)
            df.ta.sma(close='volume', length=20, append=True)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Map columns
            rsi = latest.get('RSI_14', 50)
            macd = latest.get('MACD_12_26_9', 0)
            macd_signal = latest.get('MACDs_12_26_9', 0)
            prev_macd = prev.get('MACD_12_26_9', 0)
            prev_macd_signal = prev.get('MACDs_12_26_9', 0)
            
            ema20 = latest.get('EMA_20', 0)
            ema50 = latest.get('EMA_50', 0)
            ema200 = latest.get('EMA_200', 0)
            prev_ema50 = prev.get('EMA_50', 0)
            prev_ema200 = prev.get('EMA_200', 0)
            
            bb_upper = latest.get('BBU_20_2.0', 0)
            bb_lower = latest.get('BBL_20_2.0', 0)
            bb_mid = latest.get('BBM_20_2.0', 0)
            
            vol_sma = latest.get('SMA_20', 0)
            close = latest['close']
        except Exception as e:
            logger.error(f"Error calculating TA for {symbol}: {e}")
            return TechnicalAnalysisResult(
                symbol=symbol, timeframe=timeframe,
                indicators={}, signals=[], trend="neutral"
            )

        signals = []
        trend = "neutral"
        
        # Golden Cross
        if pd.notna(ema50) and pd.notna(ema200) and prev_ema50 <= prev_ema200 and ema50 > ema200:
            signals.append("golden_cross")
        # Death Cross
        elif pd.notna(ema50) and pd.notna(ema200) and prev_ema50 >= prev_ema200 and ema50 < ema200:
            signals.append("death_cross")
            
        # RSI
        if pd.notna(rsi):
            if rsi < 30:
                signals.append("rsi_oversold(<30)")
            elif rsi > 70:
                signals.append("rsi_overbought(>70)")
            
        # BB Squeeze
        if pd.notna(bb_mid) and bb_mid > 0 and (bb_upper - bb_lower) / bb_mid < 0.05:
            signals.append("bb_squeeze")
            
        # MACD Crossover
        if pd.notna(macd) and pd.notna(macd_signal) and prev_macd <= prev_macd_signal and macd > macd_signal:
            signals.append("macd_crossover")
            
        # Trend
        if pd.notna(ema50) and pd.notna(ema200):
            if close > ema50 and ema50 > ema200:
                trend = "bullish"
            elif close < ema50 and ema50 < ema200:
                trend = "bearish"
            
        indicators = {
            "RSI": float(rsi) if pd.notna(rsi) else 0.0,
            "MACD": float(macd) if pd.notna(macd) else 0.0,
            "EMA20": float(ema20) if pd.notna(ema20) else 0.0,
            "EMA50": float(ema50) if pd.notna(ema50) else 0.0,
            "EMA200": float(ema200) if pd.notna(ema200) else 0.0,
            "ATR": float(latest.get('ATRr_14', 0)) if pd.notna(latest.get('ATRr_14')) else 0.0,
            "Volume_SMA": float(vol_sma) if pd.notna(vol_sma) else 0.0,
            "Close": float(close)
        }
        
        return TechnicalAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
            signals=signals,
            trend=trend
        )
