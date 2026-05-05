"""
Scoring Engine — Tier 1 Requirement 4 (Core KPI Framework).

Computes all KPIs for each region and writes to the Supabase scores table.
Called after the forecasting engine runs.

KPIs computed:
  1. projected_prod  — Projected Production Estimate (Tier 1 required)
  2. yoy_growth      — Year-over-year % change
  3. momentum        — 6-month vs 12-month avg ratio
  4. volatility      — Coefficient of variation (24-month)
  5. score           — Composite investment score (0–100)
  6. rank            — Region rank by composite score

Run standalone:
    python -m src.forecasting.scoring
"""

import logging
import warnings
import pandas as pd
import numpy as np
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

REGIONS     = ["Permian", "Bakken", "Eagle Ford", "Appalachia", "Gulf Coast"]
COMMODITIES = ["oil", "gas"]

# Composite score weights — must sum to 1.0
WEIGHT_YOY_GROWTH = 0.40
WEIGHT_MOMENTUM   = 0.30
WEIGHT_STABILITY  = 0.30   # stability = 1 - volatility


def compute_yoy_growth(series: pd.Series, selected_year: int) -> float:
    """
    Year-over-year growth rate for the selected year vs prior year.
    Formula: ((year_Y_avg - year_Y1_avg) / year_Y1_avg) * 100
    Returns percentage as a float, or 0.0 if data unavailable.
    """
    yr    = series[series.index.year == selected_year]
    yr_m1 = series[series.index.year == selected_year - 1]

    if yr.empty or yr_m1.empty:
        return 0.0

    avg_yr   = yr.mean()
    avg_yr_m1 = yr_m1.mean()

    if avg_yr_m1 == 0:
        return 0.0

    return round(((avg_yr - avg_yr_m1) / avg_yr_m1) * 100, 2)


def compute_momentum(series: pd.Series) -> float:
    """
    Momentum = (6-month trailing avg / 12-month trailing avg) - 1
    Positive = accelerating, Negative = decelerating.
    Uses the most recent available months.
    """
    recent = series.sort_index().dropna().tail(12)
    if len(recent) < 6:
        return 0.0

    avg_6  = recent.tail(6).mean()
    avg_12 = recent.mean()

    if avg_12 == 0:
        return 0.0

    return round((avg_6 / avg_12) - 1, 4)


def compute_volatility(series: pd.Series) -> float:
    """
    Volatility = std / mean over trailing 24 months (coefficient of variation).
    Lower = more stable production = better for investment.
    """
    recent = series.sort_index().dropna().tail(24)
    if len(recent) < 6:
        return 1.0   # max volatility if insufficient data

    mean = recent.mean()
    std  = recent.std()

    if mean == 0:
        return 1.0

    return round(std / mean, 4)


def compute_projected_production(
    df: pd.DataFrame,
    selected_year: int,
    region: str,
    commodity: str = "oil",
) -> float:
    """
    Projected annual production for a region/commodity in selected_year.
    Uses actual data if available, SARIMA forecast otherwise.
    Returns annual total (sum of monthly values).
    """
    from src.forecasting.prophet_model import projected_production
    kpi = projected_production(df, selected_year, region, commodity)
    return kpi.get("projected_total") or 0.0


