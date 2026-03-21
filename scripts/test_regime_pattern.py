import asyncio
from datetime import datetime, timezone
from modules.investment.ai.pattern_engine import HistoricalPatternMiner
from modules.investment.ai.schemas import MarketRegime

async def check():
    print("Testing Regime-Aware Pattern Mining...")
    miner = HistoricalPatternMiner()
    
    symbol = "THYAO.IS"
    indicators = {
        "rsi": 45,
        "trend": "bullish",
        "volume_avg_20": 10000000 
    }
    
    from modules.investment.ai.market_regime import MarketRegimeDetector
    detector = MarketRegimeDetector()
    current_regime = await detector.detect_regime()
    
    print(f"\nScanning for {symbol} with regime: {current_regime.regime}")
    print(f"Signals used by regime detector: {current_regime.signals_used}")
    result = await miner.scan_similar_setups(symbol, indicators, current_regime)
    
    print("\nResults:")
    print(f"Total Matches (Before Regime Filter): {result.total_similar_setups}")
    print(f"Regime Filtered Matches: {result.regime_filtered_count}")
    print(f"Match Rate: {result.regime_match_rate}")
    print(f"Confidence: {result.confidence}")
    print(f"Median 1M Return: {result.median_1m_return * 100:.2f}%")
    
    if result.regime_filtered_count is not None and result.regime_filtered_count > 0:
        print("\nTest PASSED! Successfully fetched historical macro data and filtered dates by regime.")
    else:
        print("\nNote: No matches found, but execution completed without errors (which is mathematically possible). Check db data.")

if __name__ == "__main__":
    asyncio.run(check())
