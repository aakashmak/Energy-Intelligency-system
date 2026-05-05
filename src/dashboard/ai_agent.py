"""
Conversational AI Agent — Tier 1 Required.

A data-grounded analyst that answers questions about OilPulse data.
Uses GPT-4o with live Supabase data injected as context.

Key design decisions:
  - System prompt contains LIVE KPI snapshot from Supabase (not training data)
  - Agent distinguishes data-backed claims (labeled [DATA]) from model inference ([INFERENCE])
  - Agent can answer: "Which region has highest production?", "Summarize Permian",
    "What if decline rate increases 15%?", "Compare Eagle Ford vs Bakken"
  - No hallucinations on numbers — all figures come from the context snapshot
  - Falls back gracefully if OpenAI key is not set

Limitations:
  - OpenAI key required (set OPENAI_API_KEY in .env or Streamlit secrets)
  - Context window = current snapshot, not full history
"""

import os
import json
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime


# ── Build live data context from Supabase ─────────────────────────────────────

def build_data_context(
    scores_df: pd.DataFrame,
    quarterly_df: pd.DataFrame,
    prod_df: pd.DataFrame,
    fc_df: pd.DataFrame,
    rig_df: pd.DataFrame,
    val_df: pd.DataFrame,
    selected_year: int,
) -> str:
    """
    Build a structured text snapshot of all live Supabase data.
    This is injected into the GPT system prompt so the agent
    answers with current numbers, not training data.
    """
    lines = [
        f"=== OilPulse Live Data Snapshot ===",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Selected forecast year: {selected_year}",
        "",
    ]

    # ── Investment scores + KPIs ───────────────────────────────────────────────
    lines.append("--- INVESTMENT SCORES & KPIs (all regions) ---")
    if not scores_df.empty:
        for _, row in scores_df.sort_values("score", ascending=False).iterrows():
            lines.append(
                f"Region: {row.get('region','?')} | "
                f"Score: {float(row.get('score',0) or 0):.1f}/100 | "
                f"Rank: {row.get('rank','?')} | "
                f"YoY Growth: {float(row.get('yoy_growth',0) or 0):.2f}% | "
                f"Decline Rate: {float(row.get('decline_rate',0) or 0):.2f}% | "
                f"Revenue Potential: ${float(row.get('revenue_potential',0) or 0):,.0f}M | "
                f"Consistency Score: {float(row.get('consistency_score',0) or 0):.1f}/100 | "
                f"Rel. Performance: {float(row.get('rel_performance',50) or 50):.1f}/100 | "
                f"Momentum: {float(row.get('momentum',0) or 0):.4f}"
            )
    else:
        lines.append("No scores data available.")
    lines.append("")

    # ── Projected production for selected year ─────────────────────────────────
    lines.append(f"--- PROJECTED PRODUCTION ({selected_year}) ---")
    if not quarterly_df.empty:
        for commodity in ["oil", "gas"]:
            unit = "Mbbl/year" if commodity == "oil" else "MMcf/year"
            yr_data = quarterly_df[
                (quarterly_df["year"] == selected_year) &
                (quarterly_df["commodity"] == commodity)
            ]
            if not yr_data.empty:
                annual = yr_data.groupby("region")["value"].sum().reset_index()
                lines.append(f"  {commodity.upper()} ({unit}):")
                for _, r in annual.sort_values("value", ascending=False).iterrows():
                    lines.append(f"    {r['region']}: {float(r['value']):,.0f}")
    lines.append("")

    # ── Latest production actuals ──────────────────────────────────────────────
    lines.append("--- LATEST ACTUAL PRODUCTION (most recent month) ---")
    if not prod_df.empty:
        latest = prod_df.sort_values("period").groupby(["region","commodity"]).last().reset_index()
        for _, r in latest.iterrows():
            lines.append(
                f"  {r['region']} {r['commodity']}: "
                f"{float(r['value']):,.0f} "
                f"({'Mbbl/month' if r['commodity']=='oil' else 'MMcf/month'}) "
                f"as of {str(r['period'])[:7]}"
            )
    lines.append("")

    # ── Latest rig counts ──────────────────────────────────────────────────────
    lines.append("--- ACTIVE RIG COUNTS (latest) ---")
    if not rig_df.empty:
        latest_rigs = rig_df.sort_values("period").groupby("region").last().reset_index()
        for _, r in latest_rigs.iterrows():
            lines.append(f"  {r['region']}: {int(r['rigs'])} rigs as of {str(r['period'])[:7]}")
    lines.append("")

    # ── Model validation metrics ───────────────────────────────────────────────
    lines.append("--- SARIMA MODEL ACCURACY ---")
    if not val_df.empty:
        for _, r in val_df.iterrows():
            lines.append(
                f"  {r.get('region','?')} {r.get('commodity','?')}: "
                f"MAPE={float(r.get('mape',0) or 0):.2f}% | "
                f"Grade={r.get('grade','?')} | "
                f"MAE={float(r.get('mae',0) or 0):,.0f}"
            )
    lines.append("")

    # ── Forecasts for next 3 years ─────────────────────────────────────────────
    lines.append(f"--- SARIMA FORECASTS ({selected_year}–{selected_year+2}) ---")
    if not fc_df.empty:
        for commodity in ["oil", "gas"]:
            unit = "Mbbl/month" if commodity == "oil" else "MMcf/month"
            fc_sub = fc_df[fc_df["commodity"] == commodity]
            if fc_sub.empty: continue
            lines.append(f"  {commodity.upper()} ({unit}):")
            annual_fc = (
                fc_sub.assign(year=fc_sub["period"].dt.year)
                .groupby(["region","year"])["forecast"].sum()
                .reset_index()
            )
            for yr in [selected_year, selected_year+1, selected_year+2]:
                yr_data = annual_fc[annual_fc["year"] == yr]
                if yr_data.empty: continue
                lines.append(f"    {yr}:")
                for _, r in yr_data.sort_values("forecast", ascending=False).iterrows():
                    lines.append(f"      {r['region']}: {float(r['forecast']):,.0f}")
    lines.append("")

    return "\n".join(lines)


