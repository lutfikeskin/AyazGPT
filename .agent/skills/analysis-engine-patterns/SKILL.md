---
name: analysis-engine-patterns
description: Expert in technical, fundamental, and sentiment analysis patterns.
---
# Analysis Engine Patterns

**Trigger:** "technical analysis", "RSI", "MACD", "sentiment score", "temel analiz", "risk"

**Description:**
Knows the analysis layer architecture.
- **TechnicalAnalyzer:** Uses pandas_ta (NOT TA-Lib).
- **FundamentalAnalyzer:** Fetches from yfinance .info dict; always check key existence before access.
- **SentimentAnalyzer:** Uses ProsusAI/finbert from HuggingFace, runs in thread pool executor.
- **RiskAnalyzer:** Uses PyPortfolioOpt for MPT calculations.

All analyzers cache results in Redis with key pattern: analysis:{symbol}:{timeframe}, TTL 3600.
Returns typed dataclasses, never raw dicts.
