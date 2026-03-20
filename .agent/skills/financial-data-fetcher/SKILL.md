---
name: financial-data-fetcher
description: Expert in fetching financial data from yfinance, NewsAPI, and FRED.
---
# Financial Data Fetcher

**Trigger:** "fetch data", "get prices", "collect market data", "haber çek"

**Description:**
Knows how to correctly fetch financial data from yfinance, NewsAPI, FRED API.
Handles Turkish stock symbols (.IS suffix), gold (GC=F), silver (SI=F), USDTRY=X.
Always validates symbols, handles rate limits with exponential backoff, stores results to TimescaleDB market_prices hypertable.
Key patterns: async httpx for NewsAPI/FRED, yfinance.download() for bulk OHLCV, always include error handling and logging with loguru.
Never fetch data synchronously in a FastAPI endpoint — use background tasks.
