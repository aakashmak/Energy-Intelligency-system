"""
Rig Count Fetcher — EIA STEO basin-level active rig counts.

Source: EIA Short-Term Energy Outlook (STEO) — Table 10a
Endpoint: /v2/steo/data

Confirmed series IDs from diagnose_steo_rigs.py output:
  RIGSPM  — Permian Active Rigs
  RIGSBK  — Bakken Active Rigs
  RIGSEF  — Eagle Ford Active Rigs
  RIGSAP  — Appalachia Active Rigs
  RIGSHA  — Haynesville Active Rigs (used for Gulf Coast — closest available)

These are the same Baker Hughes-sourced rig counts that EIA uses internally
for its Drilling Productivity Report, published through STEO Table 10a.
No distribution math required — direct per-basin values.

Run standalone:
    python -m src.data.rig_fetcher
"""

import os
import logging
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

logger  = logging.getLogger(__name__)
API_KEY = os.getenv("EIA_API_KEY", "")

# ── STEO series ID → OilPulse region mapping ──────────────────────────────────
# Confirmed working from diagnose_steo_rigs.py
# Gulf Coast uses Haynesville (closest available STEO basin to Gulf Coast)
STEO_REGION_SERIES = {
    "Permian":    "RIGSPM",
    "Bakken":     "RIGSBK",
    "Eagle Ford": "RIGSEF",
    "Appalachia": "RIGSAP",
    "Gulf Coast": "RIGSHA",   # Haynesville — best proxy for Gulf Coast
}


def _fetch_steo_series(series_id: str, start: str) -> pd.Series:
    """
    Fetch one STEO rig count series by seriesId.
    Returns pd.Series with DatetimeIndex and integer rig count values.
    """
    resp = requests.get(
        "https://api.eia.gov/v2/steo/data",
        params={
            "api_key":            API_KEY,
            "frequency":          "monthly",
            "data[0]":            "value",
            "facets[seriesId][]": series_id,
            "sort[0][column]":    "period",
            "sort[0][direction]": "asc",
            "start":              start,
            "length":             500,
            "offset":             0,
        },
        timeout=30,
    )
    resp.raise_for_status()
    records = resp.json().get("response", {}).get("data", [])

    if not records:
        return pd.Series(dtype=float)

    df = pd.DataFrame(records)
    df["period"] = pd.to_datetime(df["period"], format="%Y-%m", errors="coerce")
    df["value"]  = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["period", "value"])
    return df.set_index("period")["value"].sort_index()


def fetch_rig_counts(start: str = "2015-01") -> pd.DataFrame:
    """
    Fetch monthly active rig counts for all 5 regions from EIA STEO.

    Uses confirmed per-basin series IDs (RIGSPM, RIGSBK, RIGSEF, RIGSAP, RIGSHA).
    These are the same Baker Hughes-sourced counts EIA uses in its DPR/STEO,
    published directly through the STEO API endpoint.

    Returns:
        DataFrame with columns [region, period, rigs]
        One row per (region, month) from start date to latest available.
    """
    if not API_KEY:
        logger.warning("EIA_API_KEY not set — cannot fetch rig counts")
        return pd.DataFrame(columns=["region", "period", "rigs"])

    rows = []
    logger.info("Fetching basin-level rig counts from EIA STEO ...")

    for region, series_id in STEO_REGION_SERIES.items():
        try:
            series = _fetch_steo_series(series_id, start)
            if series.empty:
                logger.warning(f"  {region} ({series_id}): no data returned")
                continue

            for period, value in series.items():
                rows.append({
                    "region": region,
                    "period": period,
                    "rigs":   int(round(value)),
                })

            logger.info(
                f"  {region:<15} ({series_id}): {len(series)} months | "
                f"latest={int(series.iloc[-1])} rigs | "
                f"{series.index[0].date()} → {series.index[-1].date()}"
            )

        except Exception as e:
            logger.warning(f"  {region} ({series_id}): failed — {e}")

    if not rows:
        logger.warning("Rig counts unavailable — all STEO series failed")
        return pd.DataFrame(columns=["region", "period", "rigs"])

    result = pd.DataFrame(rows).sort_values(["region", "period"]).reset_index(drop=True)
    logger.info(
        f"Rig counts complete: {len(result)} rows | "
        f"{result['region'].nunique()} regions | "
        f"avg rigs: {result['rigs'].mean():.0f}"
    )
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    df = fetch_rig_counts()
    if df.empty:
        print("No rig count data available")
    else:
        print(f"\n{len(df)} rows | {df['region'].nunique()} regions")
        print("\nLatest rig counts per region:")
        latest = df.groupby("region").last().reset_index()
        print(latest[["region", "period", "rigs"]].to_string(index=False))
        print(f"\nFull range: {df['period'].min().date()} → {df['period'].max().date()}")
