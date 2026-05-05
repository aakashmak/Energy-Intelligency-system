"""
Supabase REST client — raw HTTP requests, works with all key types.
(sb_secret_, sb_publishable_, legacy JWT)
"""
import os
import logging
import pandas as pd
import requests as req
from pathlib import Path
from dotenv import load_dotenv
from src.data.schema import REGION_META

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def _headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }


def _rest_url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


def _validate_env() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise EnvironmentError(
            f"Missing SUPABASE_URL or SUPABASE_KEY\n"
            f"  .env expected at: {_PROJECT_ROOT / '.env'}"
        )


def test_connection() -> bool:
    _validate_env()
    try:
        resp = req.get(
            _rest_url("regions"),
            headers=_headers(),
            params={"select": "region", "limit": "1"},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Supabase connection OK")
            return True
        logger.error(f"Supabase ping failed: {resp.status_code} — {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Supabase ping error: {e}")
        return False


def init_schema() -> None:
    """Upsert region metadata into Supabase regions table."""
    _validate_env()
    payload = [
        {"region": r, "state_codes": sc, "basin_type": bt, "lat": lat, "lon": lon}
        for r, sc, bt, lat, lon in REGION_META
    ]
    resp = req.post(
        _rest_url("regions"),
        headers=_headers(),
        json=payload,
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"init_schema failed: {resp.status_code} — {resp.text}")
    logger.info(f"Seeded {len(REGION_META)} regions")


def _upsert(table: str, records: list[dict], chunk_size: int = 500) -> int:
    """POST records to Supabase REST with upsert. Returns total rows written."""
    _validate_env()
    total = 0
    for i in range(0, len(records), chunk_size):
        chunk = records[i: i + chunk_size]
        resp  = req.post(
            _rest_url(table),
            headers=_headers(),
            json=chunk,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Upsert to {table} failed: {resp.status_code} — {resp.text[:300]}"
            )
        total += len(chunk)
    return total


# ── Upserts ────────────────────────────────────────────────────────────────────

def upsert_production(df: pd.DataFrame) -> int:
    """Upsert region-level production. Required: [region, commodity, period, value, source]"""
    if df.empty:
        logger.warning("upsert_production: empty — skipping")
        return 0
    required = {"region", "commodity", "period", "value", "source"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")

    df = df.copy()
    df["period"]     = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
    df["updated_at"] = pd.Timestamp.now().isoformat()
    for col in ["unit", "process_name", "product_name"]:
        if col not in df.columns:
            df[col] = None

    cols    = ["region", "commodity", "period", "value",
               "source", "unit", "process_name", "product_name", "updated_at"]
    records = df[cols].to_dict("records")
    total   = _upsert("production", records)
    logger.info(f"upsert_production — {total} rows written")
    return total


def upsert_state_production(df: pd.DataFrame) -> int:
    """Upsert raw state-level production. Required: [state, commodity, period, value, source]"""
    if df.empty:
        return 0
    df = df.copy()
    df["period"]     = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
    df["updated_at"] = pd.Timestamp.now().isoformat()
    for col in ["unit", "process_name", "product_name", "process_code", "product_code"]:
        if col not in df.columns:
            df[col] = None
    cols = [c for c in [
        "state", "commodity", "period", "value", "source", "unit",
        "process_name", "product_name", "process_code", "product_code", "updated_at",
    ] if c in df.columns]
    records = df[cols].to_dict("records")
    total   = _upsert("state_production", records)
    logger.info(f"upsert_state_production — {total} rows written")
    return total


def upsert_rig_counts(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    df = df.copy()
    df["period"] = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
    records = df[["region", "period", "rigs"]].to_dict("records")
    total   = _upsert("rig_counts", records)
    logger.info(f"upsert_rig_counts — {total} rows written")
    return total


def upsert_forecasts(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    df = df.copy()
    df["period"]   = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
    df["run_date"] = pd.to_datetime(df["run_date"]).dt.strftime("%Y-%m-%d")
    records = df[["region", "commodity", "period",
                  "forecast", "lower_ci", "upper_ci", "run_date"]].to_dict("records")
    total   = _upsert("forecasts", records)
    logger.info(f"upsert_forecasts — {total} rows written")
    return total


def upsert_scores(df: pd.DataFrame) -> int:
    """Upsert all KPI scores — Tier 1 + Tier 2 custom KPIs."""
    if df.empty:
        return 0
    df = df.copy()
    df["computed_at"] = pd.Timestamp.now().isoformat()
    all_score_cols = [
        "region", "score", "rank", "projected_prod",
        "yoy_growth", "momentum", "volatility",
        "decline_rate", "revenue_potential", "consistency_score",
        "rel_performance", "wti_price_used", "henry_price_used",
        "computed_at",
    ]
    cols    = [c for c in all_score_cols if c in df.columns]
    records = df[cols].to_dict("records")
    total   = _upsert("scores", records)
    logger.info(f"upsert_scores — {total} rows written")
    return total


def upsert_quarterly_kpis(df: pd.DataFrame) -> int:
    """
    Upsert quarterly KPI data to Supabase quarterly_kpis table.
    One row per (region, commodity, year, quarter).

    This is the table the dashboard reads for:
      - Projected Production KPI (quarterly breakdown)
      - QoQ and YoY growth cards per quarter
      - Forecast vs actuals by quarter (is_forecast flag)
    """
    if df.empty:
        return 0
    d = df.copy()
    d["computed_at"] = pd.Timestamp.now().isoformat()
    cols = [c for c in [
        "region", "commodity", "year", "quarter",
        "value", "lower_ci", "upper_ci",
        "is_forecast", "data_type", "confidence",
        "qoq_growth", "yoy_growth", "computed_at",
    ] if c in d.columns]
    records = d[cols].to_dict("records")
    total   = _upsert("quarterly_kpis", records)
    logger.info(f"upsert_quarterly_kpis — {total} rows written")
    return total


# ── Reads ──────────────────────────────────────────────────────────────────────

def _select(table: str, columns: str, filters: dict | None = None) -> pd.DataFrame:
    _validate_env()
    params: dict = {"select": columns}
    if filters:
        params.update(filters)
    resp = req.get(
        _rest_url(table),
        headers={**_headers(), "Prefer": ""},
        params=params,
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"SELECT {table} failed: {resp.status_code} — {resp.text[:300]}")
    return pd.DataFrame(resp.json())


def read_production(region: str | None = None, commodity: str | None = None) -> pd.DataFrame:
    filters = {}
    if region:
        filters["region"] = f"eq.{region}"
    if commodity:
        filters["commodity"] = f"eq.{commodity}"
    df = _select(
        "production",
        "region,commodity,period,value,source,unit,process_name,product_name",
        filters,
    )
    if not df.empty:
        df["period"] = pd.to_datetime(df["period"])
    return df


def read_state_production(state: str | None = None, commodity: str | None = None) -> pd.DataFrame:
    filters = {}
    if state:
        filters["state"] = f"eq.{state}"
    if commodity:
        filters["commodity"] = f"eq.{commodity}"
    df = _select(
        "state_production",
        "state,commodity,period,value,unit,source,process_name,product_name",
        filters,
    )
    if not df.empty:
        df["period"] = pd.to_datetime(df["period"])
    return df


def read_rig_counts(region: str | None = None) -> pd.DataFrame:
    filters = {"region": f"eq.{region}"} if region else {}
    df = _select("rig_counts", "region,period,rigs", filters)
    if not df.empty:
        df["period"] = pd.to_datetime(df["period"])
    return df


def read_forecasts(region: str | None = None, commodity: str | None = None) -> pd.DataFrame:
    filters = {}
    if region:
        filters["region"] = f"eq.{region}"
    if commodity:
        filters["commodity"] = f"eq.{commodity}"
    df = _select(
        "forecasts",
        "region,commodity,period,forecast,lower_ci,upper_ci,run_date",
        filters,
    )
    if not df.empty:
        df["period"]   = pd.to_datetime(df["period"])
        df["run_date"] = pd.to_datetime(df["run_date"])
    return df


def read_scores() -> pd.DataFrame:
    return _select("scores", "*")


def read_quarterly_kpis(
    region: str | None = None,
    commodity: str | None = None,
    year: int | None = None,
) -> pd.DataFrame:
    """
    Read quarterly KPIs from Supabase.
    Used by dashboard to render KPI cards and forecast charts per quarter.
    """
    filters = {}
    if region:
        filters["region"] = f"eq.{region}"
    if commodity:
        filters["commodity"] = f"eq.{commodity}"
    if year:
        filters["year"] = f"eq.{year}"
    return _select(
        "quarterly_kpis",
        "region,commodity,year,quarter,value,lower_ci,upper_ci,"
        "is_forecast,data_type,confidence,qoq_growth,yoy_growth",
        filters,
    )


def health_check() -> dict:
    df = read_production()
    if df.empty:
        return {"rows": 0, "regions": 0, "summary": pd.DataFrame()}
    summary = (
        df.groupby(["region", "commodity"])
        .agg(
            months    = ("value",  "count"),
            avg_value = ("value",  "mean"),
            from_date = ("period", "min"),
            to_date   = ("period", "max"),
        )
        .round(2)
        .reset_index()
    )
    return {"rows": len(df), "regions": df["region"].nunique(), "summary": summary}
