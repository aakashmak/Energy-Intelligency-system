"""
OilPulse — Energy Intelligence Dashboard
CDF Energy AI Hackathon

Run from the project root:
    streamlit run src/dashboard/app.py
"""

# ── Path fix ───────────────────────────────────────────────────────────────────
import sys
import os
import datetime
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

from dotenv import load_dotenv
load_dotenv(dotenv_path=_ROOT / ".env", override=True)

try:
    import streamlit as st
    for key in ["SUPABASE_URL", "SUPABASE_KEY", "EIA_API_KEY", "OPENAI_API_KEY"]:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = st.secrets[key]
except Exception:
    pass

import warnings
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="OilPulse — Energy Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

REGIONS = ["Permian", "Bakken", "Eagle Ford", "Appalachia", "Gulf Coast"]
REGION_COLORS = {
    "Permian":    "#2563EB",
    "Bakken":     "#16A34A",
    "Eagle Ford": "#D97706",
    "Appalachia": "#9333EA",
    "Gulf Coast": "#DC2626",
}

# ── Vision UI chart constants ──────────────────────────────────────────────────
_CHART_BG   = "#060B28"
_GRID       = "rgba(226,232,240,0.07)"
_AXIS_CLR   = "#A0AEC0"
_FONT_CLR   = "#A0AEC0"
_LEGEND_BG  = "rgba(6,11,40,0.92)"


# ══════════════════════════════════════════════════════════════════════════════
# Data loaders — session-state cache with on-demand refresh
#
# Each loader fetches independently — one failure never blocks the others.
# Results live in st.session_state:
#   _data_{key}  → DataFrame
#   _ts_{key}    → "HH:MM:SS" timestamp string
#   _err_{key}   → error message string, or None on success
#
# The sidebar "🔄 Refresh All Data" button calls _fetch_all(force=True),
# which clears all keys first then re-fetches fresh from Supabase.
# ══════════════════════════════════════════════════════════════════════════════

DATASET_KEYS = ["prod_df", "fc_df", "scores_df", "quarterly_df", "rig_df", "val_df"]


def _now_str():
    return datetime.datetime.now().strftime("%H:%M:%S")


def _fetch_all(force: bool = False):
    """Load all datasets into session_state. force=True clears cache first."""
    if force:
        for k in DATASET_KEYS:
            st.session_state.pop(f"_data_{k}", None)
            st.session_state.pop(f"_ts_{k}",   None)
            st.session_state.pop(f"_err_{k}",  None)

    fetchers = {
        "prod_df":      _load_production,
        "fc_df":        _load_forecasts,
        "scores_df":    _load_scores,
        "quarterly_df": _load_quarterly_kpis,
        "rig_df":       _load_rig_counts,
        "val_df":       _load_validation,
    }
    for key, fn in fetchers.items():
        if f"_data_{key}" not in st.session_state:
            df, err = fn()
            st.session_state[f"_data_{key}"] = df
            st.session_state[f"_ts_{key}"]   = _now_str()
            st.session_state[f"_err_{key}"]  = err


def _load_production():
    try:
        from src.data.db import read_production
        df = read_production()
        if not df.empty:
            df["period"] = pd.to_datetime(df["period"])
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def _load_forecasts():
    try:
        from src.data.db import read_forecasts
        df = read_forecasts()
        if not df.empty:
            df["period"] = pd.to_datetime(df["period"])
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def _load_scores():
    try:
        from src.data.db import read_scores
        return read_scores(), None
    except Exception as e:
        return pd.DataFrame(), str(e)


def _load_quarterly_kpis():
    try:
        from src.data.db import read_quarterly_kpis
        return read_quarterly_kpis(), None
    except Exception as e:
        return pd.DataFrame(), str(e)


def _load_rig_counts():
    try:
        from src.data.db import read_rig_counts
        df = read_rig_counts()
        if not df.empty:
            df["period"] = pd.to_datetime(df["period"])
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def _load_validation():
    try:
        from src.data.db import _select
        return _select("model_validation", "*"), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# ── Helpers ────────────────────────────────────────────────────────────────────

def fmt_pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{'+'if val>0 else ''}{val:.1f}%"


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ══════════════════════════════════════════════════════════════════════════════
# Production & Forecast chart
# ══════════════════════════════════════════════════════════════════════════════

