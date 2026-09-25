"""Front page content for the IND320 reservoir statistics app."""

import streamlit as st

from modules.data_loader import load_reservoir_data


st.header("IND320: Reservoir statistics")
st.markdown(
    "Explore weekly Norwegian reservoir statistics and compare the national "
    "series with electricity price areas and watercourse areas."
)

# Reuse the cached loader so the overview always matches the local app data.
reservoir_data = load_reservoir_data()
first_observation = reservoir_data["date"].min()
last_observation = reservoir_data["date"].max()
area_types = ", ".join(sorted(reservoir_data["area_type"].unique()))

st.subheader("Dataset at a glance")
with st.container(horizontal=True):
    st.metric("Observations", f"{len(reservoir_data):,}")
    st.metric(
        "Period",
        f"{first_observation:%b %Y}–{last_observation:%b %Y}",
    )
    st.metric("Area types", area_types)

st.subheader("Explore the app")
st.markdown(
    """
- **Data table:** Review every imported column and the first month of national data.
- **Interactive chart:** Explore the national series and regional alternatives with a dynamic chart.
- **Project information:** Read about the data and the main presentation choices.
"""
)
