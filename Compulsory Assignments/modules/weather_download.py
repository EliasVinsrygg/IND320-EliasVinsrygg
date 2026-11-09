"""Downloading confirmed region-years, with shared limits and resumable local responses."""

import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pymongo import UpdateOne
from pymongo.errors import PyMongoError

from modules.database import get_mongo_client
from modules.weather_loader import WeatherDataMissing, load_weather_data


VARIABLES = ["temperature_2m", "precipitation"]
UNITS = {"temperature_2m": "°C", "precipitation": "mm"}
API_URL = "https://archive-api.open-meteo.com/v1/archive"
APP_FOLDER = Path(__file__).resolve().parents[1]
MIN_PAUSE_SECONDS = 90
HOURLY_DOWNLOADS = 9
DAILY_DOWNLOADS = 19


def weather_request(region, year):
    """Building one annual request using the exact sample already used for the app."""
    # Loading fixed coordinates from the repo, independently of notebooks and shapefiles.
    samples = json.loads((APP_FOLDER / "assets/weather_locations.json").read_text(encoding="utf-8"))
    if region not in samples["regions"] or not 1940 <= year < pd.Timestamp.now(tz="UTC").year:
        raise ValueError("Choose a known region and a completed year from 1940 onwards.")
    locations = np.asarray(samples["regions"][region], dtype=float)
    if locations.shape != (100, 2) or not np.isfinite(locations).all() or (np.abs(locations) > [180, 90]).any():
        raise ValueError("The fixed weather sample must contain 100 valid longitude/latitude pairs.")
    params = {"latitude": ",".join(map(str, locations[:, 1])),
              "longitude": ",".join(map(str, locations[:, 0])),
              "hourly": ",".join(VARIABLES), "models": "era5", "timezone": "GMT",
              "temperature_unit": "celsius", "precipitation_unit": "mm"}
    sample_id = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    params.update(start_date=f"{year}-01-01", end_date=f"{year}-12-31")
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    hours = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq="h", inclusive="left", tz="UTC")
    return {"params": params, "sample_id": sample_id, "hours": hours,
            "cache_path": APP_FOLDER / "data/weather" / region / "app_100" / f"{key}.json"}


def download_status():
    """Reading shared app usage and calculating the next available download time."""
    state = get_mongo_client()["ind320_ca3"]["weather_download_control"].find_one({"_id": "open_meteo"}) or {}
    now = pd.Timestamp.now(tz="UTC")
    # Retaining request attempts for 24 hours; failed requests may also use API quota.
    recent = sorted(t for t in pd.to_datetime(state.get("requests", []), utc=True)
                    if t > now - pd.Timedelta(days=1))
    deadlines = [(now, "Ready to start")]
    for field, reason in [("next_allowed", "90-second pause"), ("blocked_until", "Hourly or API pause"),
                          ("active_until", "Another download is running; check availability again")]:
        deadlines.append((pd.to_datetime(state.get(field, now), utc=True), reason))
    if len(recent) >= DAILY_DOWNLOADS:
        deadlines.append((recent[-DAILY_DOWNLOADS] + pd.Timedelta(days=1), "Daily limit reached"))
    available_at, reason = max(deadlines, key=lambda item: item[0])
    return {"wait_seconds": max(0, math.ceil((available_at - now).total_seconds())), "reason": reason,
            "estimated_seconds": max(5, round(state.get("last_duration_seconds", 60))),
            "measured_estimate": "last_duration_seconds" in state, "state": state, "recent": recent}


def mean_weather(payload, hours):
    """Validating all 100 hourly responses before calculating regional means."""
    if not isinstance(payload, list) or len(payload) != 100:
        raise ValueError("Open-Meteo must return exactly 100 locations.")
    frames = []
    for point in payload:
        # Keeping identical model series as separate sampled points, as in the notebook.
        frame = pd.DataFrame(point["hourly"])[["time", *VARIABLES]]
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
        if not pd.DatetimeIndex(frame["time"]).equals(hours):
            raise ValueError("Open-Meteo returned incomplete or irregular hours.")
        if point.get("utc_offset_seconds", 0) != 0 or any(point["hourly_units"].get(v) != UNITS[v] for v in VARIABLES):
            raise ValueError("Open-Meteo returned unexpected units or time zone.")
        frame[VARIABLES] = frame[VARIABLES].apply(pd.to_numeric, errors="raise")
        if not np.isfinite(frame[VARIABLES].to_numpy(dtype=float)).all():
            raise ValueError("Open-Meteo returned missing or non-finite values.")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).groupby("time")[VARIABLES].mean()


