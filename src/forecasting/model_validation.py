"""
Model Validation Engine — SARIMA accuracy metrics.

Computes all 4 statistical error metrics mentioned in the hackathon:
  1. MAE   — Mean Absolute Error
  2. RMSE  — Root Mean Squared Error
  3. MAPE  — Mean Absolute Percentage Error
  4. AIC/BIC — Akaike / Bayesian Information Criterion (model fit quality)

Validation method: Walk-Forward Cross-Validation (also called time-series split)
  - Split history into TRAIN (first 80%) and TEST (last 20%)
  - Fit SARIMA on TRAIN only
  - Forecast the TEST period length
  - Compare forecasted values vs actual TEST values
  - This is the correct way to validate time series — no data leakage

Why walk-forward and not random split:
  - Time series cannot be shuffled — future cannot be used to predict past
  - Walk-forward simulates real-world deployment: train on old data, test on new

Run standalone:
    python -m src.forecasting.model_validation

Output example:
  ── SARIMA Model Validation Results ──
  Region         Commodity  MAE      RMSE     MAPE%   AIC       BIC
  Permian        oil        4821.3   6234.1   3.2     1842.3    1861.2
  Permian        gas        82341.2  94231.4  4.1     2103.4    2122.3
  ...
  Overall MAE: 5123.4 | RMSE: 6891.2 | MAPE: 3.8%
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

SARIMA_ORDER    = (1, 1, 1)
SARIMA_SEASONAL = (1, 1, 0, 12)
TRAIN_RATIO     = 0.80    # 80% train, 20% test
MIN_TEST_MONTHS = 12      # need at least 12 months to compute meaningful metrics


# ── Core metric functions ──────────────────────────────────────────────────────

def compute_mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Mean Absolute Error.

    Formula: MAE = (1/n) × Σ|actual_i - predicted_i|

    Interpretation for oil & gas:
      - Units are the same as production values (Mbbl/month or MMcf/month)
      - MAE = 5000 Mbbl/month means forecasts are off by ~5000 Mbbl on average
      - Good for understanding raw error magnitude in business terms
      - Less sensitive to outlier spikes than RMSE

    Lower is better.
    """
    return float(np.mean(np.abs(actual - predicted)))


def compute_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Root Mean Squared Error.

    Formula: RMSE = √[(1/n) × Σ(actual_i - predicted_i)²]

    Interpretation for oil & gas:
      - Same units as production (Mbbl/month or MMcf/month)
      - Penalizes large errors more heavily than MAE
      - If RMSE >> MAE, there are occasional large forecast misses
        (e.g. production spike due to new well completions)
      - Energy firms prioritise RMSE because large deviations directly
        affect capital allocation and hedging decisions

    Lower is better.
    """
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def compute_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Mean Absolute Percentage Error.

    Formula: MAPE = (100/n) × Σ|( actual_i - predicted_i ) / actual_i|

    Interpretation for oil & gas:
      - Scale-free percentage — allows comparison across regions
      - Permian (5M Mbbl/mo) vs Appalachia (50K Mbbl/mo) can be compared directly
      - MAPE = 5% means forecasts are typically within 5% of actual production
      - Industry benchmark: MAPE < 5% is excellent, 5-10% is acceptable,
        >10% suggests the model needs improvement for that region

    Lower is better. Returns NaN if any actual value is zero.
    """
    mask   = actual != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def compute_aic_bic(fitted_model) -> tuple[float, float]:
    """
    AIC (Akaike Information Criterion) and BIC (Bayesian Information Criterion).

    These are extracted directly from the fitted SARIMAX model — no test data needed.
    They measure model fit quality penalized for model complexity.

    Formula:
      AIC = 2k - 2ln(L)      where k = number of parameters, L = likelihood
      BIC = k·ln(n) - 2ln(L) where n = training observations

    Interpretation:
      - Lower AIC = better fit without overfitting
      - Lower BIC = same, with stronger penalty for extra parameters
      - Use to compare SARIMA(1,1,1) vs SARIMA(2,1,2) — lower AIC wins
      - In this project both are used for documentation — not model selection
        since we use a fixed order for consistency and explainability

    Note: AIC/BIC are on an arbitrary scale. Only meaningful when comparing
    two models on the same dataset.
    """
    try:
        return round(float(fitted_model.aic), 2), round(float(fitted_model.bic), 2)
    except Exception:
        return float("nan"), float("nan")


# ── Walk-forward validation for one series ────────────────────────────────────

