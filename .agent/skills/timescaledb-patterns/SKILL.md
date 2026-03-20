---
name: timescaledb-patterns
description: Expert in TimescaleDB SQL patterns for time-series data.
---

# TimescaleDB Patterns

**Trigger:** "timescale", "time series query", "hypertable", "zaman serisi"

**Description:**
Expert in TimescaleDB SQL patterns for this project.
Knows the schema:

- market_prices(symbol, timestamp, open, high, low, close, volume)
- news_items(id, title, body, published_at, sentiment_score, symbols_mentioned)
- macro_indicators(indicator, timestamp, value)

Uses time_bucket() for aggregations, date_trunc() for periods.
Rolling window queries for 1W/1M/3M/1Y/5Y comparisons.
Always uses parameterized queries, never string formatting for SQL.
