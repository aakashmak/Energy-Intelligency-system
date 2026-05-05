with tab_map:
    from src.dashboard.map_view import render_map
    clicked = render_map(
        prod_df, scores_df, rig_df,
        selected_year, commodity, selected_regions,
        fc_df        = fc_df,
        quarterly_df = quarterly_df,
    )
    # Sync the button-based region selection to map_selected_region
    # so other tabs (KPIs, AI Analyst) also filter accordingly
    map_btn_region = st.session_state.get("map_active_region")
    if map_btn_region:
        st.session_state["map_selected_region"] = map_btn_region
    else:
        st.session_state["map_selected_region"] = None
