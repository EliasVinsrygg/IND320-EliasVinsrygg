"""Reuse the reservoir analysis controls across the analysis views."""

from requests import RequestException
import streamlit as st

from modules.reservoir_loader import load_reservoir_data
from modules.reservoir_analysis import reservoir_spectrogram, reservoir_stl


def filling_for_view(region):
    """Load the weekly filling series and show its coverage."""
    # Selecting the same region as the chart and converting filling ratios to percent.
    area_type = "EL" if region.startswith("NO") else "VASS"
    try:
        data = load_reservoir_data()
    except (RequestException, ValueError):
        st.warning("Reservoir observations could not be loaded from NVE.")
        return None
    filling = (data.loc[
        (data["area_type"] == area_type) & (data["area_number"] == int(region[-1]))
    ].set_index("date")["fill_level_ratio"].sort_index() * 100).rename("Filling (%)")
    if filling.empty:
        st.warning("No reservoir observations are available for this region.")
        return None
    st.caption(f"{region}: {filling.index.min():%Y-%m-%d} to {filling.index.max():%Y-%m-%d} "
               f"— all available history, {len(filling)} weekly observations.")
    return filling


def show_filling_stl(filling):
    """Show the seasonal and trend decomposition with the existing controls."""
    # Explaining how each setting changes the analysis, using built-in help icons.
    seasonal = st.number_input("Seasonal smoother (annual cycles)", min_value=3, value=7, step=2,
        key="stl_seasonal", persist_state="page",
        help="Controls how much the repeating yearly pattern can change from year to year. "
             "Higher values make this pattern more stable; lower values let it change more. Use an odd number.")
    trend = st.number_input("Trend smoother (weeks)", min_value=53, value=101, step=2,
        key="stl_trend", persist_state="page",
        help="Controls how smooth the long-term development in filling level looks. Higher values show "
             "broader, slower changes; lower values follow shorter changes more closely. Use an odd number.")
    robust = st.checkbox("Robust fitting", value=True, key="stl_robust", persist_state="page",
        help="When enabled, unusual observations have less influence on the estimated trend and yearly "
             "pattern. The observations are kept; their departures can appear in the residual panel.")
    st.caption("The annual period is approximated by 52 weeks; week 53 is retained. "
               "Observed and trend: %. Seasonal and residual: percentage points.")
    # Displaying validation errors without interrupting the other analysis.
    try:
        fig = reservoir_stl(filling, seasonal, trend, robust)
        st.plotly_chart(fig, width="stretch", key="filling_stl")
    except ValueError as error:
        st.warning(str(error))


def show_filling_spectrogram(filling):
    """Show the time-frequency chart and its window controls."""
    # Explaining the trade-off between distinguishing cycles and locating changes in time.
    window_length = st.number_input("Window length (weeks)", min_value=3, value=260, step=1,
        key="spectrogram_window", persist_state="page",
        help="The number of weeks analysed together at each position in the chart. Longer windows "
             "distinguish repeating cycles better, but make the timing of changes less precise. "
             "260 weeks is about five years.")
    window_overlap = st.number_input("Window overlap (weeks)", min_value=0, value=208, step=1,
        key="spectrogram_overlap", persist_state="page",
        help="The number of weeks shared by neighbouring windows. Higher overlap places calculations "
             "closer together in time, without improving the frequency detail of each window. "
             "With length 260 and overlap 208, the window moves forward 52 weeks. Overlap must be smaller than length.")
    st.caption("Overlap must be smaller than the window. An annual cycle is at 1/52 ≈ 0.0192 "
               "cycles/week. Brighter colours indicate stronger oscillations.")
    # Displaying the spectrogram with hover values for window, frequency and power.
    try:
        fig = reservoir_spectrogram(filling, window_length, window_overlap)
        st.plotly_chart(fig, width="stretch", key="filling_spectrogram")
    except ValueError as error:
        st.warning(str(error))
