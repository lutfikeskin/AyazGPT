import uuid
from typing import List, Optional
from datetime import datetime, timezone

from loguru import logger
from modules.investment.ai.schemas import (
    AnalysisResult, SimilarSetupResult, MarketRegime, BlindSpot,
    EvidenceNode, EvidenceEdge, EvidenceGraph
)

class EvidenceGraphBuilder:
    """
    Constructs an interactive causal graph detailing the rationale
    behind an investment recommendation without involving the LLM.
    """

    def build(
        self,
        symbol: str,
        analysis: Optional[AnalysisResult],
        patterns: Optional[SimilarSetupResult],
        regime: MarketRegime,
        blind_spots: List[BlindSpot],
        recommendation_label: str
    ) -> EvidenceGraph:
        
        nodes: List[EvidenceNode] = []
        edges: List[EvidenceEdge] = []
        
        root_id = "conc_root"
        
        # 1. Root Conclusion Node
        nodes.append(EvidenceNode(
            id=root_id,
            type="conclusion",
            label="Recommendation",
            value=recommendation_label.upper(),
            date=datetime.now(timezone.utc)
        ))

        # 2. Market Regime (Macro)
        macro_id = "macro_regime"
        nodes.append(EvidenceNode(
            id=macro_id,
            type="macro",
            label="Market Regime",
            value=regime.regime.upper(),
            date=regime.detected_at
        ))
        
        # Link regime signals
        for i, sig in enumerate(regime.signals_used):
            sig_id = f"macro_sig_{i}"
            nodes.append(EvidenceNode(
                id=sig_id, type="macro", label="Regime Signal", value=sig
            ))
            # Edges: Signals form the regime
            edges.append(EvidenceEdge(from_id=sig_id, to_id=macro_id, relationship="triggers", weight=1.0))
            
        # 3. Technicals
        if analysis and analysis.technical:
            tech = analysis.technical
            trend_val = tech.trend
            rsi_val = tech.indicators.get("RSI", 50)
            
            # Trend Node
            trend_id = "tech_trend"
            nodes.append(EvidenceNode(id=trend_id, type="technical", label="Trend", value=trend_val))
            # Edge: Trend -> Conclusion
            rel = "supports" if (trend_val == "bullish" and recommendation_label in ["buy", "strong_buy"]) or \
                               (trend_val == "bearish" and recommendation_label in ["sell", "strong_sell"]) else "neutral"
            edges.append(EvidenceEdge(from_id=trend_id, to_id=root_id, relationship=rel, weight=0.6))
            
            # RSI Node
            if rsi_val > 70 or rsi_val < 30:
                rsi_id = "tech_rsi"
                rsi_label = "Overbought" if rsi_val > 70 else "Oversold"
                nodes.append(EvidenceNode(id=rsi_id, type="technical", label=f"RSI ({round(rsi_val)})", value=rsi_label))
                # Reversal logic mapping
                if rsi_val > 70 and recommendation_label in ["sell", "strong_sell"]: rel = "supports"
                elif rsi_val < 30 and recommendation_label in ["buy", "strong_buy"]: rel = "supports"
                else: rel = "contradicts"
                edges.append(EvidenceEdge(from_id=rsi_id, to_id=root_id, relationship=rel, weight=0.7))

        # 4. Pattern Engine
        if patterns and patterns.total_similar_setups > 0:
            pat_id = "pattern_match"
            node_val = f"Base Rate: {patterns.base_rate_positive*100:.1f}%, Fwd 1M: {patterns.median_1m_return*100:.1f}%"
            nodes.append(EvidenceNode(id=pat_id, type="pattern", label=f"{patterns.regime_filtered_count or patterns.total_similar_setups} Historical Setups", value=node_val))
            
            # Edges: Technicals & Macro form Pattern
            edges.append(EvidenceEdge(from_id=macro_id, to_id=pat_id, relationship="filters", weight=1.0))
            if analysis and analysis.technical:
                edges.append(EvidenceEdge(from_id="tech_trend", to_id=pat_id, relationship="defines", weight=0.8))
                
            # Pattern -> Conclusion
            pat_rel = "supports" if (patterns.median_1m_return > 0 and recommendation_label in ["buy", "strong_buy"]) or \
                                   (patterns.median_1m_return < 0 and recommendation_label in ["sell", "strong_sell"]) else "neutral"
            edges.append(EvidenceEdge(from_id=pat_id, to_id=root_id, relationship=pat_rel, weight=0.9))

        # 5. Fundamental
        if analysis and analysis.fundamental:
            fund = analysis.fundamental
            dcf_fair = fund.dcf_fair_value
            if dcf_fair is not None and fund.metrics.get("current_price"):
                price = float(fund.metrics["current_price"])
                dcf_val: float = float(dcf_fair)
                diff_pct = ((dcf_val - price) / price) * 100
                
                fund_id = "fund_dcf"
                nodes.append(EvidenceNode(id=fund_id, type="fundamental", label="DCF Fair Value", value=f"{diff_pct:+.1f}% vs Price"))
                
                fund_rel = "supports" if (diff_pct > 0 and recommendation_label in ["buy", "strong_buy"]) or \
                                        (diff_pct < 0 and recommendation_label in ["sell", "strong_sell"]) else "contradicts"
                edges.append(EvidenceEdge(from_id=fund_id, to_id=root_id, relationship=fund_rel, weight=0.8))

        # 6. Blind Spots
        for i, bs in enumerate(blind_spots):
            bs_id = f"blind_spot_{i}"
            desc = bs.detail or bs.description or "No detail provided"
            title = bs.title or bs.name or "Blind Spot"
            val = f"[{bs.severity.upper()}] {desc}"
            nodes.append(EvidenceNode(id=bs_id, type="blind_spot", label=title, value=val))
            # Edge: Blind spots always contradict the 'happy path' or complicate it
            edges.append(EvidenceEdge(from_id=bs_id, to_id=root_id, relationship="contradicts", weight=1.0 if bs.severity in ["high", "ALERT"] else 0.5))

        # Safeguard Node Limit (Take top 20 by prioritizing conclusions, macro, patterns)
        if len(nodes) > 20:
            logger.warning(f"Evidence graph for {symbol} generated {len(nodes)} nodes. Trimming to 20.")
            nodes = nodes[:20]
            valid_ids = {n.id for n in nodes}
            edges = [e for e in edges if e.from_id in valid_ids and e.to_id in valid_ids]

        return EvidenceGraph(nodes=nodes, edges=edges, root_conclusion=recommendation_label.upper())
