# Planning Document

## Tech Stack

**Framework / Language:** Python 3.11 + Streamlit (frontend) + FastAPI (backend API)

> Streamlit gives a hosted web app in minimal code — ideal for 5-day constraint. FastAPI provides clean REST endpoints that decouple the data/AI layer from the UI, making the architecture easy to explain and extend. Python is the only reasonable choice given the data science libs needed.

**Key Libraries:**
- `duckdb` — embedded columnar DB; zero infra, fast analytical queries, perfect for time-series
- `pandas` — data cleaning and transformation
- `prophet` — Facebook's forecasting library; handles seasonality and missing data better than ARIMA; easy to explain to a judge
- `plotly` — interactive charts in Streamlit
- `folium` + `streamlit-folium` — U.S. choropleth map
- `langchain` + `openai` — LLM agent with SQL tool (answers NL questions over live DB)
- `requests` + `python-dotenv` — EIA API client and env management

**AI Provider:** OpenAI GPT-4o via LangChain `SQLDatabaseChain`

> GPT-4o chosen for reasoning quality on structured data queries. LangChain's SQL chain lets the model query the actual DuckDB database, making every AI answer grounded in real ingested numbers — not training data. This directly satisfies the "AI must have access to live data" requirement.

---

## Phases & Priorities

| Phase | Target Dates | Goals |
|-------|-------------|-------|
| 1 — Data | Day 1 | EIA API ingestion, DuckDB schema, validation, pipeline.py running clean |
| 2 — Forecast + Score | Day 2 | Prophet model per region/commodity, investment scoring engine, scores table populated |
| 3 — API + AI | Day 3 | FastAPI endpoints (/forecast, /regions, /score, /chat), LangChain SQL agent wired |
| 4 — Dashboard | Day 4 | Streamlit app: map, KPI cards, forecast chart, drilldown, AI chat panel |
| 5 — Deploy + Docs | Day 5 | Streamlit Cloud deploy, README URL, architecture.md, kpi_definitions.md, reflection.md, video |

---

## What I'll Cut If Time Is Short

**First to cut:** Texas RRC / NDIC state-level supplements. EIA basin series covers all 5 regions adequately. State CSVs are enrichment.

**Second to cut:** Excel export (Tier 2 stretch). Useful but not scored in Tier 1.

**Last to cut:** AI chat panel. It's 25% of the score and the clearest differentiator — it stays even if the UI is rough.

**Never cut:** Live deployment URL. A broken or missing URL = zero submission per the rules.

---

## Open Questions / Risks

| Risk | Mitigation |
|------|-----------|
| EIA basin-level series IDs return empty / deprecated | Fallback series (statewide) already coded in eia_fetcher.py |
| Prophet install fails on Windows (Stan compiler) | Use `prophet` via `pystan` or switch to `statsmodels` ARIMA as fallback |
| OpenAI API costs spike | Use GPT-3.5-turbo for chat, GPT-4o only for investment summaries |
| Streamlit Cloud free tier cold-start slow | Add a spinner + "Loading data…" state; cache with `@st.cache_data` |
| EIA API rate limits | Add `time.sleep(0.5)` between series fetches; 5000-row pagination handles bulk |
