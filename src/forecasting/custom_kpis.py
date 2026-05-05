"""
Custom KPI Framework — Tier 2 Stretch Goals.

Implements all 5 custom KPIs defined in the hackathon requirements:

  1. Production Growth Rate      — YoY % change per region
  2. Production Decline Rate     — 12-month rolling decline for mature basins
  3. Estimated Revenue Potential — production × commodity price assumptions
  4. Consistency / Volatility Score — how reliably a region produces
  5. Relative Performance Index  — how a region ranks vs peer average

All KPIs:
  - Accept the prepared DataFrame from prepare_for_analysis()
  - Accept selected_year from the dashboard year selector
  - Return clean numeric values ready for the dashboard
  - Are stored in the Supabase scores table

Default commodity price assumptions (user-adjustable in dashboard):
  WTI crude oil:  $72.00 / barrel  (2024 avg)
  Henry Hub gas:  $2.50  / MMcf    (2024 avg)

Run standalone:
    python -m src.forecasting.custom_kpis
"""

import logging
import warnings
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

REGIONS     = ["Permian", "Bakken", "Eagle Ford", "Appalachia", "Gulf Coast"]
COMMODITIES = ["oil", "gas"]

# ── Default commodity price assumptions ───────────────────────────────────────
# These are used for revenue potential calculations.
# User can override from the dashboard sensitivity panel.
DEFAULT_WTI_PRICE    = 72.00   # $/bbl  — WTI crude oil (2024 annual avg)
DEFAULT_HENRY_PRICE  = 2.50    # $/MMcf — Henry Hub natural gas (2024 annual avg)

# Mbbl → bbl conversion: 1 Mbbl = 1,000 bbl
# Revenue (oil) = value_Mbbl × 1000 × price_per_bbl / 1_000_000  → $M USD
# Revenue (gas) = value_MMcf × price_per_MMcf / 1_000_000        → $M USD


# ── KPI 1: Production Growth Rate ─────────────────────────────────────────────

def compute_growth_rate(
    series: pd.Series,
    selected_year: int,
) -> float:
    """
    Year-over-year production growth rate for the selected year.

    Formula:
        Growth = ((avg_production_Y - avg_production_Y-1) / avg_production_Y-1) × 100

    Uses annual average (not sum) to handle partial years cleanly.

    Args:
        series:        monthly production pd.Series with DatetimeIndex
        selected_year: year chosen by user

    Returns:
        Float percentage. Positive = growing. Negative = shrinking.
        Returns 0.0 if data is unavailable for either year.
    """
    yr    = series[series.index.year == selected_year].dropna()
    yr_m1 = series[series.index.year == selected_year - 1].dropna()

    if yr.empty or yr_m1.empty:
        return 0.0

    avg_yr    = yr.mean()
    avg_yr_m1 = yr_m1.mean()

    if avg_yr_m1 == 0:
        return 0.0

    return round(((avg_yr - avg_yr_m1) / avg_yr_m1) * 100, 2)


# ── KPI 2: Production Decline Rate ────────────────────────────────────────────

def compute_decline_rate(series: pd.Series) -> float:
    """
    12-month rolling production decline rate.

    Measures whether a region's output is structurally declining — key signal
    for mature basins like Bakken where depletion is a concern.

    Formula:
        Decline Rate = ((avg_last_6_months - avg_prior_6_months) /
                        avg_prior_6_months) × 100

    Interpretation:
        Negative = production declining (mature/depleting basin)
        Positive = production growing (active development)
        Near zero = stable output

    Args:
        series: monthly production pd.Series with DatetimeIndex

    Returns:
        Float percentage. Negative means declining.
    """
    recent = series.sort_index().dropna().tail(12)
    if len(recent) < 12:
        return 0.0

    last_6  = recent.tail(6).mean()
    prior_6 = recent.head(6).mean()

    if prior_6 == 0:
        return 0.0

    return round(((last_6 - prior_6) / prior_6) * 100, 2)


# ── KPI 3: Estimated Revenue Potential ────────────────────────────────────────

def compute_revenue_potential(
    df: pd.DataFrame,
    selected_year: int,
    region: str,
    wti_price: float = DEFAULT_WTI_PRICE,
    henry_price: float = DEFAULT_HENRY_PRICE,
) -> dict:
    """
    Estimated annual revenue potential for a region in the selected year.

    Combines oil + gas production forecasts with commodity price assumptions
    to produce a total revenue estimate in millions of USD.

    Formulas:
        Oil Revenue ($M)  = proj_oil_Mbbl × 1000 bbl/Mbbl × wti_price / 1_000_000
        Gas Revenue ($M)  = proj_gas_MMcf × henry_price / 1_000_000
        Total Revenue ($M) = Oil Revenue + Gas Revenue

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        selected_year: year chosen by user
        region:        region name
        wti_price:     WTI crude price $/bbl (default: $72)
        henry_price:   Henry Hub gas price $/MMcf (default: $2.50)

    Returns:
        dict with oil_revenue_m, gas_revenue_m, total_revenue_m,
        wti_price_used, henry_price_used
    """
    from src.forecasting.prophet_model import projected_production

    oil_kpi = projected_production(df, selected_year, region, "oil")
    gas_kpi = projected_production(df, selected_year, region, "gas")

    # Annual total from monthly values
    oil_mbbl_year  = oil_kpi.get("projected_total") or 0.0   # Mbbl/year
    gas_mmcf_year  = gas_kpi.get("projected_total") or 0.0   # MMcf/year

    # Convert to revenue in $M USD
    oil_revenue_m  = round((oil_mbbl_year * 1000 * wti_price)  / 1_000_000, 2)
    gas_revenue_m  = round((gas_mmcf_year * henry_price)        / 1_000_000, 2)
    total_revenue_m = round(oil_revenue_m + gas_revenue_m, 2)

    return {
        "oil_revenue_m":   oil_revenue_m,
        "gas_revenue_m":   gas_revenue_m,
        "total_revenue_m": total_revenue_m,
        "wti_price_used":  wti_price,
        "henry_price_used": henry_price,
    }


