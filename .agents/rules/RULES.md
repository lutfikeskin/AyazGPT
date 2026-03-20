---
trigger: always_on
---

# MyMind — Project Rules for Antigravity Agents

## Project Identity

- Name: MyMind — Modular Personal AI Assistant
- Active module: investment (personal investment advisor, NOT a trading bot)
- Stack: Python 3.11, FastAPI, PostgreSQL, Redis, Streamlit
- AI layer: Claude API (claude-sonnet-4-20250514) + RAG (ChromaDB local)
- Single user, personal use — no multi-tenancy, no auth complexity needed

## Architecture Principles

- MODULAR FIRST: every feature lives inside /modules/{name}/. Never put business logic in /core/ or /api/
- Each module is a self-contained Python package implementing BaseModule
- New modules must NOT break existing ones — test with `pytest modules/` before completing any task
- Core layer is infrastructure only: DB, cache, config, module registry

## Code Standards

- Type hints on every function signature — no bare `def func(x):`
- Async by default for I/O: use `async def` + `await` for all DB and HTTP calls
- Use loguru for all logging — never print() in production code
- Error handling: catch specific exceptions, never bare `except:`
- All secrets via pydantic-settings from .env — never hardcode API keys
- Write docstrings on every class and public method

## Data Layer Rules

- Time-series data (prices, indicators) → TimescaleDB hypertables
- Text/documents (news, reports) → ChromaDB vector store
- Hot/computed data → Redis (TTL always set, never infinite)
- Raw API responses → never stored as-is, always transform to domain models first
- Migrations: use Alembic, never ALTER TABLE manually

## AI / LLM Rules

- LLM is synthesis only — never call Claude for data that can be computed deterministically
- Always pass structured context (ContextPackage dataclass) to LLM, never raw strings
- Every LLM prompt lives in prompts.py as a named constant — never inline prompt strings
- LLM responses must be validated with Pydantic before use
- Log all LLM calls: token count, latency, model used

## Investment Module Specific

- This is a PERSONAL ADVISOR, not a trading bot — never generate "buy/sell" signals
- Always include uncertainty: every analysis must have a `confidence_level` field
- Always show the bear case, even for bullish signals ("what_i_might_be_missing")
- Data freshness: always show `data_as_of` timestamp in every response
- Turkish stocks use .IS suffix (THYAO.IS), validate symbol format before any API call

## Agent Behavior

- Plan before coding: always output a task list artifact before writing code
- One feature per mission — don't bundle unrelated changes
- After completing a mission: run relevant tests, show file tree diff, confirm health check passes
- If a library install fails: try pip install --user before escalating
- Never delete existing files without explicit user confirmation
- Docker services (postgres, redis) may be running — check with `docker ps` before starting new containers

## File Structure (enforce this, never deviate)

mymind/
├── core/ # Infrastructure only
├── modules/
│ └── investment/ # Active module
│ ├── collectors/
│ ├── analysis/
│ ├── ai/
│ └── routes.py
├── ui/ # Streamlit
├── tests/
├── scripts/
├── docker-compose.yml
└── .env.example # Never .env itself

## Quality Gates (agent must pass before marking task done)

1. `python -m pytest tests/ -x` passes
2. `python -m mypy modules/ --ignore-missing-imports` no errors
3. FastAPI app starts: `uvicorn api.main:app` without exceptions
4. /health endpoint returns 200