def render_forecast_chart(prod_df, fc_df, active_regions, commodity,
                          selected_year, current_year):
    unit_label = "Mbbl/month" if commodity == "oil" else "MMcf/month"
    is_past    = selected_year < current_year
    is_current = selected_year == current_year
    is_future  = selected_year > current_year
    year_start = pd.Timestamp(year=selected_year, month=1,  day=1)
    year_end   = pd.Timestamp(year=selected_year, month=12, day=31)

    col_chart, col_legend = st.columns([9, 1])
    with col_legend:
        st.markdown("""
        <div style="margin-top:0.5rem;font-size:0.72rem;line-height:1.9;color:#94A3B8">
            <span style="color:#F1F5F9">━━</span> Actual<br>
            <span style="color:#F97316">┅┅</span> Forecast<br>
            <span style="color:#475569;font-size:0.65rem">Shaded = 80% CI</span>
        </div>""", unsafe_allow_html=True)

    with col_chart:
        fig = go.Figure()

        for region in active_regions:
            color = REGION_COLORS.get(region, "#6B7280")
            r_int = int(color[1:3], 16)
            g_int = int(color[3:5], 16)
            b_int = int(color[5:7], 16)

            hist = prod_df[
                (prod_df["region"] == region) &
                (prod_df["commodity"] == commodity)
            ].sort_values("period")
            if hist.empty:
                continue

            pre_year = hist[hist["period"] < year_start]
            if not pre_year.empty:
                fig.add_trace(go.Scatter(
                    x=pre_year["period"], y=pre_year["value"],
                    name=f"{region}" if len(active_regions) == 1 else f"{region} actual",
                    mode="lines", line=dict(color=color, width=2.5),
                    legendgroup=region, showlegend=True,
                    hovertemplate=f"<b>{region}</b><br>%{{x|%b %Y}}<br>Actual: %{{y:,.0f}} {unit_label}<extra></extra>",
                ))

            in_year_actual = hist[
                (hist["period"] >= year_start) & (hist["period"] <= year_end)
            ]
            if not in_year_actual.empty:
                fig.add_trace(go.Scatter(
                    x=in_year_actual["period"], y=in_year_actual["value"],
                    name=f"{region} actual {selected_year}",
                    mode="lines+markers", line=dict(color=color, width=3),
                    marker=dict(size=5, color=color, symbol="circle"),
                    legendgroup=region, showlegend=False,
                    hovertemplate=f"<b>{region}</b><br>%{{x|%b %Y}}<br>Actual: %{{y:,.0f}} {unit_label}<extra></extra>",
                ))

            fc_all = fc_df[
                (fc_df["region"] == region) & (fc_df["commodity"] == commodity)
            ].sort_values("period") if fc_df is not None and not fc_df.empty else pd.DataFrame()
            if fc_all.empty:
                continue

            fc_in_year = fc_all[(fc_all["period"] >= year_start) & (fc_all["period"] <= year_end)]
            fc_after   = fc_all[fc_all["period"] > year_end]

            def _add_ci_and_line(df_fc, name, show_legend=False):
                if df_fc.empty:
                    return
                if "upper_ci" in df_fc.columns and "lower_ci" in df_fc.columns:
                    u = df_fc["upper_ci"].fillna(df_fc["forecast"])
                    l = df_fc["lower_ci"].fillna(df_fc["forecast"])
                    fig.add_trace(go.Scatter(
                        x=pd.concat([df_fc["period"], df_fc["period"][::-1]]),
                        y=pd.concat([u, l[::-1]]),
                        fill="toself", fillcolor=f"rgba({r_int},{g_int},{b_int},0.12)",
                        line=dict(color="rgba(0,0,0,0)"),
                        showlegend=False, hoverinfo="skip", legendgroup=region,
                    ))
                fig.add_trace(go.Scatter(
                    x=df_fc["period"], y=df_fc["forecast"], name=name,
                    mode="lines", line=dict(color=color, width=2, dash="dash"),
                    legendgroup=region, showlegend=show_legend,
                    hovertemplate=f"<b>{region}</b><br>%{{x|%b %Y}}<br>Forecast: %{{y:,.0f}} {unit_label}<extra></extra>",
                ))

            if is_current:
                _add_ci_and_line(fc_in_year, f"{region} forecast")
            if is_future:
                _add_ci_and_line(fc_in_year, f"{region} forecast {selected_year}")
            _add_ci_and_line(fc_after, f"{region} forecast")

        fig.add_vrect(
            x0=year_start.strftime("%Y-%m-%d"), x1=year_end.strftime("%Y-%m-%d"),
            fillcolor="rgba(249,115,22,0.04)", layer="below", line_width=0,
        )
        fig.add_vline(x=year_start.strftime("%Y-%m-%d"),
                      line=dict(color="#334155", width=1, dash="dot"))
        fig.add_annotation(
            x=year_start.strftime("%Y-%m-%d"), y=1, yref="paper", xref="x",
            text=f"  {selected_year} start", showarrow=False,
            font=dict(size=10, color="#475569"), xanchor="left",
        )

        ann = (f"← Historical Production · {selected_year} →" if is_past else
               f"← Historical  |  {selected_year} YTD + SARIMA Forecast →" if is_current else
               f"← Historical  |  SARIMA Forecast {selected_year}+ →")

        fig.update_layout(
            height=460, margin=dict(l=0, r=0, t=40, b=0),
            yaxis_title=unit_label, xaxis_title=None,
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="left", x=0, font=dict(size=11, color=_FONT_CLR),
                        bgcolor=_LEGEND_BG, bordercolor="rgba(255,255,255,0.08)", borderwidth=1),
            plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
            xaxis=dict(gridcolor=_GRID, showgrid=True, color=_AXIS_CLR,
                       rangeslider=dict(visible=False), zerolinecolor=_GRID),
            yaxis=dict(gridcolor=_GRID, showgrid=True, color=_AXIS_CLR,
                       zerolinecolor=_GRID),
            font=dict(color=_FONT_CLR),
            annotations=[dict(text=ann, xref="paper", yref="paper",
                              x=0.5, y=1.055, showarrow=False,
                              font=dict(size=11, color="#475569"), xanchor="center")],
        )
        st.plotly_chart(fig, use_container_width=True)

    if is_current:
        st.markdown(f"""
        <div style="background:rgba(0,117,255,0.08);border-left:4px solid #0075FF;
                    padding:0.6rem 1rem;border-radius:12px;font-size:0.82rem;
                    color:#63B3ED;margin-top:-0.5rem;
                    border:1px solid rgba(0,117,255,0.2);border-left:4px solid #0075FF">
            📍 <b>{selected_year} is the current year.</b>
            Solid = confirmed actuals · Dashed = SARIMA forecast · Shaded = 80% CI.
        </div>""", unsafe_allow_html=True)
    elif is_future:
        st.markdown(f"""
        <div style="background:rgba(67,24,255,0.08);border-left:4px solid #4318FF;
                    padding:0.6rem 1rem;border-radius:12px;font-size:0.82rem;
                    color:#A78BFA;margin-top:-0.5rem;
                    border:1px solid rgba(67,24,255,0.2);border-left:4px solid #4318FF">
            🔮 <b>{selected_year} is a future year.</b>
            Full SARIMA forecast · Shaded = 80% confidence interval.
        </div>""", unsafe_allow_html=True)


