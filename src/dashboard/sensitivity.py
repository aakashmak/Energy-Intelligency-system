"""
Sensitivity Analysis — Stress-Test Forecasts.

Shows how Projected Production changes across two input variables as a
color-coded heat map. Analysts can explore multiple scenario combinations
to stress-test the SARIMA forecast for any selected year.

Design:
  - X axis: one variable (e.g. commodity price)
  - Y axis: second variable (e.g. decline rate %)
  - Cell value: projected annual production (Mbbl or MMcf)
  - Cell color: green (strong) → red (weak), relative to base case
  - Tied to year selector — works for historical, current, and future years
  - Works with or without region filter (map click)

The math:
  Rather than re-running SARIMA (which would be slow), we apply
  percentage adjustments to the SARIMA forecast to simulate the effect
  of each parameter. This is the standard sensitivity approach used
  in upstream finance.

  Supported variable pairs:
    1. Decline Rate (%) vs Commodity Price ($/bbl or $/MMcf)
    2. Decline Rate (%) vs WI % (working interest)
    3. Production Volume (% change) vs Commodity Price
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from itertools import product


# ── Sensitivity parameter definitions ─────────────────────────────────────────

VARIABLES = {
    "Decline Rate (% adj.)": {
        "key":     "decline_pct",
        "values":  [-30, -20, -10, 0, +10, +20, +30],
        "label":   "Decline Rate Adj. (%)",
        "help":    "Adjusts the SARIMA-implied decline rate. -10% = slower decline, +10% = steeper decline.",
        "default": 0,
        "fmt":     lambda v: f"{v:+d}%",
    },
    "Commodity Price ($/unit adj.)": {
        "key":     "price_pct",
        "values":  [-40, -25, -10, 0, +10, +25, +40],
        "label":   "Price Adj. (%)",
        "help":    "Adjusts WTI or Henry Hub price assumption. -25% = $54/bbl if base is $72.",
        "default": 0,
        "fmt":     lambda v: f"{v:+d}%",
    },
    "Production Volume (% adj.)": {
        "key":     "volume_pct",
        "values":  [-25, -15, -5, 0, +5, +15, +25],
        "label":   "Volume Adj. (%)",
        "help":    "Directly adjusts production volume (IP rate or plateau adjustment).",
        "default": 0,
        "fmt":     lambda v: f"{v:+d}%",
    },
    "Working Interest (% abs.)": {
        "key":     "wi_pct",
        "values":  [50, 60, 70, 80, 90, 100],
        "label":   "Working Interest (%)",
        "help":    "Net revenue share after royalty and burdens.",
        "default": 100,
        "fmt":     lambda v: f"{v}%",
    },
}

DEFAULT_PRICE_OIL = 72.0   # $/bbl WTI
DEFAULT_PRICE_GAS = 2.50   # $/MMcf Henry Hub
DEFAULT_ROYALTY   = 0.1875 # 18.75%
DEFAULT_SEV_TAX   = 0.046  # 4.6%


# ── Core sensitivity math ──────────────────────────────────────────────────────

def _apply_adjustments(base_prod, base_price, x_key, x_val, y_key, y_val, commodity, wi_pct=100.0):
    """
    Given base annual production and base price, compute adjusted
    production volume AND net revenue after applying x/y parameter changes.

    Returns: (adj_volume, adj_net_revenue_M)
    """
    adj_volume = float(base_prod)
    adj_price  = float(base_price)
    adj_wi     = wi_pct / 100.0

    for key, val in [(x_key, x_val), (y_key, y_val)]:
        if key == "decline_pct":
            # Steeper decline → less volume. +10% decline ≈ -10% volume (simplified)
            adj_volume *= (1 - val / 100 * 0.8)
        elif key == "volume_pct":
            adj_volume *= (1 + val / 100)
        elif key == "price_pct":
            adj_price  *= (1 + val / 100)
        elif key == "wi_pct":
            adj_wi = val / 100.0

    # Revenue = volume × price (oil: Mbbl × $/bbl / 1000 = $M; gas: Mcf × $/MMcf / 1000 = $M)
    if commodity == "oil":
        gross_M = adj_volume * adj_price / 1_000
    else:
        # volume in Mcf, price in $/MMcf → /1000 to get MMcf, /1000 again for $M
        gross_M = adj_volume / 1_000 * adj_price / 1_000

    royalty   = gross_M * DEFAULT_ROYALTY
    sev_tax   = (gross_M - royalty) * DEFAULT_SEV_TAX
    net_M     = (gross_M - royalty - sev_tax) * adj_wi

    return max(0, adj_volume), net_M


def build_matrix(
    base_annual_prod: float,
    base_price: float,
    x_var: str,
    y_var: str,
    commodity: str,
    metric: str = "production",
    wi_pct: float = 100.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build the sensitivity matrix.

    Returns (value_df, pct_change_df) where rows = Y variable, cols = X variable.
    """
    x_def  = VARIABLES[x_var]
    y_def  = VARIABLES[y_var]
    x_vals = x_def["values"]
    y_vals = y_def["values"]

    values   = np.zeros((len(y_vals), len(x_vals)))
    pct_chng = np.zeros((len(y_vals), len(x_vals)))

    # Base case (no adjustments)
    base_vol, base_rev = _apply_adjustments(
        base_annual_prod, base_price,
        x_def["key"], x_def["default"],
        y_def["key"], y_def["default"],
        commodity, wi_pct,
    )
    base_val = base_vol if metric == "production" else base_rev

    for i, yv in enumerate(y_vals):
        for j, xv in enumerate(x_vals):
            vol, rev = _apply_adjustments(
                base_annual_prod, base_price,
                x_def["key"], xv,
                y_def["key"], yv,
                commodity, wi_pct,
            )
            cell_val = vol if metric == "production" else rev
            values[i, j]   = cell_val
            pct_chng[i, j] = ((cell_val - base_val) / base_val * 100) if base_val > 0 else 0

    x_labels = [x_def["fmt"](v) for v in x_vals]
    y_labels = [y_def["fmt"](v) for v in y_vals]

    value_df  = pd.DataFrame(values,   index=y_labels, columns=x_labels)
    pct_df    = pd.DataFrame(pct_chng, index=y_labels, columns=x_labels)

    return value_df, pct_df


