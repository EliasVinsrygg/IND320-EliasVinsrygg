"""Prepare the most recent common map week from the CA4 forecast data."""
import math
from pathlib import Path
import sys
import time

import pandas as pd

# Resolving the app modules without changing the working directory for Streamlit secrets.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.database import get_mongo_client
from modules.forecast_update import fetch
from modules.weather_download import API_URL, mean_weather, weather_sample


def prepare_map_week():
    """Save one verified document per missing region, reusing existing NO3 data."""
    db = get_mongo_client()["ind320_ca4"]
    regions = ["NO1", "NO2", "NO3", "NO4", "NO5", "VASS1", "VASS2", "VASS3"]
    latest = db.no3_weekly.find_one({"region": "NO3"}, sort=[("date", -1)])
    week = pd.Timestamp(latest["date"])
    start = (week - pd.Timedelta(days=6)).tz_localize("Europe/Oslo").tz_convert("UTC")
    end = (week + pd.Timedelta(days=1)).tz_localize("Europe/Oslo").tz_convert("UTC")
    clock = pd.date_range(start.normalize(), end.normalize() + pd.Timedelta(days=1), freq="h", inclusive="left")
    last_request = None
    for region in regions:
        key = {"_id": f"{region}:{week.date()}"}
        if db.map_weather_weekly.find_one(key):
            continue
        # Reusing the established sample and ERA5 parameters with partial-year dates.
        params, sample_id = weather_sample(region)
        if region == "NO3":
            temperature, rain = latest["temperature_c"], latest["precipitation_mm"]
        else:
            params.update(start_date=str(clock[0].date()), end_date=str(clock[-1].date()))
            if last_request is not None:
                time.sleep(max(0, 20 - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            hourly = mean_weather(fetch("Open-Meteo", API_URL, params).json(), clock)
            # Matching temperature instants and preceding-hour precipitation to the local week.
            temperature = hourly.loc[(hourly.index >= start) & (hourly.index < end), "temperature_2m"].mean()
            rain = hourly.loc[(hourly.index > start) & (hourly.index <= end), "precipitation"].sum()
        if not math.isfinite(temperature) or not math.isfinite(rain) or rain < 0:
            raise ValueError(f"Incomplete weather for {region}")
        db.map_weather_weekly.update_one(key, {"$setOnInsert": {
            "region": region, "date": str(week.date()), "temperature_c": float(temperature),
            "precipitation_mm": float(rain), "model": "era5", "sample_id": sample_id}}, upsert=True)
        print(region, week.date(), round(temperature, 2), round(rain, 2), flush=True)


if __name__ == "__main__":
    prepare_map_week()