# ── KPI 4: Consistency / Volatility Score ─────────────────────────────────────

def compute_consistency_score(series: pd.Series) -> tuple[float, float]:
    """
    Consistency Score (0–100) measuring how reliably a region produces.

    Based on the coefficient of variation (CV = std/mean) over 24 months,
    inverted and scaled so that:
        100 = perfectly consistent (zero variance)
        0   = highly erratic production

    Formula:
        CV = std(last_24_months) / mean(last_24_months)
        Consistency Score = max(0, 100 × (1 - CV))

    Args:
        series: monthly production pd.Series with DatetimeIndex

    Returns:
        (consistency_score, raw_volatility) tuple
        consistency_score: 0–100, higher = more reliable
        raw_volatility:    raw CV value for reference
    """
    recent = series.sort_index().dropna().tail(24)
    if len(recent) < 6:
        return 0.0, 1.0

    mean = recent.mean()
    std  = recent.std()

    if mean == 0:
        return 0.0, 1.0

    cv    = std / mean
    score = round(max(0.0, 100.0 * (1.0 - cv)), 1)
    return score, round(cv, 4)


# ── KPI 5: Relative Performance Index ─────────────────────────────────────────

def compute_relative_performance(
    all_series: dict[str, pd.Series],
    region: str,
    selected_year: int,
) -> float:
    """
    Relative Performance Index — how a region ranks vs its peers.

    Measures a region's average production relative to the peer group
    average over the selected year, normalized to a 0–100 index where:
        100 = highest producing region
        0   = lowest producing region
        50  = exactly at peer average

    Formula:
        peer_avg = mean of all region averages for selected_year
        rel_perf = (region_avg / peer_avg) × 50
        clamped to [0, 100]

    Args:
        all_series:    dict of {region_name: monthly pd.Series}
        region:        region to compute index for
        selected_year: year to evaluate

    Returns:
        Float 0–100. Above 50 = outperforming peers.
    """
    year_avgs = {}
    for r, s in all_series.items():
        yr = s[s.index.year == selected_year].dropna()
        if not yr.empty:
            year_avgs[r] = yr.mean()

    if not year_avgs or region not in year_avgs:
        return 50.0   # no data — assume average

    peer_avg   = np.mean(list(year_avgs.values()))
    region_avg = year_avgs[region]

    if peer_avg == 0:
        return 50.0

    rel = (region_avg / peer_avg) * 50.0
    return round(min(100.0, max(0.0, rel)), 1)


# ── Master: compute all custom KPIs ───────────────────────────────────────────

