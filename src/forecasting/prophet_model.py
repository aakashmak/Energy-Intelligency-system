"""
Forecasting Engine — Tier 1 Requirement 3.
Method: SARIMA (Seasonal AutoRegressive Integrated Moving Average)

Why SARIMA for oil and gas production forecasting:
  - Industry standard for monthly energy time series (used by EIA itself)
  - Captures both trend (ARIMA part) and yearly production cycles (Seasonal part)
  - Ships with statsmodels — no compiler, no extra install beyond pip
  - Fully explainable: every parameter has a clear meaning
  - Confidence intervals built-in (based on model residuals)

SARIMA order used: SARIMA(1,1,1)(1,1,0)[12]
  p=1 — uses previous month's value to predict next (autoregression)
  d=1 — one differencing step to remove the upward trend
  q=1 — corrects for last month's forecast error (moving average)
  P=1 — seasonal autoregression (uses same month last year)
  D=1 — seasonal differencing (removes yearly trend)
  Q=0 — no seasonal moving average (keeps model simple/stable)
  s=12 — seasonality period = 12 months (yearly cycle)

Explainable in plain English:
  "To forecast next month's Permian oil production, SARIMA looks at:
   (1) this month's production (recent trend),
   (2) the same month last year (seasonal pattern),
   and combines them with a correction for recent forecast errors."

Year selector logic:
  - User picks any year (past or future)
  - Actuals shown: all real data UP TO December of that year
  - Forecast shown: SARIMA projection FROM January of next year onward
  - is_forecast=True column distinguishes them in the dashboard

Run standalone:
    python -m src.forecasting.prophet_model
"""

import logging
import warnings
import pandas as pd
import numpy as np
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")   # suppress statsmodels convergence warnings

# ── Constants ──────────────────────────────────────────────────────────────────

FORECAST_HORIZON_MONTHS = 36        # forecast up to 3 years ahead
MIN_TRAINING_MONTHS     = 24        # need at least 2 years to fit SARIMA reliably
CONFIDENCE_LEVEL        = 0.80      # 80% prediction interval

REGIONS     = ["Permian", "Bakken", "Eagle Ford", "Appalachia", "Gulf Coast"]
COMMODITIES = ["oil", "gas"]

# SARIMA order — same for all series (keeps methodology consistent + explainable)
# (p,d,q)(P,D,Q)[s]
SARIMA_ORDER         = (1, 1, 1)    # non-seasonal: AR(1), I(1), MA(1)
SARIMA_SEASONAL      = (1, 1, 0, 12)  # seasonal: SAR(1), SI(1), SMA(0), period=12


# ── SARIMA core ────────────────────────────────────────────────────────────────

def _fit_sarima(series: pd.Series) -> object:
    """
    Fit a SARIMA(1,1,1)(1,1,0)[12] model on a monthly production series.

    Args:
        series: pd.Series with DatetimeIndex (monthly), values = production volumes

    Returns:
        Fitted SARIMAX results object
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    model = SARIMAX(
        series,
        order          = SARIMA_ORDER,
        seasonal_order = SARIMA_SEASONAL,
        enforce_stationarity  = False,
        enforce_invertibility = False,
    )
    fitted = model.fit(disp=False)   # disp=False suppresses iteration output
    return fitted


def _forecast_sarima(
    fitted,
    horizon: int,
    last_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Generate forecast from a fitted SARIMA model.

    Args:
        fitted:    fitted SARIMAX results object
        horizon:   number of months to forecast
        last_date: last date in the training series

    Returns:
        DataFrame with [ds, yhat, yhat_lower, yhat_upper]
    """
    forecast_result = fitted.get_forecast(steps=horizon)
    mean_forecast   = forecast_result.predicted_mean
    conf_int        = forecast_result.conf_int(alpha=1 - CONFIDENCE_LEVEL)

    # Build date index for forecast periods
    future_dates = pd.date_range(
        start = last_date + pd.DateOffset(months=1),
        periods = horizon,
        freq = "MS",
    )

    df = pd.DataFrame({
        "ds":        future_dates,
        "yhat":      mean_forecast.values,
        "yhat_lower": conf_int.iloc[:, 0].values,
        "yhat_upper": conf_int.iloc[:, 1].values,
    })

    # Clip negatives — production cannot go below zero
    df["yhat"]       = df["yhat"].clip(lower=0).round(2)
    df["yhat_lower"] = df["yhat_lower"].clip(lower=0).round(2)
    df["yhat_upper"] = df["yhat_upper"].clip(lower=0).round(2)

    return df


# ── Year selector split ────────────────────────────────────────────────────────