def validate_series(
    series: pd.Series,
    region: str,
    commodity: str,
) -> dict:
    """
    Walk-forward cross-validation for a single (region, commodity) series.

    Method:
      1. Split: first 80% = train, last 20% = test
      2. Fit SARIMA(1,1,1)(1,1,0)[12] on train only
      3. Forecast for the length of the test window
      4. Compute MAE, RMSE, MAPE on (forecast vs test actuals)
      5. Extract AIC/BIC from the fitted model

    This correctly simulates how the model performs on unseen future data.

    Args:
        series:    monthly pd.Series with DatetimeIndex, no NaNs
        region:    region name (for logging)
        commodity: "oil" or "gas"

    Returns:
        dict with mae, rmse, mape, aic, bic, train_months, test_months,
        train_end, test_start, test_end
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    series = series.dropna().sort_index()
    n      = len(series)

    if n < MIN_TEST_MONTHS * 2:
        logger.warning(
            f"validate_series: {region} {commodity} — only {n} months, "
            f"need at least {MIN_TEST_MONTHS * 2} for walk-forward validation"
        )
        return _empty_metrics(region, commodity, n)

    # ── Train / test split ────────────────────────────────────────────────────
    split_idx   = int(n * TRAIN_RATIO)
    split_idx   = max(split_idx, n - MIN_TEST_MONTHS)  # at least 12 test months
    train       = series.iloc[:split_idx]
    test        = series.iloc[split_idx:]
    test_length = len(test)

    logger.info(
        f"Validating {region} {commodity} | "
        f"train={len(train)} months ({train.index[0].date()} → {train.index[-1].date()}) | "
        f"test={test_length} months ({test.index[0].date()} → {test.index[-1].date()})"
    )

    # ── Fit SARIMA on training data only ──────────────────────────────────────
    try:
        model  = SARIMAX(
            train,
            order          = SARIMA_ORDER,
            seasonal_order = SARIMA_SEASONAL,
            enforce_stationarity  = False,
            enforce_invertibility = False,
        )
        fitted = model.fit(disp=False)
    except Exception as e:
        logger.error(f"  SARIMA fit failed for {region} {commodity}: {e}")
        return _empty_metrics(region, commodity, n)

    # ── Forecast test window ───────────────────────────────────────────────────
    try:
        fc_result   = fitted.get_forecast(steps=test_length)
        fc_mean     = fc_result.predicted_mean.values
        fc_mean     = np.clip(fc_mean, 0, None)   # no negative production
    except Exception as e:
        logger.error(f"  SARIMA forecast failed for {region} {commodity}: {e}")
        return _empty_metrics(region, commodity, n)

    # ── Compute error metrics ──────────────────────────────────────────────────
    actual    = test.values
    predicted = fc_mean

    mae  = compute_mae(actual, predicted)
    rmse = compute_rmse(actual, predicted)
    mape = compute_mape(actual, predicted)
    aic, bic = compute_aic_bic(fitted)

    # ── Skill score: is SARIMA better than naive forecast? ────────────────────
    # Naive forecast = last known training value repeated for test length
    # If skill_score > 0 the model beats the naive baseline
    naive_forecast = np.full(test_length, float(train.iloc[-1]))
    naive_mae      = compute_mae(actual, naive_forecast)
    skill_score    = round((1 - mae / naive_mae) * 100, 1) if naive_mae > 0 else 0.0

    result = {
        "region":       region,
        "commodity":    commodity,
        "mae":          round(mae, 2),
        "rmse":         round(rmse, 2),
        "mape":         round(mape, 2),
        "aic":          aic,
        "bic":          bic,
        "skill_score":  skill_score,   # % improvement over naive
        "train_months": len(train),
        "test_months":  test_length,
        "train_end":    str(train.index[-1].date()),
        "test_start":   str(test.index[0].date()),
        "test_end":     str(test.index[-1].date()),
        "unit":         "Mbbl/month" if commodity == "oil" else "MMcf/month",
        "grade":        _grade(mape),
    }

    logger.info(
        f"  {region} {commodity} | "
        f"MAE={mae:,.1f} | RMSE={rmse:,.1f} | MAPE={mape:.2f}% | "
        f"AIC={aic:.1f} | skill={skill_score:+.1f}% | grade={result['grade']}"
    )
    return result


def _grade(mape: float) -> str:
    """
    Convert MAPE to a letter grade for the dashboard.
    Industry benchmark for energy forecasting:
      A = MAPE < 5%   — excellent
      B = MAPE < 10%  — good
      C = MAPE < 15%  — acceptable
      D = MAPE >= 15% — needs improvement
    """
    if pd.isna(mape):
        return "N/A"
    if mape < 5:   return "A"
    if mape < 10:  return "B"
    if mape < 15:  return "C"
    return "D"


def _empty_metrics(region: str, commodity: str, n: int) -> dict:
    return {
        "region": region, "commodity": commodity,
        "mae": None, "rmse": None, "mape": None,
        "aic": None, "bic": None,
        "skill_score": None, "grade": "N/A",
        "train_months": n, "test_months": 0,
        "train_end": None, "test_start": None, "test_end": None,
        "unit": "unknown",
    }


# ── Validate all regions + commodities ────────────────────────────────────────

def validate_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run walk-forward validation for all 5 regions × 2 commodities.

    Args:
        df: prepared DataFrame from prepare_for_analysis()

    Returns:
        DataFrame with one row per (region, commodity) and all metrics.
        Columns: [region, commodity, mae, rmse, mape, aic, bic,
                  skill_score, grade, train_months, test_months,
                  train_end, test_start, test_end, unit]
    """
    logger.info("=" * 60)
    logger.info("SARIMA Model Validation — Walk-Forward Cross-Validation")
    logger.info(f"Model: SARIMA{SARIMA_ORDER}{SARIMA_SEASONAL}")
    logger.info(f"Split: {int(TRAIN_RATIO*100)}% train / {int((1-TRAIN_RATIO)*100)}% test")
    logger.info("=" * 60)

    rows = []
    for region in REGIONS:
        for commodity in COMMODITIES:
            series = df[
                (df["region"] == region) &
                (df["commodity"] == commodity)
            ].set_index("period")["value"].sort_index()

            # Use only non-interpolated rows for honest validation
            interp_mask = df[
                (df["region"] == region) &
                (df["commodity"] == commodity)
            ].set_index("period").get("is_interpolated", pd.Series(False))

            if not interp_mask.empty:
                real_series = series[~interp_mask]
            else:
                real_series = series

            real_series = real_series.asfreq("MS").interpolate(method="linear")

            result = validate_series(real_series, region, commodity)
            rows.append(result)

    results_df = pd.DataFrame(rows)
    results_df = results_df.sort_values(["commodity", "mape"], na_position="last")
    return results_df.reset_index(drop=True)


