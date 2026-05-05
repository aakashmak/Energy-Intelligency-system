"""
Colorado DJ Basin Case Study — Tab renderer.

Showcases 10 years of well-level production data (2015-2024) from the
Colorado Oil & Gas Conservation Commission (COGCC).

Purpose: Demonstrates OilPulse's ability to ingest and analyze well-level
production data at scale — beyond the state/region aggregates from EIA.

Charts:
  1. Monthly basin production (oil + gas trend, active wells overlay)
  2. Formation breakdown (Niobrara, Codell, J Sand stacked annual bars)
  3. Top 10 operators (horizontal bar chart)
  4. Normalized decline curve (avg well production month 1 → month 36)

All data loaded from 4 Supabase tables populated by colorado.aggregator.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_CHART_BG  = "#060B28"
_GRID      = "rgba(226,232,240,0.07)"
_AXIS_CLR  = "#A0AEC0"
_FONT_CLR  = "#A0AEC0"
_LEGEND_BG = "rgba(6,11,40,0.92)"


@st.cache_data(ttl=600)
def load_colorado_data():
    """Load all 4 Colorado tables from Supabase. Returns dict of DataFrames."""
    try:
        from src.data.db import _select
        monthly   = _select("colorado_monthly",       "*")
        formation = _select("colorado_formations",    "*")
        operator  = _select("colorado_operators",     "*")
        decline   = _select("colorado_decline_curve", "*")

        if not monthly.empty:
            monthly["period"] = pd.to_datetime(monthly["period"])
            monthly = monthly.sort_values("period")

        if not operator.empty:
            operator = operator.sort_values("oil_bbl", ascending=False).head(10)

        if not decline.empty:
            decline = decline.sort_values("month_index")

        return {
            "monthly":   monthly,
            "formation": formation,
            "operator":  operator,
            "decline":   decline,
        }
    except Exception as e:
        st.error(f"Colorado data load error: {e}")
        return {"monthly": pd.DataFrame(), "formation": pd.DataFrame(),
                "operator": pd.DataFrame(), "decline": pd.DataFrame()}


def render_colorado_tab():
    """Render the full Colorado DJ Basin case study."""
    st.markdown(
        '<div class="section-header">🔬 Colorado DJ Basin — Well-Level Case Study</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div style="background:linear-gradient(127.09deg,rgba(6,11,40,0.94) 19.41%,rgba(10,14,35,0.49) 76.65%);
                border-left:4px solid #0EA5E9;border-radius:12px;
                padding:1rem 1.2rem;margin-bottom:1rem;
                border:1px solid rgba(14,165,233,0.25);
                backdrop-filter:blur(40px);">
        <b style="color:#F1F5F9">Why this matters:</b>
        <span style="color:#94A3B8"> While the main dashboard uses EIA state-level
        aggregates, this case study demonstrates OilPulse processing
        <b style="color:#E2E8F0">10 years of well-level production data</b> (2015–2024) from the
        Colorado Oil &amp; Gas Conservation Commission (COGCC). Over 10 million
        individual well-month records aggregated into basin intelligence.</span>
    </div>""", unsafe_allow_html=True)

    data = load_colorado_data()

    if data["monthly"].empty:
        st.warning(
            "⚠️ Colorado data not loaded yet. Run the aggregator first:\n\n"
            "```\npython -m src.data.colorado.aggregator\n```"
        )
        st.info(
            "This one-time script processes ~1 GB of well-level CSVs and saves "
            "aggregated summaries to Supabase. Takes ~5 minutes.",
            icon="💡",
        )
        return

    # ── Summary cards ─────────────────────────────────────────────────────────
    m = data["monthly"]
    total_oil   = float(m["oil_bbl"].sum())
    total_gas   = float(m["gas_mcf"].sum())
    total_water = float(m["water_bbl"].sum())
    avg_wells   = float(m["active_wells"].mean())
    avg_ops     = float(m["active_operators"].mean())
    date_range  = f"{m['period'].min().strftime('%Y-%m')} → {m['period'].max().strftime('%Y-%m')}"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🛢️ Total Oil Produced",   f"{total_oil/1e6:,.1f}M bbl")
    c2.metric("🔥 Total Gas Produced",    f"{total_gas/1e6:,.1f}M Mcf")
    c3.metric("💧 Total Water",           f"{total_water/1e6:,.1f}M bbl")
    c4.metric("⛏️ Avg Active Wells/mo",   f"{avg_wells:,.0f}")
    c5.metric("🏢 Avg Active Operators",  f"{avg_ops:,.0f}")

    st.caption(f"📅 Data range: {date_range} · Source: Colorado COGCC monthly production reports")

    # ── Chart 1: Monthly production + active wells overlay ────────────────────
    st.markdown('<div class="section-header">📈 Monthly Basin Production (2015–2024)</div>', unsafe_allow_html=True)

    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(
        go.Scatter(
            x=m["period"], y=m["oil_bbl"],
            name="Oil (bbl)", mode="lines",
            line=dict(color="#2563EB", width=2.5),
            fill="tozeroy", fillcolor="rgba(37,99,235,0.1)",
        ),
        secondary_y=False,
    )
    fig1.add_trace(
        go.Scatter(
            x=m["period"], y=m["gas_mcf"],
            name="Gas (Mcf)", mode="lines",
            line=dict(color="#16A34A", width=2, dash="dot"),
        ),
        secondary_y=False,
    )
    fig1.add_trace(
        go.Scatter(
            x=m["period"], y=m["active_wells"],
            name="Active Wells", mode="lines",
            line=dict(color="#F97316", width=1.5),
        ),
        secondary_y=True,
    )

    fig1.update_layout(
        height=400, margin=dict(l=0, r=0, t=15, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=_FONT_CLR), bgcolor=_LEGEND_BG),
        plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
        font=dict(color=_FONT_CLR),
        xaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID),
        yaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID),
    )
    fig1.update_yaxes(title_text="Production Volume", title_font=dict(color=_AXIS_CLR),
                      secondary_y=False, gridcolor=_GRID, tickfont=dict(color=_AXIS_CLR))
    fig1.update_yaxes(title_text="Active Wells", title_font=dict(color=_AXIS_CLR),
                      secondary_y=True, showgrid=False, tickfont=dict(color=_AXIS_CLR))
    st.plotly_chart(fig1, use_container_width=True)

    # ── Chart 2: Formation breakdown ──────────────────────────────────────────
    st.markdown('<div class="section-header">🪨 Production by Formation</div>', unsafe_allow_html=True)
    st.caption("Niobrara and Codell are the dominant DJ Basin shale formations")

    f_df = data["formation"]
    if not f_df.empty:
        # Top 5 formations by lifetime oil
        top_formations = (
            f_df.groupby("formation")["oil_bbl"].sum()
            .sort_values(ascending=False).head(5).index.tolist()
        )
        f_top = f_df[f_df["formation"].isin(top_formations)]

        col1, col2 = st.columns(2)

        with col1:
            # Oil by formation — stacked annual bars
            fig_fo = go.Figure()
            for formation in top_formations:
                subset = f_top[f_top["formation"] == formation].sort_values("year")
                fig_fo.add_trace(go.Bar(
                    x=subset["year"], y=subset["oil_bbl"],
                    name=formation,
                ))
            fig_fo.update_layout(
                title=dict(text="Oil Production by Formation (annual)", font=dict(color=_FONT_CLR)),
                barmode="stack", height=340,
                margin=dict(l=0, r=0, t=40, b=0),
                plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
                font=dict(color=_FONT_CLR),
                xaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID),
                yaxis=dict(title="Oil (bbl)", gridcolor=_GRID, color=_AXIS_CLR,
                           title_font=dict(color=_AXIS_CLR)),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            font=dict(color=_FONT_CLR), bgcolor=_LEGEND_BG),
            )
            st.plotly_chart(fig_fo, use_container_width=True)

        with col2:
            # Gas by formation — stacked annual bars
            fig_fg = go.Figure()
            for formation in top_formations:
                subset = f_top[f_top["formation"] == formation].sort_values("year")
                fig_fg.add_trace(go.Bar(
                    x=subset["year"], y=subset["gas_mcf"],
                    name=formation,
                ))
            fig_fg.update_layout(
                title=dict(text="Gas Production by Formation (annual)", font=dict(color=_FONT_CLR)),
                barmode="stack", height=340,
                margin=dict(l=0, r=0, t=40, b=0),
                plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
                font=dict(color=_FONT_CLR),
                xaxis=dict(gridcolor=_GRID, color=_AXIS_CLR, zerolinecolor=_GRID),
                yaxis=dict(title="Gas (Mcf)", gridcolor=_GRID, color=_AXIS_CLR,
                           title_font=dict(color=_AXIS_CLR)),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            font=dict(color=_FONT_CLR), bgcolor=_LEGEND_BG),
            )
            st.plotly_chart(fig_fg, use_container_width=True)

    # ── Chart 3: Top operators ────────────────────────────────────────────────
    st.markdown('<div class="section-header">🏢 Top 10 Operators by Cumulative Oil Production</div>', unsafe_allow_html=True)

    op_df = data["operator"]
    if not op_df.empty:
        op_df_sorted = op_df.sort_values("oil_bbl", ascending=True).head(10)

        fig_op = go.Figure(go.Bar(
            x=op_df_sorted["oil_bbl"],
            y=op_df_sorted["operator"],
            orientation="h",
            marker_color="#3B82F6",
            text=[f"{v/1e6:.1f}M bbl" for v in op_df_sorted["oil_bbl"]],
            textposition="outside",
            textfont=dict(color=_FONT_CLR, size=11),
            hovertext=[
                f"<b>{row['operator']}</b><br>"
                f"Oil: {row['oil_bbl']/1e6:.1f}M bbl<br>"
                f"Gas: {row['gas_mcf']/1e6:.1f}M Mcf<br>"
                f"Wells: {int(row['wells']):,}<br>"
                f"Years active: {int(row['years_active'])}"
                for _, row in op_df_sorted.iterrows()
            ],
            hoverinfo="text",
        ))
        fig_op.update_layout(
            height=400, margin=dict(l=0, r=80, t=15, b=0),
            plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
            font=dict(color=_FONT_CLR),
            xaxis=dict(title="Cumulative Oil (bbl)", gridcolor=_GRID, color=_AXIS_CLR,
                       zerolinecolor=_GRID, title_font=dict(color=_AXIS_CLR)),
            yaxis=dict(title=None, color=_AXIS_CLR),
        )
        st.plotly_chart(fig_op, use_container_width=True)

        with st.expander("📋 Full operator table"):
            display_op = op_df.copy()
            display_op["oil_bbl"] = display_op["oil_bbl"].apply(lambda x: f"{x/1e6:,.2f}M")
            display_op["gas_mcf"] = display_op["gas_mcf"].apply(lambda x: f"{x/1e6:,.2f}M")
            display_op.columns = ["Operator","Oil (bbl)","Gas (Mcf)","Wells","Years Active","computed_at"]
            st.dataframe(display_op.drop(columns=["computed_at"]), use_container_width=True)

    # ── Chart 4: Decline curve ────────────────────────────────────────────────
    st.markdown('<div class="section-header">📉 Normalized Well Decline Curve</div>', unsafe_allow_html=True)
    st.caption(
        "Average production over the first 36 months of a well's life, computed from the top 500 most productive wells. "
        "Shows the typical steep initial decline characteristic of shale wells."
    )

    d_df = data["decline"]
    if not d_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig_d_oil = go.Figure()
            fig_d_oil.add_trace(go.Scatter(
                x=d_df["month_index"],
                y=d_df["avg_oil_bbl"],
                mode="lines+markers",
                line=dict(color="#2563EB", width=2.5),
                marker=dict(size=6),
                name="Avg oil per well",
                fill="tozeroy", fillcolor="rgba(37,99,235,0.1)",
            ))
            fig_d_oil.update_layout(
                title=dict(text="Oil Decline Curve (avg bbl/well/month)", font=dict(color=_FONT_CLR)),
                height=340, margin=dict(l=0, r=0, t=40, b=0),
                plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
                font=dict(color=_FONT_CLR),
                xaxis=dict(title="Months since first production", gridcolor=_GRID,
                           color=_AXIS_CLR, zerolinecolor=_GRID,
                           title_font=dict(color=_AXIS_CLR)),
                yaxis=dict(title="Avg Oil (bbl)", gridcolor=_GRID, color=_AXIS_CLR,
                           title_font=dict(color=_AXIS_CLR)),
            )
            st.plotly_chart(fig_d_oil, use_container_width=True)

        with col2:
            fig_d_pct = go.Figure()
            fig_d_pct.add_trace(go.Scatter(
                x=d_df["month_index"],
                y=d_df["oil_pct_of_month1"],
                mode="lines+markers",
                line=dict(color="#DC2626", width=2.5),
                marker=dict(size=6),
                name="Oil % of Month 1",
            ))
            fig_d_pct.add_trace(go.Scatter(
                x=d_df["month_index"],
                y=d_df["gas_pct_of_month1"],
                mode="lines+markers",
                line=dict(color="#16A34A", width=2, dash="dash"),
                marker=dict(size=5),
                name="Gas % of Month 1",
            ))
            fig_d_pct.update_layout(
                title=dict(text="Decline Rate (% of Month 1 Production)", font=dict(color=_FONT_CLR)),
                height=340, margin=dict(l=0, r=0, t=40, b=0),
                plot_bgcolor=_CHART_BG, paper_bgcolor=_CHART_BG,
                font=dict(color=_FONT_CLR),
                xaxis=dict(title="Months since first production", gridcolor=_GRID,
                           color=_AXIS_CLR, zerolinecolor=_GRID,
                           title_font=dict(color=_AXIS_CLR)),
                yaxis=dict(title="% of Month 1", gridcolor=_GRID, color=_AXIS_CLR,
                           range=[0, 110], title_font=dict(color=_AXIS_CLR)),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            font=dict(color=_FONT_CLR), bgcolor=_LEGEND_BG),
            )
            st.plotly_chart(fig_d_pct, use_container_width=True)

        # Key decline metrics
        if len(d_df) >= 12:
            m1  = float(d_df.iloc[0]["avg_oil_bbl"])
            m6  = float(d_df[d_df["month_index"] == 6]["avg_oil_bbl"].values[0]) if 6 in d_df["month_index"].values else None
            m12 = float(d_df[d_df["month_index"] == 12]["avg_oil_bbl"].values[0]) if 12 in d_df["month_index"].values else None
            m24 = float(d_df[d_df["month_index"] == 24]["avg_oil_bbl"].values[0]) if 24 in d_df["month_index"].values else None

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Month 1 avg",       f"{m1:,.0f} bbl",       help="Initial production")
            if m6 is not None:
                c2.metric("Month 6 decline",   f"{(1-m6/m1)*100:.0f}%",  help=f"{m6:,.0f} bbl — typical 6-mo decline")
            if m12 is not None:
                c3.metric("Month 12 decline",  f"{(1-m12/m1)*100:.0f}%", help=f"{m12:,.0f} bbl — first-year decline")
            if m24 is not None:
                c4.metric("Month 24 decline", f"{(1-m24/m1)*100:.0f}%", help=f"{m24:,.0f} bbl — two-year cumulative decline")

    # ── Methodology note ──────────────────────────────────────────────────────
    with st.expander("📖 Methodology & Data Sources"):
        st.markdown("""
        **Data source:** Colorado Oil & Gas Conservation Commission (COGCC)
        monthly production reports, 2015–2024 (10 annual CSV files, ~1 GB total).
        
        **Processing pipeline:**
        1. Each yearly CSV read in 500K-row chunks to manage memory
        2. Wells identified by (ApiCountyCode × ApiSequenceNumber) composite ID
        3. Formation codes normalized to canonical names (Niobrara, Codell, J Sand, etc.)
        4. Aggregates computed across 4 dimensions: month, formation, operator, well-age
        5. Decline curve built from top 500 wells by cumulative oil production
        6. All summaries persisted to Supabase for fast dashboard access
        
        **Why this adds value beyond the main dashboard:**
        - **Well-level granularity** (vs state/region aggregates in main dashboard)
        - **Formation-specific economics** (Niobrara vs Codell vs J Sand)
        - **Operator benchmarking** (which companies drill the best wells)
        - **Real decline curves** (used in the Well Economics Calculator, Tier 2)
        
        **Relevance to investment decisions:**
        The decline curve here is real data, not modeled. It shows the typical
        shale well drops ~65% in year 1 and ~85% by end of year 2, confirming
        why rig replenishment rate is so critical to basin production sustainability.
        """)
