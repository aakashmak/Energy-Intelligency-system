# CDF Energy AI Hackathon

**Energy Intelligence System**


**Time Limit:** 5 Days
**Format:** Hosted Web App or Dashboard + 5-minute walkthrough video

---

## About This Hackathon

CDF Energy is running this hackathon to identify strong AI engineering talent. This challenge is designed to test your ability to combine data engineering, forecasting, and AI into a working decision-support tool — not just a static dashboard.

Your task is to build an **Energy Intelligence System** focused on U.S. oil and gas production across regions, designed to support investment and business development decisions.

**What we're evaluating:**

| Dimension | Weight | What we're looking for |
|-----------|--------|----------------------|
| AI Integration & Usage | 25% | AI meaningfully enhances analysis or workflow — not just a wrapper around an API. |
| Technical Architecture | 25% | Clear system design, sensible data flow, and structured component thinking. |
| UI/UX & Usability | 20% | Interface helps users make decisions. Clarity and utility matter more than aesthetics. |
| Data Engineering | 15% | Functional data ingestion, cleaning, and handling from public sources. |
| Project Management & Process | 15% | Structured thinking, prioritization decisions, and documentation quality. |

---

## The Challenge

Build a **U.S. Oil & Gas Production Analysis System** — a working decision-support tool that helps a business development analyst evaluate regional production opportunities, forecast future output, and identify high-potential areas to pursue.

The system should ingest real public data, implement a forecasting mechanism, surface meaningful KPIs, and include AI-powered analysis. This is not a dashboard exercise. Think in terms of building something someone would actually use.

**You are free to choose any tech stack, tools, frameworks, or AI agents.** We care about the result, not the specific tools — though we expect you to justify your choices in your documentation.

---

## Requirements

### Tier 1 - Core Requirements (Must Complete)

These are the minimum expectations. A well-built Tier 1 beats a rushed attempt at everything.

#### 1. Data Collection

Pull real production data from publicly available sources.

**Must include:**
- At least one primary public data source (e.g., EIA, state-level production databases)
- Data covering multiple U.S. regions to enable geographic comparison
- You may combine multiple datasets for richer coverage