def split_by_year(
    df: pd.DataFrame,
    selected_year: int,
    region: str,
    commodity: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split production data into actuals + SARIMA forecast by selected year.

    Actuals  = all real data where period.year <= selected_year
    Forecast = SARIMA projection from Jan(selected_year+1) for 36 months

    Args:
        df:            prepared DataFrame from prepare_for_analysis()
        selected_year: year chosen by user in the dashboard
        region:        e.g. "Permian"
        commodity:     "oil" or "gas"

    Returns:
        (actuals_df, forecast_df)

        actuals_df columns:
            period, value, is_forecast=False, is_interpolated

        forecast_df columns:
            period, value, lower_ci, upper_ci, is_forecast=True
    """
    # Filter to this region/commodity series
    series = df[
        (df["region"]    == region) &
        (df["commodity"] == commodity)
    ].copy().sort_values("period").reset_index(drop=True)

    if series.empty:
        logger.warning(f"split_by_year: no data for {region} {commodity}")
        return pd.DataFrame(), pd.DataFrame()

    latest_real = series["period"].max()
    cutoff      = pd.Timestamp(year=selected_year, month=12, day=31)
    actual_end  = min(cutoff, latest_real)

    # ── Actuals ───────────────────────────────────────────────────────────────
    actuals = series[series["period"] <= actual_end].copy()
    actuals["is_forecast"] = False

    # ── Training data — use non-interpolated rows for model fit ───────────────
    interp_col = "is_interpolated" if "is_interpolated" in series.columns else None
    if interp_col:
        train = series[~series[interp_col]].copy()
    else:
        train = series.copy()

    # Fall back to all data if not enough non-interpolated rows
    if len(train) < MIN_TRAINING_MONTHS:
        train = series.copy()

    if len(train) < MIN_TRAINING_MONTHS:
        logger.warning(
            f"split_by_year: {region} {commodity} only {len(train)} months "
            f"(need {MIN_TRAINING_MONTHS}) — skipping forecast"
        )
        return actuals, pd.DataFrame()

    forecast_start = pd.Timestamp(year=selected_year + 1, month=1, day=1)

    # ── Fit SARIMA + generate forecast ────────────────────────────────────────
    try:
        ts = train.set_index("period")["value"].asfreq("MS")
        ts = ts.interpolate(method="linear")   # fill any remaining gaps for model

        fitted   = _fit_sarima(ts)
        last_date = ts.index[-1]
        raw_fc   = _forecast_sarima(fitted, FORECAST_HORIZON_MONTHS, last_date)

        # Filter to rows from forecast_start onward
        raw_fc = raw_fc[raw_fc["ds"] >= forecast_start].copy()

        if raw_fc.empty:
            # selected_year is so far ahead we need to extend the horizon
            extra_months = (forecast_start.year - last_date.year) * 12 + \
                           (forecast_start.month - last_date.month) + \
                           FORECAST_HORIZON_MONTHS
            raw_fc = _forecast_sarima(fitted, extra_months, last_date)
            raw_fc = raw_fc[raw_fc["ds"] >= forecast_start].copy()

        forecast_df = pd.DataFrame({
            "period":          raw_fc["ds"].values,
            "value":           raw_fc["yhat"].values,
            "lower_ci":        raw_fc["yhat_lower"].values,
            "upper_ci":        raw_fc["yhat_upper"].values,
            "is_forecast":     True,
            "is_interpolated": False,
        })

        logger.info(
            f"SARIMA | {region} {commodity} | "
            f"trained on {len(train)} months | "
            f"actuals={len(actuals)} | forecast={len(forecast_df)} months"
        )
        return actuals, forecast_df

    except Exception as e:
        logger.error(f"SARIMA failed for {region} {commodity}: {e}")
        return actuals, pd.DataFrame()


# ── Batch: all regions + commodities ──────────────────────────────────────────

def run_forecast_all(df: pd.DataFrame, selected_year: int) -> pd.DataFrame:
    """
    Run SARIMA forecasting for all 5 regions × 2 commodities.

    Returns combined DataFrame with is_forecast column.
    Dashboard uses this directly to render actuals vs forecasts.
    """
    logger.info(f"SARIMA forecast run | selected_year={selected_year}")
    logger.info(f"Model: SARIMA{SARIMA_ORDER}{SARIMA_SEASONAL} | "
                f"horizon={FORECAST_HORIZON_MONTHS} months | "
                f"CI={int(CONFIDENCE_LEVEL*100)}%")

    all_frames = []

    for region in REGIONS:
        for commodity in COMMODITIES:
            actuals, forecast = split_by_year(df, selected_year, region, commodity)

            if not actuals.empty:
                actuals["region"]    = region
                actuals["commodity"] = commodity
                for col in ["lower_ci", "upper_ci"]:
                    if col not in actuals.columns:
                        actuals[col] = None
                all_frames.append(actuals)

            if not forecast.empty:
                forecast["region"]    = region
                forecast["commodity"] = commodity
                all_frames.append(forecast)

    if not all_frames:
        logger.error("run_forecast_all: no output produced")
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    result = result.sort_values(["region", "commodity", "period"]).reset_index(drop=True)

    n_actual   = int((~result["is_forecast"]).sum())
    n_forecast = int(result["is_forecast"].sum())
    logger.info(f"Complete — {n_actual} actual rows + {n_forecast} forecast rows")
    return result


# ── Tier 1 Required KPI: Projected Production Estimate ────────────────────────

def projected_production(
    df: pd.DataFrame,
    selected_year: int,
    region: str,
    commodity: str = "oil",
) -> dict:
    """
    Tier 1 Required KPI — Projected Production Estimate.

    Returns total + monthly average production for a region in the selected year.
    Uses actuals if available, SARIMA forecast if not.

    Confidence levels:
      high   — actual data exists for selected year
      medium — forecast 1–2 years beyond latest data
      low    — forecast 3+ years beyond latest data
    """
    series = df[
        (df["region"]    == region) &
        (df["commodity"] == commodity)
    ].copy()

    if series.empty:
        return _empty_kpi(region, commodity, selected_year)

    interp_col = "is_interpolated" if "is_interpolated" in series.columns else None
    real        = series[~series[interp_col]] if interp_col else series
    latest_real_year = int(real["period"].dt.year.max()) if not real.empty else 0

    if selected_year <= latest_real_year:
        # Use actual data
        year_data  = series[series["period"].dt.year == selected_year]
        data_type  = "actual"
        confidence = "high"
    else:
        # Use SARIMA forecast
        _, fc = split_by_year(df, selected_year - 1, region, commodity)
        year_data  = fc[fc["period"].dt.year == selected_year] if not fc.empty else pd.DataFrame()
        data_type  = "forecast"
        years_out  = selected_year - latest_real_year
        confidence = "medium" if years_out <= 2 else "low"

    if year_data.empty:
        return _empty_kpi(region, commodity, selected_year)

    val_col = "value"
    total   = round(float(year_data[val_col].sum()), 2)
    avg     = round(float(year_data[val_col].mean()), 2)

    return {
        "region":          region,
        "commodity":       commodity,
        "year":            selected_year,
        "projected_total": total,
        "monthly_avg":     avg,
        "unit":            "Mbbl/month" if commodity == "oil" else "MMcf/month",
        "data_type":       data_type,
        "confidence":      confidence,
        "method":          f"SARIMA{SARIMA_ORDER}{SARIMA_SEASONAL}",
    }


def _empty_kpi(region: str, commodity: str, year: int) -> dict:
    return {
        "region": region, "commodity": commodity, "year": year,
        "projected_total": None, "monthly_avg": None,
        "unit": "Mbbl/month" if commodity == "oil" else "MMcf/month",
        "data_type": "unavailable", "confidence": "low",
        "method": f"SARIMA{SARIMA_ORDER}{SARIMA_SEASONAL}",
    }


# ── Save forecasts to Supabase ─────────────────────────────────────────────────

def save_forecasts_to_db(df: pd.DataFrame, selected_year: int) -> int:
    """Run SARIMA forecasts and save results to the Supabase forecasts table."""
    from src.data.db import upsert_forecasts

    rows     = []
    run_date = date.today().isoformat()

    for region in REGIONS:
        for commodity in COMMODITIES:
            _, forecast = split_by_year(df, selected_year, region, commodity)
            if forecast.empty:
                continue
            for _, row in forecast.iterrows():
                rows.append({
                    "region":    region,
                    "commodity": commodity,
                    "period":    row["period"],
                    "forecast":  row["value"],
                    "lower_ci":  row.get("lower_ci"),
                    "upper_ci":  row.get("upper_ci"),
                    "run_date":  run_date,
                })

    if not rows:
        logger.warning("save_forecasts_to_db: no rows to save")
        return 0

    fc_df = pd.DataFrame(rows)
    saved = upsert_forecasts(fc_df)
    logger.info(f"Saved {saved} forecast rows to Supabase (run_date={run_date})")
    return saved


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
        logger.error("No data in production table — run pipeline.py first")
        sys.exit(1)

    logger.info("Preparing data ...")
    df = prepare_for_analysis(raw)

    selected_year = datetime.now().year
    logger.info(f"Running SARIMA forecasts for {selected_year} ...")

    result = run_forecast_all(df, selected_year)
    n_fc   = int(result["is_forecast"].sum())
    n_act  = int((~result["is_forecast"]).sum())
    print(f"\nResult: {n_act} actual rows + {n_fc} forecast rows")

    saved = save_forecasts_to_db(df, selected_year)
    print(f"Saved {saved} forecast rows to Supabase")

    print(f"\n── Projected Production KPI (oil, {selected_year}) ──")
    for region in REGIONS:
        kpi = projected_production(df, selected_year, region, "oil")
        print(
            f"  {region:<15} "
            f"total={kpi['projected_total']} {kpi['unit']} | "
            f"avg/mo={kpi['monthly_avg']} | "
            f"{kpi['data_type']} | confidence={kpi['confidence']}"
        )
