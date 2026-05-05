"""
ETL + Forecasting Pipeline — full end-to-end run.

Steps:
  1.  Seed region metadata
  2.  Fetch EIA data (Petroleum Supply Monthly + Natural Gas Monthly)
  3.  Store raw state-level data → state_production
  4.  Aggregate states → 5 regions
  5.  Data preparation: clean → normalize → align
  6.  Store prepared data → production table
  7.  SARIMA forecasting → forecasts table
  8.  Model validation (MAE, RMSE, MAPE, AIC/BIC) → model_validation table
  9.  Scoring engine — Tier 1 KPIs + all 5 Tier 2 custom KPIs → scores table
  10. Quarterly KPI engine → quarterly_kpis table (per region/year/quarter)
  11. Health check

Run:  python -m src.data.pipeline
Log:  pipeline.log
"""

import logging
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

from src.data.db import (
    init_schema,
    upsert_production,
    upsert_state_production,
    upsert_rig_counts,
    upsert_quarterly_kpis,
    health_check,
)
from src.data.eia_fetcher import (
    fetch_oil_by_state,
    fetch_gas_by_state,
    _aggregate_to_regions,
)
from src.data.prepare import prepare_for_analysis, preparation_summary
from src.data.rig_fetcher import fetch_rig_counts
from src.data.validate import check_coverage
from src.forecasting.prophet_model import run_forecast_all, save_forecasts_to_db
from src.forecasting.model_validation import validate_all, save_validation_to_db, print_validation_report
from src.forecasting.scoring import run_scoring
from src.forecasting.custom_kpis import run_custom_kpis
from src.forecasting.quarterly_kpis import compute_all_quarterly_kpis

