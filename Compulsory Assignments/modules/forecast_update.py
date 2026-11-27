"""Refresh complete NO3 weeks using the four CA4 sources."""
from io import StringIO
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests
from datetime import timedelta, timezone, datetime
from uuid import uuid4
from pymongo import UpdateOne
import streamlit as st

from modules.database import get_mongo_client

ZONE = "Europe/Oslo"
FIRST = pd.Timestamp("2026-01-04")
NO3 = "10YNO-3--------J"
NEIGHBOURS = {"se2": "10Y1001A1001A45N", "no5": "10Y1001A1001A48H",
              "no1": "10YNO-1--------2", "no4": "10YNO-4--------9"}


def fetch(source, url, params=None):
    """Report the source and status while keeping token-bearing URLs private."""
    try:
        response = requests.get(url, params=params, timeout=(15, 120))
    except requests.RequestException:
        raise ValueError(f"{source}: connection failed. Completed weeks are saved.") from None
    if not response.ok:
        raise ValueError(f"{source}: HTTP {response.status_code}. Completed weeks are saved.")
    return response


def parse_flow_response(text, origin, destination, request_start, request_end):
    """Read published MW intervals, clipping them to one non-overlapping request."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise ValueError("ENTSO-E returned an unreadable response. Completed weeks are saved.") from None
    if root.tag.endswith("Acknowledgement_MarketDocument"):
        reason = root.findtext(".//{*}Reason/{*}text") or "Unknown acknowledgement"
        if "no matching data" in reason.lower() or "no data" in reason.lower():
            return []
        raise ValueError(f"ENTSO-E rejected a query: {reason}")
    rows = []
    for series in root.findall(".//{*}TimeSeries"):
        if (series.findtext("{*}out_Domain.mRID") != origin
                or series.findtext("{*}in_Domain.mRID") != destination
                or series.findtext("{*}quantity_Measure_Unit.name") != "MAW"):
            raise ValueError("Unexpected ENTSO-E bidding zones, direction or power unit.")
        curve = series.findtext("{*}curveType")
        if curve not in {"A01", "A03"}:
            raise ValueError("Unsupported ENTSO-E curve type.")
        for period in series.findall("{*}Period"):
            begin = pd.to_datetime(period.findtext("{*}timeInterval/{*}start"), utc=True)
            finish = pd.to_datetime(period.findtext("{*}timeInterval/{*}end"), utc=True)
            step = pd.Timedelta(period.findtext("{*}resolution"))
            if step not in (pd.Timedelta(minutes=15), pd.Timedelta(minutes=30), pd.Timedelta(hours=1)):
                raise ValueError("Unexpected ENTSO-E resolution.")
            points = period.findall("{*}Point")
            positions = [int(point.findtext("{*}position")) for point in points]
            if positions != sorted(set(positions)):
                raise ValueError("ENTSO-E positions must be ordered and unique.")
            # Interpreting A01 as fixed steps and A03 as values lasting until the next change.
            for i, point in enumerate(points):
                start = begin + (positions[i] - 1) * step
                end = (begin + (positions[i + 1] - 1) * step
                       if curve == "A03" and i + 1 < len(points)
                       else finish if curve == "A03" else start + step)
                power = float(point.findtext("{*}quantity"))
                if not begin <= start < end <= finish or not np.isfinite(power):
                    raise ValueError("Invalid ENTSO-E interval or power.")
                start, end = max(start, request_start), min(end, request_end)
                if start < end:
                    rows.append((start, end, power))
    return rows



def source_inputs(weeks, progress=None):
    """Build currency, weather and direction-specific flow inputs for full local weeks."""
    # Including the preceding December days for the first ISO week in January.
    monday = weeks[0] - pd.Timedelta(days=6)
    start = monday.tz_localize(ZONE).tz_convert("UTC")
    stop = (weeks[-1] + pd.Timedelta(days=1)).tz_localize(ZONE).tz_convert("UTC")
    rates = fetch("Norges Bank", "https://data.norges-bank.no/api/data/EXR/B.USD+EUR.NOK.SP",
                  {"startPeriod": str(monday.date()), "endPeriod": str(weeks[-1].date()),
                   "format": "csv", "locale": "en"})
    raw = pd.read_csv(StringIO(rates.text), sep=";")
    if not (raw.QUOTE_CUR.eq("NOK") & raw.UNIT_MULT.eq(0)).all():
        raise ValueError("Unexpected currency units.")
    raw["date"] = pd.to_datetime(raw.TIME_PERIOD)
    currency = raw.pivot(index="date", columns="BASE_CUR", values="OBS_VALUE")
    table = currency[["EUR", "USD"]].resample("W-SUN").mean().reindex(weeks)
    table.columns = ["eur_nok", "usd_nok"]
    table = table.where(table > 0)

    # Averaging the original 100 sample points before aggregating temperature and rain.
    path = Path(__file__).resolve().parents[1] / "assets/weather_locations.json"
    points = json.loads(path.read_text(encoding="utf8"))["regions"]["NO3"]
    hourly = fetch("Open-Meteo", "https://archive-api.open-meteo.com/v1/archive", {
        "longitude": ",".join(str(x) for x, y in points), "latitude": ",".join(str(y) for x, y in points),
        "start_date": str(start.date()), "end_date": str(stop.date()), "timezone": "GMT",
        "models": "era5", "hourly": "temperature_2m,precipitation"}).json()
    if len(hourly) != len(points) or len(points) != 100:
        raise ValueError("Incomplete Open-Meteo sample.")
    clock = pd.date_range(start.normalize(), stop.normalize() + pd.Timedelta(days=1), freq="h", inclusive="left")
    arrays = []
    for item in hourly:
        frame = pd.DataFrame(item["hourly"])
        if (not pd.DatetimeIndex(pd.to_datetime(frame.time, utc=True)).equals(clock)
                or item["hourly_units"]["precipitation"] != "mm"
                or item["hourly_units"]["temperature_2m"] != "\u00b0C" or item["utc_offset_seconds"] != 0):
            raise ValueError("Unexpected Open-Meteo hours or units.")
        arrays.append(frame[["temperature_2m", "precipitation"]].to_numpy(dtype=float))
    weather = pd.DataFrame(np.mean(arrays, axis=0), index=clock)
    weather[1] = weather[1].shift(-1)  # Matching precipitation to the preceding hour.
    weather = weather.loc[(clock >= start) & (clock < stop)].tz_convert(ZONE)
    for name, col in (("temperature_c", 0), ("precipitation_mm", 1)):
        grouped = weather[col].groupby(weather.index.tz_localize(None).to_period("W-SUN").end_time.normalize())
        values = grouped.mean() if col == 0 else grouped.sum()
        table[name] = values.where(grouped.count().eq(grouped.size()))

    # Integrating published MW blocks against each local week's actual UTC boundaries.
    token = st.secrets["entsoe"]["security_token"]
    for neighbour, code in NEIGHBOURS.items():
        if progress:
            progress(f"Checking NO3 flows with {neighbour.upper()} through {weeks[-1].date()}...")
        for direction, origin, destination in (("import", code, NO3), ("export", NO3, code)):
            response = fetch("ENTSO-E", "https://web-api.tp.entsoe.eu/api", {
                "securityToken": token, "documentType": "A11", "out_Domain": origin,
                "in_Domain": destination, "periodStart": start.strftime("%Y%m%d%H%M"),
                "periodEnd": stop.strftime("%Y%m%d%H%M")})
            blocks = sorted(parse_flow_response(response.text, origin, destination, start, stop))
            if any(a[1] > b[0] for a, b in zip(blocks, blocks[1:])):
                raise ValueError("Overlapping ENTSO-E intervals.")
            energies = []
            for week in weeks:
                lo = (week - pd.Timedelta(days=6)).tz_localize(ZONE).tz_convert("UTC")
                hi = (week + pd.Timedelta(days=1)).tz_localize(ZONE).tz_convert("UTC")
                parts = [((min(b, hi) - max(a, lo)).total_seconds(), mw)
                         for a, b, mw in blocks if a < hi and b > lo]
                covered = sum(seconds for seconds, mw in parts)
                energies.append(sum(seconds * mw / 3600 for seconds, mw in parts)
                                if covered == (hi - lo).total_seconds() else np.nan)
            table[f"no3_{neighbour}_{direction}_mwh"] = energies
    return table


def refresh_window(now):
    """Identify the latest Monday 06:00 boundary in Oslo local time."""
    local = pd.Timestamp(now).tz_convert(ZONE).tz_localize(None)
    monday = local.normalize() - pd.Timedelta(days=local.weekday()) + pd.Timedelta(hours=6)
    if local < monday:
        monday -= pd.Timedelta(weeks=1)
    return monday.date().isoformat()


def update_weeks(progress=print):
    """Share one completed source check per weekly window across app sessions."""
    db = get_mongo_client()["ind320_ca4"]
    status = db["refresh_status"]
    key = {"_id": "no3_weekly"}
    now = datetime.now(timezone.utc)
    window = refresh_window(now)
    message = "Most recent data is downloaded"
    status.update_one(key, {"$setOnInsert": {"completed": ""}}, upsert=True)
    # Claiming the run atomically and allowing recovery if a worker disappears.
    owner = uuid4().hex
    claim = status.update_one({**key, "completed": {"$lt": window},
        "$or": [{"lease_until": {"$exists": False}}, {"lease_until": {"$lte": now}}]},
        {"$set": {"owner": owner, "lease_until": now + timedelta(hours=1)}})
    if not claim.modified_count:
        if status.find_one(key)["completed"] >= window:
            return message
        return "An update is already running."
    owned = {**key, "owner": owner}
    release = {"owner": "", "lease_until": ""}
    try:
        download_weeks(db["no3_weekly"], progress)
        status.update_one(owned, {"$set": {"completed": window}, "$unset": release})
    except Exception:
        # Leaving the week open for a retry after an API or database error.
        status.update_one(owned, {"$unset": release})
        raise
    return message


def download_weeks(collection, progress):
    """Append all consecutive weeks with complete published inputs."""
    last = collection.find_one({"region": "NO3"}, sort=[("date", -1)])
    if not last:
        raise ValueError("Seed the historical NO3 table first.")
    latest = pd.Timestamp(last["date"])
    progress("Checking published NO3 reservoir observations...")
    raw = pd.DataFrame(fetch("NVE", "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData").json())
    reservoir = raw.loc[raw.omrType.eq("EL") & raw.omrnr.eq(3)].copy()
    reservoir.index = pd.to_datetime(reservoir.dato_Id)
    filling = reservoir.fyllingsgrad * 100
    if not filling.index.is_unique or not filling.between(0, 100).all():
        raise ValueError("Unexpected NO3 reservoir observations.")
    today = pd.Timestamp.now(tz=ZONE).tz_localize(None).normalize()
    weeks = pd.date_range(max(FIRST, latest - pd.Timedelta(weeks=1)),
                          min(filling.index.max(), today - pd.Timedelta(days=1)), freq="W-SUN")
    # Committing validated batches so a later click can resume after a provider error.
    for i in range(0, len(weeks), 8):
        batch = weeks[i:i + 8]
        progress(f"Checking sources for weeks ending {batch[0].date()} to {batch[-1].date()}...")
        table = source_inputs(batch, progress)
        table["filling_percent"] = filling.reindex(batch)
        writes = []
        pending_week = None
        for week, row in table.iterrows():
            if not np.isfinite(row).all():
                if week <= latest:
                    continue
                pending_week = week
                break
            label = str(week.date())
            writes.append(UpdateOne({"_id": f"NO3:{label}"}, {"$set": {
                "region": "NO3", "date": label, **row.to_dict()}}, upsert=True))
        if writes:
            collection.bulk_write(writes)
        if pending_week is not None:
            return
