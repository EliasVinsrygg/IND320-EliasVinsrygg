"""Load prepared NO3 observations from MongoDB and cache forecast results."""

import pandas as pd
import streamlit as st

from modules.forecasting import EXOGENOUS_LABELS, forecast_quantiles
from modules.database import get_mongo_client


@st.cache_data(max_entries=1, ttl=600)
def load_forecast_data():
    """Read weekly NO3 documents, preserving missing flows as numeric gaps."""
    collection = get_mongo_client()["ind320_ca4"]["no3_weekly"]
    required = ["filling_percent", *EXOGENOUS_LABELS]
    # Reading only the model fields and parsing the local Sunday observation labels.
    fields = dict.fromkeys(["date", *required], 1)
    records = list(collection.find({"region": "NO3"}, {**fields, "_id": 0}).sort("date", 1))
    if not records:
        raise ValueError("No weekly NO3 observations are available.")
    data = pd.DataFrame(records).set_index("date")
    data.index = pd.to_datetime(data.index)
    if (not set(required).issubset(data.columns) or not data.index.is_unique
            or not data.index.is_monotonic_increasing or data.index.hasnans):
        raise ValueError("The prepared NO3 table has invalid columns or dates.")
    return data[required]


@st.cache_data(max_entries=32, show_spinner=False)
def run_calibrated_forecast(data, origin, coverage, settings):
    """Cache the error-based band together with its number of historical forecasts."""
    # Using a separate cache from the earlier band, which had no calibration count.
    result = forecast_quantiles(data, origin, coverage=coverage, **settings)
    return result, result.attrs["calibration_origins"]
