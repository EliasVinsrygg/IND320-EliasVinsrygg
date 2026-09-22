"""Load and prepare the local reservoir CSV for the Streamlit app."""

from pathlib import Path

import pandas as pd
import streamlit as st


# Keep the English names used in the notebook and Streamlit app in one place.
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

COLUMN_DESCRIPTIONS = {
    "date": "Observation date",
    "area_type": "Geographical aggregation type",
    "area_number": "Area identifier",
    "iso_year": "ISO calendar year",
    "iso_week": "ISO calendar week number",
    "fill_level_ratio": "Reservoir fill level (ratio)",
    "capacity_twh": "Reservoir capacity (TWh)",
    "stored_energy_twh": "Stored energy (TWh)",
    "next_publication_date": "Next planned publication date",
    "previous_week_fill_level_ratio": "Previous-week fill level (ratio)",
    "weekly_fill_level_change": "Weekly fill-level change (ratio)",
}

# Only these columns describe measured quantities suitable for line sparklines.
MEASUREMENT_COLUMNS = {
    "fill_level_ratio",
    "capacity_twh",
    "stored_energy_twh",
    "previous_week_fill_level_ratio",
    "weekly_fill_level_change",
}

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "reservoirs.csv"


@st.cache_data
def load_reservoir_data() -> pd.DataFrame:
    """Read the local CSV once per cache and return an English analysis version."""
    data = pd.read_csv(DATA_PATH).rename(columns=COLUMN_NAMES)
    data["date"] = pd.to_datetime(data["date"])

    return data.sort_values(["date", "area_type", "area_number"]).reset_index(
        drop=True
    )


def build_column_summary(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Period]:
    """Create one table row per imported column with January 1995 sparklines."""
    national_data = data.loc[
        (data["area_type"] == "NO") & (data["area_number"] == 0)
    ].copy()

    if national_data.empty:
        raise ValueError("The national reservoir series (NO-0) is missing from the data.")

    first_month = national_data["date"].min().to_period("M")
    first_month_data = national_data.loc[
        national_data["date"].dt.to_period("M") == first_month
    ]

    summary_rows = []
    for column in data.columns:
        # Chart columns require lists of numbers. Metadata remains visible but blank.
        if column in MEASUREMENT_COLUMNS:
            sparkline_values = first_month_data[column].astype(float).tolist()
            chart_note = "First-month measurement series"
        else:
            sparkline_values = []
            chart_note = "Metadata: no numeric measurement series"

        summary_rows.append(
            {
                "Column": column,
                "Description": COLUMN_DESCRIPTIONS[column],
                "First month series": sparkline_values,
                "Chart note": chart_note,
            }
        )

    return pd.DataFrame(summary_rows), first_month
