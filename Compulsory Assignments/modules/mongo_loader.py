"""Read the monthly Norway cross-border flows saved by the CA2 notebook."""

import streamlit as st
from pymongo import MongoClient


DATABASE = "ind320_ca2"
COLLECTION = "monthly_flows"


@st.cache_resource
def get_mongo_client() -> MongoClient:
    """Open MongoDB with the private URI and reuse the client on app reruns."""
    # The same [mongo].uri secret is used by the notebook and hosted app.
    return MongoClient(st.secrets["mongo"]["uri"], serverSelectionTimeoutMS=10000)


@st.cache_data(ttl=600)
def get_available_flows() -> list[tuple[str, int]]:
    """List saved country-year pairs for the page controls; refresh every 10 minutes."""
    collection = get_mongo_client()[DATABASE][COLLECTION]
    # Read only the small fields needed to build the page's controls.
    documents = collection.find({}, {"_id": 0, "country": 1, "year": 1})
    return sorted({(item["country"], item["year"]) for item in documents})


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
