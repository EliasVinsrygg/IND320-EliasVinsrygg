"""Showing precipitation SPC and temperature LOF for saved regional weather."""

from datetime import date
import math

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from pymongo.errors import PyMongoError

from modules.weather_analysis import precipitation_spc, temperature_lof
from modules.weather_download import download_status, download_weather, weather_request
from modules.weather_loader import WeatherDataMissing, load_weather_data


def close_weather_dialog():
    """Remembering cancellation or dismissal across full-page reruns."""
    st.session_state["weather_dialog_open"] = False


@st.dialog("Weather data not downloaded", on_dismiss=close_weather_dialog)
def confirm_weather_download(region, year):
    """Showing costs and shared availability before any new API request is allowed."""
    st.write(f"Weather data for **{region}, {year}** have not been fully downloaded in advance.")
    # Allowing cancellation even when the quota-status database cannot be reached.
    if st.button("Cancel", key="cancel_weather_download"):
        close_weather_dialog()
        st.rerun()
    try:
        settings = weather_request(region, year)
        status = download_status()
    except (ValueError, PyMongoError):
        st.error("Download availability could not be checked. Please try again later.")
        return
    cached = settings["cache_path"].is_file()
    if cached:
        st.info("A local response can be reused. No new API request or quota slot is needed.")
    else:
        # Explaining the supplied API-call estimate, including the extra day in leap years.
        calls = len(settings["hours"]) / 24 / 14 * 100 * 2 / 10
        st.write(f"100 points, {len(settings['hours']):,} UTC hours, temperature and precipitation. "
                 f"One HTTP request, approximately **{calls:.1f} weighted API calls**.")
        if status["wait_seconds"]:
            st.info(f"{status['reason']}. Check again in approximately {status['wait_seconds']} seconds.")
        else:
            st.success("Ready to start now.")
    estimate_source = "based on the last completed download" if status["measured_estimate"] else "initial estimate"
    st.caption(f"Processing estimate: about {math.ceil(status['estimated_seconds'] / 60)} minute(s), "
               f"{estimate_source}. Actual time varies.")
    st.caption("Shared limits: 90 seconds between downloads, a one-hour pause after the ninth "
               "request within an hour, and at most 19 requests per rolling 24 hours. Failed attempts also count.")
    # Rerunning the dialog on demand to update availability without automatically starting work.
    st.button("Check availability", key="check_weather_download")
    if st.button("Download", key="confirm_weather_download", type="primary",
                 disabled=bool(status["wait_seconds"]) and not cached):
        with st.status("Preparing weather data...", expanded=True) as progress:
            try:
                download_weather(region, year, progress=progress.write)
            except (ValueError, OSError) as error:
                progress.update(label="Download stopped", state="error")
                st.error(str(error))
                return
            progress.update(label="Weather data saved", state="complete")
        close_weather_dialog()
        st.rerun()


st.header("Weather analysis")
region = st.session_state["selected_region"]
year = st.selectbox("Year", range(1940, date.today().year), index=2024 - 1940,
    help="Chooses a complete year from 1940 onwards. Missing data can be downloaded after confirmation.")

# Opening a missing-data prompt once per selection; cancellation leaves a manual request button.
if st.session_state.get("weather_selection") != (region, year):
    st.session_state["weather_selection"] = (region, year)
    st.session_state["weather_prompted"] = False
    st.session_state["weather_dialog_open"] = False

# Reading saved means only; refreshing never starts a weather download.
if st.button("Refresh saved data", help="Checks MongoDB again for completed data. No weather data are downloaded."):
    load_weather_data.clear(region, year)
try:
    weather = load_weather_data(region, year)
except WeatherDataMissing as error:
    st.info(str(error))
    request_download = st.button("Request missing weather data")
    if request_download or not st.session_state["weather_prompted"]:
        st.session_state["weather_prompted"] = True
        st.session_state["weather_dialog_open"] = True
    if st.session_state["weather_dialog_open"]:
        confirm_weather_download(region, year)
    st.stop()
