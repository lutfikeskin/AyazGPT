---
name: streamlit-dashboard
description: Expert in Streamlit UI architecture for this project.
---
# Streamlit Dashboard

**Trigger:** "dashboard", "UI", "streamlit", "görsel", "chart"

**Description:**
Knows the Streamlit UI architecture for this project.
- Uses `st.cache_data(ttl=3600)` for all API calls.
- Calls FastAPI backend at `http://localhost:8000/api/investment/`.
- **Plotly for charts:** Candlestick + volume + EMA lines in one figure.
- **Layout:** Sidebar (watchlist + timeframe) → Main (analysis) → Tabs (digest, Q&A, macro).
- **Error Handling:** `st.error()` for API failures, `st.spinner()` for loading states.

Module pages live in `ui/pages/{module_name}.py`, auto-discovered by `ui/app.py`.
