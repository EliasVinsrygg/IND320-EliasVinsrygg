"""Data-table page for the IND320 reservoir statistics app."""

import math

import pandas as pd
import streamlit as st

from modules.data_loader import (
    COLUMN_DESCRIPTIONS,
    MEASUREMENT_COLUMNS,
    load_reservoir_data,
)


st.header("Reservoir data table")
st.write(
    "Explore the column descriptions, recent national measurements, "
    "and a small page of the NVE dataset."
)

# The API response is cached by the loader, so page controls do not download it again.
with st.spinner("Loading NVE reservoir data..."):
    reservoir_data = load_reservoir_data()

# Metadata describes columns; measurements receive numeric trend lists.
metadata = pd.DataFrame([
    {"Column": column, "Description": COLUMN_DESCRIPTIONS[column]}
    for column in reservoir_data.columns if column not in MEASUREMENT_COLUMNS
])
national_data = reservoir_data.loc[
    (reservoir_data["area_type"] == "NO")
    & (reservoir_data["area_number"] == 0)
].sort_values("date")
if national_data.empty:
    raise ValueError("The national reservoir series (NO-0) is missing from the data.")

# Anchor the sparkline window to the latest published national observation.
last_date = national_data["date"].max()
year_start = last_date - pd.DateOffset(years=1)
recent_data = national_data.loc[national_data["date"] >= year_start]
first_date = recent_data["date"].min()
measurements = pd.DataFrame([
    {
        "Column": column,
        "Description": COLUMN_DESCRIPTIONS[column],
        # LineChartColumn expects each cell to contain a list of numbers.
        "Last year": recent_data[column].dropna().astype(float).tolist(),
    }
    for column in MEASUREMENT_COLUMNS
])

st.subheader("Metadata")
st.dataframe(metadata, hide_index=True)

st.subheader("Measured data")
st.caption(
    f"NO-0 weekly observations from {first_date:%d %b %Y} to "
    f"{last_date:%d %b %Y}, the latest year in the dataset."
)
st.dataframe(
    measurements,
    column_config={
        "Last year": st.column_config.LineChartColumn(
            "Last year",
            help="Weekly national values in chronological order.",
            width="medium",
            color="blue",
        ),
    },
    hide_index=True,
)

st.subheader("Dataset preview")
st.caption("Browse pages without sending the whole dataset to the table at once.")
rows_per_page = st.selectbox("Rows per page", options=[20, 50, 100])
page_count = max(1, math.ceil(len(reservoir_data) / rows_per_page))
page = st.number_input("Page", min_value=1, max_value=page_count, value=1)

# Slice only the requested page before sending rows to Streamlit's table.
first_row = (page - 1) * rows_per_page
last_row = min(first_row + rows_per_page, len(reservoir_data))
st.caption(f"Rows {first_row + 1}–{last_row} of {len(reservoir_data):,}")
st.dataframe(
    reservoir_data.iloc[first_row:last_row],
    hide_index=True,
    height=400,
)
