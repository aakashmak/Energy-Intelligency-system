"""
EIA Petroleum Supply Monthly fetcher.
Source: https://www.eia.gov/petroleum/supply/monthly/
API:    /v2/petroleum/crd/crpdn/data  — Crude Oil Production by state

This is the exact dataset the hackathon references as:
"EIA Petroleum Supply Monthly — historical production volumes"

Endpoint: /v2/petroleum/crd/crpdn/data
  - crpdn = Crude oil production (the PSM production series)
  - duoarea facet with state codes: STX, SNM, SND, SMT, SWV, SPA, SOH, SLA
  - NO product/process facets needed — this endpoint is already scoped to
    crude oil field production by state
  - Unit: Thousand Barrels (MBBL) per month

Note: /v2/petroleum/sum/sndprd/data is a supply & disposition endpoint that
requires specific product+process facet combinations that vary by state.
/v2/petroleum/crd/crpdn/data is the cleaner, direct crude production endpoint.
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

STATE_DUOAREA = {
    "TX": "STX",
    "NM": "SNM",
    "ND": "SND",
    "MT": "SMT",
    "WV": "SWV",
    "PA": "SPA",
    "OH": "SOH",
    "LA": "SLA",
}
DUOAREA_STATE = {v: k for k, v in STATE_DUOAREA.items()}

REGION_STATES = {
    "Permian":    ["TX", "NM"],
    "Bakken":     ["ND", "MT"],
    "Eagle Ford": ["TX"],
    "Appalachia": ["WV", "PA", "OH"],
    "Gulf Coast": ["LA", "TX"],
}


def fetch_petroleum_supply_monthly(start: str = "2015-01") -> pd.DataFrame:
    """
    Fetch EIA crude oil production by state (Petroleum Supply Monthly equivalent).

    Endpoint: /v2/petroleum/crd/crpdn/data
    Unit:     Thousand Barrels (MBBL) per month
    States:   TX, NM, ND, MT, WV, PA, OH, LA

    Returns DataFrame:
        [state, period, value, unit, product, process, source]
    """
    if not API_KEY:
        raise ValueError("EIA_API_KEY not set.")

    logger.info("Fetching EIA Petroleum Supply Monthly (crude oil production) ...")
    logger.info("  Endpoint: /v2/petroleum/crd/crpdn/data")
    logger.info(f"  States: {', '.join(STATE_DUOAREA.keys())} | Period: {start} → present")

    all_records = []
    offset = 0

    while True:
        params = {
            "api_key":              API_KEY,
            "frequency":            "monthly",
            "data[0]":              "value",
            "facets[duoarea][]":    list(STATE_DUOAREA.values()),
            "sort[0][column]":      "period",
            "sort[0][direction]":   "asc",
            "offset":               offset,
            "length":               5000,
            "start":                start,
        }

        try:
            resp = requests.get(
                f"{BASE_URL}/petroleum/crd/crpdn/data",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Petroleum Supply Monthly fetch failed: {e}")
            raise

        body    = resp.json().get("response", {})
        records = body.get("data", [])
        total   = int(body.get("total", 0))
        all_records.extend(records)

        logger.info(f"  fetched {len(all_records)}/{total} records ...")

        if len(all_records) >= total or not records:
            break
        offset += 5000
        time.sleep(0.3)

    if not all_records:
        logger.warning("Petroleum Supply Monthly: no records returned")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)

    # Parse
    df["value"]  = pd.to_numeric(df.get("value", pd.Series(dtype=float)), errors="coerce")
    df["period"] = pd.to_datetime(df["period"], format="%Y-%m", errors="coerce")
    df = df.dropna(subset=["period", "value"])
    df = df[df["value"] > 0]

    # Map duoarea → state
    df["state"] = df["duoarea"].map(DUOAREA_STATE)
    df = df[df["state"].notna()]

    # Deduplicate (state, period) — sum if multiple product lines returned
    df = df.groupby(["period", "state"], as_index=False)["value"].sum()

    df["unit"]    = "MBBL/month"
    df["product"] = "crude_oil"
    df["process"] = "field_production"
    df["source"]  = "EIA_petroleum_supply_monthly"

    logger.info(
        f"Petroleum Supply Monthly: {len(df)} rows | "
        f"{df['state'].nunique()} states | "
        f"{df['period'].min().date()} → {df['period'].max().date()}"
    )

    return df[["state", "period", "value", "unit", "product", "process", "source"]]


def aggregate_psm_to_regions(psm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate state-level PSM data into 5 investment regions.
    Returns DataFrame compatible with the production table schema:
        [region, commodity, period, value, source, unit]
    """
    if psm_df.empty:
        return pd.DataFrame()

    rows = []
    for region, states in REGION_STATES.items():
        subset = psm_df[psm_df["state"].isin(states)]
        if subset.empty:
            continue
        agg = subset.groupby("period")["value"].sum().reset_index()
        agg["region"]    = region
        agg["commodity"] = "oil"
        agg["source"]    = "EIA_psm_agg"
        agg["unit"]      = "MBBL/month"
        rows.append(agg)

    if not rows:
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True)
    return result[["region", "commodity", "period", "value", "source", "unit"]]
