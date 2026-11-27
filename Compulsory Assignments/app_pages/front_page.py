"""Open the main IND320 views from a single landing page."""

from pathlib import Path

import streamlit as st


st.set_page_config(layout="wide")
st.title("IND320 Energy and Weather")
st.write("Explore Norwegian reservoirs, regional weather and electricity flows. "
         "Investigate patterns in the data and see the latest reservoir forecast for NO3.")

# Showing local previews of the actual figures alongside navigation to each tool.
assets = Path(__file__).resolve().parents[1] / "assets/home"
# Extending each native page link across its card, including the image.
st.html(assets / "cards.css")
views = (
    ("Explore", "reservoir_map", "explore.png", ":material/map:",
     "Compare reservoir levels and electricity flows on the map."),
    ("Analyse", "analyse", "analyse.png", ":material/analytics:",
     "Investigate seasonal patterns and unusual weather."),
    ("Forecast", "forecast", "forecast.png", ":material/trending_up:",
     "See the weekly outlook for reservoir filling in NO3."),
)
for column, (label, page, preview, icon, description) in zip(st.columns(3, gap="medium"), views):
    with column.container(border=True, key=f"home_card_{page}"):
        st.image(assets / preview, width="stretch")
        st.page_link(f"app_pages/{page}.py", label=label, icon=icon, width="stretch")
        st.caption(description)

st.page_link("app_pages/project_information.py", label="Project information", icon=":material/info:")
