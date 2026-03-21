from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Literal
from modules.investment.analysis.schemas import AnalysisResult



class SourceRef(BaseModel):
    id: str
    type: Literal["news", "macro", "price", "report"]
    label: str
    date: datetime


class MarketRegime(BaseModel):
    regime: Literal[
        "risk_on", "risk_off", "rate_tightening", "rate_easing",
        "fx_pressure", "inflation_driven", "earnings_season"
    ]
    narrative: str           # 2-sentence Gemini Flash explanation
    detected_at: datetime
    confidence: Literal["high", "medium", "low"]
    signals_used: List[str]  # e.g. ["USDTRY +3.2% 5d", "BIST100 -4.1% 5d"]

class BlindSpot(BaseModel):
    severity: Literal["ALERT", "WARNING", "INFO", "low", "medium", "high"]
    title: str
    detail: str
    action_suggestion: Optional[str] = None
    name: Optional[str] = None # For compatibility with initial plan
    description: Optional[str] = None # For compatibility

class EvidenceNode(BaseModel):
    id: str  # Unique string, e.g., 'macro_USDTRY'
    type: Literal["macro", "technical", "fundamental", "sentiment", "pattern", "blind_spot", "conclusion"]
    label: str
    value: str
    date: Optional[datetime] = None

class EvidenceEdge(BaseModel):
    from_id: str
    to_id: str
    relationship: str  # e.g., 'triggers', 'supports', 'contradicts'
    weight: float      # 0.0 to 1.0

class EvidenceGraph(BaseModel):
    nodes: List[EvidenceNode]
    edges: List[EvidenceEdge]
    root_conclusion: str

class ReturnEstimates(BaseModel):
    return_1m: float
    return_3m: float
    return_1y: float
    data_source: str   # "historical_patterns" | "market_averages_fallback"
    regime_adjusted: bool
    confidence: Literal["high", "medium", "low"]

class InvestmentRecommendation(BaseModel):
    symbol: str
    current_price: float
    recommendation: Literal["strong_buy", "buy", "hold", "reduce", "avoid"]
    confidence: int          # 1-10

    # Return estimates — from historical data, not LLM
    returns: ReturnEstimates

    # LLM-generated thesis
    primary_thesis: str
    key_catalysts: List[str]
    supporting_data: List[str]

    # Devil's advocate — validated non-empty
    counter_thesis: str
    key_risks: List[str]
    invalidation_triggers: List[str]   # specific and measurable

    # Context
    blind_spots_flagged: List[BlindSpot]  # Ensure the recommendation accounts for what it missed
    market_regime: MarketRegime           # the macro context when this was generated
    pattern_support: str                  # textual synthesis of historical setup similarities
    macro_alignment: str                  # does this trade fight the macro regime?
    evidence_graph: Optional[EvidenceGraph] = None

    # Meta
    data_as_of: datetime
    analysis_quality: Literal["high", "medium", "low"]
    disclaimer: str = (
        "Bu analiz bilgi amaçlıdır, yatırım tavsiyesi değildir. "
        "Kendi araştırmanızı yapınız."
    )

    @field_validator('counter_thesis')
    @classmethod
    def counter_thesis_not_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 20:
            raise ValueError('counter_thesis cannot be empty or trivial')
        return v

    @field_validator('invalidation_triggers')
    @classmethod
    def triggers_must_be_specific(cls, v: List[str]) -> List[str]:
        if len(v) < 2:
            raise ValueError('At least 2 invalidation triggers required')
        return v

class AvoidSignal(BaseModel):
    symbol: str
    quick_score: float
    main_reason: str

class UniverseScan(BaseModel):
    market_regime: MarketRegime
    top_opportunities: List[InvestmentRecommendation]
    watchlist_recommendations: List[InvestmentRecommendation]
    symbols_to_avoid: List[AvoidSignal]
    scan_timestamp: datetime
    universe_size: int
    symbols_scanned: int
    scan_duration_seconds: float

class ContextPackage(BaseModel):
    symbol: str
    timeframe: str
    analysis: AnalysisResult
    relevant_news: List[Dict[str, Any]]
    macro_indicators: Dict[str, float]
    peers_comparison: List[Dict[str, Any]]
    available_sources: List[SourceRef] = []

class SymbolReport(BaseModel):
    executive_summary: str
    price_performance: str
    key_catalysts: List[str]
    risks: List[str]
    what_i_might_be_missing: List[str]
    pattern_found: bool
    pattern_description: str
    macro_connection: str
    sentiment_trend: str
    conviction_level: int = Field(ge=1, le=10)
    conviction_reasoning: str
    sources_cited: List[str] = []
    sources: List[SourceRef] = []
    data_as_of: str


class MacroTrigger(BaseModel):
    event_type: str
    avg_price_impact_pct: float
    occurrences: int
    last_occurrence: date
    description: str

class SimilarSetupResult(BaseModel):
    total_similar_setups: int
    base_rate_positive: float  # 0.0 to 1.0
    median_1m_return: float
    median_3m_return: float
    worst_case_pct: float
    best_case_pct: float
    sample_dates: List[date]
    confidence: Literal["high", "medium", "low"]
    regime_filtered_count: Optional[int] = None
    regime_match_rate: Optional[float] = None

class SectorDivergence(BaseModel):
    symbol_1m_return: float
    peers_avg_1m_return: float
    divergence_score: float
    divergence_type: Literal["outperforming", "underperforming", "inline"]
    is_significant: bool
    peer_symbols: List[str]
    note: Optional[str] = None

class PatternAnalysis(BaseModel):
    similar_setups: SimilarSetupResult
    macro_triggers: List[MacroTrigger]
    sector_divergence: SectorDivergence
    blind_spots: List[BlindSpot]
    llm_synthesis: str  # Gemini's narrative connecting all findings

class WeeklyDigest(BaseModel):
    executive_summary: str
    portfolio_insights: List[str]
    top_performers: List[str]
    macro_environment: str
    data_as_of: str

class ComparisonReport(BaseModel):
    winner: str
    reasoning: str
    comparison_table: Dict[str, Any]
    what_i_might_be_missing: List[str]


class ReportSummary(BaseModel):
    id: str
    symbol: str
    timeframe: str
    report_type: str
    llm_summary: str
    conviction_level: int
    created_at: datetime
    data_as_of: datetime

class HistoricalQAResponse(BaseModel):
    answer: str
    sources_used: List[ReportSummary]
    has_view_changed: bool
    past_prediction_outcome: Optional[str] = None


class FieldChange(BaseModel):
    field: str
    old_value: Any
    new_value: Any
    direction: Literal["improved", "worsened", "neutral", "changed"]


class ReportDiff(BaseModel):
    symbol: str
    old_report_date: datetime
    new_report_date: datetime
    days_between: int
    conviction_change: int           # e.g. +2 means conviction went from 5 to 7
    key_changes: List[FieldChange]   # top 5 most significant changes
    new_risks: List[str]             # risks that appeared in new but not old
    resolved_risks: List[str]        # risks in old but gone in new
    new_catalysts: List[str]
    resolved_catalysts: List[str]
    recommendation_changed: bool
    narrative: str                   # Gemini Flash 2-3 sentence summary
