"""Summarising sources and methods for the app's current coursework."""

import streamlit as st


st.header("Project information")
# Summarising actual sources and methods from compulsory assignments 1–3.
st.write("This app is the result of the IND320 compulsory assignments 1–3.")
st.markdown("""Course material used to create the app:
- **[Data to Decision jupyter book by khliland](https://khliland.github.io/IND320/)**
""")
st.markdown("""Data sources in the app:
- **NVE Magasinstatistikk:** weekly reservoir data, STL and spectrograms.
- **Open-Meteo ERA5:** regional weather means from 100 points; DCT/SPC and LOF analysis. Historical years can be downloaded after confirmation and saved in MongoDB.
- **ENTSO-E:** country-level electricity transfers, 2024–2025. Monthly data read from MongoDB.
""")
st.caption("Statistical flags indicate unusual values, not confirmed data errors.")
st.markdown("[GitHub repository](https://github.com/EliasVinsrygg/IND320-EliasVinsrygg)")
