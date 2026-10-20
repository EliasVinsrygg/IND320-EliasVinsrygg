"""Explain the sources and presentation choices of the IND320 app."""

import streamlit as st


st.header("Project information")
# Explain where the two datasets come from and how the app presents them.
st.markdown(
    "This app brings together work from **IND320 Compulsory Assignments 1 and 2**. "
    "It explores Norwegian reservoir statistics and physical electricity flows "
    "across Norway's country borders."
)

st.subheader("Data sources")
st.markdown(
    """
- **Reservoir statistics:** The app fetches weekly observations directly from NVE's Magasinstatistikk API. The response is cached for one hour.
- **Cross-border flows:** The CA2 notebook retrieves ENTSO-E [Physical Flows (12.1.G)](https://transparency.entsoe.eu/transmission/physicalFlows) for Norway and six foreign countries. It stores the API data in Cassandra with Spark, extracts the plotting fields with Spark, and saves monthly documents in MongoDB. The app reads those saved documents; it does not request ENTSO-E data on each visit.
"""
)

st.subheader("Presentation choices")
st.markdown(
    """
- **Reservoir pages:** Norway (NO-0) is the national reference. Electricity price areas (EL) and watercourse areas (VASS) are alternative regional views and are not added together. The data table shows column descriptions, national trends from the latest year, and a paginated preview. The interactive chart stacks regional capacity and stored energy; fill levels and weekly changes remain separate lines.
- **Cross-border page:** A connection is a country pair, not an individual cable. The pie chart compares full-year import and export energy for 2024 or 2025 in TWh. The line chart shows average power in MW for selected months, with UTC timestamps. These are transfers, not electricity production.
"""
)

st.subheader("Project link")
st.markdown(
    "[View the public GitHub repository]"
    "(https://github.com/EliasVinsrygg/IND320-EliasVinsrygg)"
)
