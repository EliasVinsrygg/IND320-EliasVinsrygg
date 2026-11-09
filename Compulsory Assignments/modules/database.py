"""Sharing one cached MongoDB connection across the app."""

import streamlit as st
from pymongo import MongoClient


@st.cache_resource
def get_mongo_client() -> MongoClient:
    """Open MongoDB with the private URI and reuse the client on app reruns."""
    # The same [mongo].uri secret is used by the notebook and hosted app.
    return MongoClient(st.secrets["mongo"]["uri"], serverSelectionTimeoutMS=10000)