# ── System prompt ──────────────────────────────────────────────────────────────

def build_system_prompt(data_context: str, selected_year: int) -> str:
    return f"""You are OilPulse Analyst, an expert energy investment analyst embedded in the OilPulse dashboard.

Your job is to answer questions about U.S. oil and gas production data grounded in LIVE data from our Supabase database.

RULES:
1. When citing a specific number from the data snapshot below, prefix it with [DATA] — example: [DATA] Permian has an investment score of 78.2/100
2. When making an inference, interpretation, or recommendation not directly in the data, prefix it with [INFERENCE] — example: [INFERENCE] The Permian's declining YoY growth suggests the basin may be approaching peak production
3. Never invent numbers. If the data snapshot doesn't contain a specific figure, say "I don't have that data available."
4. Keep answers concise and focused on investment decisions. Use bullet points for comparisons.
5. For sensitivity questions (e.g. "what if decline rate increases 15%"), do the arithmetic using the data snapshot numbers and clearly label it as [INFERENCE] since you are modifying actual data.
6. Always end with a one-sentence actionable recommendation.

LIVE DATA SNAPSHOT (from Supabase, as of right now):
{data_context}

Today's date: {datetime.now().strftime('%Y-%m-%d')}
Dashboard selected year: {selected_year}
Model: SARIMA(1,1,1)(1,1,0)[12]
Data sources: EIA Petroleum Supply Monthly, EIA Natural Gas Monthly, EIA STEO
"""


# ── Example questions ──────────────────────────────────────────────────────────

EXAMPLE_QUESTIONS = [
    "Which region has the highest projected production for the selected year?",
    "Summarize the investment opportunity in the Permian Basin.",
    "Compare Eagle Ford vs Bakken for investment attractiveness.",
    "Which region has the highest revenue potential and why?",
    "What is the SARIMA forecast accuracy for oil production?",
    "Which regions are declining and should be avoided?",
    "What happens to Permian revenue if WTI drops to $55/bbl?",
    "Rank all 5 regions for a long-term 5-year investment.",
]


# ── Chat interface ─────────────────────────────────────────────────────────────

