"""
Quarterly KPI Engine — Tier 1 Requirement 3 + 4.

Produces KPI indicators for every region × year × quarter combination.
This satisfies the hackathon requirement:
  "Projected Production Estimate — by region and year (or quarter)"

Quarter definitions (calendar year):
  Q1 = Jan, Feb, Mar
  Q2 = Apr, May, Jun
  Q3 = Jul, Aug, Sep
  Q4 = Oct, Nov, Dec

For each (region, commodity, year, quarter) the engine produces:
  - projected_production   — actual if data exists, SARIMA forecast otherwise
  - is_forecast            — True when SARIMA was used
  - confidence             — high / medium / low
  - qoq_growth             — quarter-over-quarter % change
  - yoy_growth             — same quarter vs same quarter last year
  - lower_ci               — 80% confidence interval lower bound
  - upper_ci               — 80% confidence interval upper bound
  - data_type              — "actual" | "forecast"

Run standalone:
    python -m src.forecasting.quarterly_kpis
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

QUARTER_MONTHS = {
    "Q1": [1, 2, 3],
    "Q2": [4, 5, 6],
    "Q3": [7, 8, 9],
    "Q4": [10, 11, 12],
}


# ── Helper: month → quarter label ─────────────────────────────────────────────

def _month_to_quarter(month: int) -> str:
    if month <= 3:  return "Q1"
    if month <= 6:  return "Q2"
    if month <= 9:  return "Q3"
    return "Q4"


def _quarter_start_month(quarter: str) -> int:
    return {"Q1": 1, "Q2": 4, "Q3": 7, "Q4": 10}[quarter]


# ── Get full forecast series (actuals + SARIMA) ───────────────────────────────

def _get_full_series(
    df: pd.DataFrame,
    region: str,
    commodity: str,
    selected_year: int,
) -> pd.DataFrame:
    """
    Build a complete monthly series combining actuals up to selected_year
    and SARIMA forecasts beyond, for the given region/commodity.

    Returns DataFrame with columns:
      [period, value, lower_ci, upper_ci, is_forecast, data_type]
    """
    from src.forecasting.prophet_model import split_by_year

    actuals, forecast = split_by_year(df, selected_year, region, commodity)

    frames = []

    if not actuals.empty:
        a = actuals[["period", "value"]].copy()
        a["lower_ci"]   = a["value"]   # actuals have no CI — use value itself
        a["upper_ci"]   = a["value"]
        a["is_forecast"] = False
        a["data_type"]   = "actual"
        frames.append(a)

    if not forecast.empty:
        f = forecast[["period", "value"]].copy()
        f["lower_ci"]   = forecast.get("lower_ci", forecast["value"])
        f["upper_ci"]   = forecast.get("upper_ci", forecast["value"])
        f["is_forecast"] = True
        f["data_type"]   = "forecast"
        frames.append(f)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values("period").reset_index(drop=True)
    return result


# ── Aggregate monthly → quarterly ─────────────────────────────────────────────

def _aggregate_to_quarters(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate a monthly series into quarterly totals.

    For each quarter:
      - value     = SUM of monthly values (total quarterly production)
      - lower_ci  = SUM of lower_ci
      - upper_ci  = SUM of upper_ci
      - is_forecast = True if ANY month in the quarter is a forecast
      - data_type   = "forecast" if any month is forecast, else "actual"

    Returns DataFrame with columns:
      [year, quarter, value, lower_ci, upper_ci, is_forecast, data_type]
    """
    if monthly_df.empty:
        return pd.DataFrame()

    df = monthly_df.copy()
    df["year"]    = df["period"].dt.year
    df["quarter"] = df["period"].dt.month.map(_month_to_quarter)

    agg = df.groupby(["year", "quarter"]).agg(
        value       = ("value",       "sum"),
        lower_ci    = ("lower_ci",    "sum"),
        upper_ci    = ("upper_ci",    "sum"),
        is_forecast = ("is_forecast", "any"),
        months      = ("value",       "count"),
    ).reset_index()

    agg["data_type"] = agg["is_forecast"].map({True: "forecast", False: "actual"})

    # Only include complete quarters (3 months)
    agg = agg[agg["months"] == 3].drop(columns=["months"])

    # Quarter sort order
    q_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    agg["_qsort"] = agg["quarter"].map(q_order)
    agg = agg.sort_values(["year", "_qsort"]).drop(columns=["_qsort"]).reset_index(drop=True)

    return agg


# ── QoQ and YoY growth for quarterly data ─────────────────────────────────────

