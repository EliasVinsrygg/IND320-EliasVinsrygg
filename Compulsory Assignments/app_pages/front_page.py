"""Introducing the IND320 energy and weather app briefly."""

import streamlit as st

# Introducing the datasets and directing visitors to the shared regional controls.
st.header("IND320: Energy and weather")
st.write("Explore Norwegian reservoirs, regional weather and cross-border electricity flows.")
st.markdown("**Reservoir:** statistics, trends, seasonal cycles and unusual weather. "
            "Choose a region within this section.\n\n"
            "**Country statistics:** electricity imports and exports between Norway and its neighbours.")
st.caption("Data table provides dataset previews. Project information lists sources and methods.")
