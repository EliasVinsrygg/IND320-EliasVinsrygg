"""Backfill missing 2026 map weeks for the four price areas outside NO3."""
import argparse
import time

import numpy as np
import pandas as pd
from pymongo import UpdateOne

from modules.database import get_mongo_client
from modules.forecast_update import fetch
from modules.weather_download import API_URL, mean_weather, weather_sample, save_hourly_means


def backfill_price_weather(water_areas=False):
    """Download one missing date range per area, pausing between completed requests."""
    db = get_mongo_client()["ind320_ca4"]
    collection = db.map_weather_weekly
    latest = db.no3_weekly.find_one({"region": "NO3"}, sort=[("date", -1)])
    weeks = pd.date_range("2026-01-04", min(latest["date"], "2026-12-31"), freq="W-SUN")
    regions = ("VASS1", "VASS2", "VASS3") if water_areas else ("NO1", "NO2", "NO4", "NO5")
    previous_request = False
    for region in regions:
        # Reading checkpoints so repeated runs preserve all previously verified weeks.
        saved = set(collection.distinct("date", {"region": region, "model": "era5"}))
        missing = [w for w in weeks if str(w.date()) not in saved]
        if water_areas:
            # Backfilling hours even for weeks previously stored only as weekly totals.
            hour_store = get_mongo_client()["ind320_ca3"]["weather_hourly"]
            wanted = pd.date_range(pd.Timestamp("2026-01-01", tz="UTC"), (weeks[-1] + pd.Timedelta(days=1)).tz_localize("Europe/Oslo").tz_convert("UTC"), freq="h", tz="UTC")
            saved_hours = hour_store.distinct("time", {"region": region, "sample_id": weather_sample(region)[1],
                "time": {"$gte": wanted[0].to_pydatetime(), "$lte": wanted[-1].to_pydatetime()}})
            if not wanted.difference(pd.to_datetime(saved_hours, utc=True)).empty:
                missing = list(weeks)
        if not missing:
            continue
        start = (missing[0] - pd.Timedelta(days=6)).tz_localize("Europe/Oslo").tz_convert("UTC")
        end = (missing[-1] + pd.Timedelta(days=1)).tz_localize("Europe/Oslo").tz_convert("UTC")
        hours = pd.date_range(start.normalize(), end.normalize() + pd.Timedelta(days=1), freq="h", inclusive="left")
        params, sample_id = weather_sample(region)
        params.update(start_date=str(hours[0].date()), end_date=str(hours[-1].date()))
        if previous_request:
            time.sleep(60)
        print(f"Downloading {region}: {len(missing)} weeks.", flush=True)
        hourly = mean_weather(fetch("Open-Meteo", API_URL, params).json(), hours)
        previous_request = True
        # Persisting original hourly regional means before deriving weekly values for the map.
        save_hourly_means(region, sample_id, hourly.loc[(hourly.index >= start) & (hourly.index <= end)])

        # Using local Monday boundaries and moving preceding-hour rain to its covered hour.
        hourly["precipitation"] = hourly.precipitation.shift(-1)
        labels = hourly.index.tz_convert("Europe/Oslo").tz_localize(None).to_period("W-SUN").end_time.normalize()
        grouped = hourly.groupby(labels)
        weekly = grouped.agg(temperature_c=("temperature_2m", "mean"), precipitation_mm=("precipitation", "sum")).loc[missing]
        expected = ((weekly.index + pd.Timedelta(days=1)).tz_localize("Europe/Oslo")
                    - (weekly.index - pd.Timedelta(days=6)).tz_localize("Europe/Oslo")) / pd.Timedelta(hours=1)
        if (not grouped.count().loc[missing].eq(expected, axis="index").all().all()
                or not np.isfinite(weekly).all().all() or weekly.precipitation_mm.lt(0).any()):
            raise ValueError(f"Incomplete or invalid weather for {region}.")
        writes = [UpdateOne({"_id": f"{region}:{week.date()}"}, {"$setOnInsert": {
            "region": region, "date": str(week.date()), "model": "era5", "sample_id": sample_id,
            **row.to_dict()}}, upsert=True) for week, row in weekly.iterrows()]
        result = collection.bulk_write(writes)
        print(f"{region}: {result.upserted_count} weeks saved.", flush=True)
    # Verifying contiguous coverage from the database, including the existing final week.
    for region in regions:
        dates = collection.distinct("date", {"region": region, "date": {"$gte": "2026-01-01"}})
        assert set(str(w.date()) for w in weeks).issubset(dates)
    print(f"Verified {len(weeks)} weeks per area through {weeks[-1].date()}.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--water-areas", action="store_true")
    backfill_price_weather(parser.parse_args().water_areas)

