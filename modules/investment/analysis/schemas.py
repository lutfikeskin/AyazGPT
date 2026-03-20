from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class TechnicalAnalysisResult(BaseModel):
    symbol: str
    timeframe: str
    indicators: Dict[str, float]
    signals: List[str]
    trend: str # 'bullish' | 'bearish' | 'neutral'

class FundamentalAnalysisResult(BaseModel):
    symbol: str
    metrics: Dict[str, Optional[float]]
    dcf_fair_value: Optional[float]
    vs_current_price_pct: Optional[float]
    quality_score: int = Field(ge=0, le=10)
    
    # borsapy / Analyst fields
    analyst_target_mean: Optional[float] = None
    analyst_target_high: Optional[float] = None
    analyst_target_low: Optional[float] = None
    analyst_count: Optional[int] = None
    recommendation_consensus: Optional[str] = None  # "buy" | "hold" | "sell"
    buy_pct: Optional[float] = None
    next_earnings_date: Optional[str] = None

class AggregatedSentiment(BaseModel):
    symbol: str
    timeframe: str
    avg_sentiment: float
    sentiment_trend: str
    top_bullish_headlines: List[str]
    top_bearish_headlines: List[str]

class RiskAnalysisResult(BaseModel):
    symbol: str
    timeframe: str
    volatility: float
    max_drawdown: float
    sharpe_ratio: float
    var_95: float
    beta: Optional[float]

class AnalysisResult(BaseModel):
    symbol: str
    timeframe: str
    technical: TechnicalAnalysisResult
    fundamental: FundamentalAnalysisResult
    sentiment: AggregatedSentiment
    risk: RiskAnalysisResult
