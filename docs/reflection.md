# Reflection

## What I Built

**OilPulse** is a full-stack Energy Intelligence System for U.S. oil and gas investment analysis. Below is a feature-by-feature status summary.

### What works

| Feature | Status |
|---------|--------|
| EIA data ingestion (production by basin/commodity, 1995–present) | ✅ Functional |
| SARIMA(1,1,1)(1,1,0)[12] forecasting engine — per region/commodity | ✅ Functional |
| Year selector (1995–2030) — actuals up to selected year, forecast beyond | ✅ Functional |
| **MapTab** — Mapbox GL interactive map, basin markers, production overlay, click-to-select | ✅ Functional |
| **ScoresTab** — Regional investment scores; YoY growth, decline rate, revenue potential, consistency score, relative performance index | ✅ Functional |
| **RigsTab** — Active rig count charts (Baker Hughes data via EIA) | ✅ Functional |
| **ValidationTab** — SARIMA back-test: fitted vs. actuals, MAPE by region | ✅ Functional |
| **ColoradoTab** — COGCC deep-dive: formation breakdown, operator rankings, decline curves | ✅ Functional |
| **WellEconTab** — Well economics calculator: editable IP/decline/LOE/D&C inputs → EUR, NPV@10%, IRR, payback, decline curve chart | ✅ Functional |
| **SensitivityTab** — 2-variable sensitivity heat map (e.g., decline rate × price) | ✅ Functional |
| **ChatBot** — Conversational AI agent grounded in live basin data (Groq / llama-3.3-70b) | ✅ Functional |
| Region-presets API — map click pre-fills WellEcon defaults for selected basin | ✅ Functional |
| Data provenance — source, series ID, last-updated timestamps surfaced per endpoint | ✅ Functional |
| Cyber-premium glassmorphism UI — obsidian theme, neon-indigo accents, sparklines, radial gauges | ✅ Functional |

### What has limitations

| Item | Limitation |
|------|-----------|
| Live deployment URL | Not yet deployed — **submit before deadline**. Backend needs Railway/Render; frontend needs Vercel/Netlify. |
| Walkthrough video | Not yet recorded — see `docs/walkthrough.md`. |
| Excel export | Not built — dropped as a Tier 2 item to keep Tier 1 solid. |
| EIA rate limits | Data is ingested once and stored to Supabase; real-time EIA polling is not implemented. The "Refresh" button triggers a re-fetch from Supabase (near-real-time), not a new EIA call. |
| SARIMA per-region model cold start | First forecast request for a new region/year combination runs SARIMA fit (~1–2 s). Subsequent calls hit the Supabase cache. |

---

## What I'd Do Differently

**1. Deploy earlier.**
The deployment was left until the end. If I had deployed at Day 2 (even with stub data), I would have surfaced environment variable mismatches, CORS issues, and cold-start latency problems well before the deadline.

**2. Keep the original Prophet + LangChain stack or fully commit to the replacement earlier.**
Switching from Prophet → SARIMA and LangChain → direct Groq partway through cost roughly half a day of refactoring. If I had validated the deployment environment (Windows + no Stan compiler) on Day 1, I would have chosen SARIMA from the start.

**3. Separate the data ingestion pipeline from the API.**
`api/main.py` currently handles both ingestion logic and API serving. A cleaner split would be `pipeline/ingest.py` (run once, writes to Supabase) and `api/main.py` (read-only). This would make the codebase easier to hand off and test independently.

**4. Add skeleton loading states from the start.**
Several tabs show a blank panel while React Query fetches data. Adding skeleton cards on Day 1 (before real data was wired up) would have made the loading experience feel polished throughout development, not just at the end.

**5. Write documentation incrementally.**
`architecture.md` and `reflection.md` were left to the final push. Writing a bullet point per tab as each was completed would have produced richer, more accurate docs with less recall effort at the end.

---

## AI Tools Used

| Tool | How it was used |
|------|----------------|

| **Groq (llama-3.3-70b-versatile)** | Deployed as the in-product AI feature. Powers the OilPulse ChatBot — answers analyst questions grounded in live basin data injected via the system prompt. |
| **EIA Open Data API** | Primary data source; not an AI tool, but the API responses were formatted and interpreted with Claude's help to map the correct series IDs to basin/commodity pairs. |

The most valuable use of Claude was iterative UI debugging — describing a visual goal ("Bloomberg Terminal meets Vercel") and having Claude translate that into concrete React/CSS changes. Without that feedback loop, the UI polish would have taken 2–3× longer.