def save_validation_to_db(results_df: pd.DataFrame) -> int:
    """Save validation metrics to Supabase model_validation table."""
    from src.data.db import _upsert

    if results_df.empty:
        return 0

    df = results_df.copy()
    df["validated_at"] = pd.Timestamp.now().isoformat()
    df["model"]        = f"SARIMA{SARIMA_ORDER}{SARIMA_SEASONAL}"

    records = df.to_dict("records")
    try:
        total = _upsert("model_validation", records)
        logger.info(f"Saved {total} validation rows to Supabase model_validation table")
        return total
    except Exception as e:
        logger.warning(f"Could not save validation to DB: {e} — table may not exist yet")
        return 0


def print_validation_report(results_df: pd.DataFrame) -> None:
    """
    Print a formatted validation report to stdout.
    Used by the standalone run and the pipeline log.
    """
    print("\n" + "=" * 75)
    print("  SARIMA Model Validation Report")
    print(f"  Model: SARIMA{SARIMA_ORDER}{SARIMA_SEASONAL}")
    print(f"  Split: {int(TRAIN_RATIO*100)}% train / {int((1-TRAIN_RATIO)*100)}% test (walk-forward)")
    print("=" * 75)
    print(f"  {'Region':<15} {'Commodity':<10} {'MAE':>10} {'RMSE':>10} {'MAPE%':>7} "
          f"{'AIC':>8} {'BIC':>8} {'Skill':>7} {'Grade':>5}")
    print("  " + "-" * 73)

    for _, row in results_df.iterrows():
        mae   = f"{row['mae']:,.1f}"   if row['mae']  is not None else "N/A"
        rmse  = f"{row['rmse']:,.1f}"  if row['rmse'] is not None else "N/A"
        mape  = f"{row['mape']:.2f}"   if row['mape'] is not None else "N/A"
        aic   = f"{row['aic']:.1f}"    if row['aic']  is not None else "N/A"
        bic   = f"{row['bic']:.1f}"    if row['bic']  is not None else "N/A"
        skill = f"{row['skill_score']:+.1f}%" if row['skill_score'] is not None else "N/A"
        grade = row['grade']

        print(
            f"  {row['region']:<15} {row['commodity']:<10} "
            f"{mae:>10} {rmse:>10} {mape:>7} "
            f"{aic:>8} {bic:>8} {skill:>7} {grade:>5}"
        )

    print("  " + "-" * 73)

    # Summary row
    valid = results_df.dropna(subset=["mae", "rmse", "mape"])
    if not valid.empty:
        avg_mae  = valid["mae"].mean()
        avg_rmse = valid["rmse"].mean()
        avg_mape = valid["mape"].mean()
        print(
            f"\n  Overall average:  "
            f"MAE={avg_mae:,.1f}  RMSE={avg_rmse:,.1f}  MAPE={avg_mape:.2f}%"
        )
        print(f"  Overall grade:    {_grade(avg_mape)}")

    print("\n  Metric guide:")
    print("    MAE   — avg error in same units as production (lower = better)")
    print("    RMSE  — penalises large errors more than MAE (lower = better)")
    print("    MAPE  — % error, scale-free — compare across regions (lower = better)")
    print("    AIC   — model fit quality, penalised for complexity (lower = better)")
    print("    BIC   — same as AIC with stronger complexity penalty (lower = better)")
    print("    Skill — % improvement vs naive (repeat-last-value) baseline")
    print("    Grade — A:<5% / B:<10% / C:<15% / D:≥15%")
    print("=" * 75)


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

    logger.info("Preparing data ...")
    df = prepare_for_analysis(raw)

    logger.info("Running walk-forward validation ...")
    results = validate_all(df)

    print_validation_report(results)

    # Save to Supabase
    save_validation_to_db(results)