def download_weather(region, year, progress=None):
    """Downloading and saving one confirmed region-year without automatic API retries."""
    settings = weather_request(region, year)
    cache_path = settings["cache_path"]
    version = None
    hourly_pause = False
    started = time.monotonic()
    succeeded = False
    try:
        control = get_mongo_client()["ind320_ca3"]["weather_download_control"]
        # Rechecking MongoDB because another user may have completed the data since the popup opened.
        load_weather_data.clear(region, year)
        try:
            return load_weather_data(region, year)
        except WeatherDataMissing:
            pass
        if cache_path.is_file():
            if progress:
                progress("Reusing a saved response; no new API request is needed.")
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            # Reserving one global slot with a version check so simultaneous users cannot both claim it.
            control.update_one({"_id": "open_meteo"}, {"$setOnInsert": {"version": 0, "requests": []}}, upsert=True)
            status = download_status()
            if status["wait_seconds"]:
                raise ValueError(f"{status['reason']}. Check again in {status['wait_seconds']} seconds.")
            now = pd.Timestamp.now(tz="UTC")
            recent = status["recent"] + [now]
            fields = {"requests": [t.to_pydatetime() for t in recent],
                      "active_until": (now + pd.Timedelta(minutes=10)).to_pydatetime(),
                      "next_allowed": (now + pd.Timedelta(seconds=MIN_PAUSE_SECONDS)).to_pydatetime()}
            if sum(t > now - pd.Timedelta(hours=1) for t in recent) >= HOURLY_DOWNLOADS:
                hourly_pause = True
                fields["blocked_until"] = (now + pd.Timedelta(hours=1)).to_pydatetime()
            old_version = status["state"].get("version", 0)
            claimed = control.update_one({"_id": "open_meteo", "version": old_version},
                                         {"$set": fields, "$inc": {"version": 1}})
            if not claimed.matched_count:
                raise ValueError("Another user reserved a download. Check availability again.")
            version = old_version + 1
            if progress:
                progress("Requesting temperature and precipitation for 100 points from Open-Meteo.")
            response = requests.get(API_URL, params=settings["params"], timeout=(15, 180))
            if response.status_code == 429:
                # Respecting API rejections even when other tools have used the same external quota.
                reason = response.text
                pause = 86400 if any(word in reason.lower() for word in ("day", "daily")) else 3600
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    pause = max(pause, int(retry_after))
                control.update_one({"_id": "open_meteo", "version": version},
                    {"$max": {"blocked_until": (pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=pause)).to_pydatetime()}})
                raise ValueError(f"Open-Meteo quota reached: {reason}. No automatic retry. Retry-After: {retry_after or 'not supplied'}.")
            response.raise_for_status()
            payload = response.json()

        if progress:
            progress("Checking all hours and computing the 100-point regional means.")
        means = mean_weather(payload, settings["hours"])
        if not cache_path.is_file():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
            temporary.replace(cache_path)

        # Upserting the same hourly schema and IDs as the notebook, allowing safe recovery after interruption.
        if progress:
            progress("Saving hourly means to MongoDB for all users.")
        collection = get_mongo_client()["ind320_ca3"]["weather_hourly"]
        writes = []
        for hour, row in means.iterrows():
            document = {"region": region, "time": hour.to_pydatetime(),
                        "temperature_2m": float(row["temperature_2m"]), "precipitation": float(row["precipitation"]),
                        "sample_id": settings["sample_id"], "sample_size": 100, "sample_seed": 42,
                        "model": "era5", "timezone": "UTC", "units": UNITS, "source": API_URL}
            key = f"{region}:{settings['sample_id']}:{hour.isoformat()}"
            writes.append(UpdateOne({"_id": key}, {"$set": document}, upsert=True))
        collection.bulk_write(writes, ordered=False)
        load_weather_data.clear(region, year)
        weather = load_weather_data(region, year)
        succeeded = True
        return weather
    except requests.RequestException:
        raise ValueError("The Open-Meteo request failed. No automatic retry; please try again later.") from None
    except (KeyError, TypeError):
        raise ValueError("The saved or downloaded weather response has an unexpected format.") from None
    except PyMongoError:
        raise ValueError("MongoDB could not complete the download operation. Saved responses can be reused later.") from None
    finally:
        if version is not None:
            # Releasing only our reservation; a crashed run's reservation expires after ten minutes.
            now = pd.Timestamp.now(tz="UTC")
            fields = {"active_until": now.to_pydatetime(),
                      "next_allowed": (now + pd.Timedelta(seconds=MIN_PAUSE_SECONDS)).to_pydatetime()}
            if succeeded:
                fields["last_duration_seconds"] = time.monotonic() - started
            release = {"$set": fields, "$inc": {"version": 1}}
            if hourly_pause:
                release["$max"] = {"blocked_until": (now + pd.Timedelta(hours=1)).to_pydatetime()}
            try:
                control.update_one({"_id": "open_meteo", "version": version}, release)
            except PyMongoError:
                pass  # Keeping the ten-minute expiry when the release cannot reach MongoDB.
