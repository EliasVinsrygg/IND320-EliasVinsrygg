"""Load and prepare NVE reservoir API data for the Streamlit app."""

import pandas as pd
import streamlit as st
import requests


# Translate NVE's field names to the English names used by the notebook and app.
COLUMN_NAMES = {
    "dato_Id": "date",
    "omrType": "area_type",
    "omrnr": "area_number",
    "iso_aar": "iso_year",
    "iso_uke": "iso_week",
    "fyllingsgrad": "fill_level_ratio",
    "kapasitet_TWh": "capacity_twh",
    "fylling_TWh": "stored_energy_twh",
    "neste_Publiseringsdato": "next_publication_date",
    "fyllingsgrad_forrige_uke": "previous_week_fill_level_ratio",
    "endring_fyllingsgrad": "weekly_fill_level_change",
}

# Listing the measurements available in the reservoir detail charts.
MEASUREMENT_COLUMNS = (
    "fill_level_ratio",
    "capacity_twh",
    "stored_energy_twh",
    "previous_week_fill_level_ratio",
    "weekly_fill_level_change",
)

API_URL = (
    "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData"
)


@st.cache_data(ttl="1h")
def load_reservoir_data() -> pd.DataFrame:
    """Download NVE's full dataset, name its columns, and reuse it for one hour."""
    # Check the response before trying to turn it into a table.
    response = requests.get(API_URL, timeout=60)
    response.raise_for_status()
    records = response.json()

    # Each item in the API response should be one observation.
    if not isinstance(records, list) or not records:
        raise ValueError("NVE returned no list of reservoir observations.")

    data = pd.DataFrame(records)

    # Report changed or missing API fields here, before a page tries to plot them.
    missing_columns = set(COLUMN_NAMES) - set(data.columns)
    if missing_columns:
        raise ValueError(f"Missing NVE columns: {sorted(missing_columns)}")

    # Use the same English names as the notebook and make dates sortable.
    data = data.rename(columns=COLUMN_NAMES)
    data["date"] = pd.to_datetime(data["date"], errors="raise")

    # Keep rows in time and area order for tables and plots.
    return data.sort_values(
        ["date", "area_type", "area_number"]
    ).reset_index(drop=True)
