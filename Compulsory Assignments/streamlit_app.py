"""Main entrypoint and navigation for the IND320 Streamlit app."""

import streamlit as st


# Configure shared browser settings before any page content is displayed.
st.set_page_config(
    page_title="IND320 Energy and Weather",
    page_icon=":material/water_drop:",
)

# Retaining the current groups while adding the NO3-only forecast page.
forecast_page = st.Page("app_pages/forecast.py", title="NO3 forecast", icon=":material/trending_up:")
reservoir_pages = [
    st.Page("app_pages/interactive_chart.py", title="Reservoir statistics", icon=":material/analytics:"),
    st.Page("app_pages/reservoir_analysis.py", title="Reservoir analysis", icon=":material/water_drop:"),
    st.Page("app_pages/weather_analysis.py", title="Weather analysis", icon=":material/cloud:"),
    st.Page("app_pages/weather_correlation.py", title="Weather and reservoir correlation", icon=":material/show_chart:"),
    forecast_page,
]
navigation = {
    "": [
        st.Page("app_pages/front_page.py", title="Front Page", icon=":material/home:"),
        st.Page("app_pages/data_table.py", title="Data table", icon=":material/table_chart:"),
    ],
    "Reservoir": [st.Page("app_pages/reservoir_map.py", title="Reservoir map", icon=":material/map:"), *reservoir_pages],
    "Country statistics": [
        st.Page("app_pages/cross_border_flows.py", title="Cross-border flows", icon=":material/swap_horiz:"),
    ],
    "Information": [
        st.Page("app_pages/project_information.py", title="Project information", icon=":material/info:"),
    ],
}
selected_page = st.navigation(navigation, position="hidden")

# Placing the shared selector directly under its Reservoir heading, before the page links.
for group, pages in navigation.items():
    if group:
        st.sidebar.markdown(f"**{group}**")
    if group == "Reservoir" and selected_page in reservoir_pages and selected_page != forecast_page:
        st.sidebar.selectbox(
            "Region", ["NO1", "NO2", "NO3", "NO4", "NO5", "VASS1", "VASS2", "VASS3"],
            index=2, key="selected_region", persist_state="session",
            help="Chooses the region used by Reservoir statistics, Reservoir analysis, Weather analysis and correlation. "
                 "NO1–NO5 are electricity price areas; VASS1–VASS3 are watercourse areas.",
        )
    for page in pages:
        st.sidebar.page_link(page)

# Run the page selected in the sidebar.
selected_page.run()
