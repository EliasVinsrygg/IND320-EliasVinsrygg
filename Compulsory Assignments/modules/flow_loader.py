"""Read the monthly Norway cross-border flows saved by the CA2 notebook."""

import streamlit as st

from modules.database import get_mongo_client


DATABASE = "ind320_ca2"
COLLECTION = "monthly_flows"
# Using the same calendar years in the Explore map and the flow controls.
FLOW_VIEW_YEARS = (2024, 2025)


@st.cache_data(ttl=600)
def get_flow_years_by_country() -> dict[str, list[int]]:
    """List the available years for each map connection, newest first."""
    collection = get_mongo_client()[DATABASE][COLLECTION]
    # Fetching only supported calendar years and deduplicating the monthly records.
    documents = collection.find({"year": {"$in": list(FLOW_VIEW_YEARS)}},
                                {"_id": 0, "country": 1, "year": 1})
    years_by_country: dict[str, set[int]] = {}
    for row in documents:
        years_by_country.setdefault(row["country"], set()).add(row["year"])
    return {country: sorted(years, reverse=True) for country, years in years_by_country.items()}


@st.cache_data(ttl=600, max_entries=20)
def get_monthly_flows(country: str, year: int) -> list[dict]:
    """Read one country's monthly totals and MW blocks; cache them for 10 minutes."""
    collection = get_mongo_client()[DATABASE][COLLECTION]
    # Read the whole chosen year once; month clicks then use the cached result.
    documents = collection.find(
        {"country": country, "year": year},
        {"_id": 0, "country": 1, "year": 1, "month": 1,
         "direction": 1, "energy_mwh": 1, "blocks": 1},
    ).sort([("month", 1), ("direction", 1)])
    return list(documents)
