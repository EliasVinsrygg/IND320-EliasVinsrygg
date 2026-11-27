"""Copy the prepared CA4 history to MongoDB and verify the round trip."""

from pathlib import Path
import sys

import pandas as pd
from pymongo import UpdateOne

# Resolving the shared data and app modules from the parent of scripts/.
APP_FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_FOLDER))

from modules.database import get_mongo_client
from modules.forecasting import EXOGENOUS_LABELS, forecast_no3


def seed_history():
    """Insert missing historical weeks and check the weekly values and default forecast."""
    path = APP_FOLDER / "data/ca4/no3_weekly.csv"
    data = pd.read_csv(path, parse_dates=["date"], index_col="date")
    expected = pd.date_range("2016-01-10", "2025-12-28", freq="W-SUN")
    assert data.index.equals(expected) and list(data) == ["filling_percent", *EXOGENOUS_LABELS]
    collection = get_mongo_client()["ind320_ca4"]["no3_weekly"]

    # Inserting only absent weeks, preserving gaps as BSON null and dates as Sunday labels.
    rows = data.astype(object).where(data.notna(), None)
    writes = []
    for date, values in rows.iterrows():
        label = date.date().isoformat()
        document = {"region": "NO3", "date": label, **values.to_dict()}
        writes.append(UpdateOne({"_id": f"NO3:{label}"}, {"$setOnInsert": document}, upsert=True))
    result = collection.bulk_write(writes)

    # Comparing every historical row and the weekly point forecast before switching the app.
    documents = collection.find({"region": "NO3", "date": {"$gte": "2016-01-10", "$lte": "2025-12-28"}})
    stored = pd.DataFrame(documents).set_index("date").sort_index()[data.columns]
    stored.index = pd.to_datetime(stored.index)
    pd.testing.assert_frame_equal(data, stored, check_exact=True)
    settings = dict(p=4, sd=1, history_weeks=104, horizon_weeks=12, exogenous_columns=tuple(EXOGENOUS_LABELS))
    for_data = [forecast_no3(table, table.index[-1], **settings)[0] for table in (data, stored)]
    pd.testing.assert_series_equal(*for_data, check_exact=True)
    print(f"{result.upserted_count} weeks inserted. Verified {len(stored)} rows and 12 forecast points.")


if __name__ == "__main__":
    seed_history()