# ── Quarterly visualization ────────────────────────────────────────────────────

def render_quarterly_viz(quarterly_df, active_regions, commodity, selected_year):
    unit = "Mbbl" if commodity == "oil" else "MMcf"
    year_q = quarterly_df[
        (quarterly_df["year"] == selected_year) &
        (quarterly_df["commodity"] == commodity) &
        (quarterly_df["region"].isin(active_regions))
    ].copy()

    if year_q.empty:
        st.info(f"No quarterly data for {selected_year}.")
        return

    if len(active_regions) == 1:
        region = active_regions[0]
        color  = REGION_COLORS.get(region, "#2563EB")
        r_data = year_q[year_q["region"] == region]
        q_map  = {}
        for _, r in r_data.iterrows():
            q_map[r["quarter"]] = {
                "value": float(r["value"]),
                "is_fc": bool(r.get("is_forecast", False)),
                "qoq":   r.get("qoq_growth"),
            }

        card_cols = st.columns(4)
        max_val   = max((d["value"] for d in q_map.values()), default=1)

        for i, q in enumerate(["Q1", "Q2", "Q3", "Q4"]):
            with card_cols[i]:
                if q not in q_map:
                    st.markdown(f"""<div style="background:rgba(255,255,255,0.02);
                        border:1px dashed rgba(255,255,255,0.1);
                        border-radius:10px;padding:1rem;text-align:center;height:140px;">
                        <div style="color:#475569;font-size:0.85rem;font-weight:600">{q}</div>
                        <div style="color:rgba(255,255,255,0.1);font-size:2rem;margin-top:1rem">—</div>
                    </div>""", unsafe_allow_html=True)
                    continue
                d       = q_map[q]
                bar_pct = (d["value"] / max_val) * 100
                badge   = "🔮 Forecast" if d["is_fc"] else "📊 Actual"
                bbg     = "rgba(67,24,255,0.15)" if d["is_fc"] else "rgba(0,117,255,0.12)"
                bfg     = "#A78BFA" if d["is_fc"] else "#63B3ED"
                qoq     = d["qoq"]
                qoq_html = (
                    f'<span style="color:{"#01B574" if float(qoq)>=0 else "#E31A1A"};font-weight:600">'
                    f'{"+" if float(qoq)>=0 else ""}{float(qoq):.1f}% QoQ</span>'
                ) if qoq is not None else '<span style="color:#475569">—</span>'
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,{color}18 0%,{color}06 100%);
                            border:1px solid {color}35;border-radius:10px;
                            padding:1rem;height:140px;position:relative;overflow:hidden;">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div style="color:{color};font-weight:700;font-size:1rem">{q}</div>
                        <div style="background:{bbg};color:{bfg};font-size:0.65rem;
                                    padding:0.1rem 0.45rem;border-radius:4px;font-weight:600">{badge}</div>
                    </div>
                    <div style="color:#F1F5F9;font-size:1.6rem;font-weight:700;margin-top:0.4rem">
                        {d['value']/1000:,.1f}<span style="font-size:0.78rem;color:#475569;font-weight:400">K {unit}</span>
                    </div>
                    <div style="font-size:0.8rem;margin-top:0.3rem">{qoq_html}</div>
                    <div style="position:absolute;bottom:0;left:0;height:4px;width:{bar_pct:.0f}%;
                                background:{color};border-radius:0 2px 0 0"></div>
                </div>""", unsafe_allow_html=True)

        total = sum(d["value"] for d in q_map.values())
        act   = sum(d["value"] for d in q_map.values() if not d["is_fc"])
        fct   = total - act
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,{color}18 0%,{color}06 100%);
                    border:1px solid {color}35;border-radius:8px;padding:0.9rem 1.3rem;
                    display:flex;justify-content:space-between;align-items:center;margin-top:0.8rem;">
            <div>
                <div style="color:{color};font-size:0.72rem;font-weight:700;
                            text-transform:uppercase;letter-spacing:0.05em">{selected_year} Annual Total</div>
                <div style="color:#F1F5F9;font-size:1.5rem;font-weight:700;margin-top:0.1rem">
                    {total/1000:,.1f}K <span style="font-size:0.85rem;color:#475569">{unit}</span>
                </div>
            </div>
            <div style="text-align:right;font-size:0.8rem;color:#64748B">
                <div>📊 Actual: <b style="color:#94A3B8">{act/1000:,.1f}K</b></div>
                <div style="margin-top:0.25rem">🔮 Forecast: <b style="color:#94A3B8">{fct/1000:,.1f}K</b></div>
            </div>
        </div>""", unsafe_allow_html=True)

    else:
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        fig_q = go.Figure()
        for region in active_regions:
            color  = REGION_COLORS.get(region, "#6B7280")
            r_data = year_q[year_q["region"] == region]
            vals, colors, texts = [], [], []
            for q in quarters:
                row = r_data[r_data["quarter"] == q]
                if row.empty:
                    vals.append(0); colors.append(_rgba(color, 0.3)); texts.append("—")
                else:
                    v     = float(row.iloc[0]["value"])
                    is_fc = bool(row.iloc[0].get("is_forecast", False))
                    vals.append(v)
                    colors.append(_rgba(color, 0.45) if is_fc else _rgba(color, 0.9))
                    texts.append(f"{v/1000:,.1f}K {'🔮' if is_fc else '📊'}")
            fig_q.add_trace(go.Bar(
                name=region, x=quarters, y=vals,
                marker_color=colors, marker_line=dict(color=color, width=1.5),
                text=texts, textposition="outside", textfont=dict(size=10, color=_FONT_CLR),
            ))
        fig_q.update_layout(
            barmode="group", height=380, margin=dict(l=0, r=0, t=15, b=0),
            plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
            xaxis=dict(title="Quarter", gridcolor=_GRID, color=_AXIS_CLR),
            yaxis=dict(title=f"Production ({unit})", gridcolor=_GRID, color=_AXIS_CLR),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                        font=dict(color=_FONT_CLR), bgcolor=_LEGEND_BG),
            font=dict(color=_FONT_CLR),
        )
        st.plotly_chart(fig_q, use_container_width=True)

        total_cols = st.columns(len(active_regions))
        for i, region in enumerate(active_regions):
            color  = REGION_COLORS.get(region, "#6B7280")
            r_data = year_q[year_q["region"] == region]
            total  = float(r_data["value"].sum())
            act    = float(r_data[~r_data["is_forecast"].astype(bool)]["value"].sum()) if "is_forecast" in r_data.columns else total
            fct    = total - act
            total_cols[i].markdown(f"""
            <div style="background:linear-gradient(135deg,{color}18 0%,{color}06 100%);
                        border:1px solid {color}35;border-radius:8px;
                        padding:0.7rem 0.9rem;text-align:center;">
                <div style="color:{color};font-size:0.7rem;font-weight:700;
                            text-transform:uppercase;letter-spacing:0.04em">{region}</div>
                <div style="color:#F1F5F9;font-size:1.2rem;font-weight:700;margin-top:0.2rem">{total/1000:,.1f}K</div>
                <div style="font-size:0.72rem;color:#64748B;margin-top:0.15rem">
                    📊 {act/1000:,.1f}K &nbsp;|&nbsp; 🔮 {fct/1000:,.1f}K
                </div>
            </div>""", unsafe_allow_html=True)

    st.caption(f"📊 Actual  🔮 SARIMA Forecast  |  {unit}/quarter  |  QoQ = quarter-over-quarter % change")


