"""
Data Preparation — Tier 1 Requirement 2.

Handles all cleaning, normalization, and structuring of raw production data
so the forecasting engine and dashboard can reliably consume it.

Three operations:
  1. clean()        — remove nulls, negatives, outliers, fix types
  2. normalize()    — consistent region names, unit standardization
  3. align()        — fill time series gaps so every region has a
                       complete monthly spine from start → latest period

Output: a single clean DataFrame that is the contract between the
data layer and everything above it (forecasting, scoring, dashboard).

Usage:
    from src.data.prepare import prepare_for_analysis
    df = prepare_for_analysis(raw_df)
"""

import logging
import pandas as pd
import numpy as np
from datetime import date

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

CANONICAL_REGIONS = {
    "permian":    "Permian",
    "bakken":     "Bakken",
    "eagle ford": "Eagle Ford",
    "eagleford":  "Eagle Ford",
    "appalachia": "Appalachia",
    "gulf coast": "Gulf Coast",
    "gulfcoast":  "Gulf Coast",
}

CANONICAL_COMMODITIES = {
    "oil":   "oil",
    "crude": "oil",
    "gas":   "gas",
    "ng":    "gas",
    "naturalgas": "gas",
}

EXPECTED_REGIONS     = {"Permian", "Bakken", "Eagle Ford", "Appalachia", "Gulf Coast"}
EXPECTED_COMMODITIES = {"oil", "gas"}

# Outlier threshold — flag values more than N std deviations from series mean
OUTLIER_STD_THRESHOLD = 4.0


# ── Step 1: Clean ──────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove bad rows and fix types.

    - Coerce period → datetime, value → float
    - Drop rows where period or value is null
    - Drop rows where value is negative
    - Log and cap extreme outliers (> 4 std devs) instead of dropping them
      so we don't lose real data from production spikes

    Args:
        df: raw production DataFrame with at least
            [region, commodity, period, value] columns

    Returns:
        Cleaned DataFrame, same columns
    """
    required = {"region", "commodity", "period", "value"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"prepare.clean(): missing columns {missing}")

    df = df.copy()
    original_len = len(df)

    # Type coercion
    df["period"] = pd.to_datetime(df["period"], errors="coerce")
    df["value"]  = pd.to_numeric(df["value"],  errors="coerce")

    # Drop nulls
    df = df.dropna(subset=["period", "value"])
    null_dropped = original_len - len(df)

    # Drop negatives
    df = df[df["value"] >= 0]
    neg_dropped = (original_len - null_dropped) - len(df)

    if null_dropped > 0:
        logger.warning(f"clean: dropped {null_dropped} null rows")
    if neg_dropped > 0:
        logger.warning(f"clean: dropped {neg_dropped} negative-value rows")

    # Cap outliers per series (don't drop — production spikes are real)
    capped = 0
    for (region, commodity), group in df.groupby(["region", "commodity"]):
        if len(group) < 10:
            continue
        mean = group["value"].mean()
        std  = group["value"].std()
        if std == 0:
            continue
        upper = mean + OUTLIER_STD_THRESHOLD * std
        mask  = (df["region"] == region) & (df["commodity"] == commodity) & (df["value"] > upper)
        if mask.any():
            capped += mask.sum()
            df.loc[mask, "value"] = upper
            logger.warning(
                f"clean: capped {mask.sum()} outliers in {region} {commodity} "
                f"(threshold={upper:.1f})"
            )

    logger.info(
        f"clean: {original_len} → {len(df)} rows "
        f"({null_dropped} nulls, {neg_dropped} negatives, {capped} outliers capped)"
    )
    return df.reset_index(drop=True)


# ── Step 2: Normalize ──────────────────────────────────────────────────────────

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize region names, commodity labels, period format, and units.

    - Region names → canonical form (e.g. "eagleford" → "Eagle Ford")
    - Commodity labels → "oil" or "gas" only
    - Period → first day of month (2023-06-01, not 2023-06-15)
    - Value rounded to 2 decimal places
    - Removes any region/commodity combinations outside the expected set

    Args:
        df: cleaned DataFrame

    Returns:
        Normalized DataFrame
    """
    df = df.copy()

    # Normalize region names
    df["region"] = (
        df["region"]
        .str.strip()
        .str.lower()
        .map(lambda x: CANONICAL_REGIONS.get(x, x.title()))
    )

    # Normalize commodity labels
    df["commodity"] = (
        df["commodity"]
        .str.strip()
        .str.lower()
        .map(lambda x: CANONICAL_COMMODITIES.get(x, x))
    )

    # Period → first day of month (ensures clean monthly spine later)
    df["period"] = pd.to_datetime(df["period"]).dt.to_period("M").dt.to_timestamp()

    # Round values
    df["value"] = df["value"].round(2)

    # Filter to known regions and commodities only
    before = len(df)
    df = df[df["region"].isin(EXPECTED_REGIONS)]
    df = df[df["commodity"].isin(EXPECTED_COMMODITIES)]
    filtered = before - len(df)
    if filtered > 0:
        logger.warning(f"normalize: dropped {filtered} rows with unknown region/commodity")

    logger.info(
        f"normalize: {len(df)} rows | "
        f"regions={sorted(df['region'].unique())} | "
        f"commodities={sorted(df['commodity'].unique())}"
    )
    return df.reset_index(drop=True)