**Suggested data sources:**
- [EIA Open Data API](https://www.eia.gov/opendata/) — oil and gas production by region, state, and basin
- [EIA Petroleum Supply Monthly](https://www.eia.gov/petroleum/) — historical production volumes
- State oil and gas commission data (e.g., Texas RRC, NDIC for Bakken, COGCC for Colorado)

#### 2. Data Preparation

Structure your data to support analysis and forecasting.

**Must include:**
- Basic cleaning and normalization — consistent region identifiers, time series alignment, handling of missing values
- A structured data layer that your forecasting and UI components can reliably consume
- Focus on usability over perfection — practical and functional beats technically pristine

#### 3. Forecasting Engine

Your system must support year-based forecasting as a core interactive feature.

**Must include:**
- A year selector that allows users to choose any past or future year
- Historical data displayed up to the selected year
- Forecasted values rendered beyond the selected year, clearly distinguished from actuals
- A clearly documented forecasting methodology — the logic must be explainable

**Clarity of approach matters more than model sophistication.** A well-reasoned linear trend beats an unexplained black box.

#### 4. Core KPI Framework

Your system must define and surface KPIs that directly support business development decisions.

**Required KPI:**
- **Projected Production Estimate** — by region and year (or quarter). This KPI must:
  - Combine historical production data with your forecasting logic
  - Update dynamically based on the selected year
  - Be clearly labeled and visually distinct from raw data

**What we're looking for:** KPIs should be clearly defined, surfaced in the UI, and directly answer the question: *"Is this region worth pursuing?"*

#### 5. System Interface

Your system must be delivered as a working, hosted interface.

**Must be one of:**
- A hosted web application (provide the live URL)
- A hosted lightweight dashboard (provide the live URL)

**We do not install or build from submitted code. A live, accessible URL is mandatory.**

The interface must allow users to:
- Explore production data across regions
- View and interact with forecasts via the year selector
- Understand defined KPIs at a glance
- Compare regional opportunities side by side

Tools like Tableau, Power BI, Streamlit, Vercel, or any AI agent are permitted. We value systems that go beyond passive data display.

#### 6. AI Integration

Your system must use AI in a way that adds genuine analytical value.

**Must include:**
- At least one AI-powered feature that goes beyond UI — examples:
  - A conversational interface where analysts can ask questions about regional data and forecasts
  - Auto-generated regional investment summaries based on current KPIs
  - AI-powered anomaly detection that flags unusual production patterns
- The AI must have access to live data you've pulled — it should answer questions grounded in current numbers, not just training data
- AI-generated outputs should clearly distinguish between data-backed claims and model-generated inference

**What we're really evaluating here:**
- Whether AI adds decision-making value, not just conversational novelty
- How you manage context — feeding the right data to the model at the right time
- How you handle the boundary between AI-generated content and verified figures

#### 7. Documentation

Provide a written explanation covering:
- Data sources used and why
- Forecasting approach and its assumptions
- KPI definitions and how each supports a business decision
- System design overview — how components connect
- Key insights surfaced by your system

---

### Tier 2 - Stretch Goals (Differentiators)

Not required, but these will significantly strengthen your submission. Pick the ones that showcase your strengths.

#### Custom KPIs

Define additional KPIs beyond Projected Production Estimate. Strong candidates:

- **Production growth rate** — year-over-year percentage change by region
- **Production decline rate** — rate of output decrease in mature basins
- **Estimated revenue potential** — production volume × commodity price assumptions
- **Consistency / volatility score** — how reliably a region produces across quarters
- **Relative performance index** — how a region ranks against peers over a selected period

Each custom KPI should be clearly defined in your documentation and surfaced in the interface.

#### Excel / Spreadsheet Integration

Demonstrate how your system connects with downstream analyst workflows:

- Export a formula-driven Excel workbook with editable inputs (not just a data dump)
- Show how a business development analyst could extend your output in a familiar tool
- Bonus: structured export that preserves your KPI logic as Excel formulas

#### Sensitivity Analysis

Add an interactive sensitivity view to help analysts stress-test forecasts:

- A matrix or heat map showing how Projected Production Estimate changes across two input variables (e.g., decline rate vs. price assumption)
- Color-coded cells indicating opportunity quality (red = weak, green = strong)
- Tied to the year selector so analysts can explore sensitivities across the forecast horizon

#### Data Provenance

Make every number in your system traceable:

- When a user sees a KPI value or forecast figure, they should be able to identify where it came from
- Include: source API or dataset, last updated timestamp, and a brief description of what the value represents
- This separates a prototype from a production-grade tool

#### Live Data Refresh

Make at least one data source refresh on demand (not just loaded once at startup):

- Show loading states and last-updated timestamps
- Handle API failures gracefully — degrade to cached data with a clear notice rather than a broken UI

---

### Tier 3 - Exceptional (Surprise Us)

We're not going to prescribe what "exceptional" looks like — that's the point. If you have time and a strong idea, show us something we didn't ask for.

---

## Public Data Sources — Quick Reference

| Source | URL | What it provides | Auth |
|--------|-----|-----------------|------|
| **EIA Open Data** | api.eia.gov | Oil and gas production by state, basin, and fuel type | Free API key |
| **EIA Petroleum Supply Monthly** | eia.gov/petroleum | Historical monthly production volumes | Public |
| **Texas RRC** | rrc.texas.gov | Texas-specific well and production data | Public |
| **North Dakota NDIC** | ndic.nd.gov | Bakken and statewide ND production | Public |
| **COGCC** | cogcc.state.co.us | Colorado oil and gas production | Public |
| **FRED** | api.stlouisfed.org | Interest rates, inflation, WTI price history | Free API key |
| **EIA Spot Prices** | eia.gov/dnav/pet | WTI and Brent crude price time series | Public |
| **OpenWeatherMap** | openweathermap.org | Weather/climate context if relevant | Free tier |

---

## What to Submit

All submissions are made by pushing to your designated repository. There is nothing to email or send separately — your repo state at the deadline is your submission.

Before the **5-day deadline**, make sure your submission contains:

1. **Your code or system files** — committed and pushed with a clean history
2. **Documentation** — data sources, forecasting approach, KPI definitions, system design, key insights
3. **Live deployment URL** — mandatory. Must be functional at the deadline. We do not install or run submitted code
4. **5-minute walkthrough video** — link it prominently in your README

**Your video must cover:**
- What you built and why
- How your system works end to end
- Your forecasting approach and its assumptions
- KPI definitions and how they support business decisions
- System walkthrough including the year selector in action
- How you used AI and what value it adds
- Key insights and any investment recommendations surfaced by the system

---

## Evaluation Rubric

### Good
- All Tier 1 requirements are functional
- At least one public data source successfully integrated
- Forecasting mechanism works and is clearly explained
- Required KPI surfaces and updates dynamically
- AI feature adds genuine value beyond decoration
- Live URL works at the deadline

### Great
Everything above, plus 2+ Tier 2 features, custom KPIs clearly defined and surfaced, thoughtful AI prompt engineering, and strong data visualizations that aid decision-making.

### Outstanding
Everything above, plus novel approaches to either forecasting or AI integration, production-quality code, and documentation thorough enough for a new team member to onboard from.

---

## Rules & Guidelines

1. **Use any AI coding tools.** Document your usage in your README.
2. **Free data sources only.** All suggested sources have free or open tiers.
3. **Keep AI API spend reasonable.** API costs are your own responsibility — stick to free tiers where possible.
4. **No proprietary data.** Everything must come from publicly available sources.
5. **Deadline is firm.** A well-built Tier 1 beats a rushed attempt at everything.
6. **A broken or inaccessible deployment is treated the same as no submission.** Test your live URL before the deadline.

---
A NOTE TO ALL PARTICIPANTS
We want to evaluate you more thoroughly, so we are expanding the scope of this challenge.
The deadline has been extended by 2 days — you now have 7 days total from your original start date.
Everything you have already built counts. The additions below extend what you are working on — they do not
replace it. Your existing Tier 1 requirements remain unchanged.

WHAT HAS CHANGED
Two new items have been added to Tier 1 (required). One new item has been added to Tier 2 (stretch).
Addition Tier Summary
Geographic Visualization Tier 1 — Required An interactive map showing regional production
data with clickable regions and at least one data
overlay.

Conversational AI Agent Tier 1 — Required A conversational interface grounded in your live
data — not a generic chatbot, but an analyst that
answers questions about your system's data.
Well Economics Calculator Tier 2 — Stretch An interactive financial model for a single well with

editable inputs and return metrics.

NEW TIER 1 REQUIREMENTS

Geographic Visualization
Add an interactive map to your system showing regional oil and gas production data with geographic context.
Must include:
• An interactive web map — Mapbox GL JS, Leaflet, deck.gl, or similar
• Data points or regions plotted from a public source — e.g., production by state or basin, well locations,
active rig counts
• Clickable markers or regions that surface detail on interaction
• At least one data overlay that helps users compare regions (e.g., average production, relative
performance)
The map must connect to the rest of your system.
Clicking a region should update your forecasting view or KPI panel — not just display a tooltip in isolation.

Additional suggested data sources:
• USGS (usgs.gov) — basin boundaries and resource assessments
• BSEE / BOEM (data.bsee.gov) — federal offshore well and production data

Conversational AI Agent
Upgrade your AI integration into a conversational interface where users can ask analytical questions grounded in
your live data.
Must include:
• A conversational interface where users can ask questions about regional data, forecasts, and KPIs in plain
English
• The AI must have access to the live data you have pulled — it should answer questions grounded in
current numbers, not just training data
• The agent must produce something beyond prose — at minimum: filter a view, surface a specific data
point, or generate a summary based on current KPI values
• AI-generated outputs must clearly distinguish between data-backed claims and model-generated inference
Example interactions your system should handle:
• "Which region has the highest projected production for 2027?"
• "Summarize the opportunity in the Permian Basin based on current data."
• "What happens to my forecast if I assume a 15% steeper decline rate?"
What we're really evaluating here:
• Whether AI adds decision-making value, not just conversational novelty
• How you feed the right data to the model at the right time
• How you handle the boundary between AI-generated content and verified figures

NEW TIER 2 STRETCH GOAL
This is a significant build.
Only attempt it if your Tier 1 is solid and you have time remaining.

Well Economics Calculator
Add an interactive financial model for a single horizontal oil or gas well.
Must include:
• Editable input panel — initial production rate, decline parameters, drilling and completion cost, lease
operating expense, commodity price assumptions
• Calculated output panel — forecasted monthly production, estimated ultimate recovery (EUR), annual
cash flow, NPV at 10%, IRR, payback period
• At least one visualization — production decline curve, cumulative cash flow, or similar
• Calculations must run client-side and update instantly when inputs change
Bonus: connect the calculator to your map so that clicking a region pre-fills reasonable default inputs for that
area.

UPDATED VIDEO REQUIREMENTS
Your 5-minute video must now also cover:
• Your map and how it connects to the rest of the system
• How your conversational AI agent works and what data it has access to
All original video requirements remain.

UPDATED EVALUATION RUBRIC
Good
Everything in the original Good rubric, plus:
• Geographic map is present with at least one data overlay and interactive regions
• Conversational AI agent is functional and answers questions grounded in live data
Great
Everything above, plus:
• Map connects meaningfully to the forecasting or KPI view
• AI agent produces outputs beyond prose — filtered views, summaries, or data-driven responses

Outstanding
Everything above, plus:
• Well Economics Calculator completed and integrated with the map or forecasting view
