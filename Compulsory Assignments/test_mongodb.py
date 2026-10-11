"""Test the MongoDB connection without reading or changing application data."""

from pathlib import Path
import sys
import tomllib

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError, ServerSelectionTimeoutError
from pymongo.server_api import ServerApi


# Locate the root secrets file relative to this script, regardless of terminal folder.
# tomllib is built into Python 3.12 and reads the same TOML format used by Streamlit.
project_root = Path(__file__).resolve().parents[1]
secrets_path = project_root / ".streamlit" / "secrets.toml"

try:
    with secrets_path.open("rb") as secrets_file:
        secrets = tomllib.load(secrets_file)
    uri = secrets["mongo"]["uri"]
    if not isinstance(uri, str) or not uri.strip() or "<db_password>" in uri:
        raise ValueError("Missing connection string or password placeholder.")
except (OSError, KeyError, ValueError):
    # Do not print parsing errors: they could contain part of a secret.
    print("FAIL: Check .streamlit/secrets.toml and its [mongo] uri value.")
    sys.exit(1)

client = None
try:
    # Follow the course MongoDB notebook's MongoClient and Stable API setup.
    # Limit waiting time if Atlas cannot be reached. Never print the URI.
    client = MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=10000)

    # Creating a client alone does not prove connectivity; ping requests a response.
    client.admin.command("ping")
    print("PASS: Connected to MongoDB. The server answered ping.")
    print("No application data was read or changed.")
except ServerSelectionTimeoutError:
    print("FAIL: Could not reach MongoDB. Check Atlas network access, internet, and VPN.")
    sys.exit(1)
except OperationFailure:
    print("FAIL: MongoDB rejected the request. Check the database user and password.")
    sys.exit(1)
except (PyMongoError, ValueError):
    print("FAIL: Check the MongoDB connection string and connection settings.")
    sys.exit(1)
finally:
    # Close the client after success or failure to release connection resources.
    if client is not None:
        client.close()