except ValueError as error:
    st.warning(str(error))
    st.stop()
st.caption(f"{region} · {year} · ERA5 · {len(weather)} UTC hours · means of 100 sampled points.")

# Comparing both hourly series on one timeline, using separate axes for their different units.
overview = make_subplots(specs=[[{"secondary_y": True}]])
overview.add_trace(go.Scatter(x=weather["time"], y=weather["temperature_2m"],
    name="Temperature", line={"color": "#d95f02", "width": 1}), secondary_y=False)
overview.add_trace(go.Scatter(x=weather["time"], y=weather["precipitation"],
    name="Precipitation", line={"color": "#1f77b4", "width": 1}), secondary_y=True)
overview.update_yaxes(title_text="Temperature (°C)", secondary_y=False)
overview.update_yaxes(title_text="Precipitation (mm/hour)", rangemode="tozero", secondary_y=True)
overview.update_layout(xaxis_title="Time (UTC)", hovermode="x unified", height=350,
                       legend={"orientation": "h"}, margin={"t": 20})
st.plotly_chart(overview, width="stretch")
st.caption("Temperature uses the left axis; precipitation uses the right axis.")
st.caption("Highlighted observations are statistical flags, not confirmed data errors.")

# Sharing the same complete regional series between both analyses.
spc_tab, lof_tab = st.tabs(["Precipitation outliers", "Temperature anomaly"])
with spc_tab:
    # Expressing the filter boundary as a period in days for a more intuitive control.
    period_days = st.number_input("Period cutoff (days)", min_value=1, value=30, step=1,
        help="With 30 days, variations with periods longer than about 30 days are removed before "
             "checking for unusual precipitation. Lower values focus on faster changes; higher values "
             "also retain slower variations in the signal used to detect outliers.")
    n_std = st.number_input("SPC limit width", min_value=0.1, value=3.0, step=0.5,
        help="Sets how many robust standard deviations the limits extend above and below the baseline. "
             "Higher values give wider limits and flag fewer hours; lower values flag more.")
    # Converting days to cycles/day, then showing original precipitation and shifted limits.
    try:
        fig, outliers, summary = precipitation_spc(weather, cutoff=1 / period_days, n_std=n_std)
        st.pyplot(fig)
        plt.close(fig)
        with st.container(horizontal=True):
            st.metric("Hours", int(summary["hours"]))
            st.metric("Flagged hours", int(summary["outlier_hours"]))
            st.metric("Flagged (%)", f"{summary['outlier_percent']:.2f}")
        st.caption(f"Robust residual spread: {summary['robust_sigma_mm']:.4f} mm. "
                   "Limits use robust statistics from the whole selected year.")
        st.dataframe(outliers.rename_axis("Time (UTC)").reset_index(), hide_index=True)
    except ValueError as error:
        st.warning(str(error))

with lof_tab:
    anomaly_percent = st.number_input("Expected anomalies (%)", min_value=0.1, max_value=50.0,
        value=1.0, step=0.1,
        help="The percentage of hours the method aims to flag as unusual. The default 1% means about "
             "one in every 100 hours. Increasing it generally flags more hours; it is not the probability "
             "that a measurement is wrong.")
    st.caption("LOF compares each temperature with 20 similar temperatures across the year. "
               "It does not use neighbouring times or seasonal context. Higher LOF scores mean more unusual values.")
    # Converting the percentage control to the notebook's fraction and showing ranked anomalies.
    try:
        fig, outliers, summary = temperature_lof(weather, anomaly_percent / 100)
        st.pyplot(fig)
        plt.close(fig)
        with st.container(horizontal=True):
            st.metric("Hours", int(summary["hours"]))
            st.metric("Flagged hours", int(summary["outlier_hours"]))
            st.metric("Flagged (%)", f"{summary['outlier_percent']:.2f}")
        st.dataframe(outliers.rename_axis("Time (UTC)").reset_index(), hide_index=True)
    except ValueError as error:
        st.warning(str(error))