def _add_growth_rates(quarterly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add quarter-over-quarter (QoQ) and year-over-year (YoY) growth rates
    to a quarterly DataFrame.

    QoQ = (this_quarter - prev_quarter) / prev_quarter × 100
    YoY = (this_quarter - same_quarter_last_year) / same_quarter_last_year × 100
    """
    df = quarterly_df.copy()
    df["qoq_growth"] = None
    df["yoy_growth"] = None

    for i, row in df.iterrows():
        yr = row["year"]
        q  = row["quarter"]
        v  = row["value"]

        # QoQ — previous quarter
        q_order = ["Q1", "Q2", "Q3", "Q4"]
        q_idx   = q_order.index(q)
        if q_idx == 0:
            prev_yr, prev_q = yr - 1, "Q4"
        else:
            prev_yr, prev_q = yr, q_order[q_idx - 1]

        prev_row = df[(df["year"] == prev_yr) & (df["quarter"] == prev_q)]
        if not prev_row.empty and prev_row.iloc[0]["value"] != 0:
            prev_v = prev_row.iloc[0]["value"]
            df.at[i, "qoq_growth"] = round(((v - prev_v) / prev_v) * 100, 2)

        # YoY — same quarter, prior year
        yoy_row = df[(df["year"] == yr - 1) & (df["quarter"] == q)]
        if not yoy_row.empty and yoy_row.iloc[0]["value"] != 0:
            yoy_v = yoy_row.iloc[0]["value"]
            df.at[i, "yoy_growth"] = round(((v - yoy_v) / yoy_v) * 100, 2)

    return df


# ── Confidence label ───────────────────────────────────────────────────────────

def _confidence_label(row: pd.Series, latest_actual_year: int) -> str:
    if not row["is_forecast"]:
        return "high"
    years_out = row["year"] - latest_actual_year
    if years_out <= 1:
        return "medium"
    if years_out <= 3:
        return "medium"
    return "low"


# ── Master: quarterly KPIs for one region/commodity ───────────────────────────

def compute_quarterly_kpis(
    df: pd.DataFrame,
    region: str,
    commodity: str,
    selected_year: int,
) -> pd.DataFrame:
    """
    Compute quarterly KPI breakdown for a single region/commodity.

    Covers: all historical quarters available + forecast quarters through
    (selected_year + 3) so the dashboard has a full 3-year forward view.

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        region:        e.g. "Permian"
        commodity:     "oil" or "gas"
        selected_year: year chosen by user in the dashboard

    Returns:
        DataFrame with one row per (year, quarter) and columns:
        [region, commodity, year, quarter,
         value, lower_ci, upper_ci,
         is_forecast, data_type, confidence,
         qoq_growth, yoy_growth]
    """
    # Get the latest year with real (non-interpolated) data
    series = df[
        (df["region"] == region) &
        (df["commodity"] == commodity)
    ].copy()

    if series.empty:
        logger.warning(f"No data for {region} {commodity}")
        return pd.DataFrame()

    interp_col = "is_interpolated" if "is_interpolated" in series.columns else None
    real = series[~series[interp_col]] if interp_col else series
    latest_actual_year = int(real["period"].dt.year.max()) if not real.empty else 0

    # Extend selected_year enough to always have 3 years of forecast ahead
    forecast_to_year = max(selected_year, latest_actual_year) + 3

    # Build full monthly series (actuals + forecast out to forecast_to_year)
    monthly = _get_full_series(df, region, commodity, forecast_to_year)
    if monthly.empty:
        return pd.DataFrame()

    # Aggregate to quarters
    quarterly = _aggregate_to_quarters(monthly)
    if quarterly.empty:
        return pd.DataFrame()

    # Add growth rates
    quarterly = _add_growth_rates(quarterly)

    # Add confidence labels
    quarterly["confidence"] = quarterly.apply(
        lambda r: _confidence_label(r, latest_actual_year), axis=1
    )

    # Add region + commodity
    quarterly["region"]    = region
    quarterly["commodity"] = commodity

    # Round numeric columns
    for col in ["value", "lower_ci", "upper_ci"]:
        quarterly[col] = quarterly[col].round(2)

    # Final column order
    cols = [
        "region", "commodity", "year", "quarter",
        "value", "lower_ci", "upper_ci",
        "is_forecast", "data_type", "confidence",
        "qoq_growth", "yoy_growth",
    ]
    return quarterly[cols].reset_index(drop=True)


# ── Master: all regions + commodities ─────────────────────────────────────────

def compute_all_quarterly_kpis(
    df: pd.DataFrame,
    selected_year: int,
) -> pd.DataFrame:
    """
    Compute quarterly KPIs for ALL regions and commodities.

    This is the main function called by the dashboard year selector.
    When the user changes the selected year, this function re-runs and
    the dashboard re-renders the KPI cards and forecast chart.

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        selected_year: year chosen by user

    Returns:
        Combined DataFrame with quarterly KPIs for 5 regions × 2 commodities.
        Rows are sorted by [region, commodity, year, quarter].
    """
    logger.info(
        f"Computing quarterly KPIs | selected_year={selected_year} | "
        f"{len(REGIONS)} regions × {len(COMMODITIES)} commodities"
    )

    frames = []
    for region in REGIONS:
        for commodity in COMMODITIES:
            try:
                q_df = compute_quarterly_kpis(df, region, commodity, selected_year)
                if not q_df.empty:
                    frames.append(q_df)
                    logger.info(
                        f"  {region} {commodity}: {len(q_df)} quarters "
                        f"({q_df[~q_df['is_forecast']].shape[0]} actual, "
                        f"{q_df[q_df['is_forecast']].shape[0]} forecast)"
                    )
            except Exception as e:
                logger.error(f"  {region} {commodity}: failed — {e}")

    if not frames:
        logger.error("compute_all_quarterly_kpis: no output produced")
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(
        ["region", "commodity", "year", "quarter"]
    ).reset_index(drop=True)

    n_actual   = int((~result["is_forecast"]).sum())
    n_forecast = int(result["is_forecast"].sum())
    logger.info(
        f"Quarterly KPIs complete: {len(result)} rows total | "
        f"{n_actual} actual quarters + {n_forecast} forecast quarters"
    )
    return result


# ── Projected Production KPI — quarterly version ──────────────────────────────

def projected_production_quarterly(
    df: pd.DataFrame,
    selected_year: int,
    region: str,
    commodity: str = "oil",
) -> pd.DataFrame:
    """
    Tier 1 Required KPI — Projected Production Estimate at quarterly granularity.

    Returns all 4 quarters for the selected year, combining actuals where
    available and SARIMA forecasts where not. Updates dynamically when the
    year selector changes.

    Args:
        df:            prepared DataFrame
        selected_year: year chosen by user
        region:        e.g. "Permian"
        commodity:     "oil" or "gas"

    Returns:
        DataFrame with 4 rows (one per quarter) and columns:
        [quarter, value, lower_ci, upper_ci, data_type, confidence, unit,
         qoq_growth, yoy_growth]

    Example output for Permian oil, selected_year=2026:
        quarter  value    lower_ci  upper_ci  data_type  confidence
        Q1       485230   441200    529260    actual     high
        Q2       490150   445800    534500    forecast   medium
        Q3       495100   450300    539900    forecast   medium
        Q4       498200   453000    543400    forecast   medium
    """
    unit = "Mbbl/quarter" if commodity == "oil" else "MMcf/quarter"

    q_df = compute_quarterly_kpis(df, region, commodity, selected_year)
    if q_df.empty:
        return pd.DataFrame()

    # Filter to selected year only
    year_df = q_df[q_df["year"] == selected_year].copy()
    if year_df.empty:
        return pd.DataFrame()

    year_df["unit"] = unit

    return year_df[[
        "quarter", "value", "lower_ci", "upper_ci",
        "data_type", "confidence", "unit",
        "qoq_growth", "yoy_growth",
    ]].reset_index(drop=True)


# ── Save quarterly KPIs to Supabase ───────────────────────────────────────────

def save_quarterly_kpis_to_db(quarterly_df: pd.DataFrame) -> int:
    """
    Save quarterly KPI data to the Supabase quarterly_kpis table.

    Args:
        quarterly_df: output of compute_all_quarterly_kpis()

    Returns:
        Number of rows written
    """
    from src.data.db import _upsert

    if quarterly_df.empty:
        logger.warning("save_quarterly_kpis_to_db: nothing to save")
        return 0

    df = quarterly_df.copy()
    df["computed_at"] = pd.Timestamp.now().isoformat()

    records = df.to_dict("records")
    total   = _upsert("quarterly_kpis", records)
    logger.info(f"Saved {total} quarterly KPI rows to Supabase")
    return total


# ── Standalone run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    from src.data.db import read_production
    from src.data.prepare import prepare_for_analysis

    logger.info("Loading production data from Supabase ...")
    raw = read_production()
    if raw.empty:
        logger.error("No data — run pipeline.py first")
        sys.exit(1)

    df            = prepare_for_analysis(raw)
    selected_year = datetime.now().year

    # Run quarterly KPIs for all regions
    quarterly_df = compute_all_quarterly_kpis(df, selected_year)

    print(f"\n── Quarterly KPIs ({selected_year}) — Oil ──")
    oil_df = quarterly_df[quarterly_df["commodity"] == "oil"]
    for region in REGIONS:
        r_df = oil_df[oil_df["region"] == region]
        year_df = r_df[r_df["year"] == selected_year]
        if year_df.empty:
            continue
        print(f"\n  {region}:")
        print(
            year_df[["quarter", "value", "data_type", "confidence",
                     "qoq_growth", "yoy_growth"]].to_string(index=False)
        )

    # Show Projected Production KPI for Permian oil (quarterly breakdown)
    print(f"\n── Projected Production KPI — Permian oil ({selected_year}) ──")
    pp = projected_production_quarterly(df, selected_year, "Permian", "oil")
    print(pp.to_string(index=False))
