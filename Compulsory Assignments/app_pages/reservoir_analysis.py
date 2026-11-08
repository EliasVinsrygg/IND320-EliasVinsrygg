"""Showing STL and spectrogram analyses for the shared selected region."""

import matplotlib.pyplot as plt
import streamlit as st

from modules.data_loader import load_reservoir_data
from modules.reservoir_analysis import reservoir_spectrogram, reservoir_stl


st.header("Reservoir analysis")

# Selecting the same region as the chart and converting filling ratios to percent.
region = st.session_state["selected_region"]
area_type = "EL" if region.startswith("NO") else "VASS"
data = load_reservoir_data()
filling = (data.loc[
    (data["area_type"] == area_type) & (data["area_number"] == int(region[-1]))
].set_index("date")["fill_level_ratio"].sort_index() * 100).rename("Filling (%)")
if filling.empty:
    st.warning("No reservoir observations are available for this region.")
    st.stop()
st.caption(f"{region}: {filling.index.min():%Y-%m-%d} to {filling.index.max():%Y-%m-%d} "
           f"— all available history, {len(filling)} weekly observations.")

# Separating the two analyses while sharing the same weekly series and cached figures.
stl_tab, spectrogram_tab = st.tabs(["STL", "Spectrogram"])
with stl_tab:
    # Explaining how each setting changes the analysis, using built-in help icons.
    seasonal = st.number_input("Seasonal smoother (annual cycles)", min_value=3, value=7, step=2,
        help="Controls how much the repeating yearly pattern can change from year to year. "
             "Higher values make this pattern more stable; lower values let it change more. Use an odd number.")
    trend = st.number_input("Trend smoother (weeks)", min_value=53, value=101, step=2,
        help="Controls how smooth the long-term development in filling level looks. Higher values show "
             "broader, slower changes; lower values follow shorter changes more closely. Use an odd number.")
    robust = st.checkbox("Robust fitting", value=True,
        help="When enabled, unusual observations have less influence on the estimated trend and yearly "
             "pattern. The observations are kept; their departures can appear in the residual panel.")
    st.caption("The annual period is approximated by 52 weeks; week 53 is retained. "
               "Observed and trend: %. Seasonal and residual: percentage points.")
    # Displaying validation errors without interrupting the other analysis.
    try:
        fig = reservoir_stl(filling, seasonal, trend, robust)
        st.pyplot(fig)
        plt.close(fig)
    except ValueError as error:
        st.warning(str(error))

with spectrogram_tab:
    # Explaining the trade-off between distinguishing cycles and locating changes in time.
    window_length = st.number_input("Window length (weeks)", min_value=2, value=260, step=1,
        help="The number of weeks analysed together at each position in the chart. Longer windows "
             "distinguish repeating cycles better, but make the timing of changes less precise. "
             "260 weeks is about five years.")
    window_overlap = st.number_input("Window overlap (weeks)", min_value=0, value=208, step=1,
        help="The number of weeks shared by neighbouring windows. Higher overlap places calculations "
             "closer together in time, without improving the frequency detail of each window. "
             "With length 260 and overlap 208, the window moves forward 52 weeks. Overlap must be smaller than length.")
    st.caption("Overlap must be smaller than the window. An annual cycle is at 1/52 ≈ 0.0192 "
               "cycles/week. Brighter colours indicate stronger oscillations.")
    # Rendering the notebook spectrogram and releasing the displayed figure.
    try:
        fig = reservoir_spectrogram(filling, window_length, window_overlap)
        st.pyplot(fig)
        plt.close(fig)
    except ValueError as error:
        st.warning(str(error))
