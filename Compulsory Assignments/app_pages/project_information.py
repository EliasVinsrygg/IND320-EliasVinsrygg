"""Project-information page for the IND320 reservoir statistics app."""

import streamlit as st


st.header("Project information")
st.markdown(
    "This Streamlit app is part of **IND320 Compulsory Assignment 1**. "
    "It presents weekly Norwegian reservoir statistics from the course data."
)

st.subheader("Data")
st.markdown(
    """
- The app reads a local copy of the `data/reservoirs.csv` file and caches it for faster reruns.
- Norwegian column names are converted to English after the data is loaded.
- The notebook (delivered in the Compulsory Assignment) reads the original course file directly and does not modify it.
"""
)

st.subheader("Presentation choices")
st.markdown(
    """
- Norway (NO-0) is the national reference series.
- Electricity price areas (EL) and watercourse areas (VASS) are alternative regional views.
- Capacity and stored energy is stacked; fill levels and weekly changes remain separate lines.
"""
)

st.subheader("Project link")
st.markdown(
    "[View the public GitHub repository]"
    "(https://github.com/EliasVinsrygg/IND320-EliasVinsrygg)"
)
