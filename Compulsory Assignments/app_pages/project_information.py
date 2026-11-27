"""Summarising sources and methods for the app's current coursework."""

import streamlit as st


st.header("Project information")
# Summarising the sources and methods used across the four coursework assignments.
st.write("This app brings together the four IND320 compulsory assignments.")
st.markdown("""Course material used to create the app:
- **[Data to Decision jupyter book by khliland](https://khliland.github.io/IND320/)**
""")
st.markdown("""Data sources in the app:
- **NVE Magasinstatistikk:** weekly reservoir data, STL and spectrograms.
- **Open-Meteo ERA5:** regional weather means from 100 points; DCT/SPC and LOF analysis. Historical years can be downloaded after confirmation and saved in MongoDB.
- **ENTSO-E:** country-level electricity transfers for 2024–2025 and weekly flows between NO3 and its neighbouring price areas.
- **Norges Bank:** EUR/NOK and USD/NOK exchange rates for the NO3 forecast.
""")
st.write("Forecast uses River to predict NO3 reservoir filling. The shaded band is estimated from past forecast errors.")
st.caption("Statistical flags indicate unusual values, not confirmed data errors.")
st.markdown("[GitHub repository](https://github.com/EliasVinsrygg/IND320-EliasVinsrygg)")
