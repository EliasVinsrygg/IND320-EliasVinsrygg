"""Read complete weekly regional weather values for the reservoir map."""
import numpy as np
import pandas as pd
import streamlit as st

from modules.database import get_mongo_client


@st.cache_data(ttl=600, max_entries=4)
def latest_map_weather_week(regions, last_week):
    """Find the latest prepared week shared by every displayed region."""
    collection = get_mongo_client()["ind320_ca4"]["map_weather_weekly"]
    # Checking coverage on the server so one query is enough for the whole layer.
    rows = collection.aggregate([
        {"$match": {"region": {"$in": list(regions)}, "date": {"$lte": str(last_week.date())}}},
        {"$group": {"_id": "$date", "regions": {"$addToSet": "$region"}}},
        {"$match": {"regions": {"$size": len(regions)}}},
        {"$sort": {"_id": -1}}, {"$limit": 1},
    ])
    latest = next(rows, None)
    return pd.Timestamp(latest["_id"]) if latest else None


@st.cache_data(ttl=600, max_entries=100)
def map_weather(week, regions, variable):
    """Aggregate stored regional observations over the Oslo Monday-Sunday week."""
    # Shifting the precipitation timestamps because each value covers the preceding hour.
    start = (week - pd.Timedelta(days=6)).tz_localize("Europe/Oslo").tz_convert("UTC")
    end = (week + pd.Timedelta(days=1)).tz_localize("Europe/Oslo").tz_convert("UTC")
    hours = pd.date_range(start, end, freq="h", inclusive="left")
    if variable == "precipitation":
        hours += pd.Timedelta(hours=1)
    client = get_mongo_client()
    values = pd.Series(np.nan, index=regions, dtype=float)
    # Reading completed regional weeks before falling back to the historical hourly series.
    column = "temperature_c" if variable == "temperature_2m" else "precipitation_mm"
    documents = client["ind320_ca4"]["map_weather_weekly"].find(
        {"date": str(week.date()), "region": {"$in": list(regions)}}, {"region": 1, column: 1})
    for doc in documents:
        values[doc["region"]] = doc[column]
    if values.notna().all():
        return values
    # Reusing the verified weekly NO3 series, including the recent CA4 updates.
    if "NO3" in regions and pd.isna(values["NO3"]):
        doc = client["ind320_ca4"]["no3_weekly"].find_one({"_id": f"NO3:{week.date()}"}, {column: 1})
        if doc and doc.get(column) is not None:
            values["NO3"] = doc[column]
    query = {"region": {"$in": values.index[values.isna()].tolist()}, "model": "era5",
             "sample_size": 100, "sample_seed": 42, "time": {"$gte": hours[0].to_pydatetime(),
             "$lte": hours[-1].to_pydatetime()}}
    fields = dict.fromkeys(["time", "region", "sample_id", "units", "timezone", variable], 1)
    rows = pd.DataFrame(client["ind320_ca3"]["weather_hourly"].find(query, fields))
    if not rows.empty:
        for region, group in rows.groupby("region"):
            group = group.sort_values("time")
            # Requiring one sample, matching units and every expected hour, including DST weeks.
            unit = "mm" if variable == "precipitation" else "\u00b0C"
            if (pd.DatetimeIndex(pd.to_datetime(group.time, utc=True)).equals(hours)
                    and group.sample_id.notna().all() and group.sample_id.nunique() == 1
                    and group.timezone.eq("UTC").all() and group.units.map(lambda u: u.get(variable) == unit).all()
                    and np.isfinite(group[variable].to_numpy(dtype=float)).all()):
                values[region] = group[variable].mean() if variable == "temperature_2m" else group[variable].sum()
    return values
