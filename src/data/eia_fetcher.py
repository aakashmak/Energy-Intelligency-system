"""
EIA APIv2 data fetcher — oil and gas production by region, state, and basin.

Data sourced from:
  Oil — EIA Petroleum Supply Monthly (petroleum/crd/crpdn/data)
         Process: FPF = Field Production of Crude Oil
  Gas — EIA Natural Gas Monthly (natural-gas/prod/sum/data)
         Process: FGW = Gross Withdrawals

Confirmed process codes from debug_gas_processes.py output:
  Gas endpoint natural-gas/prod/sum returns three processes per state:
    FGW = Gross Withdrawals        ← total gas at wellhead (use this)
    FGG = Withdrawals from Gas Wells
    FGO = Withdrawals from Oil Wells
  FGW = FGG + FGO (it is the sum of the two sub-types)
  We use FGW only — filtering to one process gives exactly 1 row per
  state per month and prevents the 3x inflation from summing all codes.

Both commodities fetched ONE STATE AT A TIME — EIA batched multi-state
requests only return partial results. Per-state loop guarantees coverage.
"""

import os
import time
import logging
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

logger   = logging.getLogger(__name__)
API_KEY  = os.getenv("EIA_API_KEY", "")
BASE_URL = "https://api.eia.gov/v2"

REGION_STATES = {
    "Permian":    ["TX", "NM"],
    "Bakken":     ["ND", "MT"],
    "Eagle Ford": ["TX"],
    "Appalachia": ["WV", "PA", "OH"],
    "Gulf Coast": ["LA", "TX"],
}

STATE_DUOAREA = {
    "TX": "STX", "NM": "SNM", "ND": "SND", "MT": "SMT",
    "WV": "SWV", "PA": "SPA", "OH": "SOH", "LA": "SLA",
}
DUOAREA_STATE = {v: k for k, v in STATE_DUOAREA.items()}

SOURCE_OIL_PRIMARY  = "EIA Petroleum Supply Monthly"
SOURCE_OIL_FALLBACK = "EIA Petroleum Supply Monthly (PSM)"
SOURCE_GAS_PRIMARY  = "EIA Natural Gas Monthly (Gross Withdrawals)"
SOURCE_GAS_FALLBACK = "EIA Natural Gas Monthly (Gas Wells)"

# ── Process code filters ───────────────────────────────────────────────────────
# Filter to ONE process per endpoint so each (state, period) = exactly 1 row.
# Without this filter the gas endpoint returns FGW + FGG + FGO summed = 3x inflation.
OIL_PROCESS         = "FPF"   # Field Production of Crude Oil
GAS_PROCESS         = "FGW"   # Gross Withdrawals (= FGG + FGO combined, the total)
GAS_FALLBACK_PROCESS= "FGG"   # Withdrawals from Gas Wells (fallback)


def _validate_key() -> None:
    if not API_KEY:
        raise ValueError("EIA_API_KEY not set.")


def _fetch_one(route: str, params: dict) -> list[dict]:
    """
    Paginated GET for one state + one process. Returns raw record dicts.
    Fetching one state at a time is required — EIA batched multi-state
    requests only return partial results for these endpoints.
    """
    _validate_key()
    url         = f"{BASE_URL}/{route}"
    all_records = []
    offset      = 0
    length      = 5000

    while True:
        p = {**params, "api_key": API_KEY, "offset": offset, "length": length}
        try:
            resp = requests.get(url, params=p, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"EIA request failed [{route}]: {e}")
            return []

        body    = resp.json().get("response", {})
        records = body.get("data", [])
        total   = int(body.get("total", 0))
        all_records.extend(records)

        if len(all_records) >= total or not records:
            break
        offset += length
        time.sleep(0.2)

    return all_records