# ── Step 3: Align (time series gap filling) ───────────────────────────────────

def align(df: pd.DataFrame, start: str = "2015-01-01") -> pd.DataFrame:
    """
    Ensure every (region, commodity) series has a complete monthly spine
    from `start` to the latest period in the data.

    Missing months are filled using linear interpolation.
    If a series has no data at all, it is skipped with a warning.

    This is critical for forecasting — SARIMA requires evenly spaced
    data with no gaps.

    Args:
        df:    normalized DataFrame
        start: earliest date for the spine (YYYY-MM-DD)

    Returns:
        DataFrame with complete monthly time series per region/commodity.
        New columns: is_interpolated (bool) — True for filled months.
    """
    df = df.copy()
    df["is_interpolated"] = False

    end_date   = df["period"].max()
    full_spine = pd.date_range(start=start, end=end_date, freq="MS")

    frames = []
    for (region, commodity), group in df.groupby(["region", "commodity"]):
        group = group.set_index("period").sort_index()

        # Reindex to full monthly spine
        group = group.reindex(full_spine)

        # Mark gaps before filling
        gap_mask  = group["value"].isna()
        gap_count = gap_mask.sum()

        # Fill region/commodity/source for newly created rows
        group["region"]    = region
        group["commodity"] = commodity
        if "source" in group.columns:
            group["source"] = group["source"].ffill().bfill()
        if "unit" in group.columns:
            group["unit"] = group["unit"].ffill().bfill()

        # Interpolate missing values linearly
        group["value"] = group["value"].interpolate(method="linear", limit_direction="both")
        group["value"] = group["value"].round(2)

        # Mark interpolated rows
        group["is_interpolated"] = gap_mask

        group.index.name = "period"
        group = group.reset_index()

        if gap_count > 0:
            logger.warning(
                f"align: {region} {commodity} — filled {gap_count} missing months "
                f"via linear interpolation"
            )

        frames.append(group)

    if not frames:
        logger.error("align: no data to align")
        return df

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(["region", "commodity", "period"]).reset_index(drop=True)

    total_interpolated = result["is_interpolated"].sum()
    logger.info(
        f"align: {len(result)} total rows | "
        f"{total_interpolated} interpolated gaps filled | "
        f"spine: {result['period'].min().date()} → {result['period'].max().date()}"
    )
    return result


# ── Master function ────────────────────────────────────────────────────────────

def prepare_for_analysis(
    df: pd.DataFrame,
    start: str = "2015-01-01",
) -> pd.DataFrame:
    """
    Full data preparation pipeline — runs clean → normalize → align in sequence.

    This is the single entry point for the forecasting engine and dashboard.
    Both should call this function on raw data from Supabase before using it.

    Args:
        df:    raw production DataFrame from db.read_production()
        start: earliest date for time series spine

    Returns:
        Clean, normalized, gap-filled DataFrame ready for forecasting and UI.
        Columns: [region, commodity, period, value, source, unit, is_interpolated]

    Example:
        from src.data.db import read_production
        from src.data.prepare import prepare_for_analysis

        raw = read_production()
        df  = prepare_for_analysis(raw)
        # df is now ready for SARIMA or the Streamlit dashboard
    """
    logger.info("── Data Preparation: clean → normalize → align ──")

    df = clean(df)
    df = normalize(df)
    df = align(df, start=start)

    # Final column order — consistent contract for all consumers
    cols = ["region", "commodity", "period", "value", "is_interpolated"]
    for optional in ["source", "unit"]:
        if optional in df.columns:
            cols.append(optional)
    df = df[cols]

    logger.info(
        f"── Preparation complete: {len(df)} rows ready │ "
        f"{df['region'].nunique()} regions │ "
        f"{df['commodity'].nunique()} commodities ──"
    )
    return df


# ── Summary helper (used by dashboard + docs) ─────────────────────────────────

def preparation_summary(df: pd.DataFrame) -> dict:
    """
    Return a human-readable summary dict of the prepared dataset.
    Used by the dashboard KPI panel and kpi_definitions.md documentation.

    Returns:
        {
          "regions":           list of region names,
          "commodities":       list of commodity names,
          "date_range":        {"min": str, "max": str},
          "total_rows":        int,
          "interpolated_rows": int,
          "completeness_pct":  float,
          "series_summary":    DataFrame with per-series stats
        }
    """
    series_summary = (
        df.groupby(["region", "commodity"])
        .agg(
            months       = ("value",           "count"),
            min_date     = ("period",          "min"),
            max_date     = ("period",          "max"),
            avg_value    = ("value",           "mean"),
            min_value    = ("value",           "min"),
            max_value    = ("value",           "max"),
            interpolated = ("is_interpolated", "sum"),
        )
        .round(2)
        .reset_index()
    )

    total        = len(df)
    interpolated = int(df["is_interpolated"].sum())

    return {
        "regions":           sorted(df["region"].unique().tolist()),
        "commodities":       sorted(df["commodity"].unique().tolist()),
        "date_range": {
            "min": str(df["period"].min().date()),
            "max": str(df["period"].max().date()),
        },
        "total_rows":        total,
        "interpolated_rows": interpolated,
        "completeness_pct":  round((total - interpolated) / total * 100, 1) if total > 0 else 0,
        "series_summary":    series_summary,
    }