def compute_custom_kpis(
    df: pd.DataFrame,
    selected_year: int,
    wti_price: float = DEFAULT_WTI_PRICE,
    henry_price: float = DEFAULT_HENRY_PRICE,
) -> pd.DataFrame:
    """
    Compute all 5 Tier 2 custom KPIs for all regions.

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        selected_year: year chosen by user (dashboard year selector)
        wti_price:     WTI crude price $/bbl — user adjustable
        henry_price:   Henry Hub gas price $/MMcf — user adjustable

    Returns:
        DataFrame with one row per region and columns:
        [region, growth_rate, decline_rate, revenue_potential_m,
         consistency_score, volatility, rel_performance,
         wti_price_used, henry_price_used]
    """
    logger.info(
        f"Computing custom KPIs | year={selected_year} | "
        f"WTI=${wti_price}/bbl | HH=${henry_price}/MMcf"
    )

    # Pre-build all oil series for relative performance calculation
    all_oil_series = {}
    for region in REGIONS:
        s = df[
            (df["region"] == region) & (df["commodity"] == "oil")
        ].set_index("period")["value"].sort_index()
        if not s.empty:
            all_oil_series[region] = s

    rows = []
    for region in REGIONS:
        oil_series = all_oil_series.get(region, pd.Series(dtype=float))

        if oil_series.empty:
            logger.warning(f"No oil data for {region} — using defaults")
            rows.append({
                "region":              region,
                "growth_rate":         0.0,
                "decline_rate":        0.0,
                "revenue_potential_m": 0.0,
                "consistency_score":   0.0,
                "volatility":          1.0,
                "rel_performance":     50.0,
                "wti_price_used":      wti_price,
                "henry_price_used":    henry_price,
            })
            continue

        # ── KPI 1: Growth Rate ─────────────────────────────────────────────
        growth = compute_growth_rate(oil_series, selected_year)

        # ── KPI 2: Decline Rate ────────────────────────────────────────────
        decline = compute_decline_rate(oil_series)

        # ── KPI 3: Revenue Potential ───────────────────────────────────────
        rev = compute_revenue_potential(df, selected_year, region, wti_price, henry_price)

        # ── KPI 4: Consistency Score ───────────────────────────────────────
        consistency, volatility = compute_consistency_score(oil_series)

        # ── KPI 5: Relative Performance Index ─────────────────────────────
        rel_perf = compute_relative_performance(all_oil_series, region, selected_year)

        rows.append({
            "region":              region,
            "growth_rate":         growth,
            "decline_rate":        decline,
            "revenue_potential_m": rev["total_revenue_m"],
            "consistency_score":   consistency,
            "volatility":          volatility,
            "rel_performance":     rel_perf,
            "wti_price_used":      wti_price,
            "henry_price_used":    henry_price,
        })

        logger.info(
            f"  {region:<15} | "
            f"growth={growth:+.1f}% | "
            f"decline={decline:+.1f}% | "
            f"revenue=${rev['total_revenue_m']:.0f}M | "
            f"consistency={consistency:.0f}/100 | "
            f"rel_perf={rel_perf:.0f}/100"
        )

    result = pd.DataFrame(rows).sort_values("revenue_potential_m", ascending=False)
    result = result.reset_index(drop=True)
    return result


def save_custom_kpis_to_db(
    custom_df: pd.DataFrame,
    scores_df: pd.DataFrame,
) -> int:
    """
    Merge custom KPIs into the scores DataFrame and save to Supabase.

    Args:
        custom_df: output of compute_custom_kpis()
        scores_df: output of compute_all_scores() from scoring.py

    Returns:
        Number of rows written to Supabase scores table
    """
    from src.data.db import upsert_scores

    if custom_df.empty:
        logger.warning("save_custom_kpis_to_db: custom_df empty — skipping")
        return 0

    # Merge custom KPIs into scores on region
    if not scores_df.empty:
        merged = scores_df.merge(
            custom_df[[
                "region", "decline_rate", "revenue_potential_m",
                "consistency_score", "rel_performance",
                "wti_price_used", "henry_price_used",
            ]],
            on="region",
            how="left",
        )
        # Rename to match schema column names
        merged = merged.rename(columns={
            "revenue_potential_m": "revenue_potential",
        })
    else:
        # No base scores — build minimal scores from custom KPIs
        merged = custom_df.rename(columns={
            "growth_rate":         "yoy_growth",
            "revenue_potential_m": "revenue_potential",
        })
        merged["score"] = 0.0
        merged["rank"]  = 0
        merged["projected_prod"] = 0.0
        merged["momentum"] = 0.0

    merged["computed_at"] = pd.Timestamp.now().isoformat()

    total = upsert_scores(merged)
    logger.info(f"Saved {total} rows with custom KPIs to Supabase scores table")
    return total


def run_custom_kpis(
    df: pd.DataFrame,
    selected_year: int,
    scores_df: pd.DataFrame = None,
    wti_price: float = DEFAULT_WTI_PRICE,
    henry_price: float = DEFAULT_HENRY_PRICE,
) -> pd.DataFrame:
    """
    Full custom KPI run — compute all 5 KPIs and save to Supabase.

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        selected_year: year chosen by user
        scores_df:     base scores DataFrame from scoring.py (optional)
        wti_price:     WTI price $/bbl (default $72)
        henry_price:   Henry Hub price $/MMcf (default $2.50)

    Returns:
        Custom KPIs DataFrame
    """
    custom_df = compute_custom_kpis(df, selected_year, wti_price, henry_price)
    if scores_df is None:
        scores_df = pd.DataFrame()
    save_custom_kpis_to_db(custom_df, scores_df)
    return custom_df


# ── Standalone run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    from src.data.db import read_production
    from src.data.prepare import prepare_for_analysis
    from src.forecasting.scoring import compute_all_scores

    logger.info("Loading data from Supabase ...")
    raw = read_production()
    if raw.empty:
        logger.error("No data — run pipeline.py first")
        sys.exit(1)

    df            = prepare_for_analysis(raw)
    selected_year = datetime.now().year

    # Run base scores first
    scores_df = compute_all_scores(df, selected_year)

    # Run all 5 custom KPIs
    custom_df = run_custom_kpis(df, selected_year, scores_df)

    print(f"\n── Custom KPIs ({selected_year}) ──")
    print(f"  Prices used: WTI=${DEFAULT_WTI_PRICE}/bbl | HH=${DEFAULT_HENRY_PRICE}/MMcf")
    print()
    cols = ["region", "growth_rate", "decline_rate",
            "revenue_potential_m", "consistency_score", "rel_performance"]
    print(custom_df[cols].to_string(index=False))