def _minmax_normalize(series: pd.Series) -> pd.Series:
    """Normalize a series to 0–1 range. Handles constant series."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - mn) / (mx - mn)


def compute_all_scores(df: pd.DataFrame, selected_year: int) -> pd.DataFrame:
    """
    Compute all KPIs and composite investment score for all regions.

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        selected_year: year chosen by user (dashboard year selector)

    Returns:
        DataFrame with columns:
        [region, score, rank, yoy_growth, momentum, volatility,
         projected_prod, computed_at]
    """
    logger.info(f"Computing scores for selected_year={selected_year} ...")
    rows = []

    for region in REGIONS:
        # Use oil as primary commodity for scoring (main investment metric)
        oil_series = df[
            (df["region"] == region) & (df["commodity"] == "oil")
        ].set_index("period")["value"].sort_index()

        if oil_series.empty:
            logger.warning(f"No oil data for {region} — skipping scoring")
            continue

        # ── KPI 1: YoY Growth ─────────────────────────────────────────────
        yoy = compute_yoy_growth(oil_series, selected_year)

        # ── KPI 2: Momentum ───────────────────────────────────────────────
        momentum = compute_momentum(oil_series)

        # ── KPI 3: Volatility ─────────────────────────────────────────────
        volatility = compute_volatility(oil_series)

        # ── KPI 4: Projected Production (Tier 1 required) ─────────────────
        proj_prod = compute_projected_production(df, selected_year, region, "oil")

        rows.append({
            "region":       region,
            "yoy_growth":   yoy,
            "momentum":     momentum,
            "volatility":   volatility,
            "projected_prod": proj_prod,
        })

    if not rows:
        logger.error("No scores computed — no oil data found")
        return pd.DataFrame()

    scores_df = pd.DataFrame(rows)

    # ── Composite score (0–100) ────────────────────────────────────────────
    # Normalize each KPI to 0–1, then weight and scale to 100
    scores_df["norm_yoy"]      = _minmax_normalize(scores_df["yoy_growth"])
    scores_df["norm_momentum"] = _minmax_normalize(scores_df["momentum"])
    scores_df["norm_stability"]= _minmax_normalize(-scores_df["volatility"])  # lower vol = better

    scores_df["score"] = (
        scores_df["norm_yoy"]       * WEIGHT_YOY_GROWTH +
        scores_df["norm_momentum"]  * WEIGHT_MOMENTUM   +
        scores_df["norm_stability"] * WEIGHT_STABILITY
    ) * 100

    scores_df["score"] = scores_df["score"].round(1)

    # ── Rank ──────────────────────────────────────────────────────────────
    scores_df["rank"] = scores_df["score"].rank(
        ascending=False, method="min"
    ).astype(int)

    scores_df["computed_at"] = pd.Timestamp.now().isoformat()

    # Clean up normalized columns
    scores_df = scores_df.drop(
        columns=["norm_yoy", "norm_momentum", "norm_stability"]
    )

    scores_df = scores_df.sort_values("rank").reset_index(drop=True)

    logger.info(
        f"Scores computed for {len(scores_df)} regions:\n"
        + scores_df[["region", "score", "rank", "yoy_growth", "momentum"]].to_string(index=False)
    )
    return scores_df


def save_scores_to_db(scores_df: pd.DataFrame) -> int:
    """Write scores DataFrame to Supabase scores table."""
    from src.data.db import upsert_scores

    if scores_df.empty:
        logger.warning("save_scores_to_db: nothing to save")
        return 0

    rows = upsert_scores(scores_df)
    logger.info(f"Saved {rows} score rows to Supabase")
    return rows


def run_scoring(df: pd.DataFrame, selected_year: int) -> pd.DataFrame:
    """
    Full scoring run — compute all KPIs and save to Supabase.

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        selected_year: year chosen by user

    Returns:
        Scores DataFrame
    """
    scores = compute_all_scores(df, selected_year)
    if not scores.empty:
        save_scores_to_db(scores)
    return scores


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    from src.data.db import read_production
    from src.data.prepare import prepare_for_analysis

    logger.info("Loading data from Supabase ...")
    raw = read_production()
    if raw.empty:
        logger.error("No data — run pipeline.py first")
        sys.exit(1)

    df            = prepare_for_analysis(raw)
    selected_year = datetime.now().year

    scores = run_scoring(df, selected_year)

    print(f"\n── Investment Scores ({selected_year}) ──")
    print(scores[["rank", "region", "score", "yoy_growth",
                  "momentum", "volatility", "projected_prod"]].to_string(index=False))
