# MyMind — Modular Personal AI Assistant

MyMind is a modular personal AI assistant designed to help with information synthesis and decision-making.

## Project Structure

- `core/`: Shared infrastructure (DB, Cache, Registry, BaseModule).
- `modules/`: pluggable backend modules (e.g., `investment`).
- `api/`: FastAPI application server.
- `ui/`: Streamlit dashboard.
- `tests/`: Module and integration tests.

## Features (Active Modules)

### Investment Module
- Personal investment advisor (not a trading bot).
- Focus on BIST and Global stocks, Commodities, and Macro.
- Uses Gemini API for deep context synthesis.

## Getting Started

1. **Setup Environment**:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY
   ```

2. **Run Infrastructure**:
   ```bash
   docker-compose up -d
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start Backend**:
   ```bash
   uvicorn api.main:app --reload
   ```

5. **Start UI**:
   ```bash
   streamlit run ui/app.py
   ```

## Development

Run tests with:
```bash
pytest tests/
```
