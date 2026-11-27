"""Main entrypoint and navigation for the IND320 Streamlit app."""

import streamlit as st


# Configure shared browser settings before any page content is displayed.
st.set_page_config(
    page_title="IND320 Energy and Weather",
    page_icon=":material/water_drop:",
)

# Listing the five destinations in a single menu, with Home opening first.
pages = [
    st.Page("app_pages/front_page.py", title="Home", icon=":material/home:"),
    st.Page("app_pages/reservoir_map.py", title="Explore", icon=":material/map:"),
    st.Page("app_pages/analyse.py", title="Analyse", icon=":material/analytics:"),
    st.Page("app_pages/forecast.py", title="Forecast", icon=":material/trending_up:"),
    st.Page("app_pages/project_information.py", title="Project information", icon=":material/info:"),
]

st.navigation(pages, position="sidebar").run()