# ── Plotly heat map builder ────────────────────────────────────────────────────

def build_heatmap(
    value_df:  pd.DataFrame,
    pct_df:    pd.DataFrame,
    x_title:   str,
    y_title:   str,
    unit:      str,
    metric:    str,
    base_val:  float,
    selected_year: int,
    region_label:  str,
) -> go.Figure:
    """
    Build a Plotly annotated heat map with:
      - Green (strong) → Red (weak) colorscale
      - Cell text = value + % change from base
      - Base case cell highlighted with a bold border
      - Axis labels = parameter values
    """
    z   = value_df.values
    pct = pct_df.values
    rows, cols = z.shape

    # Diverging colorscale: red for weak, white for base, green for strong
    colorscale = [
        [0.0,  "#DC2626"],   # deep red  (−40%+)
        [0.25, "#F97316"],   # orange
        [0.45, "#FEF9C3"],   # pale yellow
        [0.5,  "#FFFFFF"],   # white = base case
        [0.55, "#D1FAE5"],   # pale green
        [0.75, "#10B981"],   # emerald
        [1.0,  "#065F46"],   # deep green (+40%+)
    ]

    # Build annotation text for each cell
    cell_text = []
    for i in range(rows):
        row_text = []
        for j in range(cols):
            v = z[i, j]
            p = pct[i, j]
            if metric == "production":
                val_str = f"{v/1000:,.1f}K" if v < 1_000_000 else f"{v/1_000_000:.2f}M"
            else:
                val_str = f"${v:,.1f}M"
            pct_str = f"<br><span style='font-size:9px'>{'▲' if p>0 else '▼' if p<0 else '●'} {abs(p):.0f}%</span>" if abs(p) > 0.1 else "<br><span style='font-size:9px'>● base</span>"
            row_text.append(f"<b>{val_str}</b>{pct_str}")
        cell_text.append(row_text)

    # Normalize z to [-1, 1] range for colorscale mapping
    z_min, z_max = z.min(), z.max()
    z_norm = (z - z_min) / (z_max - z_min) if z_max > z_min else np.full_like(z, 0.5)

    fig = go.Figure(go.Heatmap(
        z          = z_norm,
        x          = value_df.columns.tolist(),
        y          = value_df.index.tolist(),
        colorscale = colorscale,
        showscale  = True,
        colorbar   = dict(
            title      = "Opportunity<br>Quality",
            tickvals   = [0, 0.5, 1],
            ticktext   = ["Weak", "Base", "Strong"],
            thickness  = 14,
            len        = 0.7,
            titlefont  = dict(size=11),
            tickfont   = dict(size=10),
        ),
        hovertemplate=(
            f"<b>{{x}} / {{y}}</b><br>"
            f"Value: %{{customdata[0]}}<br>"
            f"Change from base: %{{customdata[1]:.1f}}%"
            "<extra></extra>"
        ),
        customdata=np.stack([z, pct], axis=-1),
        zmin=0, zmax=1,
    ))

    # Add text annotations
    for i in range(rows):
        for j in range(cols):
            v = z[i, j]
            p = pct[i, j]
            if metric == "production":
                val_str = f"{v/1000:,.1f}K" if v < 1_000_000 else f"{v/1_000_000:.2f}M"
            else:
                val_str = f"${v:,.1f}M"

            pct_str = f"{'▲' if p>0 else '▼' if p<0 else '●'} {abs(p):.0f}%" if abs(p) > 0.1 else "● base"

            fig.add_annotation(
                x     = value_df.columns[j],
                y     = value_df.index[i],
                text  = f"<b>{val_str}</b><br><span style='font-size:9px;color:#374151'>{pct_str}</span>",
                showarrow    = False,
                font         = dict(size=11, color="#111827"),
                bgcolor      = "rgba(255,255,255,0.0)",
                bordercolor  = "rgba(0,0,0,0)",
            )

    # Highlight base case cell
    # Find row/col index where both variables are at their default
    x_def_label = VARIABLES.get(x_title, {}).get("fmt", lambda v: str(v))(
        VARIABLES.get(x_title, {}).get("default", 0)
    ) if x_title in VARIABLES else None
    y_def_label = VARIABLES.get(y_title, {}).get("fmt", lambda v: str(v))(
        VARIABLES.get(y_title, {}).get("default", 0)
    ) if y_title in VARIABLES else None

    if x_def_label in value_df.columns.tolist() and y_def_label in value_df.index.tolist():
        fig.add_shape(
            type="rect",
            x0=value_df.columns.tolist().index(x_def_label) - 0.5,
            x1=value_df.columns.tolist().index(x_def_label) + 0.5,
            y0=value_df.index.tolist().index(y_def_label) - 0.5,
            y1=value_df.index.tolist().index(y_def_label) + 0.5,
            line=dict(color="#1E3A5F", width=3),
            fillcolor="rgba(0,0,0,0)",
            xref="x", yref="y",
        )

    fig.update_layout(
        title=dict(
            text=(
                f"<b>Sensitivity: {metric.title()} ({unit}) · {selected_year}</b>"
                f"<br><span style='font-size:11px;color:#64748B'>{region_label}</span>"
            ),
            font=dict(size=14, color="#1E3A5F"),
            x=0,
        ),
        height     = 480,
        margin     = dict(l=0, r=120, t=70, b=60),
        xaxis=dict(
            title      = x_title,
            side       = "bottom",
            tickfont   = dict(size=11, color="#374151"),
            titlefont  = dict(size=12, color="#1E3A5F", family="Arial Black"),
            showgrid   = False,
        ),
        yaxis=dict(
            title      = y_title,
            tickfont   = dict(size=11, color="#374151"),
            titlefont  = dict(size=12, color="#1E3A5F", family="Arial Black"),
            showgrid   = False,
            autorange  = "reversed",
        ),
        paper_bgcolor = "white",
        plot_bgcolor  = "white",
    )

    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Main render function
