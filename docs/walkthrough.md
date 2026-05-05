# Walkthrough Video

**Video Link:** https://www.loom.com/share/457a45b8dca44a8abbc47dd4b20b54cd

> Record ~5 minutes. Use the script below as a guide. No editing needed — one continuous take is fine.

---

## Recording Script (~5 min)

### 0:00 — Opening (20 s)
*Show the live dashboard URL in the browser address bar.*

> "This is OilPulse — an Energy Intelligence System I built for the CDF hackathon. It ingests real EIA production data across five U.S. basins, runs SARIMA forecasting out to 2030, surfaces investment KPIs, and includes a conversational AI analyst grounded in live numbers. Let me walk through it."

---

### 0:20 — Map Tab (1 min)
*Open the Map tab. Click a basin marker (e.g., Permian).*

> "The map shows all five basins — Permian, Bakken, DJ Basin, Eagle Ford, and Haynesville. Each marker is sized and colored by projected production for the selected year. Clicking Permian updates the sidebar and pre-fills the Well Economics calculator with Permian-specific defaults."

*Change the year selector from 2025 to 2028.*

> "Changing the year selector to 2028 re-queries the forecast endpoint and re-colors the map in real time. Blue markers are oil basins; amber are gas-dominant."

---

### 1:20 — Scores Tab and KPIs (1 min)
*Open Scores tab. Point out the regional score table.*

> "The Scores tab surfaces five Tier-2 KPIs on top of the required Projected Production Estimate: YoY Growth Rate, Decline Rate, Revenue Potential, Consistency Score, and Relative Performance Index. Each has a sparkline showing the trailing 24-month trend. These answer the core question: is this region worth pursuing right now?"

*Point to the highest-ranked basin.*

> "Permian is top-ranked on revenue potential and consistency — low volatility, high sustained output."

---

### 2:20 — Forecasting and Validation (45 s)
*Open Validation tab.*

> "All forecasts use SARIMA(1,1,1)(1,1,0)[12] — a seasonal ARIMA model fit independently per region and commodity. This table shows the back-test: SARIMA fitted values versus actual EIA production. MAPEs are under 8% across most basins, which is solid for a monthly production series with irregular supply disruptions."

*Scroll to a chart showing actuals vs. fitted.*

> "The shaded area beyond the selected year is forecast. Actuals are solid lines; forecast is dashed. The distinction is always explicit — I never blend them."

---

### 3:05 — AI Chat (45 s)
*Click the floating chat button. Type: "Which region has the highest projected oil production in 2027?"*

> "The chatbot is a conversational analyst backed by Groq's llama-3.3-70b model. Before calling the model, the backend injects a live data snapshot: current production figures and SARIMA forecasts for the selected year across all five basins. So this answer is grounded in real numbers, not training data."

*Wait for response. Point out the data-backed answer.*

> "Every factual claim cites a number from that live data block. If the model infers something beyond the data, it flags it with 'Model inference:' — the UI highlights those sentences in amber so users know when to apply judgment."

---

### 3:50 — Well Economics Calculator (30 s)
*Open WellEcon tab. Change IP rate or price assumption.*

> "The Well Economics calculator runs entirely client-side. Enter IP rate, decline parameters, D&C cost, LOE, and price — it instantly outputs EUR, NPV@10%, IRR, and payback period, plus a full decline curve. All Permian defaults were pre-filled from when I clicked that basin on the map."

---

### 4:20 — Sensitivity Analysis + Close (40 s)
*Open Sensitivity tab. Point to the heat map.*

> "The sensitivity heat map stress-tests the NPV across two variables simultaneously — for example, decline rate on one axis and price assumption on the other. Green cells are strong opportunities; red are marginal at best. This helps an analyst understand how fragile a thesis is before committing capital."

*Back to map tab for the closing shot.*

> "Everything connects: map selection pre-fills well economics, year selector propagates to map, scores, and validation simultaneously, and the AI agent has access to all of it. That's OilPulse."

---

## Video Checklist

Before uploading, confirm the video covers:

- [ ] Live URL visible in browser address bar
- [ ] Year selector changed at least once (shows forecast updating)
- [ ] Map region click demonstrated
- [ ] At least one KPI explained
- [ ] SARIMA methodology mentioned
- [ ] AI chatbot demonstrated with a real question and data-backed answer
- [ ] Distinction between data-backed AI claims and model inference
- [ ] Well Economics calculator shown
- [ ] Key investment insight stated (which region and why)
