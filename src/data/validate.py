"""
Data validation — checks the production DataFrame before it enters DuckDB.
Raises ValueError with a clear message if anything critical is wrong.
Logs warnings for soft issues (gaps, outliers) without blocking the pipeline.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_REGIONS = {"Permian", "Bakken", "Eagle Ford", "Appalachia", "Gulf Coast"}
EXPECTED_COMMODITIES = {"oil", "gas"}
MIN_ROWS_PER_SERIES = 60   # ~5 years of monthly data minimum
MAX_ZERO_PCT = 0.10        # flag if >10% of values are zero


def validate_production(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and clean a production DataFrame.

    Steps:
      1. Check required columns exist
      2. Drop rows with null period or null/negative production
      3. Warn on unexpected regions or commodities
      4. Warn if any series has fewer than MIN_ROWS_PER_SERIES rows
      5. Warn if any series has > MAX_ZERO_PCT zero values
      6. Log a clean summary

    Args:
        df: raw DataFrame from fetch_all_regions()

    Returns:
        Cleaned DataFrame (same schema, bad rows removed)

    Raises:
        ValueError: if required columns are missing or DataFrame is entirely empty
    """
    required_cols = {"region", "commodity", "period", "production"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Production DataFrame missing required columns: {missing}")

    if df.empty:
        raise ValueError("Production DataFrame is empty — nothing to validate")

    original_len = len(df)

    # ── 1. Drop nulls and negatives ──────────────────────────────────────────
    df = df.copy()
    df["period"]     = pd.to_datetime(df["period"], errors="coerce")
    df["production"] = pd.to_numeric(df["production"], errors="coerce")
    df = df.dropna(subset=["period", "production"])
    df = df[df["production"] >= 0]

    dropped = original_len - len(df)
    if dropped > 0:
        logger.warning(f"Validation: dropped {dropped} rows with null/negative values")

    # ── 2. Region / commodity checks ─────────────────────────────────────────
    unknown_regions = set(df["region"].unique()) - EXPECTED_REGIONS
    if unknown_regions:
        logger.warning(f"Unexpected regions in data: {unknown_regions}")

    unknown_commodities = set(df["commodity"].unique()) - EXPECTED_COMMODITIES
    if unknown_commodities:
        logger.warning(f"Unexpected commodities in data: {unknown_commodities}")

    # ── 3. Per-series row count ───────────────────────────────────────────────
    series_counts = df.groupby(["region", "commodity"]).size()
    thin_series = series_counts[series_counts < MIN_ROWS_PER_SERIES]
    if not thin_series.empty:
        for (region, commodity), count in thin_series.items():
            logger.warning(
                f"Thin series: {region} {commodity} has only {count} rows "
                f"(expected >= {MIN_ROWS_PER_SERIES})"
            )

    # ── 4. Zero-value check ───────────────────────────────────────────────────
    for (region, commodity), group in df.groupby(["region", "commodity"]):
        zero_pct = (group["production"] == 0).mean()
        if zero_pct > MAX_ZERO_PCT:
            logger.warning(
                f"High zero rate: {region} {commodity} — {zero_pct:.1%} zero values"
            )

    # ── 5. Coverage summary ──────────────────────────────────────────────────
    summary = (
        df.groupby(["region", "commodity"])
        .agg(rows=("production", "count"),
             min_date=("period", "min"),
             max_date=("period", "max"),
             avg_prod=("production", "mean"))
        .round(2)
    )
    logger.info(f"Validation passed — {len(df)} clean rows across {len(summary)} series\n{summary.to_string()}")

    return df.reset_index(drop=True)


def check_coverage(df: pd.DataFrame) -> dict:
    """
    Return coverage metrics as a dict — used in health_check endpoint.

    Returns:
        {
          "total_rows": int,
          "regions_covered": int,
          "missing_series": list of (region, commodity) tuples,
          "date_range": {"min": str, "max": str}
        }
    """
    present = set(zip(df["region"], df["commodity"]))
    expected = {
        (r, c)
        for r in EXPECTED_REGIONS
        for c in EXPECTED_COMMODITIES
    }
    missing = sorted(expected - present)

    return {
        "total_rows":      len(df),
        "regions_covered": df["region"].nunique(),
        "missing_series":  missing,
        "date_range": {
            "min": str(df["period"].min().date()) if not df.empty else None,
            "max": str(df["period"].max().date()) if not df.empty else None,
        },
    }
