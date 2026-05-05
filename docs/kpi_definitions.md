# KPI Definitions — OilPulse

All KPIs surfaced in the dashboard. Each includes calculation logic, data source, and the business decision it supports.

---

## Tier 1 — Required KPI

### Projected Production Estimate

**Definition:** Total estimated oil or gas production for a region in the user-selected year.
Units: Thousand Barrels/year (oil) · Million Cubic Feet/year (gas)

**Calculation:**
- Selected year ≤ latest real data → sum of actual monthly EIA values
- Selected year > latest real data → sum of SARIMA-forecasted monthly values

**Confidence labels:**
- High — actual data exists
- Medium — forecast 1–2 years beyond last real data
- Low — forecast 3+ years beyond last real data

**Business decision:** "How much can we expect from this region in year X?" — core input for investment sizing and capital allocation.

---

## Tier 2 — Custom KPIs

### 1. Production Growth Rate

**Definition:** Year-over-year percentage change in average monthly production.

**Formula:**
```
Growth Rate = ((avg_production_Y - avg_production_Y-1) / avg_production_Y-1) × 100
```

Uses annual average (not sum) to handle partial years cleanly.

**Interpretation:**
- Positive = region is growing → strong candidate for new investment
- Negative = region is shrinking → investigate before committing capital
- Zero = stable output → mature, predictable basin

**Business decision:** Identifies which regions have development momentum vs. which are past peak. A region with +15% YoY growth signals active well development and rising operator confidence.

---

### 2. Production Decline Rate

**Definition:** 12-month rolling decline rate — rate at which output is changing over the most recent 12 months.

**Formula:**
```
Decline Rate = ((avg_last_6_months - avg_prior_6_months) / avg_prior_6_months) × 100
```

Compares the most recent 6-month average to the preceding 6-month average.

**Interpretation:**
- Negative = basin is declining (mature, depletion exceeding new completions)
- Positive = basin is growing (new wells offsetting or exceeding depletion)
- Near zero = output is plateauing

**Business decision:** Critical for mature basins like Bakken where natural depletion rates are high. A steep decline rate signals a region needs constant new drilling just to maintain output — higher operating risk.

---

### 3. Estimated Revenue Potential

**Definition:** Estimated annual revenue from a region based on projected production × commodity price assumptions.

**Formulas:**
```
Oil Revenue ($M) = Projected Oil (Mbbl/yr) × 1,000 bbl/Mbbl × WTI Price ($/bbl) ÷ 1,000,000
Gas Revenue ($M) = Projected Gas (MMcf/yr) × Henry Hub Price ($/MMcf) ÷ 1,000,000
Total Revenue ($M) = Oil Revenue + Gas Revenue
```

**Default price assumptions (user-adjustable in dashboard):**
- WTI Crude Oil: $72.00/bbl (2024 annual average)
- Henry Hub Natural Gas: $2.50/MMcf (2024 annual average)

**Business decision:** Translates physical production into financial terms — the language of investment decisions. Allows direct comparison of regions on a revenue basis, not just volume. Users can stress-test by adjusting price assumptions in the sensitivity panel.

---

### 4. Consistency / Volatility Score

**Definition:** A 0–100 score measuring how reliably a region produces month over month. Higher = more consistent.

**Formula:**
```
CV (Coefficient of Variation) = std(last 24 months) / mean(last 24 months)
Consistency Score = max(0, 100 × (1 - CV))
```

**Interpretation:**
- 90–100 = extremely consistent (e.g., Appalachia conventional gas)
- 70–89 = reliable with minor seasonal variation
- 50–69 = moderate variability — review before long-term commitments
- Below 50 = high variability — elevated production risk

**Business decision:** Two regions with identical revenue potential but different consistency scores represent very different risk profiles. A low-consistency region may require larger financial buffers to manage uncertain cash flows.

---

### 5. Relative Performance Index

**Definition:** How a region's production compares to the average of all 5 peer regions, expressed as a 0–100 index.

**Formula:**
```
peer_avg = mean of all region annual averages for selected year
Relative Performance = (region_avg / peer_avg) × 50
Clamped to [0, 100]
```

**Interpretation:**
- 100 = highest producing region (top of peer group)
- 50 = exactly at peer average
- 0 = lowest producing region
- Above 50 = outperforming peers
- Below 50 = underperforming peers

**Business decision:** Provides relative context — a region may have strong absolute production but still lag peers. Useful for portfolio allocation decisions: favor regions consistently above 60 for core positions, explore below-50 regions only with a specific thesis.

---

## Composite Investment Score

**Definition:** A 0–100 weighted score combining Growth Rate, Momentum, and Stability (inverse of volatility) into a single investment attractiveness ranking.

**Formula:**
```
Score = (YoY Growth normalized × 0.40)
      + (Momentum normalized × 0.30)
      + (Stability normalized × 0.30)
      × 100
```

All inputs min-max normalized to 0–1 before weighting. Score then scaled to 0–100.

**Latest scores (2026):**
| Rank | Region | Score |
|---|---|---|
| 1 | Eagle Ford | 78.2 |
| 2 | Gulf Coast | 73.1 |
| 3 | Appalachia | 69.4 |
| 4 | Bakken | 40.6 |
| 5 | Permian | 40.1 |

---

## Forecasting Methodology

### Model: SARIMA(1,1,1)(1,1,0)[12]

**What it is:** Seasonal AutoRegressive Integrated Moving Average — the industry standard for monthly energy time series forecasting. Used by the EIA itself for its Short-Term Energy Outlook.

**Parameter meanings:**

| Parameter | Value | Plain English |
|---|---|---|
| p=1 | AR(1) | Uses last month's production to predict next month |
| d=1 | I(1) | Removes the long-run upward trend via differencing |
| q=1 | MA(1) | Corrects for the previous month's forecast error |
| P=1 | SAR(1) | Uses the same month last year (seasonal pattern) |
| D=1 | SI(1) | Removes yearly seasonal trend |
| Q=0 | SMA(0) | No seasonal moving average — keeps model stable |
| s=12 | Period | 12-month cycle (yearly production seasonality) |

**In plain English:**
> "To forecast Permian oil production for next month, SARIMA looks at this month's production level, the same month last year, and corrects for how wrong last month's forecast was. It chains this logic forward for up to 36 months."

**Forecast horizon:** 36 months beyond the selected year
**Confidence intervals:** 80% prediction bands (shown as shaded area on chart)
**Training data:** Full EIA history from 2015 to latest available month

**Assumptions and limitations:**
- Assumes historical seasonal and trend patterns continue
- Does not model price shocks, regulatory changes, or geopolitical events
- Confidence degrades beyond 18 months — labeled accordingly in UI
- Model is re-fit on each pipeline run using latest available data

---

## Data Provenance

| Table | Source | Columns | Updated |
|---|---|---|---|
| `production` | EIA Petroleum Supply Monthly (oil) + EIA Natural Gas Monthly (gas) | region, commodity, period, value, process_name, product_name | Monthly |
| `state_production` | Same, state level | state, commodity, period, value, process_code, product_code | Monthly |
| `forecasts` | SARIMA model output | region, commodity, period, forecast, lower_ci, upper_ci | On demand |
| `scores` | Computed from production + forecasts | All 5 custom KPIs + composite score | On demand |
