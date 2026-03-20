---
name: docker-dev-setup
description: Expert in the dev environment setup using Docker, Alembic, and FastAPI.
---
# Docker Dev Setup

**Trigger:** "docker", "postgres", "redis", "setup", "kurulum", "başlat"

**Description:**
Knows the dev environment setup.
- **`docker-compose.yml` components:**
  - `timescale/timescaledb-ha:pg16` on port 5432.
  - `Redis 7` on port 6379.
- **Commands:**
  - **Start:** `docker-compose up -d postgres redis`
  - **Check:** `docker ps`, `docker logs mymind-postgres-1`
  - **DB Migrations:** `alembic upgrade head`
  - **Seed symbols:** `python scripts/seed_watchlist.py`
  - **Streamlit:** `streamlit run ui/app.py --server.port 8501` (separate terminal)
  - **FastAPI:** `uvicorn api.main:app --reload` on port 8000
  - **Test data fetch:** `python -m modules.investment.collectors.market_collector --symbol THYAO.IS --test`