# ══════════════════════════════════════════════════════════════════════════════

def render_sensitivity(
    prod_df:       pd.DataFrame,
    fc_df:         pd.DataFrame,
    scores_df:     pd.DataFrame,
    active_regions: list[str],
    commodity:     str,
    selected_year: int,
    current_year:  int,
):
    st.markdown(
        '<div class="section-header">🔬 Sensitivity Analysis — Forecast Stress Test</div>',
        unsafe_allow_html=True,
    )

    st.markdown("""
    <div style="background:#F0F9FF;border-left:4px solid #0EA5E9;
                padding:0.9rem 1.2rem;border-radius:4px;margin-bottom:1rem;font-size:0.85rem;">
        <b>How to read this:</b> Each cell shows projected annual production
        (or net revenue) for a combination of two input variables. The
        <b>base case</b> is outlined in navy. Green cells = stronger outlook,
        red cells = weaker. Use the year slider to explore sensitivity
        across the forecast horizon.
    </div>""", unsafe_allow_html=True)

    # ── Controls row ──────────────────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([2, 2, 2, 1])

    with ctrl1:
        region_options = active_regions if active_regions else ["All (portfolio avg)"]
        region_sel = st.selectbox(
            "📍 Region",
            options=region_options,
            key="sens_region",
            help="Select a single region to model. Defaults to map selection.",
        )

    with ctrl2:
        var_list = list(VARIABLES.keys())
        x_var = st.selectbox(
            "📐 X Axis Variable",
            options=var_list,
            index=1,   # default: Price
            key="sens_x",
        )

    with ctrl3:
        remaining = [v for v in var_list if v != x_var]
        y_var = st.selectbox(
            "📐 Y Axis Variable",
            options=remaining,
            index=0,   # default: Decline Rate
            key="sens_y",
        )

    with ctrl4:
        metric = st.radio(
            "📊 Show",
            options=["production", "revenue"],
            format_func=lambda x: "🛢️ Volume" if x == "production" else "💰 Revenue",
            key="sens_metric",
            help="Choose whether cells show production volume or net revenue.",
        )

    unit = "Mbbl" if commodity == "oil" else "MMcf"
    base_price = DEFAULT_PRICE_OIL if commodity == "oil" else DEFAULT_PRICE_GAS

    # ── Compute base annual production ────────────────────────────────────────
    is_future = selected_year > current_year

    if is_future:
        # Use SARIMA forecast
        fc_region = fc_df[
            (fc_df["region"] == region_sel) &
            (fc_df["commodity"] == commodity) &
            (fc_df["period"].dt.year == selected_year)
        ] if not fc_df.empty else pd.DataFrame()

        base_prod = float(fc_region["forecast"].sum()) if not fc_region.empty else 0.0
        data_source = f"SARIMA forecast · {selected_year}"
    else:
        # Use actual data for historical / current year
        act_region = prod_df[
            (prod_df["region"] == region_sel) &
            (prod_df["commodity"] == commodity) &
            (prod_df["period"].dt.year == selected_year)
        ]
        base_prod = float(act_region["value"].sum()) if not act_region.empty else 0.0

        # If actuals incomplete (current year), blend with forecast
        if base_prod == 0 or (selected_year == current_year and len(act_region) < 12):
            fc_region = fc_df[
                (fc_df["region"] == region_sel) &
                (fc_df["commodity"] == commodity) &
                (fc_df["period"].dt.year == selected_year)
            ] if not fc_df.empty else pd.DataFrame()
            if not fc_region.empty:
                base_prod = float(fc_region["forecast"].sum())
        data_source = f"{'Historical actuals' if not is_future else 'SARIMA forecast'} · {selected_year}"

    if base_prod == 0:
        st.warning(f"No production data available for **{region_sel}** in {selected_year}. Try a different year or region.")
        return

    # ── Build matrix ──────────────────────────────────────────────────────────
    value_df, pct_df = build_matrix(
        base_annual_prod = base_prod,
        base_price       = base_price,
        x_var            = x_var,
        y_var            = y_var,
        commodity        = commodity,
        metric           = metric,
        wi_pct           = 100.0,
    )

    # ── KPI summary row ───────────────────────────────────────────────────────
    base_vol, base_rev = _apply_adjustments(
        base_prod, base_price,
        VARIABLES[x_var]["key"], VARIABLES[x_var]["default"],
        VARIABLES[y_var]["key"], VARIABLES[y_var]["default"],
        commodity,
    )
    best_val  = value_df.values.max()
    worst_val = value_df.values.min()
    spread    = (best_val - worst_val) / worst_val * 100 if worst_val > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f"""
    <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid #2563EB;
                border-radius:6px;padding:0.7rem 1rem;">
        <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em">Base Case ({unit}/yr)</div>
        <div style="font-size:1.3rem;font-weight:700;color:#1E3A5F;margin-top:0.2rem">
            {base_prod/1000:,.1f}K
        </div>
        <div style="font-size:0.72rem;color:#94A3B8">{data_source}</div>
    </div>""", unsafe_allow_html=True)

    m2.markdown(f"""
    <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid #10B981;
                border-radius:6px;padding:0.7rem 1rem;">
        <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em">Best Case</div>
        <div style="font-size:1.3rem;font-weight:700;color:#10B981;margin-top:0.2rem">
            {best_val/1000:,.1f}K {unit if metric=='production' else 'M'}
        </div>
        <div style="font-size:0.72rem;color:#94A3B8">{'▲ '+f'{(best_val/base_prod-1)*100:.0f}% vs base' if base_prod>0 else '—'}</div>
    </div>""", unsafe_allow_html=True)

    m3.markdown(f"""
    <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid #EF4444;
                border-radius:6px;padding:0.7rem 1rem;">
        <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em">Worst Case</div>
        <div style="font-size:1.3rem;font-weight:700;color:#EF4444;margin-top:0.2rem">
            {worst_val/1000:,.1f}K {unit if metric=='production' else 'M'}
        </div>
        <div style="font-size:0.72rem;color:#94A3B8">{'▼ '+f'{(1-worst_val/base_prod)*100:.0f}% vs base' if base_prod>0 else '—'}</div>
    </div>""", unsafe_allow_html=True)

    m4.markdown(f"""
    <div style="background:white;border:1px solid #E5E7EB;border-left:4px solid #F59E0B;
                border-radius:6px;padding:0.7rem 1rem;">
        <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em">Scenario Spread</div>
        <div style="font-size:1.3rem;font-weight:700;color:#F59E0B;margin-top:0.2rem">
            {spread:.0f}%
        </div>
        <div style="font-size:0.72rem;color:#94A3B8">best vs worst</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

    # ── Heat map ──────────────────────────────────────────────────────────────
    region_label = f"{region_sel} · {commodity.upper()} · {'SARIMA Forecast' if is_future else 'Actual/Model'}"

    fig = build_heatmap(
        value_df       = value_df,
        pct_df         = pct_df,
        x_title        = VARIABLES[x_var]["label"],
        y_title        = VARIABLES[y_var]["label"],
        unit           = unit if metric == "production" else "$M",
        metric         = metric,
        base_val       = base_prod if metric == "production" else base_rev,
        selected_year  = selected_year,
        region_label   = region_label,
    )

    st.plotly_chart(fig, width="stretch", key=f"sens_heatmap_{region_sel}_{x_var}_{y_var}_{metric}_{selected_year}")

    # ── Interpretation bar ─────────────────────────────────────────────────────
    # Find the top-right and bottom-left quadrant interpretation
    top_right_pct = pct_df.values[0, -1]     # min Y, max X
    bot_left_pct  = pct_df.values[-1, 0]     # max Y, min X

    st.markdown(f"""
    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;
                padding:0.9rem 1.2rem;margin-top:0.5rem;display:grid;
                grid-template-columns:1fr 1fr 1fr;gap:1rem;font-size:0.82rem;">
        <div>
            <div style="color:#10B981;font-weight:700;font-size:0.85rem">✅ Bull Case (top-right)</div>
            <div style="color:#374151;margin-top:0.2rem">
                {VARIABLES[y_var]['label']} at best + {VARIABLES[x_var]['label']} at best:
                <b style="color:#10B981">{top_right_pct:+.0f}%</b> vs base
            </div>
        </div>
        <div style="border-left:1px solid #E2E8F0;padding-left:1rem">
            <div style="color:#1E3A5F;font-weight:700;font-size:0.85rem">📊 Base Case (navy border)</div>
            <div style="color:#374151;margin-top:0.2rem">
                Both variables at default assumptions:
                <b>{base_prod/1000:,.1f}K {unit}</b>/year
            </div>
        </div>
        <div style="border-left:1px solid #E2E8F0;padding-left:1rem">
            <div style="color:#EF4444;font-weight:700;font-size:0.85rem">⚠️ Bear Case (bottom-left)</div>
            <div style="color:#374151;margin-top:0.2rem">
                {VARIABLES[y_var]['label']} at worst + {VARIABLES[x_var]['label']} at worst:
                <b style="color:#EF4444">{bot_left_pct:+.0f}%</b> vs base
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Data table (expandable) ────────────────────────────────────────────────
    with st.expander("📋 Full sensitivity matrix — raw values"):
        display_df = value_df.copy()
        if metric == "production":
            display_df = display_df.applymap(lambda v: f"{v/1000:,.1f}K {unit}")
        else:
            display_df = display_df.applymap(lambda v: f"${v:,.1f}M")

        st.dataframe(display_df, width="stretch")
        st.caption(
            f"Rows = {VARIABLES[y_var]['label']} · "
            f"Cols = {VARIABLES[x_var]['label']} · "
            f"Base: {region_sel}, {selected_year}, {commodity.upper()}"
        )

    # ── Methodology note ───────────────────────────────────────────────────────
    with st.expander("📖 Methodology"):
        st.markdown(f"""
        **Data source:** {'SARIMA 36-month forecast (future year)' if is_future else 'EIA actual production data'} for {region_sel} · {selected_year}

        **Sensitivity approach:** Percentage adjustments are applied to the base
        case production and price assumptions. This is a simplified
        parametric sensitivity — not a full SARIMA re-run — which allows
        instant updates as variables change.

        **Variable definitions:**
        - **Decline Rate adj.** — shifts the effective decline rate of the basin.
          A +10% adjustment means 10% steeper decline, reducing annual volume ~8%.
        - **Price adj.** — directly scales the commodity price assumption
          (WTI for oil, Henry Hub for gas).
        - **Volume adj.** — directly scales production volume (e.g. better-than-expected completions).
        - **Working Interest** — the net revenue share after royalty and burdens.

        **Revenue formula:**
        ```
        Gross = Volume × Price
        Net   = (Gross − Royalty − Severance Tax) × WI%
        ```
        Royalty = 18.75%, Severance Tax = 4.6% (Texas/Permian defaults).

        **Color scale:** Cells are colored relative to the minimum/maximum values
        in the current matrix. Green = highest value in matrix, Red = lowest.
        The navy border marks the base case (zero adjustments).
        """)
