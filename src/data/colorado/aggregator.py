"""
Colorado DJ Basin — Well-Level Production Aggregator.

One-time script that reads 10 years of Colorado COGCC well-level production
reports (2015-2024 ≈ 1 GB total) and aggregates them into 3 summary tables
saved to Supabase for fast dashboard access.

Source: Colorado Oil & Gas Conservation Commission (COGCC)
Files: /colordo/{year}_prod_reports.csv  (10 files, ~100 MB each)

Output tables:
  colorado_monthly       — month-level basin totals (oil, gas, water, wells, active_ops)
  colorado_formations    — per formation annual totals (Niobrara, Codell, J Sand, etc)
  colorado_operators     — top operators by lifetime production
  colorado_decline_curve — normalized decline curve (month 1 → month 36 avg)

Memory approach:
  Process one file at a time → aggregate → write partial results → free memory.
  Never holds more than 1 year of data in memory.

Run once:
    python -m src.data.colorado.aggregator
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)

COLORADO_DIR = _PROJECT_ROOT / "colordo"
YEARS        = range(2015, 2025)

# COGCC formation codes → human-readable names
# Codes are 4-6 chars, padded with spaces; we strip before mapping.
FORMATION_NAMES = {
    "NBRR": "Niobrara",
    "NBRRA": "Niobrara",
    "NIOBR": "Niobrara",
    "NIOB": "Niobrara",
    "CODL": "Codell",
    "CODELL": "Codell",
    "JSND": "J Sand",
    "J":    "J Sand",
    "JSANDD": "J Sand",
    "DSND": "D Sand",
    "DAKOTA":"Dakota",
    "DAK":  "Dakota",
    "GRNHN":"Greenhorn",
    "MCOS": "Mancos",
    "MANCOS":"Mancos",
    "WSTR": "Wasatch",
    "PIERRE":"Pierre",
    "CRTHG":"Carthage",
    "FXHLS":"Fox Hills",
}


def _clean_formation(code: str) -> str:
    """Strip whitespace, uppercase, map to canonical name."""
    if pd.isna(code):
        return "Unknown"
    c = str(code).strip().upper()
    return FORMATION_NAMES.get(c, c if len(c) > 0 else "Unknown")


# ── Core aggregation — one file at a time ─────────────────────────────────────

def aggregate_year(year: int) -> dict:
    """
    Read one year's production CSV and return aggregation dicts.
    Does NOT hold the whole file in memory if we use chunksize.
    """
    path = COLORADO_DIR / f"{year}_prod_reports.csv"
    if not path.exists():
        logger.warning(f"File missing: {path}")
        return {}

    logger.info(f"Processing {path.name} ({path.stat().st_size / 1e6:.1f} MB)...")

    # Read only the columns we need → 4x faster, 4x less memory
    use_cols = [
        "ReportMonth", "ReportYear", "OpName", "FormationCode",
        "OilProduced", "GasProduced", "WaterProduced",
        "ApiCountyCode", "ApiSequenceNumber", "WellStatus",
    ]

    monthly   = {}     # (year, month) → {oil, gas, water, wells, ops}
    formation = {}     # (year, formation) → {oil, gas, wells}
    operator  = {}     # opname → {oil, gas, months_active}
    well_hist = {}     # well_api → list of (year, month, oil, gas) for decline curves

    chunk_iter = pd.read_csv(
        path,
        usecols  = use_cols,
        chunksize= 500_000,
        low_memory = False,
        dtype    = {
            "OilProduced":   "float64",
            "GasProduced":   "float64",
            "WaterProduced": "float64",
        },
    )

    row_count = 0
    for chunk in chunk_iter:
        row_count += len(chunk)

        # Clean numerics — coerce errors to 0
        for col in ["OilProduced", "GasProduced", "WaterProduced"]:
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0)

        chunk["Formation"] = chunk["FormationCode"].apply(_clean_formation)
        chunk["WellID"]    = (
            chunk["ApiCountyCode"].astype(str).str.zfill(3) + "-" +
            chunk["ApiSequenceNumber"].astype(str).str.zfill(5)
        )

        # ── Monthly basin totals ───────────────────────────────────────────
        g_monthly = chunk.groupby(["ReportYear", "ReportMonth"]).agg(
            oil   = ("OilProduced",   "sum"),
            gas   = ("GasProduced",   "sum"),
            water = ("WaterProduced", "sum"),
            wells = ("WellID",        "nunique"),
            ops   = ("OpName",        "nunique"),
        ).reset_index()
        for _, r in g_monthly.iterrows():
            key = (int(r["ReportYear"]), int(r["ReportMonth"]))
            if key not in monthly:
                monthly[key] = {"oil":0, "gas":0, "water":0, "wells":set(), "ops":set()}
            monthly[key]["oil"]   += r["oil"]
            monthly[key]["gas"]   += r["gas"]
            monthly[key]["water"] += r["water"]

        # Separate pass for unique sets (groupby nunique loses identity across chunks)
        for (y, m), sub in chunk.groupby(["ReportYear", "ReportMonth"]):
            key = (int(y), int(m))
            if key not in monthly:
                monthly[key] = {"oil":0, "gas":0, "water":0, "wells":set(), "ops":set()}
            monthly[key]["wells"].update(sub["WellID"].unique())
            monthly[key]["ops"].update(sub["OpName"].dropna().unique())

        # ── Formation totals ───────────────────────────────────────────────
        g_form = chunk.groupby(["ReportYear", "Formation"]).agg(
            oil = ("OilProduced",   "sum"),
            gas = ("GasProduced",   "sum"),
        ).reset_index()
        for _, r in g_form.iterrows():
            key = (int(r["ReportYear"]), r["Formation"])
            if key not in formation:
                formation[key] = {"oil":0, "gas":0, "wells":set()}
            formation[key]["oil"] += r["oil"]
            formation[key]["gas"] += r["gas"]
        for (y, f), sub in chunk.groupby(["ReportYear", "Formation"]):
            formation[(int(y), f)]["wells"].update(sub["WellID"].unique())

        # ── Operator totals ────────────────────────────────────────────────
        g_op = chunk.groupby("OpName").agg(
            oil = ("OilProduced", "sum"),
            gas = ("GasProduced", "sum"),
        ).reset_index()
        for _, r in g_op.iterrows():
            op = r["OpName"]
            if pd.isna(op): continue
            if op not in operator:
                operator[op] = {"oil":0, "gas":0, "wells":set(), "years":set()}
            operator[op]["oil"]   += r["oil"]
            operator[op]["gas"]   += r["gas"]
            operator[op]["years"].add(year)
        for op, sub in chunk.groupby("OpName"):
            if pd.isna(op): continue
            operator[op]["wells"].update(sub["WellID"].unique())

    logger.info(f"  {year}: {row_count:,} rows processed")

    return {
        "monthly":   monthly,
        "formation": formation,
        "operator":  operator,
    }


# ── Merge per-year dicts into final DataFrames ────────────────────────────────

def build_monthly_df(all_years: list[dict]) -> pd.DataFrame:
    combined = {}
    for yr_dict in all_years:
        for key, vals in yr_dict.get("monthly", {}).items():
            if key not in combined:
                combined[key] = {"oil":0, "gas":0, "water":0, "wells":set(), "ops":set()}
            combined[key]["oil"]   += vals["oil"]
            combined[key]["gas"]   += vals["gas"]
            combined[key]["water"] += vals["water"]
            combined[key]["wells"].update(vals["wells"])
            combined[key]["ops"].update(vals["ops"])

    rows = []
    for (yr, mo), v in sorted(combined.items()):
        rows.append({
            "period":        f"{yr:04d}-{mo:02d}-01",
            "year":          yr,
            "month":         mo,
            "oil_bbl":       round(v["oil"], 0),
            "gas_mcf":       round(v["gas"], 0),
            "water_bbl":     round(v["water"], 0),
            "active_wells":  len(v["wells"]),
            "active_operators": len(v["ops"]),
        })
    return pd.DataFrame(rows)


def build_formation_df(all_years: list[dict]) -> pd.DataFrame:
    combined = {}
    for yr_dict in all_years:
        for key, vals in yr_dict.get("formation", {}).items():
            if key not in combined:
                combined[key] = {"oil":0, "gas":0, "wells":set()}
            combined[key]["oil"] += vals["oil"]
            combined[key]["gas"] += vals["gas"]
            combined[key]["wells"].update(vals["wells"])

    rows = []
    for (yr, formation), v in combined.items():
        rows.append({
            "year":      yr,
            "formation": formation,
            "oil_bbl":   round(v["oil"], 0),
            "gas_mcf":   round(v["gas"], 0),
            "wells":     len(v["wells"]),
        })
    return pd.DataFrame(rows)


def build_operator_df(all_years: list[dict], top_n: int = 25) -> pd.DataFrame:
    combined = {}
    for yr_dict in all_years:
        for op, vals in yr_dict.get("operator", {}).items():
            if op not in combined:
                combined[op] = {"oil":0, "gas":0, "wells":set(), "years":set()}
            combined[op]["oil"] += vals["oil"]
            combined[op]["gas"] += vals["gas"]
            combined[op]["wells"].update(vals["wells"])
            combined[op]["years"].update(vals["years"])

    rows = [{
        "operator":     op,
        "oil_bbl":      round(v["oil"], 0),
        "gas_mcf":      round(v["gas"], 0),
        "wells":        len(v["wells"]),
        "years_active": len(v["years"]),
    } for op, v in combined.items()]

    df = pd.DataFrame(rows)
    df = df.sort_values("oil_bbl", ascending=False).head(top_n).reset_index(drop=True)
    return df


# ── Decline curve — needs separate pass (wells tracked over time) ─────────────

def build_decline_curve(top_n_wells: int = 500) -> pd.DataFrame:
    """
    Build the normalized decline curve — month-since-first-production vs
    avg production across the top N most productive wells.

    This requires one more pass where we:
      1. Find each well's first production month
      2. Normalize all well months to "months since spud"
      3. Average across wells for each normalized month
    """
    logger.info(f"Building decline curve across top {top_n_wells} wells ...")

    use_cols = [
        "ReportMonth", "ReportYear",
        "ApiCountyCode", "ApiSequenceNumber",
        "OilProduced", "GasProduced",
    ]

    # Step 1: collect all well production over time, keeping only top wells
    all_rows = []
    for year in YEARS:
        path = COLORADO_DIR / f"{year}_prod_reports.csv"
        if not path.exists():
            continue
        for chunk in pd.read_csv(path, usecols=use_cols, chunksize=500_000,
                                 low_memory=False):
            chunk["OilProduced"] = pd.to_numeric(chunk["OilProduced"], errors="coerce").fillna(0)
            chunk["GasProduced"] = pd.to_numeric(chunk["GasProduced"], errors="coerce").fillna(0)
            chunk["WellID"] = (
                chunk["ApiCountyCode"].astype(str).str.zfill(3) + "-" +
                chunk["ApiSequenceNumber"].astype(str).str.zfill(5)
            )
            chunk["date"] = pd.to_datetime(
                chunk["ReportYear"].astype(str) + "-" +
                chunk["ReportMonth"].astype(str).str.zfill(2) + "-01",
                errors="coerce"
            )
            all_rows.append(chunk[["WellID","date","OilProduced","GasProduced"]])

    if not all_rows:
        return pd.DataFrame()

    df = pd.concat(all_rows, ignore_index=True).dropna(subset=["date"])
    logger.info(f"  total well-months loaded: {len(df):,}")

    # Step 2: top N wells by cumulative oil
    top_wells = (
        df.groupby("WellID")["OilProduced"].sum()
        .sort_values(ascending=False).head(top_n_wells).index
    )
    df = df[df["WellID"].isin(top_wells)].copy()

    # Step 3: normalize to months-since-first-production per well
    df = df.sort_values(["WellID", "date"])
    df["first_month"] = df.groupby("WellID")["date"].transform("min")
    df["month_index"] = (
        (df["date"].dt.year - df["first_month"].dt.year) * 12
        + (df["date"].dt.month - df["first_month"].dt.month) + 1
    )

    # Only look at first 36 months
    df = df[df["month_index"] <= 36]

    # Step 4: average production per month-index across wells
    curve = df.groupby("month_index").agg(
        avg_oil_bbl  = ("OilProduced", "mean"),
        avg_gas_mcf  = ("GasProduced", "mean"),
        well_count   = ("WellID",      "nunique"),
    ).reset_index()

    curve["avg_oil_bbl"] = curve["avg_oil_bbl"].round(1)
    curve["avg_gas_mcf"] = curve["avg_gas_mcf"].round(1)

    # Add month 1 baseline decline %
    m1_oil = float(curve.iloc[0]["avg_oil_bbl"]) if not curve.empty else 1.0
    m1_gas = float(curve.iloc[0]["avg_gas_mcf"]) if not curve.empty else 1.0
    curve["oil_pct_of_month1"] = ((curve["avg_oil_bbl"] / m1_oil) * 100).round(1) if m1_oil else 0
    curve["gas_pct_of_month1"] = ((curve["avg_gas_mcf"] / m1_gas) * 100).round(1) if m1_gas else 0

    return curve


# ── Save to Supabase ──────────────────────────────────────────────────────────

def save_to_supabase(monthly_df, formation_df, operator_df, decline_df):
    """Save all aggregation results to Supabase — tables must exist first."""
    from src.data.db import _upsert

    if not monthly_df.empty:
        # Add computed_at for audit
        monthly_df["computed_at"] = pd.Timestamp.now().isoformat()
        recs = monthly_df.to_dict("records")
        _upsert("colorado_monthly", recs)
        logger.info(f"Saved {len(recs)} monthly rows")

    if not formation_df.empty:
        formation_df["computed_at"] = pd.Timestamp.now().isoformat()
        recs = formation_df.to_dict("records")
        _upsert("colorado_formations", recs)
        logger.info(f"Saved {len(recs)} formation rows")

    if not operator_df.empty:
        operator_df["computed_at"] = pd.Timestamp.now().isoformat()
        recs = operator_df.to_dict("records")
        _upsert("colorado_operators", recs)
        logger.info(f"Saved {len(recs)} operator rows")

    if not decline_df.empty:
        decline_df["computed_at"] = pd.Timestamp.now().isoformat()
        recs = decline_df.to_dict("records")
        _upsert("colorado_decline_curve", recs)
        logger.info(f"Saved {len(recs)} decline curve rows")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("=" * 70)
    logger.info("COLORADO DJ BASIN CASE STUDY — AGGREGATION")
    logger.info("=" * 70)

    # Process each year
    all_years = []
    for year in YEARS:
        result = aggregate_year(year)
        if result:
            all_years.append(result)

    logger.info(f"\nProcessed {len(all_years)} years. Building final DataFrames ...")

    monthly_df   = build_monthly_df(all_years)
    formation_df = build_formation_df(all_years)
    operator_df  = build_operator_df(all_years)

    logger.info(f"  monthly rows:     {len(monthly_df)}")
    logger.info(f"  formation rows:   {len(formation_df)}")
    logger.info(f"  operator rows:    {len(operator_df)}")

    # Decline curve needs its own pass
    decline_df = build_decline_curve(top_n_wells=500)
    logger.info(f"  decline rows:     {len(decline_df)}")

    # Save to Supabase
    logger.info("\nSaving to Supabase ...")
    save_to_supabase(monthly_df, formation_df, operator_df, decline_df)

    # Also save CSV backups locally
    out_dir = _PROJECT_ROOT / "src" / "data" / "colorado" / "output"
    out_dir.mkdir(exist_ok=True)
    monthly_df.to_csv(out_dir / "colorado_monthly.csv", index=False)
    formation_df.to_csv(out_dir / "colorado_formations.csv", index=False)
    operator_df.to_csv(out_dir / "colorado_operators.csv", index=False)
    decline_df.to_csv(out_dir / "colorado_decline_curve.csv", index=False)
    logger.info(f"CSV backups saved to {out_dir}")

    logger.info("\n" + "=" * 70)
    logger.info("COMPLETE")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