def _fetch_all_states(
    route: str,
    base_params: dict,
    start: str,
    process: str | None = None,
) -> list[dict]:
    """
    Fetch data for all 8 states one at a time with an optional process filter.
    Returns combined list of all raw records.
    """
    all_records = []
    for state, duoarea in STATE_DUOAREA.items():
        params = {
            **base_params,
            "facets[duoarea][]": duoarea,
            "start":             start,
        }
        if process:
            params["facets[process][]"] = process

        records = _fetch_one(route, params)
        if records:
            logger.info(f"    {state} ({duoarea}): {len(records)} records")
            all_records.extend(records)
        else:
            logger.warning(f"    {state} ({duoarea}): no data returned")
        time.sleep(0.3)

    return all_records


def _safe_col(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col in df.columns:
        return df[col].fillna(default)
    return pd.Series(default, index=df.index)


def _parse_state_df(
    records: list[dict],
    source: str,
    unit: str,
    commodity: str,
) -> pd.DataFrame:
    """
    Parse raw EIA records into a clean deduplicated state-level DataFrame.
    With process filter applied upstream, each (state, period) = 1 row.
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    df["value"]  = pd.to_numeric(df["value"], errors="coerce") if "value" in df.columns else 0
    df["period"] = pd.to_datetime(df["period"], format="%Y-%m", errors="coerce")
    df = df.dropna(subset=["period", "value"])
    df = df[df["value"] > 0]

    df["state"] = df["duoarea"].map(DUOAREA_STATE)
    df = df[df["state"].notna()]

    df["process_name"] = _safe_col(df, "process-name")
    df["product_name"] = _safe_col(df, "product-name")
    df["process_code"] = _safe_col(df, "process")
    df["product_code"] = _safe_col(df, "product")

    sample_proc  = df["process_name"].iloc[0] if len(df) else "EMPTY"
    sample_prod  = df["product_name"].iloc[0] if len(df) else "EMPTY"
    states_found = sorted(df["state"].unique())
    logger.info(
        f"  EIA parse | process='{sample_proc}' | product='{sample_prod}' | "
        f"rows={len(df)} | states={states_found}"
    )

    # Deduplicate (state, period) — with process filter this is 1:1
    meta = (
        df.groupby(["period", "state"])[
            ["process_name", "product_name", "process_code", "product_code"]
        ].first().reset_index()
    )
    values = df.groupby(["period", "state"], as_index=False)["value"].sum()
    result = values.merge(meta, on=["period", "state"], how="left")

    result["commodity"] = commodity
    result["source"]    = source
    result["unit"]      = unit

    return result


# ── Oil production ─────────────────────────────────────────────────────────────

def fetch_oil_by_state(start: str = "2015-01") -> pd.DataFrame:
    """
    Monthly crude oil field production by state.
    Source: EIA Petroleum Supply Monthly
    Endpoint: /v2/petroleum/crd/crpdn/data | Process: FPF
    Unit: Thousand Barrels/month
    """
    base_params = {
        "frequency":          "monthly",
        "data[0]":            "value",
        "sort[0][column]":    "period",
        "sort[0][direction]": "asc",
    }

    logger.info(f"Fetching oil — process={OIL_PROCESS} | one state at a time ...")
    records = _fetch_all_states(
        "petroleum/crd/crpdn/data", base_params, start, process=OIL_PROCESS
    )

    if records:
        df = _parse_state_df(records, SOURCE_OIL_PRIMARY, "Mbbl/month", "oil")
        if not df.empty:
            logger.info(
                f"  Oil: {len(df)} rows | "
                f"{df['state'].nunique()} states | "
                f"{df['period'].min().date()} → {df['period'].max().date()}"
            )
            return df

    logger.info("Oil fallback — petroleum/sum/sndprd | process=FPF ...")
    records = _fetch_all_states(
        "petroleum/sum/sndprd/data", base_params, start, process="FPF"
    )
    if records:
        return _parse_state_df(records, SOURCE_OIL_FALLBACK, "Mbbl/month", "oil")

    logger.error("All oil fetch attempts failed")
    return pd.DataFrame()


# ── Gas production ─────────────────────────────────────────────────────────────

def fetch_gas_by_state(start: str = "2015-01") -> pd.DataFrame:
    """
    Monthly natural gas gross withdrawals by state.
    Source: EIA Natural Gas Monthly
    Endpoint: /v2/natural-gas/prod/sum/data | Process: FGW

    Process selection rationale (from debug_gas_processes.py):
      FGW (Gross Withdrawals) = FGG + FGO — the total wellhead figure.
      Using FGW alone gives exactly 1 clean row per state per month.
      Summing FGW+FGG+FGO would triple-count and inflate by 3x.

    Fallback: FGG (Withdrawals from Gas Wells) if FGW unavailable.
    Unit: Million Cubic Feet/month
    """
    base_params = {
        "frequency":          "monthly",
        "data[0]":            "value",
        "sort[0][column]":    "period",
        "sort[0][direction]": "asc",
    }

    logger.info(f"Fetching gas — process={GAS_PROCESS} | one state at a time ...")
    records = _fetch_all_states(
        "natural-gas/prod/sum/data", base_params, start, process=GAS_PROCESS
    )

    if records:
        df = _parse_state_df(records, SOURCE_GAS_PRIMARY, "MMcf/month", "gas")
        if not df.empty:
            logger.info(
                f"  Gas: {len(df)} rows | "
                f"{df['state'].nunique()} states | "
                f"{df['period'].min().date()} → {df['period'].max().date()}"
            )
            return df

    logger.info(f"Gas fallback — process={GAS_FALLBACK_PROCESS} ...")
    records = _fetch_all_states(
        "natural-gas/prod/sum/data", base_params, start, process=GAS_FALLBACK_PROCESS
    )
    if records:
        return _parse_state_df(records, SOURCE_GAS_FALLBACK, "MMcf/month", "gas")

    logger.error("All gas fetch attempts failed")
    return pd.DataFrame()


# ── Aggregate states → regions ─────────────────────────────────────────────────

def _aggregate_to_regions(state_df: pd.DataFrame, commodity: str) -> pd.DataFrame:
    """Sum state-level production into 5 investment regions."""
    if state_df.empty:
        return pd.DataFrame()

    rows = []
    for region, states in REGION_STATES.items():
        subset = state_df[state_df["state"].isin(states)]
        if subset.empty:
            continue

        agg = subset.groupby("period")["value"].sum().reset_index()
        agg["region"]       = region
        agg["commodity"]    = commodity
        agg["source"]       = state_df["source"].iloc[0] + " (by region)"
        agg["unit"]         = state_df["unit"].iloc[0]
        agg["process_name"] = state_df["process_name"].iloc[0] if "process_name" in state_df.columns else ""
        agg["product_name"] = state_df["product_name"].iloc[0] if "product_name" in state_df.columns else ""
        rows.append(agg)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


# ── Master fetch ───────────────────────────────────────────────────────────────

def fetch_all_production(start: str = "2015-01") -> pd.DataFrame:
    """
    Fetch all oil and gas production aggregated to region level.
    Each commodity fetched per-state with correct process code filter.
    """
    frames = []

    oil_state = fetch_oil_by_state(start)
    if not oil_state.empty:
        oil_region = _aggregate_to_regions(oil_state, "oil")
        if not oil_region.empty:
            frames.append(oil_region)

    gas_state = fetch_gas_by_state(start)
    if not gas_state.empty:
        gas_region = _aggregate_to_regions(gas_state, "gas")
        if not gas_region.empty:
            frames.append(gas_region)

    if not frames:
        raise RuntimeError("All EIA fetches failed.")

    return (
        pd.concat(frames, ignore_index=True)
        .dropna(subset=["value"])
        .pipe(lambda d: d[d["value"] > 0])
        .sort_values(["region", "commodity", "period"])
        .reset_index(drop=True)
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    df = fetch_all_production()
    print(f"\n{len(df)} total rows")
    print(df.groupby(["region", "commodity"])[["value"]].describe().round(0))