def render_ai_agent(
    scores_df: pd.DataFrame,
    quarterly_df: pd.DataFrame,
    prod_df: pd.DataFrame,
    fc_df: pd.DataFrame,
    rig_df: pd.DataFrame,
    val_df: pd.DataFrame,
    selected_year: int,
    selected_region: str | None = None,
) -> None:
    """
    Render the conversational AI agent panel.
    """
    st.markdown('<div class="section-header">🤖 OilPulse AI Analyst</div>', unsafe_allow_html=True)

    # Check OpenAI key
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key or openai_key == "your_openai_api_key_here":
        st.warning(
            "⚠️ OpenAI API key not configured. "
            "Set OPENAI_API_KEY in your .env file or Streamlit secrets to enable the AI agent.",
            icon="⚠️"
        )
        st.info(
            "**To enable:** Add `OPENAI_API_KEY = 'sk-...'` to your `.env` file, "
            "then restart the dashboard.",
            icon="💡"
        )
        _render_demo_mode(scores_df, selected_year)
        return

    # Build live data context
    data_context = build_data_context(
        scores_df, quarterly_df, prod_df, fc_df, rig_df, val_df, selected_year
    )
    system_prompt = build_system_prompt(data_context, selected_year)

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Auto-populate question if region was clicked on map
    if selected_region and selected_region != "All Regions":
        prefill = f"Summarize the investment opportunity in the {selected_region} Basin."
    else:
        prefill = ""

    # Example question buttons
    st.markdown("**💡 Try these questions:**")
    q_cols = st.columns(4)
    for i, q in enumerate(EXAMPLE_QUESTIONS[:4]):
        if q_cols[i].button(q[:45] + "...", key=f"eq_{i}", use_container_width=True):
            st.session_state["pending_question"] = q

    # Chat input
    user_input = st.chat_input(
        placeholder="Ask about regional data, forecasts, or investment decisions...",
    )

    # Handle pending question from example buttons
    if "pending_question" in st.session_state:
        user_input = st.session_state.pop("pending_question")

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Process new message
    if user_input:
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Call OpenAI
        with st.chat_message("assistant"):
            with st.spinner("Analyzing live data ..."):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)

                    messages = [{"role": "system", "content": system_prompt}]
                    # Add last 6 messages of history (3 turns) for context
                    for h in st.session_state.chat_history[-6:]:
                        messages.append({"role": h["role"], "content": h["content"]})

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0.3,   # low temp = more factual
                        max_tokens=800,
                    )
                    answer = response.choices[0].message.content

                    # Color-code [DATA] and [INFERENCE] labels
                    answer_html = answer.replace(
                        "[DATA]", '<span style="background:rgba(1,181,116,0.15);color:#01B574;padding:2px 6px;border-radius:6px;font-size:0.78em;font-weight:700;border:1px solid rgba(1,181,116,0.3)">DATA</span>'
                    ).replace(
                        "[INFERENCE]", '<span style="background:rgba(255,181,71,0.12);color:#FFB547;padding:2px 6px;border-radius:6px;font-size:0.78em;font-weight:700;border:1px solid rgba(255,181,71,0.3)">INFERENCE</span>'
                    )

                    st.markdown(answer_html, unsafe_allow_html=True)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})

                except ImportError:
                    st.error("OpenAI package not installed. Run: `pip install openai`")
                except Exception as e:
                    st.error(f"AI agent error: {e}")

    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()

    # Data context expander for transparency
    with st.expander("🔍 View live data context sent to AI (transparency)"):
        st.text(data_context)
        st.caption(
            "This is the exact data snapshot injected into the AI system prompt. "
            "All [DATA] claims in answers are grounded in these numbers."
        )


def _render_demo_mode(scores_df: pd.DataFrame, selected_year: int) -> None:
    """Show a demo of what the AI would answer without the API key."""
    st.markdown("**Demo — example of what the AI agent answers:**")

    if not scores_df.empty:
        top = scores_df.sort_values("score", ascending=False).iloc[0]
        region = top["region"]
        score  = float(top.get("score", 0) or 0)
        rev    = float(top.get("revenue_potential", 0) or 0)
        yoy    = float(top.get("yoy_growth", 0) or 0)

        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                    border-radius:10px;padding:1.2rem;color:#94A3B8;">
            <b style="color:#F1F5F9">Question:</b> Which region has the highest investment score for {selected_year}?<br><br>
            <b style="color:#F1F5F9">Answer:</b><br>
            <span style="background:rgba(1,181,116,0.15);color:#01B574;padding:2px 6px;border-radius:6px;font-size:0.78em;font-weight:700;border:1px solid rgba(1,181,116,0.3)">DATA</span>
            <b style="color:#F1F5F9">{region}</b> leads with an investment score of <b style="color:#F1F5F9">{score:.1f}/100</b>,
            a revenue potential of <b style="color:#F1F5F9">${rev:,.0f}M</b>, and a YoY growth rate of <b style="color:#F1F5F9">{yoy:+.1f}%</b>.
            <br><br>
            <span style="background:rgba(255,181,71,0.12);color:#FFB547;padding:2px 6px;border-radius:6px;font-size:0.78em;font-weight:700;border:1px solid rgba(255,181,71,0.3)">INFERENCE</span>
            The combination of high revenue potential and strong consistency score suggests
            {region} remains the primary target for capital deployment in {selected_year}.
            <br><br>
            <b style="color:#F1F5F9">Recommendation:</b> Prioritize {region} for core position sizing given its top-ranked
            composite score and revenue leadership.
        </div>
        """, unsafe_allow_html=True)
