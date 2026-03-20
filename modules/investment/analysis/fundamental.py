import yfinance as yf # type: ignore
import borsapy as bp
from loguru import logger
from typing import Optional, Dict, Any, List
import pandas as pd

from modules.investment.analysis.schemas import FundamentalAnalysisResult

class FundamentalAnalyzer:
    def __init__(self):
        pass
        
    async def analyze(self, symbol: str) -> FundamentalAnalysisResult:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
        except Exception as e:
            logger.error(f"Error fetching fundamental data for {symbol}: {e}")
            info = {}

        def safe_get(key: str) -> Optional[float]:
            val = info.get(key)
            if val is not None and val != 'Infinity' and val != 'NaN':
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None
            return None

        pe = safe_get('trailingPE')
        pb = safe_get('priceToBook')
        ev_ebitda = safe_get('enterpriseToEbitda')
        debt_equity = safe_get('debtToEquity')
        roe = safe_get('returnOnEquity')
        rev_growth = safe_get('revenueGrowth')
        fcf = safe_get('freeCashflow')
        market_cap = safe_get('marketCap')
        current_price = safe_get('currentPrice') or safe_get('previousClose')
        
        fcf_yield = None
        dcf_fair_value = None
        vs_current_price_pct = None
        
        if fcf is not None and market_cap is not None and market_cap > 0:
            fcf_yield = fcf / market_cap
            
            # Simple DCF: 5% growth, 5 years, terminal mutiple 15x, discount 10%
            if fcf > 0:
                discounted_fcf_sum = 0.0
                projected_fcf = fcf
                for n in range(1, 6):
                    projected_fcf *= 1.05
                    discounted_fcf_sum += projected_fcf / (1.10 ** n)
                
                terminal_value = projected_fcf * 15
                discounted_tv = terminal_value / (1.10 ** 5)
                
                total_ev = discounted_fcf_sum + discounted_tv
                if current_price and current_price > 0:
                    shares_out = market_cap / current_price
                    dcf_fair_value = total_ev / shares_out
                    vs_current_price_pct = ((dcf_fair_value - current_price) / current_price) * 100
        
        # Calculate a basic quality score 0-10
        score = 5
        if roe and roe > 0.15: score += 1
        if roe and roe < 0: score -= 1
        if debt_equity and debt_equity < 100: score += 1
        if debt_equity and debt_equity > 200: score -= 1
        if fcf_yield and fcf_yield > 0.05: score += 1
        if pe and pe < 20: score += 1
        if pe and pe > 40: score -= 1
        if rev_growth and rev_growth > 0.10: score += 1
        
        score = max(0, min(10, int(score)))
        
        # Part A — borsapy Analyst Data Integration
        analyst_data = self._fetch_analyst_data(symbol)
        
        metrics = {
            "P/E": pe,
            "P/B": pb,
            "EV/EBITDA": ev_ebitda,
            "Debt/Equity": debt_equity,
            "ROE": roe,
            "FCF": fcf,
            "Revenue_Growth": rev_growth,
            "FCF_Yield": fcf_yield
        }
        
        return FundamentalAnalysisResult(
            symbol=symbol,
            metrics=metrics,
            dcf_fair_value=dcf_fair_value,
            vs_current_price_pct=vs_current_price_pct,
            quality_score=score,
            **analyst_data
        )

    def _fetch_analyst_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch analyst data from borsapy.
        Symbol conversion: "THYAO.IS" → "THYAO"
        """
        if not symbol.endswith(".IS"):
            return {}
            
        try:
            clean = symbol.replace(".IS", "")
            hisse = bp.Ticker(clean)
            
            res = {}
            
            # 1. Price Targets
            targets = hisse.analyst_price_targets
            if targets is not None and not (isinstance(targets, pd.DataFrame) and targets.empty):
                # If targets is DataFrame (common in financial libs)
                if isinstance(targets, pd.DataFrame):
                    # Try English keys first, then Turkish if any
                    for mean_key in ['mean', 'target_mean', 'Ortalama']:
                        if mean_key in targets.columns:
                            res["analyst_target_mean"] = float(targets[mean_key].iloc[0])
                            break
                    for high_key in ['high', 'target_high', 'En Yüksek']:
                        if high_key in targets.columns:
                            res["analyst_target_high"] = float(targets[high_key].iloc[0])
                            break
                    for low_key in ['low', 'target_low', 'En Düşük']:
                        if low_key in targets.columns:
                            res["analyst_target_low"] = float(targets[low_key].iloc[0])
                            break
                    for count_key in ['count', 'analyst_count', 'Adet']:
                        if count_key in targets.columns:
                            res["analyst_count"] = int(targets[count_key].iloc[0])
                            break
                else:
                    # If it's an object with attributes
                    res["analyst_target_mean"] = getattr(targets, 'mean', None)
                    res["analyst_target_high"] = getattr(targets, 'high', None)
                    res["analyst_target_low"] = getattr(targets, 'low', None)
                    res["analyst_count"] = getattr(targets, 'count', None)

            # 2. Recommendations Summary
            recs = hisse.recommendations_summary
            if recs is not None and not (isinstance(recs, pd.DataFrame) and recs.empty):
                if isinstance(recs, pd.DataFrame):
                    # borsapy uses AL, TUT, SAT usually
                    al = float(recs['AL'].iloc[0]) if 'AL' in recs.columns else 0
                    tut = float(recs['TUT'].iloc[0]) if 'TUT' in recs.columns else 0
                    sat = float(recs['SAT'].iloc[0]) if 'SAT' in recs.columns else 0
                    total = al + tut + sat
                    if total > 0:
                        res["buy_pct"] = (al / total) * 100
                        if al > tut and al > sat:
                            res["recommendation_consensus"] = "buy"
                        elif tut > sat:
                            res["recommendation_consensus"] = "hold"
                        else:
                            res["recommendation_consensus"] = "sell"
                else:
                    # Object fallback
                    res["recommendation_consensus"] = getattr(recs, 'consensus', None)
                    res["buy_pct"] = getattr(recs, 'buy_pct', None)

            # 3. Earnings Dates
            earnings = hisse.earnings_dates
            if isinstance(earnings, list) and len(earnings) > 0:
                res["next_earnings_date"] = str(earnings[0])
            
            return res
            
        except Exception as e:
            logger.warning(f"borsapy fetch failed for {symbol}: {e}")
            return {}
