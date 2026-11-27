"""Align regional weather and NVE changes on complete calendar weeks."""
import numpy as np
import pandas as pd
import streamlit as st

from modules.database import get_mongo_client
from modules.forecast_loader import load_forecast_data
from modules.reservoir_loader import load_reservoir_data
from modules.weather_download import weather_sample


@st.cache_data(ttl=600, max_entries=8)
def correlation_inputs(region):
    """Read weekly weather and the published weekly change for one matching NVE area."""
    fields = ["temperature_c", "precipitation_mm"]
    db = get_mongo_client()
    if region == "NO3":
        weather = load_forecast_data()[fields]
    else:
        # Combining prepared map weeks with the common historical hourly dataset for 2024-25.
        rows = db["ind320_ca4"]["map_weather_weekly"].find({"region": region},
                    {"_id": 0, "date": 1, **dict.fromkeys(fields, 1)})
        prepared = pd.DataFrame(rows, columns=["date", *fields]).set_index("date")
        prepared.index = pd.to_datetime(prepared.index)
        start, end = pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC")
        query = {"region": region, "sample_id": weather_sample(region)[1],
                 "time": {"$gte": start.to_pydatetime(), "$lt": end.to_pydatetime()}}
        columns = ["time", "temperature_2m", "precipitation"]
        hours = pd.DataFrame(db["ind320_ca3"]["weather_hourly"].find(query,
                             {"_id": 0, **dict.fromkeys(columns, 1)}), columns=columns).set_index("time")
        hours.index = pd.to_datetime(hours.index, utc=True)
        # Requiring every local hour, including the last rain interval ending at Monday midnight.
        clock = pd.date_range("2024-01-01", "2026-01-05", freq="h", tz="Europe/Oslo", inclusive="left")
        temp = hours.temperature_2m.reindex(clock)
        rain = hours.precipitation.reindex(clock + pd.Timedelta(hours=1)).set_axis(clock)
        hourly = pd.DataFrame(dict(temperature_c=temp, precipitation_mm=rain))
        grouped = hourly.groupby(clock.tz_localize(None).to_period("W-SUN").end_time.normalize())
        weekly = grouped.agg({"temperature_c": "mean", "precipitation_mm": "sum"})
        weekly = weekly.where(grouped.count().eq(grouped.size(), axis=0))
        weather = prepared.combine_first(weekly)
    # Using the source change as percentage points and retaining missing calendar weeks.
    data = load_reservoir_data()
    kind = "EL" if region.startswith("NO") else "VASS"
    area = data.loc[data.area_type.eq(kind) & data.area_number.eq(int(region[-1]))]
    change = area.set_index("date").weekly_fill_level_change.mul(100).rename("change_pp")
    return weather.join(change).sort_index().asfreq("W-SUN")


def window_series(data, variable, lag, window):
    """Pair earlier weather with the current change and calculate trailing Pearson correlations."""
    x = data[variable].shift(lag)
    y = data.change_pp
    r = x.rolling(window, min_periods=window).corr(y)
    return pd.DataFrame({"weather": x, "change_pp": y, "r": r.replace([np.inf, -np.inf], np.nan).clip(-1, 1)})
