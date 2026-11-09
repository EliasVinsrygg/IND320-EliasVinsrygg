"""Inspecting the three datasets used by the energy and weather app."""

import math
from datetime import date

import pandas as pd
import streamlit as st
from pymongo.errors import PyMongoError

from modules.reservoir_loader import COLUMN_DESCRIPTIONS, MEASUREMENT_COLUMNS, load_reservoir_data
from modules.flow_loader import get_available_flows, get_monthly_flows
from modules.weather_loader import load_weather_data


st.header("Data table")
st.write("Inspect reservoir records, saved regional weather or monthly cross-border flows.")
dataset = st.selectbox("Dataset", ["Reservoir statistics", "Weather data", "Cross-border flows"],
    help="Chooses weekly reservoir records, hourly regional weather means or monthly country-pair energy totals.")

# Reading only the selected dataset, keeping the other sources idle.
if dataset == "Reservoir statistics":
    data = load_reservoir_data()
    st.caption("NVE weekly data. Filling is stored as a ratio; capacity and stored energy are in TWh.")

    # Keeping the existing national sparklines, with one year counted from the latest observation.
    national = data.loc[(data["area_type"] == "NO") & (data["area_number"] == 0)].sort_values("date")
    if not national.empty:
        recent = national.loc[national["date"] >= national["date"].max() - pd.DateOffset(years=1)]
        st.subheader("Recent national measurements")
        st.caption(f"NO-0: {recent['date'].min():%Y-%m-%d} to {recent['date'].max():%Y-%m-%d}.")
        measurements = pd.DataFrame([
            {"Column": column, "Description": COLUMN_DESCRIPTIONS[column],
             "Last year": recent[column].dropna().astype(float).tolist()}
            for column in MEASUREMENT_COLUMNS
        ])
        st.dataframe(measurements, hide_index=True, column_config={
            "Last year": st.column_config.LineChartColumn("Last year", help="Weekly national values.")
        })

elif dataset == "Weather data":
    # Choosing table-specific filters without changing the shared Reservoir section selection.
    region = st.selectbox("Weather region", ["NO1", "NO2", "NO3", "NO4", "NO5", "VASS1", "VASS2", "VASS3"], index=2,
        help="Chooses the region whose hourly average weather is shown in this table.")
    year = st.selectbox("Weather year", range(1940, date.today().year), index=2024 - 1940,
        help="Chooses a complete UTC calendar year. New years can be requested on Weather analysis.")
    try:
        data = load_weather_data(region, year)
    except ValueError as error:
        st.warning(str(error))
        st.stop()
    st.caption(f"{region}/{year}: ERA5 hourly means of 100 sampled points. Times are UTC.")

else:
    # Reading country-pair monthly totals, leaving the large underlying power blocks out of the table.
    try:
        pairs = [(country, year) for country, year in get_available_flows() if year in (2024, 2025)]
        if not pairs:
            st.warning("No saved complete-year cross-border data are available.")
            st.stop()
        country = st.selectbox("Connection with Norway", sorted({country for country, _ in pairs}),
            help="Chooses a country connected to Norway. Imports enter Norway; exports leave Norway.")
        year = st.selectbox("Flow year", sorted({year for name, year in pairs if name == country}),
            help="Chooses the calendar year for the monthly energy totals.")
        data = pd.DataFrame(get_monthly_flows(country, year))
    except PyMongoError:
        st.warning("Cross-border data could not be read from MongoDB. Please try again later.")
        st.stop()
    if data.empty:
        st.warning("No monthly records are available for this connection and year.")
        st.stop()
    # Converting saved MWh totals to TWh, retaining import and export as separate records.
    data["energy_twh"] = data["energy_mwh"] / 1_000_000
    data = data[["country", "year", "month", "direction", "energy_twh"]]
    st.caption("Monthly country-pair transfers, with import and export shown separately in TWh.")

# Explaining the columns and their units for whichever dataset is selected.
descriptions = {**COLUMN_DESCRIPTIONS,
    "time": "Hour (UTC)", "temperature_2m": "Regional mean temperature (degrees C)",
    "precipitation": "Regional mean hourly precipitation (mm)", "country": "Country connected to Norway",
    "year": "Calendar year", "month": "Calendar month", "direction": "Import to or export from Norway",
    "energy_twh": "Monthly transferred energy (TWh)",
}
with st.expander("Column descriptions"):
    st.dataframe(pd.DataFrame([{"Column": column, "Description": descriptions[column]}
                              for column in data.columns]), hide_index=True)

# Reusing the same small paginated preview for all three datasets.
st.subheader("Dataset preview")
rows_per_page = st.selectbox("Rows per page", [20, 50, 100])
page_count = max(1, math.ceil(len(data) / rows_per_page))
page = st.number_input("Page", min_value=1, max_value=page_count, value=1)
first_row = (page - 1) * rows_per_page
last_row = min(first_row + rows_per_page, len(data))
st.caption(f"Rows {first_row + 1}-{last_row} of {len(data):,}")
st.dataframe(data.iloc[first_row:last_row], hide_index=True, height=400)
