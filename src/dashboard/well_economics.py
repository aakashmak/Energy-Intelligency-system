"""
Well Economics Calculator — Tier 2 Stretch Goal.

Interactive financial model for a single horizontal oil or gas well.

Inputs (editable):
  - Initial production rate (IP30 — barrels or Mcf per day)
  - Decline parameters (hyperbolic: initial decline %, b-factor, terminal decline %)
  - Drilling & completion cost (D&C CAPEX)
  - Lease operating expense (LOE, $/bbl or $/Mcf)
  - Commodity price assumptions (WTI or Henry Hub)
  - Royalty rate, severance tax, working interest
  - Discount rate (for NPV calculation)

Outputs (calculated):
  - Forecasted monthly production for 240 months (20 years)
  - Estimated Ultimate Recovery (EUR) in MMbbl or Bcf
  - Annual cash flow schedule
  - NPV at user-specified discount rate (default 10%)
  - IRR (Internal Rate of Return)
  - Payback period (months until cumulative cash flow turns positive)

Visualizations:
  1. Production decline curve (dual-axis: monthly rate + cumulative)
  2. Cumulative cash flow (payback visualization with breakeven marker)
  3. Annual cash flow bars (positive/negative colored)

Bonus — Region presets: clicking a region in the map pre-fills reasonable
defaults for that basin (IP rate, decline, D&C cost based on industry averages).

All calculations run client-side in pure Python — update instantly when
inputs change.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ══════════════════════════════════════════════════════════════════════════════
# Region presets — industry-average well economics per basin
# Sources: EIA Drilling Productivity Report, Enverus benchmark data,
#          Colorado COGCC decline curve (for Niobrara-style comparison)
# ══════════════════════════════════════════════════════════════════════════════
REGION_PRESETS = {
    "Permian": {
        "label":      "Permian Basin (TX/NM)",
        "commodity":  "oil",
        "ip_rate":    900,
        "di":         70,
        "b_factor":   1.1,
        "d_terminal": 6,
        "dc_cost":    7.5,
        "loe":        8.0,
        "price":      72.0,
        "royalty":    22.5,
        "sev_tax":    4.6,
        "wi":         100,
        "note":       "Largest U.S. oil basin · high IP, moderate decline, thick pay zones",
    },
    "Bakken": {
        "label":      "Bakken (ND/MT)",
        "commodity":  "oil",
        "ip_rate":    700,
        "di":         75,
        "b_factor":   1.0,
        "d_terminal": 5,
        "dc_cost":    8.5,
        "loe":        10.0,
        "price":      72.0,
        "royalty":    18.75,
        "sev_tax":    11.5,
        "wi":         100,
        "note":       "Mature oil basin · higher LOE from winter operations",
    },
    "Eagle Ford": {
        "label":      "Eagle Ford (TX)",
        "commodity":  "oil",
        "ip_rate":    800,
        "di":         72,
        "b_factor":   1.2,
        "d_terminal": 6,
        "dc_cost":    6.5,
        "loe":        7.5,
        "price":      72.0,
        "royalty":    25.0,
        "sev_tax":    4.6,
        "wi":         100,
        "note":       "Liquids-rich shale · excellent infrastructure access",
    },
    "Appalachia": {
        "label":      "Appalachia — Marcellus/Utica (PA/WV/OH)",
        "commodity":  "gas",
        "ip_rate":    18,
        "di":         60,
        "b_factor":   1.4,
        "d_terminal": 5,
        "dc_cost":    7.0,
        "loe":        0.75,
        "price":      2.50,
        "royalty":    18.0,
        "sev_tax":    4.0,
        "wi":         100,
        "note":       "Largest U.S. gas basin · low LOE, flat terminal decline",
    },
    "Gulf Coast": {
        "label":      "Gulf Coast (LA/TX Offshore)",
        "commodity":  "oil",
        "ip_rate":    1200,
        "di":         55,
        "b_factor":   0.9,
        "d_terminal": 5,
        "dc_cost":    45.0,
        "loe":        15.0,
        "price":      72.0,
        "royalty":    18.75,
        "sev_tax":    0.0,
        "wi":         100,
        "note":       "Federal offshore · high CAPEX, high IP, long plateau",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Core financial math — all functions are pure Python, run instantly
# ══════════════════════════════════════════════════════════════════════════════

def hyperbolic_decline(ip_rate, di_annual, b, d_terminal, months=240):
    """
    Arps hyperbolic decline curve — industry standard for shale well forecasts.
    """
    di_monthly = di_annual / 100 / 12
    dt         = d_terminal / 100 / 12

    rates = np.zeros(months)
    for t in range(months):
        hyper_rate = ip_rate / ((1 + b * di_monthly * t) ** (1 / b))
        d_t        = di_monthly / (1 + b * di_monthly * t)
        if d_t < dt and t > 12:
            switch_t = t
            switch_r = hyper_rate
            for u in range(switch_t, months):
                rates[u] = switch_r * np.exp(-dt * (u - switch_t))
            break
        rates[t] = hyper_rate

    return rates * 30.4


def calculate_cash_flow(
    monthly_prod, price, loe,
    royalty_pct, sev_tax_pct, wi_pct,
    dc_cost_millions, commodity,
):
    """Compute full monthly cash flow schedule."""
    if commodity == "gas":
        gross_revenue = monthly_prod / 1000 * price
        loe_cost      = monthly_prod * loe
    else:
        gross_revenue = monthly_prod * price
        loe_cost      = monthly_prod * loe

    royalty       = gross_revenue * (royalty_pct / 100)
    sev_tax       = (gross_revenue - royalty) * (sev_tax_pct / 100)
    net_revenue   = gross_revenue - royalty - sev_tax - loe_cost
    net_to_wi     = net_revenue * (wi_pct / 100)

    capex         = dc_cost_millions * 1_000_000
    cash_flow     = net_to_wi.copy()
    cash_flow[0] -= capex

    cumulative    = np.cumsum(cash_flow)

    return {
        "gross_revenue":   gross_revenue,
        "royalty":         royalty,
        "sev_tax":         sev_tax,
        "loe_cost":        loe_cost,
        "net_revenue":     net_revenue,
        "monthly_cash":    cash_flow,
        "cumulative_cash": cumulative,
        "capex":           capex,
    }


def calculate_npv(monthly_cash, discount_rate_annual):
    """NPV at given annual discount rate."""
    monthly_rate = (1 + discount_rate_annual / 100) ** (1/12) - 1
    discount_factors = np.array([
        1 / (1 + monthly_rate) ** t for t in range(len(monthly_cash))
    ])
    return float(np.sum(monthly_cash * discount_factors))


def calculate_irr(monthly_cash, max_iter=200, tolerance=1.0):
    """
    IRR — the annual discount rate that makes NPV = 0.

    Bounded bisection between -50% and +500% annual. Returns None if:
      - Well never turns positive (sum of cash < 0)      → no IRR exists
      - Well never goes negative (no CAPEX)              → IRR undefined
      - Bisection fails to converge                      → return None

    Converting annual rate bounds to monthly avoids division by zero
    near mid ≈ -1 which crashed the previous implementation.
    """
    cash = np.asarray(monthly_cash, dtype=float)

    # No IRR if total undiscounted cash is negative (well never breaks even)
    if cash.sum() <= 0:
        return None
    # No IRR if no negative cash flow exists
    if (cash < 0).sum() == 0:
        return None

    # Annual rate bounds: -50% to +500%
    # Convert to monthly: (1 + r_annual)^(1/12) - 1
    low_annual, high_annual = -0.50, 5.00

    def npv_at_annual(r_annual):
        r_monthly = (1 + r_annual) ** (1/12) - 1
        # Guard against r_monthly near -1 (shouldn't happen with bounds above)
        if r_monthly <= -0.99:
            return float("inf")
        discount = np.array([
            1 / (1 + r_monthly) ** t for t in range(len(cash))
        ])
        return float(np.sum(cash * discount))

    npv_low  = npv_at_annual(low_annual)
    npv_high = npv_at_annual(high_annual)

    # If both bounds give same sign, IRR is outside the range
    if npv_low * npv_high > 0:
        return None

    low, high = low_annual, high_annual
    for _ in range(max_iter):
        mid     = (low + high) / 2
        npv_mid = npv_at_annual(mid)
        if abs(npv_mid) < tolerance or (high - low) < 1e-6:
            return mid * 100   # convert to percent
        if npv_mid > 0:
            low = mid
        else:
            high = mid

    return mid * 100


def calculate_payback(cumulative_cash):
    """Return month when cumulative turns positive, or None if never."""
    positive = np.where(cumulative_cash > 0)[0]
    return int(positive[0]) if len(positive) > 0 else None


# ══════════════════════════════════════════════════════════════════════════════
# Streamlit UI
# ══════════════════════════════════════════════════════════════════════════════

def render_well_economics(selected_region: str | None = None):
    """Main render function for the Well Economics Calculator tab."""

    st.markdown(
        '<div class="section-header">💰 Well Economics Calculator</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div style="background:#F0F9FF;border-left:4px solid #0EA5E9;
                padding:1rem 1.2rem;border-radius:4px;margin-bottom:1rem;">
        <b>Interactive well-level financial model.</b> Adjust any input on the left —
        production forecast, NPV, IRR, and payback update <b>instantly</b>. Clicking
        a basin on the Map tab pre-fills industry-average defaults for that region.
    </div>""", unsafe_allow_html=True)

    # ── Region preset selector ────────────────────────────────────────────────
    region_list = ["Custom"] + list(REGION_PRESETS.keys())
    default_idx = 0
    if selected_region and selected_region in REGION_PRESETS:
        default_idx = region_list.index(selected_region)
        st.info(
            f"🎯 Defaults pre-filled for **{selected_region}** (from map selection).",
            icon="🗺️",
        )

    preset_choice = st.selectbox(
        "🎨 Load region preset:",
        options      = region_list,
        index        = default_idx,
        help         = "Loads industry-average well economics for that basin.",
        key          = "we_preset",
    )

    if preset_choice == "Custom":
        defaults = REGION_PRESETS["Permian"]
    else:
        defaults = REGION_PRESETS[preset_choice]
        st.caption(f"📘 {defaults['label']} — _{defaults['note']}_")

    # ══════════════════════════════════════════════════════════════════════════
    # Input panel (left) + Output panel (right)
    # ══════════════════════════════════════════════════════════════════════════
    input_col, output_col = st.columns([1, 2])

    with input_col:
        st.markdown(
            '<div style="font-weight:600;color:#1E3A5F;font-size:0.95rem;'
            'margin-bottom:0.5rem;">⚙️ Input Parameters</div>',
            unsafe_allow_html=True,
        )

        commodity = st.radio(
            "Commodity",
            options=["oil", "gas"],
            format_func=lambda x: "🛢️ Oil" if x=="oil" else "🔥 Gas",
            index=0 if defaults["commodity"]=="oil" else 1,
            horizontal=True,
            key="we_commodity",
        )

        unit_prod = "bbl/day" if commodity == "oil" else "MMcf/day"
        unit_vol  = "bbl"     if commodity == "oil" else "Mcf"
        unit_loe  = "$/bbl"   if commodity == "oil" else "$/Mcf"
        unit_price= "$/bbl"   if commodity == "oil" else "$/MMcf"

        # ── Production inputs ─────────────────────────────────────────────────
        st.markdown("**📈 Production**")
        ip_rate = st.number_input(
            f"Initial Production Rate ({unit_prod})",
            min_value=1.0, max_value=5000.0,
            value=float(defaults["ip_rate"]),
            step=10.0, key="we_ip",
            help="IP30 — average daily rate over first 30 days",
        )
        di = st.slider(
            "Initial Decline Rate (% / year)",
            min_value=10, max_value=90,
            value=int(defaults["di"]),
            step=1, key="we_di",
            help="How fast production falls in year 1",
        )
        b_factor = st.slider(
            "Hyperbolic b-factor",
            min_value=0.5, max_value=2.0,
            value=float(defaults["b_factor"]),
            step=0.05, key="we_b",
            help="Shape of decline curve · 0.5 = steep · 1.5 = flat",
        )
        d_terminal = st.slider(
            "Terminal Decline Rate (% / year)",
            min_value=3, max_value=15,
            value=int(defaults["d_terminal"]),
            step=1, key="we_dt",
            help="Long-term decline after hyperbolic phase",
        )

        # ── Cost inputs ────────────────────────────────────────────────────────
        st.markdown("**💵 Costs**")
        dc_cost = st.number_input(
            "Drilling & Completion ($M)",
            min_value=0.5, max_value=100.0,
            value=float(defaults["dc_cost"]),
            step=0.5, key="we_dc",
            help="Total CAPEX to drill and complete the well",
        )
        loe = st.number_input(
            f"Lease Operating Expense ({unit_loe})",
            min_value=0.0, max_value=50.0,
            value=float(defaults["loe"]),
            step=0.25, key="we_loe",
            help="Per-unit variable operating cost",
        )

        # ── Commodity pricing ─────────────────────────────────────────────────
        st.markdown("**💰 Pricing**")
        price = st.number_input(
            f"Commodity Price ({unit_price})",
            min_value=0.1, max_value=200.0,
            value=float(defaults["price"]),
            step=0.25, key="we_price",
            help="WTI for oil, Henry Hub for gas",
        )

        # ── Fiscal terms ──────────────────────────────────────────────────────
        st.markdown("**📋 Fiscal Terms**")
        royalty = st.slider(
            "Royalty Rate (%)",
            min_value=0.0, max_value=30.0,
            value=float(defaults["royalty"]),
            step=0.25, key="we_royalty",
        )
        sev_tax = st.slider(
            "Severance Tax (%)",
            min_value=0.0, max_value=15.0,
            value=float(defaults["sev_tax"]),
            step=0.1, key="we_sev",
        )
        wi = st.slider(
            "Working Interest (%)",
            min_value=1, max_value=100,
            value=int(defaults["wi"]),
            step=1, key="we_wi",
        )

        # ── Discount rate for NPV ─────────────────────────────────────────────
        st.markdown("**🎯 NPV Discount Rate**")
        discount = st.slider(
            "Discount Rate (% / year)",
            min_value=5, max_value=20,
            value=10, step=1,
            key="we_disc",
            help="Industry standard is NPV10 (10% discount rate)",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Calculations
    # ══════════════════════════════════════════════════════════════════════════
    monthly_prod = hyperbolic_decline(
        ip_rate=ip_rate, di_annual=di, b=b_factor,
        d_terminal=d_terminal, months=240,
    )

    cf = calculate_cash_flow(
        monthly_prod=monthly_prod, price=price, loe=loe,
        royalty_pct=royalty, sev_tax_pct=sev_tax, wi_pct=wi,
        dc_cost_millions=dc_cost, commodity=commodity,
    )

    eur_vol     = monthly_prod.sum()
    eur_label   = f"{eur_vol/1e6:,.2f} MMbbl" if commodity == "oil" else f"{eur_vol/1e6:,.2f} Bcf"

    npv          = calculate_npv(cf["monthly_cash"], discount)
    irr          = calculate_irr(cf["monthly_cash"])
    payback_mo   = calculate_payback(cf["cumulative_cash"])
    total_rev    = cf["gross_revenue"].sum()
    total_cash   = cf["monthly_cash"].sum()
    npv_color    = "#10B981" if npv > 0 else "#EF4444"
    irr_color    = "#10B981" if (irr is not None and irr > discount) else "#EF4444"

    # ══════════════════════════════════════════════════════════════════════════
    # Output panel
    # ══════════════════════════════════════════════════════════════════════════
    with output_col:

        st.markdown(
            '<div style="font-weight:600;color:#1E3A5F;font-size:0.95rem;'
            'margin-bottom:0.5rem;">📊 Calculated Outputs</div>',
            unsafe_allow_html=True,
        )

        kpi_row1 = st.columns(4)
        kpi_row1[0].markdown(f"""
        <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid {npv_color};
                    border-radius:6px;padding:0.7rem 1rem;">
            <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.05em;">NPV @ {discount}%</div>
            <div style="font-size:1.4rem;font-weight:700;color:{npv_color};margin-top:0.2rem;">
                ${npv/1e6:+,.2f}M
            </div>
        </div>
        """, unsafe_allow_html=True)

        irr_display = f"{irr:.1f}%" if irr is not None else "Uneconomic"
        kpi_row1[1].markdown(f"""
        <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid {irr_color};
                    border-radius:6px;padding:0.7rem 1rem;">
            <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.05em;">IRR</div>
            <div style="font-size:1.4rem;font-weight:700;color:{irr_color};margin-top:0.2rem;">
                {irr_display}
            </div>
        </div>
        """, unsafe_allow_html=True)

        payback_str = f"{payback_mo} mo" if payback_mo is not None else "Never"
        payback_color = "#10B981" if payback_mo and payback_mo < 36 else "#F59E0B" if payback_mo else "#EF4444"
        kpi_row1[2].markdown(f"""
        <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid {payback_color};
                    border-radius:6px;padding:0.7rem 1rem;">
            <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.05em;">Payback Period</div>
            <div style="font-size:1.4rem;font-weight:700;color:{payback_color};margin-top:0.2rem;">
                {payback_str}
            </div>
        </div>
        """, unsafe_allow_html=True)

        kpi_row1[3].markdown(f"""
        <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid #3B82F6;
                    border-radius:6px;padding:0.7rem 1rem;">
            <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.05em;">EUR (20yr)</div>
            <div style="font-size:1.4rem;font-weight:700;color:#0F172A;margin-top:0.2rem;">
                {eur_label}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Secondary KPIs
        st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)
        kpi_row2 = st.columns(4)
        kpi_row2[0].metric("Gross Revenue (LOL)",    f"${total_rev/1e6:,.1f}M")
        kpi_row2[1].metric("Net Cash (undiscounted)", f"${total_cash/1e6:+,.1f}M")
        kpi_row2[2].metric("D&C CAPEX",               f"${dc_cost:,.1f}M")
        kpi_row2[3].metric("IP30 Rate",               f"{ip_rate:,.0f} {unit_prod}")

        # ── Chart 1: Production decline curve ─────────────────────────────────
        st.markdown(
            '<div style="font-weight:600;color:#1E3A5F;font-size:0.9rem;'
            'margin:1rem 0 0.3rem;">📈 Production Decline Curve</div>',
            unsafe_allow_html=True,
        )

        months_arr = np.arange(1, 241)
        cum_prod   = np.cumsum(monthly_prod)

        fig_d = make_subplots(specs=[[{"secondary_y": True}]])
        fig_d.add_trace(
            go.Scatter(
                x=months_arr, y=monthly_prod,
                name=f"Monthly ({unit_vol})", mode="lines",
                line=dict(color="#2563EB", width=2),
                fill="tozeroy", fillcolor="rgba(37,99,235,0.15)",
            ),
            secondary_y=False,
        )
        fig_d.add_trace(
            go.Scatter(
                x=months_arr, y=cum_prod,
                name=f"Cumulative ({unit_vol})", mode="lines",
                line=dict(color="#F59E0B", width=2, dash="dash"),
            ),
            secondary_y=True,
        )
        fig_d.update_layout(
            height=300, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(title="Month", gridcolor="#F1F5F9"),
            yaxis=dict(gridcolor="#F1F5F9"),
        )
        fig_d.update_yaxes(title_text=f"Monthly ({unit_vol})",    secondary_y=False)
        fig_d.update_yaxes(title_text=f"Cumulative ({unit_vol})", secondary_y=True, showgrid=False)
        st.plotly_chart(fig_d, use_container_width=True)

        # ── Chart 2: Cumulative cash flow ─────────────────────────────────────
        st.markdown(
            '<div style="font-weight:600;color:#1E3A5F;font-size:0.9rem;'
            'margin:1rem 0 0.3rem;">💰 Cumulative Cash Flow & Payback</div>',
            unsafe_allow_html=True,
        )

        fig_cf = go.Figure()
        cum_m = cf["cumulative_cash"] / 1e6

        fig_cf.add_trace(go.Scatter(
            x=months_arr, y=cum_m,
            mode="lines",
            line=dict(color="#1E3A5F", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(37,99,235,0.1)",
            name="Cumulative Cash Flow",
        ))

        fig_cf.add_hline(y=0, line=dict(color="#6B7280", width=1, dash="dot"),
                         annotation_text="Breakeven", annotation_position="right")

        if payback_mo is not None:
            fig_cf.add_vline(x=payback_mo, line=dict(color="#F59E0B", width=2, dash="dash"))
            fig_cf.add_annotation(
                x=payback_mo, y=0,
                text=f"Payback: Month {payback_mo}",
                showarrow=True, arrowhead=2, arrowcolor="#F59E0B",
                ax=40, ay=-40,
                font=dict(color="#F59E0B", size=11, family="Arial Black"),
            )

        fig_cf.update_layout(
            height=300, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(title="Month", gridcolor="#F1F5F9"),
            yaxis=dict(title="Cumulative Cash ($M)", gridcolor="#F1F5F9"),
        )
        st.plotly_chart(fig_cf, use_container_width=True)

        # ── Chart 3: Annual cash flow bars ────────────────────────────────────
        st.markdown(
            '<div style="font-weight:600;color:#1E3A5F;font-size:0.9rem;'
            'margin:1rem 0 0.3rem;">📊 Annual Net Cash Flow</div>',
            unsafe_allow_html=True,
        )

        annual_cash = cf["monthly_cash"].reshape(-1, 12).sum(axis=1) / 1e6
        years = np.arange(1, len(annual_cash) + 1)
        bar_colors = ["#EF4444" if v < 0 else "#10B981" for v in annual_cash]

        fig_an = go.Figure(go.Bar(
            x=years, y=annual_cash,
            marker_color=bar_colors,
            text=[f"${v:+.1f}M" for v in annual_cash],
            textposition="outside",
        ))
        fig_an.update_layout(
            height=260, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(title="Year", gridcolor="#F1F5F9", dtick=2),
            yaxis=dict(title="Net Cash ($M)", gridcolor="#F1F5F9"),
        )
        st.plotly_chart(fig_an, use_container_width=True)

        # ── Cash flow table ───────────────────────────────────────────────────
        with st.expander("📋 Full annual cash flow schedule"):
            yearly_summary = []
            for y in range(20):
                start_m = y * 12
                end_m   = (y + 1) * 12
                yr_prod  = monthly_prod[start_m:end_m].sum()
                yr_gross = cf["gross_revenue"][start_m:end_m].sum() / 1e6
                yr_royal = cf["royalty"][start_m:end_m].sum() / 1e6
                yr_tax   = cf["sev_tax"][start_m:end_m].sum() / 1e6
                yr_loe   = cf["loe_cost"][start_m:end_m].sum() / 1e6
                yr_net   = cf["monthly_cash"][start_m:end_m].sum() / 1e6
                yr_cum   = cf["cumulative_cash"][end_m-1] / 1e6
                yearly_summary.append({
                    "Year":           y + 1,
                    f"Prod ({unit_vol})": f"{yr_prod:,.0f}",
                    "Gross ($M)":     f"{yr_gross:,.2f}",
                    "Royalty ($M)":   f"{yr_royal:,.2f}",
                    "Sev Tax ($M)":   f"{yr_tax:,.2f}",
                    "LOE ($M)":       f"{yr_loe:,.2f}",
                    "Net Cash ($M)":  f"{yr_net:+,.2f}",
                    "Cum. Cash ($M)": f"{yr_cum:+,.2f}",
                })
            st.dataframe(pd.DataFrame(yearly_summary).set_index("Year"),
                         use_container_width=True, height=420)

        # ── Methodology ────────────────────────────────────────────────────────
        with st.expander("📖 Methodology — how these numbers are calculated"):
            st.markdown("""
            **Decline curve model:** Arps hyperbolic decline — the industry-standard
            model for shale wells. Production at month `t`:

            ```
            q(t) = q_i / (1 + b · Di · t)^(1/b)
            ```

            where `q_i` is initial rate, `Di` is initial decline, and `b` is the
            hyperbolic exponent. The model switches to exponential decline once
            effective decline falls below the terminal rate `Dt`.

            **Monthly cash flow:**
            ```
            Gross Revenue = Production × Price
            Royalty       = Gross × Royalty%
            Severance Tax = (Gross − Royalty) × SevTax%
            LOE           = Production × LOE_rate
            Net Cash      = (Gross − Royalty − SevTax − LOE) × WI%
            Month 0       = Net Cash − D&C CAPEX
            ```

            **NPV** is the sum of monthly cash flows discounted at the user-specified
            annual rate, converted to an equivalent monthly rate.

            **IRR** is solved numerically via bisection on annual rates between
            -50% and +500%. Returns "Uneconomic" if the well never turns a profit.

            **Payback** is the first month where cumulative cash flow turns positive.

            **All calculations run in pure Python (numpy) on every input change — no
            server round-trip, no database query. Updates are instant.**
            """)
