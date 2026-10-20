"""Front page for the IND320 energy data app."""

import streamlit as st

from modules.data_loader import load_reservoir_data


st.header("IND320: Norwegian energy data")
st.markdown(
    "Explore Norwegian reservoir statistics and physical electricity flows "
    "between Norway and neighbouring countries."
)

# The shared loader keeps the NVE response for one hour between page visits.
reservoir_data = load_reservoir_data()
# Show the coverage of the data currently held in that cache.
first_observation = reservoir_data["date"].min()
last_observation = reservoir_data["date"].max()
area_types = ", ".join(sorted(reservoir_data["area_type"].unique()))

st.subheader("Reservoir data at a glance")
with st.container(horizontal=True):
    st.metric("Weekly area observations", f"{len(reservoir_data):,}")
    st.metric(
        "Period",
        f"{first_observation:%b %Y} to {last_observation:%b %Y}",
    )
    st.metric("Area types", area_types)

st.subheader("Explore the app")
st.markdown(
    """
- **Data table:** Read column descriptions, see trends from the latest year, and browse a few rows at a time.
- **Interactive chart:** Choose reservoir measurements, a period, and national or regional views.
- **Cross-border flows:** Compare annual import and export energy with monthly power lines for a selected country.
- **Project information:** Read about the sources, units, and presentation choices.
"""
)
