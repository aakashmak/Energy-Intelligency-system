"""
OilPulse FastAPI Backend
Serves all data from Supabase and handles AI/analytics computations.
Run: uvicorn api.main:app --reload --port 8000
"""

import sys
import os
import math
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

try:
    import streamlit as st
    for key in ["SUPABASE_URL", "SUPABASE_KEY", "EIA_API_KEY", "GOOGLE_API_KEY"]:
        if hasattr(st, "secrets") and key in st.secrets and not os.getenv(key):
            os.environ[key] = st.secrets[key]
except Exception:
    pass

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.data.db import (
    read_production, read_forecasts, read_scores,
    read_quarterly_kpis, read_rig_counts, _select,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OilPulse API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clean(obj):
    """Recursively replace NaN/Inf with None for JSON serialization."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    return obj


def _df_to_json(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    records = df.where(pd.notnull(df), None).to_dict("records")
    return _clean(records)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "ts": datetime.now().isoformat()}


# ── Production ─────────────────────────────────────────────────────────────────

@app.get("/api/production")
def get_production(
    region: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None),
):
    try:
        df = read_production(region, commodity)
        return _df_to_json(df)
    except Exception as e:
        logger.error(f"production error: {e}")
        raise HTTPException(500, str(e))


# ── Forecasts ──────────────────────────────────────────────────────────────────

@app.get("/api/forecasts")
def get_forecasts(
    region: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None),
):
    try:
        df = read_forecasts(region, commodity)
        return _df_to_json(df)
    except Exception as e:
        logger.error(f"forecasts error: {e}")
        raise HTTPException(500, str(e))


# ── Scores ─────────────────────────────────────────────────────────────────────

@app.get("/api/scores")
def get_scores():
    try:
        df = read_scores()
        return _df_to_json(df)
    except Exception as e:
        logger.error(f"scores error: {e}")
        raise HTTPException(500, str(e))


# ── Quarterly KPIs ─────────────────────────────────────────────────────────────

@app.get("/api/quarterly")
def get_quarterly(
    region: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    try:
        df = read_quarterly_kpis(region, commodity, year)
        return _df_to_json(df)
    except Exception as e:
        logger.error(f"quarterly error: {e}")
        raise HTTPException(500, str(e))


# ── Rig counts ─────────────────────────────────────────────────────────────────

@app.get("/api/rigs")
def get_rigs(region: Optional[str] = Query(None)):
    try:
        df = read_rig_counts(region)
        return _df_to_json(df)
    except Exception as e:
        logger.error(f"rigs error: {e}")
        raise HTTPException(500, str(e))


# ── Model validation ───────────────────────────────────────────────────────────

@app.get("/api/validation")
def get_validation():
    try:
        df = _select("model_validation", "*")
        return _df_to_json(df)
    except Exception as e:
        logger.warning(f"validation not available: {e}")
        return []


# ── Colorado ───────────────────────────────────────────────────────────────────

@app.get("/api/colorado/monthly")
def get_colorado_monthly():
    try:
        df = _select("colorado_monthly", "*")
        if not df.empty and "period" in df.columns:
            df["period"] = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
        return _df_to_json(df)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/colorado/formations")
def get_colorado_formations():
    try:
        return _df_to_json(_select("colorado_formations", "*"))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/colorado/operators")
def get_colorado_operators():
    try:
        df = _select("colorado_operators", "*")
        if not df.empty:
            df = df.sort_values("oil_bbl", ascending=False).head(10)
        return _df_to_json(df)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/colorado/decline")
def get_colorado_decline():
    try:
        df = _select("colorado_decline_curve", "*")
        if not df.empty:
            df = df.sort_values("month_index")
        return _df_to_json(df)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── AI Chat ────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    selected_year: int = 2026
    commodity: str = "oil"
    wti_price: float = 72.0
    hh_price: float = 2.5


def _build_context(selected_year: int, commodity: str, wti_price: float = 72.0, hh_price: float = 2.5) -> str:
    price = wti_price if commodity == "oil" else hh_price
    unit  = "$/bbl" if commodity == "oil" else "$/MMcf"
    lines = [
        f"=== OilPulse Live Data Snapshot ===",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Selected year: {selected_year} | Commodity: {commodity}",
        f"Current price assumption: ${price:.2f} {unit}",
        f"WTI crude: ${wti_price:.2f}/bbl | Henry Hub gas: ${hh_price:.2f}/MMcf",
        "",
    ]
    try:
        scores_df = read_scores()
        lines.append("--- INVESTMENT SCORES ---")
        if not scores_df.empty:
            for _, row in scores_df.sort_values("score", ascending=False).iterrows():
                lines.append(
                    f"Region: {row.get('region','?')} | "
                    f"Score: {float(row.get('score',0) or 0):.1f}/100 | "
                    f"Rank: {row.get('rank','?')} | "
                    f"YoY Growth: {float(row.get('yoy_growth',0) or 0):.2f}% | "
                    f"Decline Rate: {float(row.get('decline_rate',0) or 0):.2f}% | "
                    f"Revenue: ${float(row.get('revenue_potential',0) or 0):,.0f}M"
                )
    except Exception:
        lines.append("Scores: unavailable")

    try:
        quarterly_df = read_quarterly_kpis(commodity=commodity, year=selected_year)
        lines.append(f"\n--- QUARTERLY PRODUCTION {selected_year} ---")
        if not quarterly_df.empty:
            annual = quarterly_df.groupby("region")["value"].sum().reset_index()
            unit = "Mbbl/year" if commodity == "oil" else "MMcf/year"
            for _, r in annual.sort_values("value", ascending=False).iterrows():
                lines.append(f"  {r['region']}: {float(r['value']):,.0f} {unit}")
    except Exception:
        pass

    try:
        rigs_df = read_rig_counts()
        lines.append("\n--- ACTIVE RIGS ---")
        if not rigs_df.empty:
            latest = rigs_df.sort_values("period").groupby("region").last().reset_index()
            for _, r in latest.iterrows():
                lines.append(f"  {r['region']}: {int(r['rigs'])} rigs")
    except Exception:
        pass

    return "\n".join(lines)


@app.post("/api/ai/chat")
def ai_chat(req: ChatRequest):
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(400, "GROQ_API_KEY not configured")

    try:
        from groq import Groq

        client = Groq(api_key=groq_key)

        data_context = _build_context(req.selected_year, req.commodity, req.wti_price, req.hh_price)
        system_prompt = f"""You are OilPulse Analyst, a senior energy investment analyst with access to live U.S. oil and gas production data.

RULES:
1. Ground every factual number in the LIVE DATA SNAPSHOT below — prefix those with [DATA].
2. You MAY perform calculations using snapshot numbers (e.g. revenue = production × price, % change, comparisons). Show your working briefly.
3. For any reasoning or recommendation that goes beyond direct calculation, prefix with [INFERENCE].
4. If a question asks about a price scenario (e.g. "what if WTI drops to $55"), use the production figures in the snapshot and compute the answer — do not refuse.
5. Keep answers concise. Use bullet points for comparisons.
6. End with one specific, actionable investment recommendation.

LIVE DATA SNAPSHOT:
{data_context}

Today: {datetime.now().strftime('%Y-%m-%d')} | Dashboard year: {req.selected_year}
Model: SARIMA(1,1,1)(1,1,0)[12] | Sources: EIA PSM, EIA NGM, EIA STEO"""

        messages = [{"role": "system", "content": system_prompt}]
        for msg in req.messages[-6:]:
            messages.append({"role": msg.role, "content": msg.content})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )
        return {"answer": response.choices[0].message.content}

    except Exception as e:
        raise HTTPException(500, str(e))


# ── Well Economics ─────────────────────────────────────────────────────────────

class WellEconRequest(BaseModel):
    ip_rate: float = 900
    di: float = 70
    b_factor: float = 1.1
    d_terminal: float = 6
    dc_cost: float = 7.5
    loe: float = 8.0
    price: float = 72.0
    royalty: float = 22.5
    sev_tax: float = 4.6
    wi: float = 100
    discount_rate: float = 10.0
    commodity: str = "oil"
    months: int = 240


@app.post("/api/well-economics")
def well_economics(req: WellEconRequest):
    try:
        di_monthly = req.di / 100 / 12
        dt = req.d_terminal / 100 / 12
        b = req.b_factor

        monthly_prod = np.zeros(req.months)
        switched = False
        switch_t = req.months
        switch_r = 0.0

        for t in range(req.months):
            if switched:
                monthly_prod[t] = switch_r * np.exp(-dt * (t - switch_t))
            else:
                hyper = req.ip_rate / ((1 + b * di_monthly * t) ** (1 / b))
                d_t = di_monthly / (1 + b * di_monthly * t)
                if d_t < dt and t > 12:
                    switched = True
                    switch_t = t
                    switch_r = hyper
                    monthly_prod[t] = hyper
                else:
                    monthly_prod[t] = hyper

        monthly_prod = monthly_prod * 30.4

        if req.commodity == "gas":
            gross_rev = monthly_prod / 1000 * req.price
            loe_cost  = monthly_prod * req.loe
        else:
            gross_rev = monthly_prod * req.price
            loe_cost  = monthly_prod * req.loe

        royalty = gross_rev * (req.royalty / 100)
        sev     = (gross_rev - royalty) * (req.sev_tax / 100)
        net_rev = gross_rev - royalty - sev - loe_cost
        net_wi  = net_rev * (req.wi / 100)

        cash_flow = net_wi.copy()
        cash_flow[0] -= req.dc_cost * 1_000_000
        cumcash = np.cumsum(cash_flow)

        monthly_rate = (1 + req.discount_rate / 100) ** (1 / 12) - 1
        disc = np.array([1 / (1 + monthly_rate) ** t for t in range(req.months)])
        npv = float(np.sum(cash_flow * disc))

        # IRR via bisection
        irr = None
        if cash_flow.sum() > 0 and (cash_flow < 0).any():
            lo, hi = -0.5, 5.0
            for _ in range(200):
                mid = (lo + hi) / 2
                r_m = (1 + mid) ** (1 / 12) - 1
                pv = sum(cf / (1 + r_m) ** t for t, cf in enumerate(cash_flow))
                if abs(pv) < 1.0:
                    irr = mid * 100
                    break
                if pv > 0:
                    lo = mid
                else:
                    hi = mid

        payback = None
        for i, v in enumerate(cumcash):
            if v >= 0:
                payback = i
                break

        eur_unit = "MMbbl" if req.commodity == "oil" else "Bcf"
        eur_raw  = float(np.sum(monthly_prod))
        eur      = eur_raw / 1_000_000 if req.commodity == "oil" else eur_raw / 1_000_000

        months_arr = list(range(1, req.months + 1))
        cum_prod   = np.cumsum(monthly_prod).tolist()

        annual_cash = []
        for yr in range(1, 21):
            start = (yr - 1) * 12
            end   = yr * 12
            annual_cash.append({
                "year": yr,
                "cash": float(np.sum(cash_flow[start:end])),
                "cum":  float(cumcash[min(end - 1, req.months - 1)]),
            })

        return _clean({
            "npv":           npv,
            "irr":           irr,
            "payback_month": payback,
            "eur":           eur,
            "eur_unit":      eur_unit,
            "monthly_prod":  monthly_prod.tolist(),
            "cum_prod":      cum_prod,
            "monthly_cash":  cash_flow.tolist(),
            "cumulative_cash": cumcash.tolist(),
            "annual_cash":   annual_cash,
            "months":        months_arr,
        })

    except Exception as e:
        raise HTTPException(500, str(e))


# ── Sensitivity ────────────────────────────────────────────────────────────────

class SensRequest(BaseModel):
    base_prod: float
    base_price: float
    x_var: str = "Decline Rate (% adj.)"
    y_var: str = "Commodity Price ($/unit adj.)"
    commodity: str = "oil"
    metric: str = "production"
    wi_pct: float = 100.0


VARIABLES = {
    "Decline Rate (% adj.)": {
        "key": "decline_pct",
        "values": [-30, -20, -10, 0, 10, 20, 30],
        "fmt": lambda v: f"{v:+d}%",
    },
    "Commodity Price ($/unit adj.)": {
        "key": "price_pct",
        "values": [-40, -25, -10, 0, 10, 25, 40],
        "fmt": lambda v: f"{v:+d}%",
    },
    "Production Volume (% adj.)": {
        "key": "volume_pct",
        "values": [-25, -15, -5, 0, 5, 15, 25],
        "fmt": lambda v: f"{v:+d}%",
    },
    "Working Interest (% abs.)": {
        "key": "wi_pct",
        "values": [50, 60, 70, 80, 90, 100],
        "fmt": lambda v: f"{v}%",
    },
}

DEFAULT_ROYALTY = 0.1875
DEFAULT_SEV_TAX = 0.046


def _sens_adjust(base_prod, base_price, x_key, x_val, y_key, y_val, commodity, wi_pct):
    adj_vol   = float(base_prod)
    adj_price = float(base_price)
    adj_wi    = wi_pct / 100.0
    for key, val in [(x_key, x_val), (y_key, y_val)]:
        if key == "decline_pct":
            adj_vol *= (1 - val / 100 * 0.8)
        elif key == "volume_pct":
            adj_vol *= (1 + val / 100)
        elif key == "price_pct":
            adj_price *= (1 + val / 100)
        elif key == "wi_pct":
            adj_wi = val / 100.0
    if commodity == "oil":
        gross_M = adj_vol * adj_price / 1_000
    else:
        gross_M = adj_vol / 1_000 * adj_price / 1_000
    royalty = gross_M * DEFAULT_ROYALTY
    sev     = (gross_M - royalty) * DEFAULT_SEV_TAX
    net_M   = (gross_M - royalty - sev) * adj_wi
    return max(0, adj_vol), net_M


@app.post("/api/sensitivity")
def sensitivity(req: SensRequest):
    try:
        x_def = VARIABLES[req.x_var]
        y_def = VARIABLES[req.y_var]
        x_vals = x_def["values"]
        y_vals = y_def["values"]

        base_vol, base_rev = _sens_adjust(
            req.base_prod, req.base_price,
            x_def["key"], 0,
            y_def["key"], 0,
            req.commodity, req.wi_pct,
        )
        base_val = base_vol if req.metric == "production" else base_rev

        matrix = []
        for yv in y_vals:
            row = []
            for xv in x_vals:
                vol, rev = _sens_adjust(
                    req.base_prod, req.base_price,
                    x_def["key"], xv,
                    y_def["key"], yv,
                    req.commodity, req.wi_pct,
                )
                cell_val = vol if req.metric == "production" else rev
                pct      = ((cell_val - base_val) / base_val * 100) if base_val > 0 else 0
                row.append({"value": cell_val, "pct": pct})
            matrix.append(row)

        return _clean({
            "x_labels":  [x_def["fmt"](v) for v in x_vals],
            "y_labels":  [y_def["fmt"](v) for v in y_vals],
            "x_var":     req.x_var,
            "y_var":     req.y_var,
            "matrix":    matrix,
            "base_val":  base_val,
            "commodity": req.commodity,
            "metric":    req.metric,
        })
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/region-presets")
def region_presets():
    return {
        "Permian":    {"label": "Permian Basin (TX/NM)", "commodity": "oil",  "ip_rate": 900,  "di": 70, "b_factor": 1.1, "d_terminal": 6, "dc_cost": 7.5,  "loe": 8.0,   "price": 72.0, "royalty": 22.5, "sev_tax": 4.6,  "wi": 100},
        "Bakken":     {"label": "Bakken (ND/MT)",         "commodity": "oil",  "ip_rate": 700,  "di": 75, "b_factor": 1.0, "d_terminal": 5, "dc_cost": 8.5,  "loe": 10.0,  "price": 72.0, "royalty": 18.75,"sev_tax": 11.5, "wi": 100},
        "Eagle Ford": {"label": "Eagle Ford (TX)",         "commodity": "oil",  "ip_rate": 800,  "di": 72, "b_factor": 1.2, "d_terminal": 6, "dc_cost": 6.5,  "loe": 7.5,   "price": 72.0, "royalty": 25.0, "sev_tax": 4.6,  "wi": 100},
        "Appalachia": {"label": "Appalachia (PA/WV/OH)",  "commodity": "gas",  "ip_rate": 18,   "di": 60, "b_factor": 1.4, "d_terminal": 5, "dc_cost": 7.0,  "loe": 0.75,  "price": 2.50, "royalty": 18.0, "sev_tax": 4.0,  "wi": 100},
        "Gulf Coast": {"label": "Gulf Coast (LA/TX Off)", "commodity": "oil",  "ip_rate": 1200, "di": 55, "b_factor": 0.9, "d_terminal": 5, "dc_cost": 45.0, "loe": 15.0,  "price": 72.0, "royalty": 18.75,"sev_tax": 0.0,  "wi": 100},
    }
