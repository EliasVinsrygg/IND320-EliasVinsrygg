"""Reading prepared hourly regional weather means from MongoDB."""

import numpy as np
import pandas as pd
import streamlit as st
from pymongo.errors import PyMongoError

from modules.mongo_loader import get_mongo_client


class WeatherDataMissing(ValueError):
    """Identifying missing data separately from connection failures and invalid metadata."""


@st.cache_data(ttl=600, max_entries=16)
def load_weather_data(region: str, year: int) -> pd.DataFrame:
    """Return one complete UTC year of 100-point regional means, or raise ValueError."""
    # Reading only the selected region/year, using the app's existing shared client.
    hours = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01",
                          freq="h", inclusive="left", tz="UTC")
    columns = ["time", "temperature_2m", "precipitation", "sample_id", "units", "timezone"]
    query = {"region": region, "model": "era5", "sample_size": 100, "sample_seed": 42,
             "time": {"$gte": hours[0].to_pydatetime(),
                      "$lt": (hours[-1] + pd.Timedelta(hours=1)).to_pydatetime()}}
    try:
        collection = get_mongo_client()["ind320_ca3"]["weather_hourly"]
        documents = list(collection.find(query, {"_id": 0, **dict.fromkeys(columns, 1)}))
    except PyMongoError:
        raise ValueError("Weather data could not be read from MongoDB. Please try again later.") from None
    data = pd.DataFrame(documents, columns=columns)
    if data.empty:
        raise WeatherDataMissing(f"No saved weather data for {region}/{year}.")

    # Rejecting mixed samples instead of treating different spatial averages as one series.
    if data["sample_id"].isna().any() or data["sample_id"].nunique() != 1:
        raise ValueError("Multiple or missing weather samples were found for this region/year.")
    data["time"] = pd.to_datetime(data["time"], utc=True)
    data = data.sort_values("time").reset_index(drop=True)
    if data["time"].duplicated().any():
        raise ValueError("Duplicate weather hours were found; check the saved dataset.")
    if not pd.DatetimeIndex(data["time"]).equals(hours):
        raise WeatherDataMissing(f"Incomplete weather data for {region}/{year}: {len(data)} of {len(hours)} expected hours.")

    # Verifying units and finite numbers before passing complete means to the analyses.
    units = {"temperature_2m": "°C", "precipitation": "mm"}
    if not data["units"].map(lambda value: value == units).all() or not data["timezone"].eq("UTC").all():
        raise ValueError("Unexpected weather units or time zone.")
    values = ["temperature_2m", "precipitation"]
    if not np.isfinite(data[values].to_numpy(dtype=float)).all():
        raise ValueError("Weather data contain missing or non-finite values.")
    weather = data[["time", *values]].copy()
    weather.attrs = {"region": region, "year": year, "sample_size": 100,
                     "sample_id": data["sample_id"].iloc[0], "model": "era5",
                     "timezone": "UTC", "units": units}
    return weather