log_format = "%(asctime)s  %(levelname)-8s  %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler("pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_pipeline(start: str = "2015-01") -> dict:
    run_start     = datetime.now()
    selected_year = datetime.now().year

    logger.info("=" * 60)
    logger.info(f"OilPulse ETL + Forecast Pipeline — {run_start.isoformat()}")
    logger.info(f"Supabase: ykazfpbmldhdsldqfxjf")
    logger.info(f"Data range: {start} → present | Forecast year: {selected_year}")
    logger.info("=" * 60)

    # ── Step 1: Seed regions ──────────────────────────────────────────────────
    logger.info("Step 1/11 — Seeding region metadata ...")
    try:
        init_schema()
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        sys.exit(1)

    # ── Step 2: Fetch from EIA ────────────────────────────────────────────────
    logger.info("Step 2/11 — Fetching EIA data ...")
    oil_state = pd.DataFrame()
    gas_state = pd.DataFrame()

    try:
        oil_state = fetch_oil_by_state(start=start)
        logger.info(f"  Oil: {len(oil_state)} state rows")
    except Exception as e:
        logger.warning(f"  Oil fetch failed: {e}")

    try:
        gas_state = fetch_gas_by_state(start=start)
        logger.info(f"  Gas: {len(gas_state)} state rows")
    except Exception as e:
        logger.warning(f"  Gas fetch failed: {e}")

    if oil_state.empty and gas_state.empty:
        logger.error("Both oil and gas fetches failed — check EIA_API_KEY")
        sys.exit(1)

    # ── Step 3: Store raw state data ──────────────────────────────────────────
    logger.info("Step 3/11 — Storing state-level data → state_production ...")
    try:
        if not oil_state.empty:
            upsert_state_production(oil_state)
            logger.info(f"  Oil state rows: {len(oil_state)}")
        if not gas_state.empty:
            upsert_state_production(gas_state)
            logger.info(f"  Gas state rows: {len(gas_state)}")
    except Exception as e:
        logger.warning(f"  State storage error: {e} — continuing")

    # ── Step 4: Aggregate → regions ───────────────────────────────────────────
    logger.info("Step 4/11 — Aggregating states → 5 regions ...")
    region_frames = []

    if not oil_state.empty:
        oil_regions = _aggregate_to_regions(oil_state, "oil")
        if not oil_regions.empty:
            region_frames.append(oil_regions)
            logger.info(f"  Oil regions: {len(oil_regions)} rows")

    if not gas_state.empty:
        gas_regions = _aggregate_to_regions(gas_state, "gas")
        if not gas_regions.empty:
            region_frames.append(gas_regions)
            logger.info(f"  Gas regions: {len(gas_regions)} rows")

    if not region_frames:
        logger.error("No region-level data — exiting")
        sys.exit(1)

    raw_df = pd.concat(region_frames, ignore_index=True)

    # Save process/product metadata before prepare strips it
    meta_cols = [c for c in ["region", "commodity", "process_name", "product_name"]
                 if c in raw_df.columns]
    meta_lookup = (
        raw_df[meta_cols].drop_duplicates(subset=["region", "commodity"])
        .set_index(["region", "commodity"])
    ) if len(meta_cols) > 2 else None

    # ── Step 5: Data preparation ──────────────────────────────────────────────
    logger.info("Step 5/11 — Data preparation: clean → normalize → align ...")
    try:
        prepared_df = prepare_for_analysis(raw_df, start=f"{start[:4]}-{start[5:7]}-01")
        summary     = preparation_summary(prepared_df)
        logger.info(
            f"  Rows: {summary['total_rows']} | "
            f"Interpolated: {summary['interpolated_rows']} | "
            f"Completeness: {summary['completeness_pct']}%"
        )
    except Exception as e:
        logger.error(f"Data preparation failed: {e}")
        sys.exit(1)

    # ── Step 6: Store prepared data → production ──────────────────────────────
    logger.info("Step 6/11 — Storing prepared data → production table ...")
    prod_to_store = prepared_df.copy()

    if meta_lookup is not None and not meta_lookup.empty:
        prod_to_store["process_name"] = prod_to_store.apply(
            lambda r: meta_lookup.loc[(r["region"], r["commodity"]), "process_name"]
            if (r["region"], r["commodity"]) in meta_lookup.index else None, axis=1,
        )
        prod_to_store["product_name"] = prod_to_store.apply(
            lambda r: meta_lookup.loc[(r["region"], r["commodity"]), "product_name"]
            if (r["region"], r["commodity"]) in meta_lookup.index else None, axis=1,
        )

    if "source" not in prod_to_store.columns:
        prod_to_store["source"] = "EIA APIv2 (prepared)"
    if "unit" not in prod_to_store.columns:
        prod_to_store["unit"] = None

    coverage     = check_coverage(prepared_df.rename(columns={"value": "production"}))
    rows_written = upsert_production(prod_to_store)
    logger.info(f"  Rows written: {rows_written}")
    if coverage["missing_series"]:
        logger.warning(f"  Missing series: {coverage['missing_series']}")

    # ── Step 7: SARIMA forecasting ────────────────────────────────────────────
    logger.info(f"Step 7/11 — SARIMA forecasting for {selected_year} ...")
    try:
        forecast_df   = run_forecast_all(prepared_df, selected_year)
        forecast_rows = save_forecasts_to_db(prepared_df, selected_year)
        n_fc = int(forecast_df["is_forecast"].sum()) if not forecast_df.empty else 0
        logger.info(f"  Forecast rows: {n_fc} generated | {forecast_rows} saved")
    except Exception as e:
        logger.warning(f"  Forecasting failed: {e} — continuing")
        forecast_rows = 0

    # ── Step 8: Model validation (MAE, RMSE, MAPE, AIC/BIC) ──────────────────
    logger.info("Step 8/11 — Model validation (walk-forward cross-validation) ...")
    validation_df = pd.DataFrame()
    try:
        validation_df = validate_all(prepared_df)
        save_validation_to_db(validation_df)

        # Log summary
        valid = validation_df.dropna(subset=["mape"])
        if not valid.empty:
            avg_mape = valid["mape"].mean()
            avg_mae  = valid["mae"].mean()
            avg_rmse = valid["rmse"].mean()
            logger.info(
                f"  Validation complete | "
                f"Avg MAE={avg_mae:,.1f} | "
                f"Avg RMSE={avg_rmse:,.1f} | "
                f"Avg MAPE={avg_mape:.2f}%"
            )
            for _, row in validation_df.iterrows():
                if row.get("mape") is not None:
                    logger.info(
                        f"  {row['region']:<15} {row['commodity']:<5} | "
                        f"MAE={row['mae']:,.0f} | "
                        f"RMSE={row['rmse']:,.0f} | "
                        f"MAPE={row['mape']:.2f}% | "
                        f"AIC={row['aic']:.1f} | "
                        f"Grade={row['grade']}"
                    )
    except Exception as e:
        logger.warning(f"  Model validation failed: {e} — continuing")

    # ── Step 9: Scoring engine + Custom KPIs ─────────────────────────────────
    logger.info(f"Step 9/11 — Scoring engine + Custom KPIs for {selected_year} ...")
    try:
        scores_df = run_scoring(prepared_df, selected_year)
        logger.info(f"  Base scores: {len(scores_df)} regions")

        custom_df = run_custom_kpis(prepared_df, selected_year, scores_df)
        logger.info(f"  Custom KPIs: {len(custom_df)} regions")

        if not scores_df.empty:
            top = scores_df.iloc[0]
            logger.info(f"  Top region: {top['region']} (score={top['score']})")
        if not custom_df.empty:
            best_rev = custom_df.iloc[0]
            logger.info(f"  Best revenue: {best_rev['region']} (${best_rev['revenue_potential_m']:.0f}M)")
    except Exception as e:
        logger.warning(f"  Scoring/KPI failed: {e} — continuing")

    # ── Step 10: Quarterly KPI engine ────────────────────────────────────────
    logger.info(f"Step 10/11 — Computing quarterly KPIs for all regions ...")
    quarterly_rows = 0
    try:
        quarterly_df = compute_all_quarterly_kpis(prepared_df, selected_year)
        if not quarterly_df.empty:
            quarterly_rows = upsert_quarterly_kpis(quarterly_df)
            n_act_q  = int((~quarterly_df["is_forecast"]).sum())
            n_fc_q   = int(quarterly_df["is_forecast"].sum())
            logger.info(
                f"  {len(quarterly_df)} rows | "
                f"{n_act_q} actual quarters + {n_fc_q} forecast quarters | "
                f"{quarterly_rows} saved"
            )
    except Exception as e:
        logger.warning(f"  Quarterly KPI engine failed: {e} — continuing")

    # ── Step 11: Rig counts + health check ────────────────────────────────────
    logger.info("Step 11/11 — Rig counts + health check ...")
    try:
        rig_df   = fetch_rig_counts(start=start)
        rig_rows = upsert_rig_counts(rig_df) if not rig_df.empty else 0
        logger.info(f"  Rig rows: {rig_rows}")
    except Exception as e:
        logger.warning(f"  Rig counts failed: {e} — skipping")
        rig_rows = 0

    health  = health_check()
    elapsed = (datetime.now() - run_start).total_seconds()

    # Print validation report at end of pipeline
    if not validation_df.empty:
        print_validation_report(validation_df)

    logger.info("=" * 60)
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info(f"production rows    : {health['rows']}")
    logger.info(f"regions covered    : {health['regions']}/5")
    logger.info(f"forecast rows      : {forecast_rows}")
    logger.info(f"quarterly kpi rows : {quarterly_rows}")
    logger.info(f"completeness       : {summary['completeness_pct']}%")
    if not health["summary"].empty:
        logger.info("\n" + health["summary"].to_string())
    logger.info("=" * 60)

    return {
        "status":            "success",
        "elapsed_sec":       round(elapsed, 1),
        "rows_written":      rows_written,
        "forecast_rows":     forecast_rows,
        "quarterly_rows":    quarterly_rows,
        "rig_rows":          rig_rows,
        "db_rows":           health["rows"],
        "regions":           health["regions"],
        "completeness_pct":  summary["completeness_pct"],
        "interpolated_rows": summary["interpolated_rows"],
        "coverage":          coverage,
        "date_range":        summary["date_range"],
        "validation":        validation_df.to_dict("records") if not validation_df.empty else [],
    }


if __name__ == "__main__":
    result = run_pipeline()
    print("\n── Pipeline Summary ──")
    for k, v in result.items():
        if k not in ("coverage", "date_range", "validation"):
            print(f"  {k}: {v}")
    print(f"  date range:     {result['date_range']['min']} → {result['date_range']['max']}")
    print(f"  missing series: {result['coverage']['missing_series'] or 'none'}")
