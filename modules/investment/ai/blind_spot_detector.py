import asyncio
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import text
from loguru import logger

from core.database import AsyncSessionLocal
from modules.investment.ai.schemas import BlindSpot
from modules.investment.analysis.schemas import AnalysisResult
from modules.investment.ai.pattern_engine import HistoricalPatternMiner

class BlindSpotDetector:
    """
    Identifies psychological biases and hidden risks in investment setups.
    """

    async def check_valuation_vs_sentiment(self, symbol: str, analysis: AnalysisResult) -> Optional[BlindSpot]:
        """Flag mismatches between sentiment and valuation."""
        sent = analysis.sentiment.avg_sentiment if analysis.sentiment else 0
        pe = analysis.fundamental.metrics.get("pe_ratio") if analysis.fundamental else None
        dcf = analysis.fundamental.dcf_fair_value if analysis.fundamental else None
        
        # We need current price to compare with fair value. 
        # If not direct, we check if we have it in metrics or calculate from DCF and pct.
        curr = analysis.fundamental.metrics.get("current_price")
        if not curr and analysis.fundamental.dcf_fair_value and analysis.fundamental.vs_current_price_pct:
            # fair_value / (1 + pct) = current
            curr = analysis.fundamental.dcf_fair_value / (1 + analysis.fundamental.vs_current_price_pct)

        # TRAP: euphoric but expensive
        if sent > 0.5:
            if dcf and curr and dcf < curr * 0.8:
                return BlindSpot(
                    severity="ALERT",
                    title="Valuation Trap",
                    detail=f"Sentiment is euphoric ({sent:.2f}) but the DCF fair value ({dcf:.2f}) is significantly lower than current price ({curr:.2f}).",
                    action_suggestion="Wait for a pullback or verify if the growth assumptions justify this premium."
                )

        # OPPORTUNITY: hated but solid
        if sent < -0.3:
            quality = analysis.fundamental.quality_score if analysis.fundamental else 0
            if quality > 7 and dcf and curr and dcf > curr * 1.2:
                return BlindSpot(
                    severity="INFO",
                    title="Contrarian Opportunity",
                    detail=f"Sentiment is negative ({sent:.2f}) but quality score is high ({quality}/10) and fair value suggests 20%+ upside.",
                    action_suggestion="Consider this as a possible contrarian entry point."
                )
        
        return None

    async def check_correlation_risk(self, symbols: List[str]) -> Optional[BlindSpot]:
        """Detect hidden correlation using last 1Y of daily returns."""
        if len(symbols) < 2:
            return None

        # Fetch last 1Y returns for all symbols
        async def get_returns(s: str):
            query = text("""
                SELECT timestamp, close FROM market_prices 
                WHERE symbol = :symbol AND timestamp > NOW() - INTERVAL '1 year'
                ORDER BY timestamp ASC
            """)
            async with AsyncSessionLocal() as session:
                res = await session.execute(query, {"symbol": s})
                df = pd.DataFrame(res.fetchall(), columns=['timestamp', 'close'])
                if df.empty: return pd.Series()
                return df.set_index('timestamp')['close'].pct_change()

        rets_list = await asyncio.gather(*[get_returns(s) for s in symbols])
        rets_df = pd.concat(rets_list, axis=1, keys=symbols).dropna()
        
        if rets_df.empty:
            return None

        corr_matrix = rets_df.correlation().abs() if hasattr(rets_df, 'correlation') else rets_df.corr().abs()
        
        risk_pairs = []
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                s1, s2 = symbols[i], symbols[j]
                corr = corr_matrix.loc[s1, s2]
                if corr > 0.85:
                    risk_pairs.append(f"{s1} & {s2} ({corr:.2f})")

        if risk_pairs:
            return BlindSpot(
                severity="WARNING",
                title="Hidden Correlation Risk",
                detail=f"The following pairs are highly correlated: {', '.join(risk_pairs)}. They might feel like different bets, but they move together.",
                action_suggestion="Ensure your portfolio isn't overly exposed to the same underlying drivers."
            )
        return None

    async def check_recency_bias(self, symbol: str, analysis: AnalysisResult) -> Optional[BlindSpot]:
        """Counter recency bias if recent performance is euphoric."""
        # We need historical data for 52W high
        query = text("""
            SELECT MAX(high) as high_52w, MIN(low) as low_52w 
            FROM market_prices 
            WHERE symbol = :symbol AND timestamp > NOW() - INTERVAL '1 year'
        """)
        async with AsyncSessionLocal() as session:
            res = await session.execute(query, {"symbol": symbol})
            row = res.fetchone()
            if not row or row[0] is None: return None
            high_52w = float(row[0])

        curr = analysis.fundamental.metrics.get("current_price")
        if not curr and analysis.fundamental.dcf_fair_value and analysis.fundamental.vs_current_price_pct:
            curr = analysis.fundamental.dcf_fair_value / (1 + analysis.fundamental.vs_current_price_pct)
            
        if not curr: return None

        dist_from_high = (curr - high_52w) / high_52w * 100
        # Dummy 1M return check (ideally passed in or fetched)
        # Assuming we can get it from technical analysis or fetch it
        fwd_ret = analysis.risk.volatility if analysis.risk else 0 # Replace with actual 1M if available
        # Let's fetch actual 1M return
        query_1m = text("""
            SELECT close FROM market_prices WHERE symbol = :symbol 
            AND timestamp <= NOW() - INTERVAL '30 days' ORDER BY timestamp DESC LIMIT 1
        """)
        async with AsyncSessionLocal() as session:
            res_1m = await session.execute(query_1m, {"symbol": symbol})
            row_1m = res_1m.fetchone()
            if row_1m:
                p_1m = float(row_1m[0])
                ret_1m = (curr - p_1m) / p_1m * 100
                if ret_1m > 15 and dist_from_high < -15:
                    return BlindSpot(
                        severity="INFO",
                        title="Recency Bias Alert",
                        detail=f"This looks great this month (+{ret_1m:.1f}%), but it's still {abs(dist_from_high):.1f}% below its 52-week high.",
                        action_suggestion="Don't mistake a relief rally for a full trend reversal without broader confirmation."
                    )
        return None

    async def check_concentration_risk(self, portfolio: Dict[str, float]) -> Optional[BlindSpot]:
        """Flags overweight symbols or sectors."""
        if not portfolio:
            return None

        for sym, weight in portfolio.items():
            if weight > 0.35:
                return BlindSpot(
                    severity="ALERT",
                    title="Heavy Concentration",
                    detail=f"{sym} occupies {weight*100:.1f}% of your portfolio.",
                    action_suggestion="Consider trimming or rebalancing to reduce single-stock risk."
                )
            elif weight > 0.25:
                return BlindSpot(
                    severity="WARNING",
                    title="Concentration Warning",
                    detail=f"{sym} occupies {weight*100:.1f}% of your portfolio.",
                    action_suggestion="Monitor this position closely for signs of reversal."
                )
        
        # Sector check
        sector_weights: Dict[str, float] = {}
        pm = HistoricalPatternMiner()
        for sym, weight in portfolio.items():
            sector = "Other"
            for sname, peers in pm.PEER_GROUPS.items():
                if sym in peers:
                    sector = sname
                    break
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        for sec, sw in sector_weights.items():
            if sw > 0.45:
                return BlindSpot(
                    severity="WARNING",
                    title="Sector Concentration",
                    detail=f"Your exposure to '{sec}' is {sw*100:.1f}%.",
                    action_suggestion="Diversify into other sectors to avoid systemic industry shocks."
                )
        return None

    async def check_ignored_risks(self, symbol: str) -> Optional[BlindSpot]:
        """Surface hidden fundamental red flags."""
        import yfinance as yf
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Severity sorted checks
            debt_to_equity = info.get('debtToEquity', 0)
            if debt_to_equity > 2:
                return BlindSpot(
                    severity="ALERT",
                    title="High Leverage",
                    detail=f"Debt/Equity ratio is {debt_to_equity:.2f}. High debt service costs in a rising rate environment could squeeze margins.",
                    action_suggestion="Review interest coverage ratio and debt maturity schedule."
                )
                
            rev_growth = info.get('revenueGrowth', 0)
            if rev_growth and rev_growth < -0.1:
                return BlindSpot(
                    severity="WARNING",
                    title="Declining Revenue",
                    detail=f"Revenue is declining {abs(rev_growth)*100:.1f}% YoY.",
                    action_suggestion="Verify if this is a cyclical dip or a structural decline in market share."
                )

            short_ratio = info.get('shortRatio', 0)
            if short_ratio > 10:
                return BlindSpot(
                    severity="INFO",
                    title="Heavily Shorted",
                    detail=f"Short ratio is {short_ratio:.2f}. Many market participants are betting against this stock.",
                    action_suggestion="Be aware of potential volatility and 'short squeeze' risks."
                )
        except:
            pass
        return None

    async def run_all_checks(
        self,
        symbol: str,
        analysis: AnalysisResult,
        watchlist_symbols: List[str],
        portfolio: Optional[Dict[str, float]] = None
    ) -> List[BlindSpot]:
        """Run all checks concurrently."""
        tasks = [
            self.check_valuation_vs_sentiment(symbol, analysis),
            self.check_correlation_risk(watchlist_symbols),
            self.check_recency_bias(symbol, analysis),
            self.check_concentration_risk(portfolio or {}),
            self.check_ignored_risks(symbol)
        ]
        
        results = await asyncio.gather(*tasks)
        blind_spots = [b for b in results if b is not None]
        
        # Sort by severity
        severity_map = {"ALERT": 0, "WARNING": 1, "INFO": 2}
        blind_spots.sort(key=lambda x: severity_map.get(x.severity, 3))
        
        return blind_spots
