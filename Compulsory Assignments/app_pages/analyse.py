"""Combine the regional analysis views on one page."""

import streamlit as st

from modules.correlation_view import show_weather_correlation
from modules.filling_view import filling_for_view, show_filling_spectrogram, show_filling_stl
from modules.region_selection import select_region
from modules.weather_view import show_weather_lof, show_weather_overview, show_weather_satv, weather_for_view


# Giving the time-frequency chart enough room while keeping the selector compact.
st.set_page_config(layout="wide")
st.title("Analyse", icon=":material/analytics:")
region = select_region(st, width=240)

# Loading and computing only the visible analysis for the shared region.
stl, spectrogram, satv, lof, correlation = st.tabs(
    ["Filling STL", "Filling Spectrogram", "Weather SATV", "Weather LOF", "Weather and reservoir correlation"],
    key="analysis_pane", on_change="rerun",
)
if stl.open or spectrogram.open:
    with stl if stl.open else spectrogram:
        filling = filling_for_view(region)
        if filling is not None:
            render_filling = show_filling_stl if stl.open else show_filling_spectrogram
            render_filling(filling)
elif satv.open or lof.open:
    with satv if satv.open else lof:
        weather = weather_for_view(region)
        if weather is not None:
            show_weather_overview(weather)
            render_weather = show_weather_satv if satv.open else show_weather_lof
            render_weather(weather)
elif correlation.open:
    with correlation:
        show_weather_correlation(region)
