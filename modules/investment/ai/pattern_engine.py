import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Literal
from sqlalchemy import text
from loguru import logger

from core.database import AsyncSessionLocal
from modules.investment.ai.schemas import SimilarSetupResult, MacroTrigger, SectorDivergence

class HistoricalPatternMiner:
    """
    Scans historical data for technical setups and macro correlations.
    """

    # Mapping for UI display and peer analysis
    PEER_GROUPS = {
        "Bankalar": ["AKBNK.IS","GARAN.IS","ISCTR.IS","YKBNK.IS","VAKBN.IS","HALKB.IS","SKBNK.IS","TSKB.IS"],
        "Sanayi": ["EREGL.IS","KRDMD.IS","SISE.IS","PETKM.IS","CIMSA.IS","BUCIM.IS","CEMTS.IS","IZMDC.IS"],
        "Enerji": ["TUPRS.IS","AKSEN.IS","ENKAI.IS","ENJSA.IS","ZOREN.IS","ODAS.IS","GWIND.IS"],
        "Perakende": ["BIMAS.IS","MGROS.IS","SOKM.IS","MAVI.IS"],
        "Havacılık": ["THYAO.IS","PGSUS.IS","TAVHL.IS","CLEBI.IS"],
        "Otomotiv": ["FROTO.IS","TOASO.IS","OTKAR.IS","DOAS.IS","ASUZU.IS"],
        "Holdingler": ["KCHOL.IS","SAHOL.IS","DOHOL.IS","ALARK.IS","GSDHO.IS"],
        "Savunma & Teknoloji": ["ASELS.IS","SDTTR.IS","MIATK.IS","REEDR.IS","KORDS.IS"],
        "Gıda & Kimya": ["SASA.IS","HEKTS.IS","GUBRF.IS","AEFES.IS","CCOLA.IS","TATGD.IS"],
        "Gayrimenkul": ["EKGYO.IS","ISGYO.IS","SNGYO.IS","TRGYO.IS"],
        "Telekom": ["TCELL.IS","TTKOM.IS"],
        "Global Teknoloji": ["AAPL","MSFT","GOOGL","NVDA","META","AMZN","TSLA","AVGO","ORCL"],
        "Global Finans": ["JPM","GS","BAC","MS","BRK-B"],
        "Emtia & FX": ["GC=F","SI=F","CL=F","NG=F","USDTRY=X","EURUSD=X"]
    }

    async def _get_historical_data(self, symbol: str, days: int = 3650) -> pd.DataFrame:
        """Fetch historical price data from database."""
        query = text("""
            SELECT timestamp, open, high, low, close, volume
            FROM market_prices
            WHERE symbol = :symbol
            AND timestamp > NOW() - (:days * INTERVAL '1 day')
            ORDER BY timestamp ASC
        """)
        async with AsyncSessionLocal() as session:
            result = await session.execute(query, {"symbol": symbol, "days": days})
            df = pd.DataFrame(result.fetchall(), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            return df

    async def scan_similar_setups(self, symbol: str, current_indicators: dict) -> SimilarSetupResult:
        """
        Search last 10 years for dates where this symbol had a similar technical setup.
        """
        df = await self._get_historical_data(symbol, days=3650)
        if df.empty or len(df) < 60:
            return SimilarSetupResult(
                total_similar_setups=0, base_rate_positive=0, median_1m_return=0, median_3m_return=0,
                worst_case_pct=0, best_case_pct=0, sample_dates=[], confidence='low'
            )

        # Calculate indicators for historical data
        import pandas_ta as ta
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['vol_avg20'] = df['volume'].rolling(window=20).mean()
        
        curr_rsi = current_indicators.get('rsi', 50)
        curr_trend = current_indicators.get('trend', 'bullish') # bullish if price > ema50
        curr_vol_avg = current_indicators.get('volume_avg_20', df['volume'].iloc[-1])

        # Define similarity mask
        # 1. RSI within ±8
        rsi_mask = (df['rsi'] >= curr_rsi - 8) & (df['rsi'] <= curr_rsi + 8)
        
        # 2. Same trend direction
        if curr_trend == 'bullish':
            trend_mask = df['close'] > df['ema50']
        else:
            trend_mask = df['close'] <= df['ema50']
            
        # 3. Volume within ±30%
        vol_mask = (df['volume'] >= curr_vol_avg * 0.7) & (df['volume'] <= curr_vol_avg * 1.3)

        similar_dates = df[rsi_mask & trend_mask & vol_mask].index.tolist()
        
        # Filter out very recent dates (within last 3 months) to allow for forward return calculation
        cutoff = df.index[-1] - timedelta(days=90)
        similar_dates = [d for d in similar_dates if d < cutoff]

        results_1m = []
        results_3m = []
        worst_cases = []
        best_cases = []
        
        for d in similar_dates:
            try:
                # Find the index of the date
                idx = df.index.get_loc(d)
                price_at_d = df['close'].iloc[idx]
                
                # Forward windows (approx 21 trading days for 1M, 63 for 3M)
                fwd_idx_1m = min(idx + 21, len(df)-1)
                fwd_idx_3m = min(idx + 63, len(df)-1)
                
                ret_1m = (df['close'].iloc[fwd_idx_1m] - price_at_d) / price_at_d
                ret_3m = (df['close'].iloc[fwd_idx_3m] - price_at_d) / price_at_d
                
                window_3m = df['close'].iloc[idx:fwd_idx_3m+1]
                worst = (window_3m.min() - price_at_d) / price_at_d
                best = (window_3m.max() - price_at_d) / price_at_d
                
                results_1m.append(ret_1m)
                results_3m.append(ret_3m)
                worst_cases.append(worst)
                best_cases.append(best)
            except:
                continue

        count = len(results_1m)
        if count == 0:
            return SimilarSetupResult(
                total_similar_setups=0, base_rate_positive=0, median_1m_return=0, median_3m_return=0,
                worst_case_pct=0, best_case_pct=0, sample_dates=[], confidence='low'
            )

        base_rate = len([r for r in results_1m if r > 0]) / count
        
        confidence: Literal['high', 'medium', 'low'] = 'low'
        if count > 15: confidence = 'high'
        elif count >= 5: confidence = 'medium'

        return SimilarSetupResult(
            total_similar_setups=count,
            base_rate_positive=base_rate,
            median_1m_return=float(np.median(results_1m)),
            median_3m_return=float(np.median(results_3m)),
            worst_case_pct=float(np.min(worst_cases)),
            best_case_pct=float(np.max(best_cases)),
            sample_dates=[d.date() if hasattr(d, 'date') else d for d in similar_dates[-5:]],
            confidence=confidence
        )

    async def detect_macro_triggers(self, symbol: str, timeframe: str) -> List[MacroTrigger]:
        """
        Correlate historical price drops/spikes (>3%) with macro events.
        """
        df = await self._get_historical_data(symbol, days=1825) # 5 years
        if df.empty or len(df) < 5:
            return []

        df['pct_change'] = df['close'].pct_change()
        big_move_dates = df[df['pct_change'].abs() > 0.03].index.tolist()
        
        if not big_move_dates:
            return []

        # Fetch macro events
        macro_query = text("""
            SELECT indicator, timestamp, value
            FROM macro_indicators
            WHERE timestamp > NOW() - INTERVAL '5 years'
            ORDER BY timestamp ASC
        """)
        
        async with AsyncSessionLocal() as session:
            m_result = await session.execute(macro_query)
            m_df = pd.DataFrame(m_result.fetchall(), columns=['indicator', 'timestamp', 'value'])
        
        if m_df.empty:
            return []
            
        m_df['timestamp'] = pd.to_datetime(m_df['timestamp'])
        
        # Define events
        triggers: Dict[str, List[datetime]] = {} # indicator -> list of events
        
        # 1. Rate changes
        for ind in ['TCMB_POLICY_RATE', 'FRED_FEDFUNDS']:
            ind_df = m_df[m_df['indicator'] == ind].copy()
            if not ind_df.empty:
                ind_df['diff'] = ind_df['value'].diff()
                changes = ind_df[ind_df['diff'] != 0].dropna()
                for _, row in changes.iterrows():
                    etype = "TCMB rate hike" if row['diff'] > 0 else "TCMB rate cut"
                    if ind == 'FRED_FEDFUNDS':
                        etype = "FED rate hike" if row['diff'] > 0 else "FED rate cut"
                    
                    if etype not in triggers: triggers[etype] = []
                    triggers[etype].append(row['timestamp'])

        # 2. USDTRY spikes
        usd_df = m_df[m_df['indicator'] == 'FRED_DEXTHUS'].copy()
        if not usd_df.empty:
            usd_df['pct'] = usd_df['value'].pct_change()
            spikes = usd_df[usd_df['pct'] > 0.02]
            if not spikes.empty:
                etype = "USDTRY spike"
                if etype not in triggers: triggers[etype] = []
                triggers[etype].extend(spikes['timestamp'].tolist())

        # 3. CPI releases (monthly)
        cpi_df = m_df[m_df['indicator'] == 'FRED_CPIAUCSL'].copy()
        if not cpi_df.empty:
            etype = "CPI Release"
            if etype not in triggers: triggers[etype] = []
            triggers[etype].extend(cpi_df['timestamp'].tolist())

        macro_triggers = []
        
        for etype, event_dates in triggers.items():
            impacts = []
            occurrences = 0
            last_occ = None
            
            # Check if big moves happened near these event dates
            for edate in event_dates:
                # Look for price data around edate ± 3 days
                start = edate - timedelta(days=3)
                end = edate + timedelta(days=3)
                window = df.loc[start:end] # type: ignore
                
                if not window.empty:
                    # avg impact within 3 days after
                    post_window = df.loc[edate:edate+timedelta(days=3)] # type: ignore
                    if not post_window.empty:
                        impact = (post_window['close'].iloc[-1] - df['close'].asof(edate)) / df['close'].asof(edate)
                        impacts.append(impact)
                        occurrences += 1
                        last_occ = edate.date()

            if occurrences > 0:
                avg_impact = float(np.mean(impacts))
                # Correlation check: how many big moves are explained by this etype
                total_big_moves = len(big_move_dates)
                explained = 0
                for bdate in big_move_dates:
                    if any(abs((bdate - edate).days) <= 3 for edate in event_dates):
                        explained += 1
                
                desc = f"{symbol} moved avg {avg_impact*100:.1f}% near {etype} events. Explained {explained}/{total_big_moves} major moves."
                
                macro_triggers.append(MacroTrigger(
                    event_type=etype,
                    avg_price_impact_pct=avg_impact,
                    occurrences=occurrences,
                    last_occurrence=last_occ or date.today(),
                    description=desc
                ))

        return macro_triggers

    async def find_sector_divergence(self, symbol: str) -> SectorDivergence:
        """
        Compare symbol's 1M and 3M performance against its sector peers.
        """
        # Identify sector
        peers = []
        sector_name = None
        for sname, plist in self.PEER_GROUPS.items():
            if symbol in plist:
                sector_name = sname
                peers = [p for p in plist if p != symbol]
                break
        
        if sector_name in ["commodities", "fx", "crypto"]:
            return SectorDivergence(
                symbol_1m_return=0, 
                peers_avg_1m_return=0, 
                divergence_score=0,
                divergence_type='inline', 
                is_significant=False, 
                peer_symbols=[],
                note="No peer comparison available for this asset class"
            )

        if not peers:
            # Fallback
            return SectorDivergence(
                symbol_1m_return=0, 
                peers_avg_1m_return=0, 
                divergence_score=0,
                divergence_type='inline', 
                is_significant=False, 
                peer_symbols=[]
            )

        # Get returns for symbol and peers
        async def get_return(s: str, days: int) -> float:
            df = await self._get_historical_data(s, days=days+10)
            if df.empty or len(df) < 2: return 0.0
            p_start = df['close'].asof(df.index[-1] - timedelta(days=days))
            p_end = df['close'].iloc[-1]
            return float((p_end - p_start) / p_start)

        sym_ret_1m = await get_return(symbol, 30)
        
        peer_rets = await asyncio.gather(*[get_return(p, 30) for p in peers])
        peers_avg = float(np.mean(peer_rets)) if peer_rets else 0.0
        
        div_score = sym_ret_1m - peers_avg
        
        div_type: Literal['outperforming', 'underperforming', 'inline'] = 'inline'
        if div_score > 0.03: div_type = 'outperforming'
        elif div_score < -0.03: div_type = 'underperforming'
        
        return SectorDivergence(
            symbol_1m_return=sym_ret_1m,
            peers_avg_1m_return=peers_avg,
            divergence_score=div_score,
            divergence_type=div_type,
            is_significant=abs(div_score) > 0.1,
            peer_symbols=peers
        )
