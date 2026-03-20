import yfinance as yf # type: ignore
from loguru import logger
from typing import Optional

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
            quality_score=score
        )