# ── Global CSS — Vision UI Design System ──────────────────────────────────────
st.markdown("""<style>

/* ── Page background ── */
.stApp { background: #0B1437 !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(127.09deg, rgba(6,11,40,0.97) 19.41%, rgba(10,14,35,0.75) 76.65%) !important;
    border-right: 1px solid rgba(226,232,240,0.1) !important;
    backdrop-filter: blur(30px) !important;
    -webkit-backdrop-filter: blur(30px) !important;
}

/* ── Main header ── */
.main-header {
    background: linear-gradient(127.09deg, rgba(6,11,40,0.97) 19.41%, rgba(26,19,73,0.7) 76.65%);
    padding: 2rem 2.5rem 1.8rem;
    border-radius: 20px;
    color: white;
    margin-bottom: 1.5rem;
    text-align: center;
    border: 1px solid rgba(226,232,240,0.2);
    backdrop-filter: blur(120px);
    -webkit-backdrop-filter: blur(120px);
    box-shadow: 0 20px 40px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.03);
    position: relative;
    overflow: hidden;
}
.main-header::before {
    content: '';
    position: absolute;
    top: -40%; left: 30%;
    width: 80%; height: 200%;
    background: radial-gradient(ellipse at center, rgba(67,24,255,0.09) 0%, transparent 60%);
    pointer-events: none;
}
.main-header h1 {
    font-size: 3rem;
    margin: 0 0 0.3rem;
    font-weight: 900;
    background: linear-gradient(96.01deg, #7551ff 34.28%, #39b8ff 99.1%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.03em;
    line-height: 1.1;
}
.main-header p {
    font-size: 0.78rem;
    margin: 0.4rem 0 0;
    color: rgba(255,255,255,0.38);
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

/* ── KPI cards — Vision UI glass ── */
.kpi-card {
    background: linear-gradient(127.09deg, rgba(6,11,40,0.94) 19.41%, rgba(10,14,35,0.49) 76.65%);
    border: 1px solid rgba(226,232,240,0.3);
    border-radius: 20px;
    padding: 1.2rem 1.3rem;
    text-align: center;
    backdrop-filter: blur(120px);
    -webkit-backdrop-filter: blur(120px);
    box-shadow: 0 20px 27px rgba(0,0,0,0.1);
    height: 100%;
}
.kpi-label {
    font-size: 0.68rem;
    color: #A0AEC0;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.35rem;
    font-weight: 600;
}
.kpi-value { font-size: 1.9rem; font-weight: 800; color: #FFFFFF; line-height: 1.1; }
.kpi-sub   { font-size: 0.78rem; color: #A0AEC0; margin-top: 0.25rem; }
.kpi-pos   { color: #01B574 !important; font-weight: 700; }
.kpi-neg   { color: #E31A1A !important; font-weight: 700; }

/* ── Section headers ── */
.section-header {
    font-size: 1.05rem;
    font-weight: 700;
    color: #FFFFFF;
    border-left: 3px solid #4318FF;
    padding-left: 0.8rem;
    margin: 1.6rem 0 0.9rem;
    letter-spacing: 0.01em;
}

/* ── Badges ── */
.badge-fc {
    background: rgba(67,24,255,0.15);
    color: #A78BFA;
    border: 1px solid rgba(67,24,255,0.35);
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    display: inline-block;
}
.badge-act {
    background: rgba(0,117,255,0.15);
    color: #63B3ED;
    border: 1px solid rgba(0,117,255,0.35);
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    display: inline-block;
}

/* ── Tabs — Vision UI pill style ── */
.stTabs [data-baseweb="tab-list"],
div[data-testid="stTabs"] > div:first-child {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 15px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: 1px solid rgba(226,232,240,0.1) !important;
}
/* All tab buttons — inactive */
.stTabs button[role="tab"],
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 12px !important;
    color: #A0AEC0 !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    padding: 0.45rem 0.9rem !important;
    border: none !important;
    outline: none !important;
    transition: all 0.3s ease !important;
}
/* Active tab — multiple selector fallbacks for Streamlit compatibility */
.stTabs button[role="tab"][aria-selected="true"],
.stTabs button[aria-selected="true"],
.stTabs [data-baseweb="tab"][aria-selected="true"],
[data-testid="stTabs"] button[aria-selected="true"] {
    background: #0075FF !important;
    color: #FFFFFF !important;
    border-radius: 12px !important;
    border: none !important;
    box-shadow: 0 4px 15px rgba(0,117,255,0.4) !important;
    font-weight: 700 !important;
}
/* Hover on inactive tabs */
.stTabs button[role="tab"]:not([aria-selected="true"]):hover {
    background: rgba(0,117,255,0.1) !important;
    color: #FFFFFF !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── Metrics — Vision UI glass ── */
div[data-testid="metric-container"] {
    background: linear-gradient(127.09deg, rgba(6,11,40,0.94) 19.41%, rgba(10,14,35,0.49) 76.65%) !important;
    border: 1px solid rgba(226,232,240,0.3) !important;
    border-radius: 20px !important;
    padding: 0.9rem 1.1rem !important;
    backdrop-filter: blur(120px) !important;
}
div[data-testid="metric-container"] label {
    color: #A0AEC0 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 1.5rem !important;
    font-weight: 800 !important;
}

/* ── Buttons — Vision UI glass ── */
.stButton > button {
    background: linear-gradient(127.09deg, rgba(6,11,40,0.94) 19.41%, rgba(10,14,35,0.49) 76.65%) !important;
    border: 1px solid rgba(226,232,240,0.3) !important;
    color: #A0AEC0 !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    backdrop-filter: blur(40px) !important;
    transition: all 0.25s ease;
}
.stButton > button:hover {
    background: linear-gradient(127.09deg, rgba(67,24,255,0.25) 19.41%, rgba(10,14,35,0.7) 76.65%) !important;
    border-color: rgba(67,24,255,0.5) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 15px rgba(67,24,255,0.2) !important;
}

/* ── Dividers ── */
hr { border-color: rgba(226,232,240,0.1) !important; }

</style>""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <div style="font-size:0.72rem;color:rgba(117,81,255,0.75);letter-spacing:0.2em;
                text-transform:uppercase;margin-bottom:0.6rem;font-weight:600">
        CDF Energy AI Hackathon
    </div>
    <h1>⚡ OilPulse</h1>
    <p>U.S. Oil &amp; Gas Production Intelligence Platform</p>
    <div style="display:flex;justify-content:center;gap:2.5rem;margin-top:1rem;
                font-size:0.74rem;color:rgba(255,255,255,0.28);letter-spacing:0.05em">
        <span>📡 EIA APIv2</span>
        <span>🤖 SARIMA Forecasting</span>
        <span>🗄️ Supabase Live Data</span>
        <span>💬 GPT-4o Analyst</span>
    </div>
</div>""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Controls")

selected_year = st.sidebar.slider(
    "📅 Year Selector", min_value=2015, max_value=2029, value=2026, step=1,
)
current_year = pd.Timestamp.now().year
if selected_year < current_year:
    st.sidebar.markdown('<span class="badge-act">📊 Historical</span>', unsafe_allow_html=True)
elif selected_year == current_year:
    st.sidebar.markdown('<span class="badge-act">📍 Current Year — YTD + Forecast</span>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<span class="badge-fc">🔮 Future Forecast</span>', unsafe_allow_html=True)

st.sidebar.markdown("---")
commodity = st.sidebar.radio(
    "🛢️ Commodity", options=["oil", "gas"],
    format_func=lambda x: "🛢️ Crude Oil" if x == "oil" else "🔥 Natural Gas",
)

st.sidebar.markdown("---")
selected_regions = st.sidebar.multiselect("📍 Regions", options=REGIONS, default=REGIONS)
if not selected_regions:
    selected_regions = REGIONS

st.sidebar.markdown("---")
st.sidebar.markdown("**💰 Price Assumptions**")
wti_price   = st.sidebar.number_input("WTI ($/bbl)",        value=72.0, min_value=20.0,  max_value=200.0, step=1.0)
henry_price = st.sidebar.number_input("Henry Hub ($/MMcf)", value=2.50, min_value=1.0,   max_value=20.0,  step=0.25)

st.sidebar.markdown("---")

# ── On-demand data refresh ─────────────────────────────────────────────────────
st.sidebar.markdown("**📡 Live Data**")
if st.sidebar.button("🔄 Refresh All Data", use_container_width=True, key="btn_refresh"):
    with st.sidebar:
        with st.spinner("Fetching latest data..."):
            _fetch_all(force=True)
    st.sidebar.success("✅ Refreshed at " + _now_str())

# Last-updated timestamps (shown after first load)
if "_ts_prod_df" in st.session_state:
    st.sidebar.markdown(
        f"<div style='font-size:0.72rem;color:#475569;line-height:1.9'>"
        f"📊 Production: <b style='color:#64748B'>{st.session_state.get('_ts_prod_df', '—')}</b><br>"
        f"📈 Forecasts:&nbsp;&nbsp;<b style='color:#64748B'>{st.session_state.get('_ts_fc_df',   '—')}</b><br>"
        f"🏗️ Rig counts: <b style='color:#64748B'>{st.session_state.get('_ts_rig_df',  '—')}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.sidebar.caption("📡 EIA APIv2 + EIA STEO + Colorado COGCC")
st.sidebar.caption("🤖 SARIMA(1,1,1)(1,1,0)[12]")
st.sidebar.caption("🗄️ Supabase PostgreSQL")

# ── Initial data load (once per session) ──────────────────────────────────────
if "_data_prod_df" not in st.session_state:
    with st.spinner("📡 Connecting to Supabase..."):
        _fetch_all(force=False)

# Unpack from session state
prod_df      = st.session_state.get("_data_prod_df",      pd.DataFrame())
fc_df        = st.session_state.get("_data_fc_df",        pd.DataFrame())
scores_df    = st.session_state.get("_data_scores_df",    pd.DataFrame())
quarterly_df = st.session_state.get("_data_quarterly_df", pd.DataFrame())
rig_df       = st.session_state.get("_data_rig_df",       pd.DataFrame())
val_df       = st.session_state.get("_data_val_df",       pd.DataFrame())

# ── Graceful degradation — per-dataset error notices ──────────────────────────
for _key, _label in {
    "prod_df":      "Production data",
    "fc_df":        "SARIMA Forecasts",
    "scores_df":    "KPI Scores",
    "quarterly_df": "Quarterly KPIs",
    "rig_df":       "Rig Counts",
    "val_df":       "Model Validation",
}.items():
    _err = st.session_state.get(f"_err_{_key}")
    if _err:
        st.warning(
            f"⚠️ **{_label}** could not be loaded — showing cached/empty data. "
            f"Click **🔄 Refresh** to retry. _{_err[:120]}_",
            icon="📡",
        )

if prod_df.empty:
    st.error("⚠️ No production data. Run: `python -m src.data.pipeline` to populate Supabase, then click 🔄 Refresh.")
    st.stop()

if "map_selected_region" not in st.session_state:
    st.session_state["map_selected_region"] = None

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_map, tab2, tab_ai, tab3, tab4, tab_co, tab_we, tab_sens = st.tabs([
    "🗺️ Basin Map & Forecasts",
    "📊 Investment Scores",
    "🤖 Ask AI Analyst",
    "🏗️ Rig Activity",
    "🎯 Forecast Accuracy",
    "🔬 Colorado Deep Dive",
    "💰 Well Economics",
    "📐 Sensitivity Analysis",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB MAP
# ══════════════════════════════════════════════════════════════════════════════
with tab_map:
    from src.dashboard.map_view import render_map
    render_map(
        prod_df, scores_df, rig_df,
        selected_year, commodity, selected_regions,
        fc_df=fc_df, quarterly_df=quarterly_df,
    )
    btn_region = st.session_state.get("map_active_region")
    st.session_state["map_selected_region"] = btn_region

active_regions = selected_regions
if st.session_state.get("map_selected_region"):
    active_regions = [st.session_state["map_selected_region"]]

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — KPIs & Scoring
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if st.session_state.get("map_selected_region"):
        st.info(f"📍 Filtered to **{st.session_state['map_selected_region']}**.", icon="🗺️")

    st.markdown('<div class="section-header">🔍 Regional KPI Detail</div>', unsafe_allow_html=True)
    if not scores_df.empty:
        for _, row in scores_df[scores_df["region"].isin(active_regions)].sort_values("score", ascending=False).iterrows():
            region = row["region"]
            score  = float(row.get("score", 0) or 0)
            with st.expander(f"**{region}** — Investment Score {score:.0f}/100", expanded=True):
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("YoY Growth",      fmt_pct(float(row.get("yoy_growth", 0) or 0)))
                c2.metric("Decline Rate",     fmt_pct(float(row.get("decline_rate", 0) or 0)))
                c3.metric("Revenue",          f"${float(row.get('revenue_potential', 0) or 0):,.0f}M")
                c4.metric("Consistency",      f"{float(row.get('consistency_score', 0) or 0):.0f}/100")
                c5.metric("Rel. Performance", f"{float(row.get('rel_performance', 50) or 50):.0f}/100")

    st.markdown('<div class="section-header">🗺️ Regional Comparison</div>', unsafe_allow_html=True)
    if not scores_df.empty:
        df_cmp = scores_df[scores_df["region"].isin(active_regions)].copy()
        _cl = dict(
            height=300, margin=dict(l=0, r=0, t=40, b=0),
            plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
            font=dict(color=_FONT_CLR),
            xaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID),
            yaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID),
        )
        c1, c2 = st.columns(2)
        with c1:
            s = df_cmp.sort_values("score")
            fig_s = go.Figure(go.Bar(
                x=s["region"], y=s["score"],
                marker_color=[REGION_COLORS.get(r, "#6B7280") for r in s["region"]],
                text=s["score"].round(1).astype(str), textposition="outside",
                textfont=dict(color=_FONT_CLR),
            ))
            fig_s.update_layout(title="Investment Score", **_cl)
            fig_s.update_layout(title_font_color="#F1F5F9")
            fig_s.update_yaxes(range=[0, 115])
            st.plotly_chart(fig_s, use_container_width=True)
        with c2:
            if "revenue_potential" in df_cmp.columns:
                rv = df_cmp.dropna(subset=["revenue_potential"]).sort_values("revenue_potential")
                fig_r = go.Figure(go.Bar(
                    x=rv["region"], y=rv["revenue_potential"],
                    marker_color=[REGION_COLORS.get(r, "#6B7280") for r in rv["region"]],
                    text=["$" + f"{v:,.0f}M" for v in rv["revenue_potential"]],
                    textposition="outside",
                    textfont=dict(color=_FONT_CLR),
                ))
                fig_r.update_layout(title="Revenue Potential ($M)", **_cl)
                fig_r.update_layout(title_font_color="#F1F5F9")
                st.plotly_chart(fig_r, use_container_width=True)
        c3, c4 = st.columns(2)
        with c3:
            if "consistency_score" in df_cmp.columns:
                cs = df_cmp.sort_values("consistency_score")
                fig_c = go.Figure(go.Bar(
                    x=cs["region"], y=cs["consistency_score"],
                    marker_color=[REGION_COLORS.get(r, "#6B7280") for r in cs["region"]],
                    text=cs["consistency_score"].round(0).astype(str), textposition="outside",
                    textfont=dict(color=_FONT_CLR),
                ))
                fig_c.update_layout(title="Consistency Score (0–100)", **_cl)
                fig_c.update_layout(title_font_color="#F1F5F9")
                fig_c.update_yaxes(range=[0, 115])
                st.plotly_chart(fig_c, use_container_width=True)
        with c4:
            if "rel_performance" in df_cmp.columns:
                rp = df_cmp.sort_values("rel_performance")
                fig_p = go.Figure(go.Bar(
                    x=rp["region"], y=rp["rel_performance"],
                    marker_color=[REGION_COLORS.get(r, "#6B7280") for r in rp["region"]],
                    text=rp["rel_performance"].round(0).astype(str), textposition="outside",
                    textfont=dict(color=_FONT_CLR),
                ))
                fig_p.add_hline(y=50, line_dash="dot", line_color="#334155",
                                annotation_text="peer average",
                                annotation_font_color="#475569")
                fig_p.update_layout(title="Relative Performance Index", **_cl)
                fig_p.update_layout(title_font_color="#F1F5F9")
                fig_p.update_yaxes(range=[0, 115])
                st.plotly_chart(fig_p, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB AI
# ══════════════════════════════════════════════════════════════════════════════
with tab_ai:
    from src.dashboard.ai_agent import render_ai_agent
    render_ai_agent(
        scores_df=scores_df, quarterly_df=quarterly_df, prod_df=prod_df,
        fc_df=fc_df, rig_df=rig_df, val_df=val_df,
        selected_year=selected_year,
        selected_region=st.session_state.get("map_selected_region"),
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Rig Counts
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">🏗️ Active Rig Counts by Region</div>', unsafe_allow_html=True)
    st.caption("Source: EIA STEO Table 10a — RIGSPM, RIGSBK, RIGSEF, RIGSAP, RIGSHA")
    if not rig_df.empty:
        fig_rigs = go.Figure()
        for region in active_regions:
            r_df = rig_df[rig_df["region"] == region].sort_values("period")
            if r_df.empty: continue
            fig_rigs.add_trace(go.Scatter(
                x=r_df["period"], y=r_df["rigs"], name=region, mode="lines",
                line=dict(color=REGION_COLORS.get(region, "#6B7280"), width=2.5),
            ))
        fig_rigs.update_layout(
            height=380, margin=dict(l=0, r=0, t=15, b=0), yaxis_title="Active Rigs",
            legend=dict(orientation="h", yanchor="bottom", y=1.01,
                        font=dict(color=_FONT_CLR), bgcolor=_LEGEND_BG),
            plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
            xaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID),
            yaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID,
                       title_font_color=_FONT_CLR),
            font=dict(color=_FONT_CLR),
        )
        st.plotly_chart(fig_rigs, use_container_width=True)
        latest = (
            rig_df[rig_df["region"].isin(active_regions)]
            .sort_values("period").groupby("region").last().reset_index()
            [["region", "period", "rigs"]]
        )
        latest["period"] = latest["period"].dt.strftime("%Y-%m")
        latest.columns   = ["Region", "As of", "Active Rigs"]
        st.dataframe(latest.set_index("Region"), use_container_width=True)
    else:
        st.info("No rig data. Run `python -m src.data.rig_fetcher` first.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Model Validation
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header">🎯 SARIMA Model Validation</div>', unsafe_allow_html=True)
    st.caption("Walk-forward cross-validation · 80% train / 20% test")
    if not val_df.empty:
        valid = val_df.dropna(subset=["mape"])
        if not valid.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Overall MAPE",   f"{valid['mape'].mean():.2f}%")
            c2.metric("Oil MAPE (avg)", f"{valid[valid['commodity']=='oil']['mape'].mean():.2f}%")
            c3.metric("Gas MAPE (avg)", f"{valid[valid['commodity']=='gas']['mape'].mean():.2f}%")
            c4.metric("Best Region",    valid.loc[valid['mape'].idxmin(), 'region'])
        cols_show = [c for c in ["region", "commodity", "mae", "rmse", "mape", "aic", "bic", "skill_score", "grade"] if c in val_df.columns]
        display   = val_df[cols_show].copy()
        display.columns = ["Region", "Commodity", "MAE", "RMSE", "MAPE%", "AIC", "BIC", "Skill%", "Grade"][:len(cols_show)]
        for col in ["MAE", "RMSE"]:
            if col in display.columns: display[col] = display[col].round(0)
        for col in ["MAPE%", "AIC", "BIC", "Skill%"]:
            if col in display.columns: display[col] = display[col].round(2)
        def _sg(val):
            return {
                "A": "background-color:rgba(1,181,116,0.15);color:#01B574",
                "B": "background-color:rgba(0,117,255,0.15);color:#63B3ED",
                "C": "background-color:rgba(255,181,71,0.15);color:#FFB547",
                "D": "background-color:rgba(227,26,26,0.15);color:#E31A1A",
            }.get(val, "")
        if "Grade" in display.columns:
            st.dataframe(display.style.applymap(_sg, subset=["Grade"]), use_container_width=True, height=390)
        else:
            st.dataframe(display, use_container_width=True, height=390)
        st.markdown("🟢 **A** <5% · 🔵 **B** <10% · 🟡 **C** <15% · 🔴 **D** ≥15%")
    else:
        st.info("No validation data. Run `python -m src.forecasting.model_validation` first.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB CO — Colorado DJ Basin Case Study
# ══════════════════════════════════════════════════════════════════════════════
with tab_co:
    from src.dashboard.colorado_case_study import render_colorado_tab
    render_colorado_tab()

# ══════════════════════════════════════════════════════════════════════════════
# TAB WE — Well Economics Calculator
# ══════════════════════════════════════════════════════════════════════════════
with tab_we:
    from src.dashboard.well_economics import render_well_economics
    render_well_economics(selected_region=st.session_state.get("map_selected_region"))

# ══════════════════════════════════════════════════════════════════════════════
# TAB SENS — Sensitivity Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab_sens:
    from src.dashboard.sensitivity import render_sensitivity
    render_sensitivity(
        prod_df        = prod_df,
        fc_df          = fc_df,
        scores_df      = scores_df,
        active_regions = active_regions,
        commodity      = commodity,
        selected_year  = selected_year,
        current_year   = current_year,
    )

st.markdown("---")
st.caption("OilPulse · CDF Energy AI Hackathon · EIA APIv2 + EIA STEO + Colorado COGCC · SARIMA(1,1,1)(1,1,0)[12] · Supabase PostgreSQL")
