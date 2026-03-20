import pandas as pd
import numpy as np
from sqlalchemy import select
from loguru import logger
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

from core.database import AsyncSessionLocal
from modules.investment.models import MarketPrice
from modules.investment.analysis.schemas import RiskAnalysisResult

class RiskAnalyzer:
    def __init__(self):
        pass

    async def get_price_series(self, symbol: str, timeframe: str) -> pd.Series:
        async with AsyncSessionLocal() as session:
            days_map = {'1W': 7, '1M': 30, '3M': 90, '1Y': 365, '5Y': 1825}
            days = days_map.get(timeframe, 365)
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = select(MarketPrice.timestamp, MarketPrice.close).where(
                MarketPrice.symbol == symbol,
                MarketPrice.timestamp >= cutoff
            ).order_by(MarketPrice.timestamp.asc())
            
            result = await session.execute(query)
            rows = result.all()
            
            if not rows:
                return pd.Series(dtype=float)
                
            df = pd.DataFrame(rows, columns=['timestamp', 'close'])
            df.set_index('timestamp', inplace=True)
            return df['close']

    async def analyze(self, symbol: str, timeframe: str) -> RiskAnalysisResult:
        close_prices = await self.get_price_series(symbol, timeframe)
        
        if close_prices.empty or len(close_prices) < 10:
            return RiskAnalysisResult(
                symbol=symbol, timeframe=timeframe,
                volatility=0.0, max_drawdown=0.0,
                sharpe_ratio=0.0, var_95=0.0, beta=None
            )
            
        returns = close_prices.pct_change().dropna()
        if returns.empty:
            return RiskAnalysisResult(
                symbol=symbol, timeframe=timeframe,
                volatility=0.0, max_drawdown=0.0,
                sharpe_ratio=0.0, var_95=0.0, beta=None
            )
            
        # Volatility (annualized)
        daily_vol = returns.std()
        ann_vol = daily_vol * np.sqrt(252)
        
        # Max Drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        max_dd = drawdowns.min()
        
        # Sharpe (rf=0.05)
        rf = 0.05
        ann_return = returns.mean() * 252
        sharpe = (ann_return - rf) / ann_vol if ann_vol > 0 else 0.0
        
        # VaR 95% historical
        var_95 = float(np.percentile(returns, 5))
        
        # Beta
        benchmark_symbol = "XU100.IS" if symbol.endswith(".IS") else "SPY"
        benchmark_prices = await self.get_price_series(benchmark_symbol, timeframe)
        
        beta = None
        if not benchmark_prices.empty and len(benchmark_prices) > 10:
            bench_returns = benchmark_prices.pct_change().dropna()
            
            aligned = pd.concat([returns, bench_returns], axis=1, join='inner').dropna()
            if not aligned.empty and len(aligned) > 10:
                cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1]
                var_bench = np.var(aligned.iloc[:, 1])
                if var_bench > 0:
                    beta = float(cov / var_bench)

        return RiskAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            volatility=float(ann_vol),
            max_drawdown=float(max_dd),
            sharpe_ratio=float(sharpe),
            var_95=var_95,
            beta=beta
        )
        
    async def correlation_matrix(self, symbols: List[str], timeframe: str) -> Dict[str, Dict[str, float]]:
        series_dict = {}
        for sym in symbols:
            s = await self.get_price_series(sym, timeframe)
            if not s.empty:
                series_dict[sym] = s
                
        if len(series_dict) < 2:
            return {}
            
        df = pd.DataFrame(series_dict)
        df = df.ffill().dropna()
        daily_returns = df.pct_change().dropna()
        
        corr = daily_returns.corr()
        return corr.to_dict()
