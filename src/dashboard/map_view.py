"""
Geographic Visualization — Interactive Basin Intelligence Map.

Key design:
  - 5 styled basin selector buttons with each basin's OWN color
  - Clicking a basin → map RE-RENDERS zoomed in on that basin
  - Hover tooltip: Rank, Score, Grade only
  - Legend: basin names only
  - Below map: summary card + forecast chart + quarterly viz inline
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go


REGION_COORDS = {
    "Permian":    {"lat": 31.9,  "lon": -102.3, "state": "TX/NM",         "zoom": 5.2},
    "Bakken":     {"lat": 47.8,  "lon": -103.4, "state": "ND/MT",         "zoom": 5.5},
    "Eagle Ford": {"lat": 28.4,  "lon":  -98.1, "state": "TX",            "zoom": 5.8},
    "Appalachia": {"lat": 39.5,  "lon":  -80.2, "state": "PA/WV/OH",      "zoom": 5.5},
    "Gulf Coast": {"lat": 28.0,  "lon":  -90.5, "state": "LA/TX Offshore","zoom": 5.0},
}

REGION_POLYGONS = {
    "Permian": [
        (32.9, -104.2), (33.8, -103.1), (33.5, -101.8),
        (32.6, -100.9), (31.0, -100.8), (30.4, -101.6),
        (30.2, -102.8), (30.6, -104.3), (31.7, -104.8), (32.9, -104.2),
    ],
    "Bakken": [
        (48.9, -104.3), (48.9, -102.4), (47.9, -101.3),
        (46.9, -101.2), (46.5, -102.8), (46.8, -104.5),
        (47.8, -104.9), (48.9, -104.3),
    ],
    "Eagle Ford": [
        (29.6,  -99.7), (29.9,  -98.1), (29.3,  -96.8),
        (28.2,  -96.5), (27.2,  -97.5), (27.0,  -99.3),
        (28.3, -100.1), (29.6,  -99.7),
    ],
    "Appalachia": [
        (41.8,  -81.1), (41.6,  -78.4), (40.4,  -76.8),
        (38.4,  -78.2), (37.2,  -80.4), (37.8,  -82.8),
        (39.6,  -82.5), (41.1,  -82.1), (41.8,  -81.1),
    ],
    "Gulf Coast": [
        (30.1,  -94.2), (30.1,  -89.1), (29.1,  -87.5),
        (27.2,  -87.8), (26.5,  -90.5), (27.1,  -93.5),
        (28.3,  -94.8), (29.8,  -94.6), (30.1,  -94.2),
    ],
}

REGION_COLORS = {
    "Permian":    "#3B82F6",
    "Bakken":     "#10B981",
    "Eagle Ford": "#F59E0B",
    "Appalachia": "#A855F7",
    "Gulf Coast": "#EF4444",
}

GRADE_COLORS = {
    "A": "#10B981", "B": "#3B82F6", "C": "#F59E0B", "D": "#EF4444",
}

# Vision UI chart constants
_CHART_BG  = "#060B28"
_GRID      = "rgba(226,232,240,0.07)"
_AXIS_CLR  = "#A0AEC0"
_FONT_CLR  = "#A0AEC0"
_LEGEND_BG = "rgba(6,11,40,0.92)"


def _compute_grade(score):
    if score >= 75: return "A"
    if score >= 60: return "B"
    if score >= 45: return "C"
    return "D"


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgba(hex_color, alpha):
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


def _darken(hex_color, factor=0.7):
    r, g, b = _hex_to_rgb(hex_color)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


# ══════════════════════════════════════════════════════════════════════════════
# Inline: Production & Forecast chart
# ══════════════════════════════════════════════════════════════════════════════

def _render_inline_forecast(region, prod_df, fc_df, commodity, selected_year, color):
    r_int, g_int, b_int = _hex_to_rgb(color)
    unit_label = "Mbbl/month" if commodity == "oil" else "MMcf/month"
    cutoff_ts  = pd.Timestamp(year=selected_year, month=12, day=31)
    cutoff_str = cutoff_ts.strftime("%Y-%m-%d")
    fig = go.Figure()

    actual = prod_df[
        (prod_df["region"] == region) &
        (prod_df["commodity"] == commodity) &
        (prod_df["period"] <= cutoff_ts)
    ].sort_values("period")
    if not actual.empty:
        fig.add_trace(go.Scatter(
            x=actual["period"], y=actual["value"],
            name="Actual", mode="lines",
            line=dict(color=color, width=2.8),
            fill="tozeroy", fillcolor=f"rgba({r_int},{g_int},{b_int},0.07)",
        ))

    if fc_df is not None and not fc_df.empty:
        forecast = fc_df[
            (fc_df["region"] == region) &
            (fc_df["commodity"] == commodity)
        ].sort_values("period")
        if not forecast.empty:
            if "upper_ci" in forecast.columns and "lower_ci" in forecast.columns:
                fc_up  = forecast["upper_ci"].fillna(forecast["forecast"])
                fc_low = forecast["lower_ci"].fillna(forecast["forecast"])
                fig.add_trace(go.Scatter(
                    x=pd.concat([forecast["period"], forecast["period"][::-1]]),
                    y=pd.concat([fc_up, fc_low[::-1]]),
                    fill="toself", fillcolor=f"rgba({r_int},{g_int},{b_int},0.10)",
                    line=dict(color="rgba(0,0,0,0)"),
                    showlegend=False, hoverinfo="skip",
                ))
            fig.add_trace(go.Scatter(
                x=forecast["period"], y=forecast["forecast"],
                name="SARIMA Forecast", mode="lines",
                line=dict(color=color, width=2, dash="dash"),
            ))

    fig.update_layout(shapes=[dict(
        type="line", xref="x", yref="paper",
        x0=cutoff_str, x1=cutoff_str, y0=0, y1=1,
        line=dict(color="#334155", width=1.5, dash="dot"),
    )])
    fig.add_annotation(
        xref="x", yref="paper", x=cutoff_str, y=1.02,
        text=f"{selected_year}", showarrow=False,
        font=dict(size=11, color="#64748B"), xanchor="left",
    )
    fig.update_layout(
        height=360, margin=dict(l=0, r=0, t=30, b=0),
        yaxis_title=unit_label, xaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=_FONT_CLR), bgcolor=_LEGEND_BG),
        plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
        xaxis=dict(gridcolor=_GRID, showgrid=True, color=_AXIS_CLR, zerolinecolor=_GRID),
        yaxis=dict(gridcolor=_GRID, showgrid=True, color=_AXIS_CLR, zerolinecolor=_GRID),
        font=dict(color=_FONT_CLR),
    )
    st.plotly_chart(fig, width="stretch", key=f"map_fc_{region}_{commodity}_{selected_year}")


# ══════════════════════════════════════════════════════════════════════════════
# Inline: Quarterly KPI visualization
# ══════════════════════════════════════════════════════════════════════════════

def _render_inline_quarterly(region, quarterly_df, commodity, selected_year, color):
    if quarterly_df is None or quarterly_df.empty:
        return
    q_data = quarterly_df[
        (quarterly_df["year"] == selected_year) &
        (quarterly_df["commodity"] == commodity) &
        (quarterly_df["region"] == region)
    ].sort_values("quarter")
    if q_data.empty:
        st.caption(f"No quarterly data for {region} in {selected_year}.")
        return

    unit = "Mbbl" if commodity == "oil" else "MMcf"
    q_map = {}
    for _, r in q_data.iterrows():
        q_map[r["quarter"]] = {
            "value": float(r["value"]),
            "is_fc": bool(r.get("is_forecast", False)),
            "qoq":   r.get("qoq_growth"),
        }

    card_cols = st.columns(4)
    max_val   = max((d["value"] for d in q_map.values()), default=1)
    for i, q in enumerate(["Q1","Q2","Q3","Q4"]):
        with card_cols[i]:
            if q not in q_map:
                st.markdown(f"""<div style="background:rgba(255,255,255,0.02);
                    border:1px dashed rgba(255,255,255,0.1);
                    border-radius:10px;padding:1rem;text-align:center;height:130px;">
                    <div style="color:#475569;font-size:0.8rem;font-weight:600">{q}</div>
                    <div style="color:rgba(255,255,255,0.1);font-size:1.5rem;margin-top:1.5rem">—</div>
                </div>""", unsafe_allow_html=True)
                continue
            d       = q_map[q]
            bar_pct = (d["value"] / max_val) * 100 if max_val > 0 else 0
            badge   = "🔮 Forecast" if d["is_fc"] else "📊 Actual"
            bbg     = "rgba(67,24,255,0.15)" if d["is_fc"] else "rgba(0,117,255,0.12)"
            bfg     = "#A78BFA" if d["is_fc"] else "#63B3ED"
            qoq     = d["qoq"]
            if qoq is not None:
                qv = float(qoq)
                qoq_html = f'<span style="color:{"#01B574" if qv>=0 else "#E31A1A"};font-weight:600">{"+" if qv>=0 else ""}{qv:.1f}% QoQ</span>'
            else:
                qoq_html = '<span style="color:#475569">—</span>'
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,{color}18 0%,{color}06 100%);
                        border:1px solid {color}35;border-radius:10px;
                        padding:0.9rem 1rem;height:130px;position:relative;overflow:hidden;">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div style="color:{color};font-weight:700;font-size:0.95rem">{q}</div>
                    <div style="background:{bbg};color:{bfg};font-size:0.65rem;
                                padding:0.1rem 0.4rem;border-radius:4px;font-weight:600">{badge}</div>
                </div>
                <div style="color:#F1F5F9;font-size:1.5rem;font-weight:700;margin-top:0.3rem">
                    {d['value']/1000:,.1f}<span style="font-size:0.75rem;color:#475569;font-weight:400">K {unit}</span>
                </div>
                <div style="font-size:0.78rem;margin-top:0.3rem">{qoq_html}</div>
                <div style="position:absolute;bottom:0;left:0;height:3px;width:{bar_pct:.0f}%;
                            background:{color};border-radius:0 2px 0 0"></div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    quarters   = [q for q in ["Q1","Q2","Q3","Q4"] if q in q_map]
    values     = [q_map[q]["value"] for q in quarters]
    is_fc_list = [q_map[q]["is_fc"] for q in quarters]
    bar_colors = [_rgba(color, 0.45) if fc else _rgba(color, 0.88) for fc in is_fc_list]
    labels     = [f"{v/1000:,.1f}K {unit}" + (" 🔮" if fc else " 📊") for v, fc in zip(values, is_fc_list)]
    fig_q = go.Figure(go.Bar(
        x=values, y=quarters, orientation="h",
        marker=dict(color=bar_colors, line=dict(color=color, width=1.5)),
        text=labels, textposition="outside",
        textfont=dict(size=11, color=_FONT_CLR),
        hovertemplate="<b>%{y}</b><br>Production: %{x:,.0f} " + unit + "<extra></extra>",
    ))
    fig_q.update_layout(
        height=200, margin=dict(l=0, r=80, t=10, b=0),
        plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
        xaxis=dict(title=f"Production ({unit})", gridcolor=_GRID, showgrid=True,
                   zeroline=False, color=_AXIS_CLR, zerolinecolor=_GRID),
        yaxis=dict(title=None, autorange="reversed", tickfont=dict(size=12, color=color)),
        font=dict(color=_FONT_CLR),
        showlegend=False,
    )
    st.plotly_chart(fig_q, width="stretch", key=f"map_q_{region}_{commodity}_{selected_year}")

    total = sum(values)
    act   = sum(v for v, fc in zip(values, is_fc_list) if not fc)
    fct   = total - act
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{color}18 0%,{color}06 100%);
                border:1px solid {color}40;border-radius:8px;padding:0.9rem 1.3rem;
                display:flex;justify-content:space-between;align-items:center;margin-top:0.3rem;">
        <div>
            <div style="color:{color};font-size:0.72rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.05em">{selected_year} Annual Total</div>
            <div style="color:#F1F5F9;font-size:1.5rem;font-weight:700;margin-top:0.1rem">
                {total/1000:,.1f}K <span style="font-size:0.85rem;color:#475569">{unit}</span>
            </div>
        </div>
        <div style="text-align:right;font-size:0.78rem;color:#64748B">
            <div>📊 Actual: <b style="color:#94A3B8">{act/1000:,.1f}K</b></div>
            <div style="margin-top:0.2rem">🔮 Forecast: <b style="color:#94A3B8">{fct/1000:,.1f}K</b></div>
        </div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Build the Plotly map figure
# ══════════════════════════════════════════════════════════════════════════════

def _build_map_figure(df_map, active, max_prod, map_style,
                      show_polygons, show_bubbles, show_rigs, show_labels):
    fig = go.Figure()

    if active and active in REGION_COORDS:
        coords = REGION_COORDS[active]
        center = dict(lat=coords["lat"], lon=coords["lon"])
        zoom   = coords["zoom"]
    else:
        center = dict(lat=37.5, lon=-96.0)
        zoom   = 3.3

    if show_polygons:
        for _, row in df_map.iterrows():
            poly = REGION_POLYGONS.get(row["region"])
            if not poly: continue
            lats = [p[0] for p in poly]
            lons = [p[1] for p in poly]

            if active is None:
                fill_alpha = 0.15 + (row["score"] / 100) * 0.35
                line_w     = 2
                line_color = row["color"]
            elif row["region"] == active:
                fill_alpha = 0.45
                line_w     = 3.5
                line_color = row["color"]
            else:
                fill_alpha = 0.04
                line_w     = 1
                line_color = _rgba(row["color"], 0.2)

            fig.add_trace(go.Scattermapbox(
                lat=lats, lon=lons, mode="lines",
                fill="toself",
                fillcolor=_rgba(row["color"], fill_alpha),
                line=dict(color=line_color, width=line_w),
                hoverinfo="skip", showlegend=False,
            ))

    if show_bubbles:
        for _, row in df_map.iterrows():
            is_sel    = (active is not None) and (row["region"] == active)
            is_dimmed = (active is not None) and (row["region"] != active)

            base_size   = max(20, (row["prod"] / max_prod) * 75) if max_prod > 0 else 30
            size_outer  = base_size * (1.6 if is_sel else 1.0)
            size_inner  = size_outer * (0.65 if is_sel else 0.55)
            glow_alpha  = 0.06 if is_dimmed else (0.45 if is_sel else 0.25)
            inner_alpha = 0.20 if is_dimmed else 0.95

            hover = (
                f"<b style='font-size:14px'>{row['region']}</b><br>"
                f"━━━━━━━━━━━━━━━━━<br>"
                f"🏆 Rank <b>#{row['rank']}</b><br>"
                f"📊 Score <b>{row['score']:.0f}/100</b><br>"
                f"🎓 Grade <b>{row['grade']}</b>"
            )

            fig.add_trace(go.Scattermapbox(
                lat=[row["lat"]], lon=[row["lon"]], mode="markers",
                marker=go.scattermapbox.Marker(size=size_outer, color=row["color"], opacity=glow_alpha),
                hoverinfo="skip", showlegend=False,
            ))

            if is_sel:
                fig.add_trace(go.Scattermapbox(
                    lat=[row["lat"]], lon=[row["lon"]], mode="markers",
                    marker=go.scattermapbox.Marker(size=size_outer * 0.85, color="white", opacity=0.25),
                    hoverinfo="skip", showlegend=False,
                ))

            text_mode = "markers+text" if (show_labels and not is_dimmed) else "markers"
            fig.add_trace(go.Scattermapbox(
                lat=[row["lat"]], lon=[row["lon"]],
                mode=text_mode,
                marker=go.scattermapbox.Marker(size=size_inner, color=row["color"], opacity=inner_alpha),
                text=[row["region"]] if (show_labels and not is_dimmed) else None,
                textposition="top center",
                textfont=dict(size=14 if is_sel else 12, color="#FFFFFF", family="Arial Black"),
                hovertext=hover if not is_dimmed else "",
                hoverinfo="text" if not is_dimmed else "skip",
                name=row["region"],
                legendgroup=row["region"],
                showlegend=(not is_dimmed),
            ))

    if show_rigs:
        rig_legend_shown = False
        for _, row in df_map.iterrows():
            if row["rigs"] <= 0: continue
            is_dimmed = (active is not None) and (row["region"] != active)
            rig_lat   = row["lat"] - 1.2
            rig_lon   = row["lon"] + 1.2
            rig_size  = max(15, min(40, row["rigs"] / 6))
            rig_alpha = 0.1 if is_dimmed else 0.95

            fig.add_trace(go.Scattermapbox(
                lat=[rig_lat], lon=[rig_lon], mode="markers",
                marker=go.scattermapbox.Marker(
                    size=rig_size * 1.8, color="#FCD34D",
                    opacity=0.05 if is_dimmed else 0.20,
                ),
                hoverinfo="skip", showlegend=False,
            ))
            fig.add_trace(go.Scattermapbox(
                lat=[rig_lat], lon=[rig_lon], mode="markers+text",
                marker=go.scattermapbox.Marker(size=rig_size, color="#F59E0B", opacity=rig_alpha),
                text=[str(row["rigs"])], textposition="middle center",
                textfont=dict(size=11, color="#0F172A", family="Arial Black"),
                hovertext=f"🏗️ <b>{row['region']}</b><br>{row['rigs']} active rigs" if not is_dimmed else "",
                hoverinfo="text" if not is_dimmed else "skip",
                name="🏗️ Rig counts", legendgroup="rigs",
                showlegend=(not rig_legend_shown and not is_dimmed),
            ))
            if not is_dimmed:
                rig_legend_shown = True

    fig.update_layout(
        mapbox=dict(style=map_style, center=center, zoom=zoom),
        height=560, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(
            orientation="v", yanchor="top", y=0.99, xanchor="left", x=0.01,
            bgcolor="rgba(6,11,40,0.92)", bordercolor="rgba(226,232,240,0.25)",
            borderwidth=1, font=dict(size=11, color="#FFFFFF"),
            title=dict(text="<b>Basins</b>", font=dict(color="#A0AEC0")),
        ),
        uirevision="map",
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Main render
# ══════════════════════════════════════════════════════════════════════════════

def render_map(
    prod_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    rig_df: pd.DataFrame,
    selected_year: int,
    commodity: str,
    selected_regions: list[str],
    fc_df: pd.DataFrame | None = None,
    quarterly_df: pd.DataFrame | None = None,
) -> str | None:

    st.markdown(
        '<div class="section-header">🗺️ U.S. Oil & Gas Basin Intelligence Map</div>',
        unsafe_allow_html=True,
    )

    rows = []
    for region, coords in REGION_COORDS.items():
        region_data = prod_df[
            (prod_df["region"] == region) &
            (prod_df["commodity"] == commodity) &
            (prod_df["period"].dt.year == selected_year)
        ]
        prod_val = float(region_data["value"].sum()) if not region_data.empty else 0.0
        if prod_val == 0:
            recent = prod_df[(prod_df["region"]==region) & (prod_df["commodity"]==commodity)]
            if not recent.empty:
                prod_val = float(recent.groupby(recent["period"].dt.year)["value"].sum().iloc[-1])

        score_row = scores_df[scores_df["region"] == region] if not scores_df.empty else pd.DataFrame()
        score = float(score_row.iloc[0]["score"])              if not score_row.empty else 50.0
        yoy   = float(score_row.iloc[0].get("yoy_growth",0)   or 0) if not score_row.empty else 0
        rev   = float(score_row.iloc[0].get("revenue_potential",0) or 0) if not score_row.empty else 0
        cons  = float(score_row.iloc[0].get("consistency_score",0) or 0) if not score_row.empty else 0

        rig_row = rig_df[rig_df["region"] == region] if not rig_df.empty else pd.DataFrame()
        rigs    = int(rig_row.sort_values("period").iloc[-1]["rigs"]) if not rig_row.empty else 0

        rows.append({
            "region":      region,
            "state":       coords["state"],
            "lat":         coords["lat"],
            "lon":         coords["lon"],
            "prod":        prod_val,
            "score":       score,
            "grade":       _compute_grade(score),
            "yoy":         yoy,
            "rigs":        rigs,
            "revenue":     rev,
            "consistency": cons,
            "color":       REGION_COLORS.get(region, "#6B7280"),
        })

    df_map = pd.DataFrame(rows)
    if df_map.empty or df_map["prod"].sum() == 0:
        st.info("No production data for selected year.")
        return None

    df_map["rank"] = df_map["score"].rank(ascending=False, method="min").astype(int)
    df_map         = df_map.sort_values("rank")
    unit           = "Mbbl" if commodity == "oil" else "MMcf"
    total_prod     = df_map["prod"].sum()
    total_rev      = df_map["revenue"].sum()
    total_rigs     = df_map["rigs"].sum()
    max_prod       = df_map["prod"].max()
    avg_score      = df_map["score"].mean()
    top_region     = df_map.iloc[0]["region"]

    # KPI banner
    st.markdown(f"""
    <div style="background:linear-gradient(127.09deg,rgba(6,11,40,0.96) 19.41%,rgba(10,14,35,0.6) 76.65%);
                border-radius:20px;padding:1.2rem 1.5rem;margin-bottom:1rem;
                display:grid;grid-template-columns:repeat(5,1fr);gap:1rem;
                border:1px solid rgba(226,232,240,0.25);
                backdrop-filter:blur(120px);
                box-shadow:0 20px 27px rgba(0,0,0,0.15);">
        <div style="border-right:1px solid rgba(255,255,255,0.07);padding-right:1rem;">
            <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">Total Production</div>
            <div style="color:#F1F5F9;font-size:1.5rem;font-weight:700">{total_prod/1e6:,.1f}M<span style="font-size:0.9rem;color:#475569"> {unit}</span></div>
            <div style="color:#10B981;font-size:0.75rem;margin-top:0.2rem">{selected_year} {commodity.upper()}</div>
        </div>
        <div style="border-right:1px solid rgba(255,255,255,0.07);padding-right:1rem;">
            <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">Revenue Potential</div>
            <div style="color:#F1F5F9;font-size:1.5rem;font-weight:700">${total_rev/1000:,.1f}B</div>
            <div style="color:#10B981;font-size:0.75rem;margin-top:0.2rem">across 5 basins</div>
        </div>
        <div style="border-right:1px solid rgba(255,255,255,0.07);padding-right:1rem;">
            <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">Active Rigs</div>
            <div style="color:#F1F5F9;font-size:1.5rem;font-weight:700">{total_rigs}</div>
            <div style="color:#F59E0B;font-size:0.75rem;margin-top:0.2rem">🏗️ drilling now</div>
        </div>
        <div style="border-right:1px solid rgba(255,255,255,0.07);padding-right:1rem;">
            <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">Avg Investment Score</div>
            <div style="color:#F1F5F9;font-size:1.5rem;font-weight:700">{avg_score:.0f}<span style="font-size:0.85rem;color:#475569"> / 100</span></div>
            <div style="color:#3B82F6;font-size:0.75rem;margin-top:0.2rem">portfolio avg</div>
        </div>
        <div>
            <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">🏆 Top Basin</div>
            <div style="color:#F1F5F9;font-size:1.3rem;font-weight:700">{top_region}</div>
            <div style="color:{REGION_COLORS[top_region]};font-size:0.75rem;margin-top:0.2rem">Score {df_map.iloc[0]['score']:.0f} · Grade {df_map.iloc[0]['grade']}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Layer controls
    lc = st.columns([1, 1, 1, 1, 1, 2])
    with lc[0]: show_polygons = st.checkbox("🗺️ Basin Areas", value=True, key="m_poly")
    with lc[1]: show_bubbles  = st.checkbox("💧 Production",  value=True, key="m_bub")
    with lc[2]: show_rigs     = st.checkbox("🏗️ Rigs",        value=True, key="m_rig")
    with lc[3]: show_labels   = st.checkbox("🏷️ Labels",       value=True, key="m_lab")
    with lc[4]:
        map_style = st.selectbox(
            "Map style",
            ["carto-darkmatter", "carto-positron", "open-street-map"],
            index=0,
            format_func=lambda s: {
                "carto-darkmatter": "🌑 Dark",
                "carto-positron":   "☀️ Light",
                "open-street-map":  "🗺️ Street",
            }[s],
            label_visibility="collapsed",
            key="m_style",
        )
    with lc[5]:
        st.markdown(
            "<div style='color:#475569;font-size:0.8rem;padding-top:0.4rem'>"
            "Hover = Rank · Score · Grade &nbsp;|&nbsp; Click a basin to zoom & drill down</div>",
            unsafe_allow_html=True,
        )

    if "map_active_region" not in st.session_state:
        st.session_state["map_active_region"] = None

    active = st.session_state.get("map_active_region")

    fig = _build_map_figure(df_map, active, max_prod, map_style,
                            show_polygons, show_bubbles, show_rigs, show_labels)
    st.plotly_chart(fig, width="stretch", key=f"main_map_{active}")

    # Basin buttons
    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.85rem;color:#475569;margin-bottom:0.5rem'>"
        "📍 <b style='color:#64748B'>Click a basin</b> to zoom the map and view production, forecast & quarterly data</div>",
        unsafe_allow_html=True,
    )

    full_css = "<style>"
    for idx, (_, row) in enumerate(df_map.iterrows()):
        color     = row["color"]
        dark      = _darken(color, 0.75)
        is_active = active == row["region"]
        pos       = idx + 1

        if is_active:
            full_css += f"""
            div.stColumns > div:nth-child({pos}) button {{
                background: {color} !important;
                color: white !important;
                border: 2px solid {dark} !important;
                box-shadow: 0 0 14px {_rgba(color, 0.5)}, 0 0 4px {_rgba(color, 0.8)} !important;
                font-weight: 700 !important;
            }}"""
        else:
            full_css += f"""
            div.stColumns > div:nth-child({pos}) button {{
                background: rgba(255,255,255,0.03) !important;
                color: {color} !important;
                border: 2px solid {_rgba(color, 0.35)} !important;
                font-weight: 600 !important;
            }}
            div.stColumns > div:nth-child({pos}) button:hover {{
                background: {_rgba(color, 0.15)} !important;
                border-color: {color} !important;
                box-shadow: 0 0 10px {_rgba(color, 0.3)} !important;
            }}"""

    full_css += """
    div.stColumns > div:nth-child(6) button {
        background: rgba(255,255,255,0.02) !important;
        color: #475569 !important;
        border: 2px solid rgba(255,255,255,0.1) !important;
    }
    div.stColumns > div:nth-child(6) button:hover {
        background: rgba(255,255,255,0.06) !important;
        border-color: rgba(255,255,255,0.2) !important;
    }
    </style>"""
    st.markdown(full_css, unsafe_allow_html=True)

    btn_cols = st.columns(6)
    for i, (_, row) in enumerate(df_map.iterrows()):
        region    = row["region"]
        is_active = active == region
        label     = f"● {region}" if is_active else f"○ {region}"
        if btn_cols[i].button(label, key=f"map_btn_{region}", use_container_width=True):
            st.session_state["map_active_region"] = None if is_active else region
            st.rerun()

    if btn_cols[5].button("✕ All", key="map_btn_clear", use_container_width=True):
        st.session_state["map_active_region"] = None
        st.rerun()

    # ── Investment Scorecard — between map & region drill-down ────────────────
    if not scores_df.empty:
        st.markdown(
            '<div class="section-header">📊 Investment Scorecard — All Basins Ranked</div>',
            unsafe_allow_html=True,
        )
        scols  = st.columns(5)
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (_, srow) in enumerate(scores_df.sort_values("score", ascending=False).iterrows()):
            if i >= 5: break
            r_name  = srow.get("region", "—")
            r_score = float(srow.get("score", 0) or 0)
            r_yoy   = float(srow.get("yoy_growth", 0) or 0)
            r_rev   = float(srow.get("revenue_potential", 0) or 0)
            yoy_color = "#01B574" if r_yoy >= 0 else "#E31A1A"
            yoy_str   = f"{r_yoy:+.2f}%"
            scols[i].markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">{medals[i]} {r_name}</div>
                <div class="kpi-value">{r_score:.0f}<span style="font-size:0.85rem;color:#475569">/100</span></div>
                <div class="kpi-sub">Investment Score</div>
                <div class="kpi-sub"><span style="color:{yoy_color}">{yoy_str}</span> YoY</div>
                <div class="kpi-sub">${r_rev:,.0f}M revenue</div>
            </div>""", unsafe_allow_html=True)

    # Active region drill-down
    active = st.session_state.get("map_active_region")

    if active and active in df_map["region"].values:
        r         = df_map[df_map["region"] == active].iloc[0]
        yoy_color = "#10B981" if r["yoy"] >= 0 else "#F43F5E"

        st.markdown(f"""
        <div style="background:linear-gradient(127.09deg,rgba(6,11,40,0.94) 19.41%,rgba(10,14,35,0.49) 76.65%);
                    border:1px solid rgba(226,232,240,0.3);border-radius:20px;
                    backdrop-filter:blur(120px);
                    padding:1.2rem 1.5rem;margin-top:0.8rem;
                    box-shadow:0 20px 27px rgba(0,0,0,0.1);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem">
                <div>
                    <span style="font-size:1.2rem;font-weight:700;color:{r['color']}">📍 {r['region']}</span>
                    <span style="font-size:0.85rem;color:#475569;margin-left:0.6rem">({r['state']})</span>
                </div>
                <div>
                    <span style="background:{GRADE_COLORS[r['grade']]};color:white;
                                 padding:0.25rem 0.7rem;border-radius:12px;
                                 font-weight:700;font-size:0.85rem">Grade {r['grade']}</span>
                    <span style="margin-left:0.5rem;color:#475569;font-size:0.85rem">Rank #{r['rank']}</span>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:1rem">
                <div>
                    <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.05em">Production</div>
                    <div style="font-size:1.1rem;font-weight:700;color:#F1F5F9">{r['prod']/1000:,.1f}K <span style="font-size:0.75rem;color:#475569">{unit}</span></div>
                </div>
                <div>
                    <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.05em">Revenue</div>
                    <div style="font-size:1.1rem;font-weight:700;color:#F1F5F9">${r['revenue']:,.0f}<span style="font-size:0.75rem;color:#475569">M</span></div>
                </div>
                <div>
                    <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.05em">Score</div>
                    <div style="font-size:1.1rem;font-weight:700;color:#F1F5F9">{r['score']:.0f}<span style="font-size:0.75rem;color:#475569">/100</span></div>
                </div>
                <div>
                    <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.05em">YoY Growth</div>
                    <div style="font-size:1.1rem;font-weight:700;color:{yoy_color}">{r['yoy']:+.1f}%</div>
                </div>
                <div>
                    <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.05em">Active Rigs</div>
                    <div style="font-size:1.1rem;font-weight:700;color:#F1F5F9">🏗️ {r['rigs']}</div>
                </div>
                <div>
                    <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.05em">Consistency</div>
                    <div style="font-size:1.1rem;font-weight:700;color:#F1F5F9">{r['consistency']:.0f}<span style="font-size:0.75rem;color:#475569">/100</span></div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(
            f'<div style="font-weight:700;color:#E2E8F0;font-size:1rem;'
            f'margin:1.2rem 0 0.4rem;border-left:4px solid {r["color"]};padding-left:0.7rem">'
            f'📈 {active} — Production & SARIMA Forecast</div>',
            unsafe_allow_html=True,
        )
        _render_inline_forecast(active, prod_df, fc_df, commodity, selected_year, r["color"])

        st.markdown(
            f'<div style="font-weight:700;color:#E2E8F0;font-size:1rem;'
            f'margin:1.2rem 0 0.4rem;border-left:4px solid {r["color"]};padding-left:0.7rem">'
            f'📅 {active} — Quarterly Projected Production · {selected_year}</div>',
            unsafe_allow_html=True,
        )
        _render_inline_quarterly(active, quarterly_df, commodity, selected_year, r["color"])

        st.markdown(f"""
        <div style="background:linear-gradient(127.09deg,rgba(6,11,40,0.94) 19.41%,rgba(10,14,35,0.49) 76.65%);
                    border:1px solid rgba(67,24,255,0.3);
                    border-radius:16px;padding:1rem 1.4rem;margin-top:1rem;
                    backdrop-filter:blur(40px);
                    display:flex;justify-content:space-between;align-items:center;">
            <div>
                <div style="color:#F1F5F9;font-weight:700;font-size:0.95rem">
                    💰 Model a single well in {active}
                </div>
                <div style="color:#64748B;font-size:0.8rem;margin-top:0.2rem">
                    Region defaults pre-filled in Well Economics tab from EIA basin averages
                </div>
            </div>
            <div style="color:#475569;font-size:0.8rem;text-align:right">
                Switch to <b style="color:#94A3B8">💰 Well Economics</b> tab →
            </div>
        </div>""", unsafe_allow_html=True)

    return active
