"""Test MongoDB connectivity and create, read, update, and delete fruit data."""

from pathlib import Path
import sys
import tomllib
from uuid import uuid4

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

    # Use a separate test collection. A unique marker isolates each test run.
    # Follow the course MongoDB notebook's Inserting, Reading, Updating, and Deleting.
    collection = client["ind320_test"]["fruit_test"]
    run_id = str(uuid4())
    test_filter = {"test_run": run_id}
    try:
        # MongoDB documents are Python dictionaries, as in the course examples.
        collection.insert_many([
            {"test_run": run_id, "fruit": "apple", "quantity": 10},
            {"test_run": run_id, "fruit": "pear", "quantity": 8},
        ])

        # Exclude internal fields from the output and compare actual stored values.
        projection = {"_id": 0, "test_run": 0}
        documents = list(collection.find(test_filter, projection).sort("fruit", 1))
        expected = [{"fruit": "apple", "quantity": 10}, {"fruit": "pear", "quantity": 8}]
        if documents != expected:
            raise RuntimeError("Inserted data did not match expected fruit values.")
        print("PASS: Inserted and read back:", documents)

        # $set changes only the quantity of this run's apple document.
        apple_filter = {"test_run": run_id, "fruit": "apple"}
        result = collection.update_one(apple_filter, {"$set": {"quantity": 12}})
        apple = collection.find_one(apple_filter, projection)
        if result.modified_count != 1 or apple != {"fruit": "apple", "quantity": 12}:
            raise RuntimeError("The apple quantity was not updated correctly.")
        print("PASS: Updated and read back:", apple)

        # Delete only documents belonging to this run, preserving any other data.
        result = collection.delete_many(test_filter)
        if result.deleted_count != 2 or collection.find_one(test_filter) is not None:
            raise RuntimeError("Test documents were not deleted correctly.")
        print("PASS: Deleted both test documents and verified they are gone.")
        print("PASS: MongoDB data manipulation from Python works.")
    finally:
        # Also attempt cleanup if a check fails; never delete the entire collection.
        collection.delete_many(test_filter)
except ServerSelectionTimeoutError:
    print("FAIL: Could not reach MongoDB. Check Atlas network access, internet, and VPN.")
    sys.exit(1)
except OperationFailure:
    print("FAIL: MongoDB rejected the request. Check credentials and read/write permissions.")
    sys.exit(1)
except RuntimeError as error:
    # These are our own verification messages, which contain no credentials.
    print(f"FAIL: {error}")
    sys.exit(1)
except (PyMongoError, ValueError):
    print("FAIL: Check the MongoDB connection string and connection settings.")
    sys.exit(1)
finally:
    # Close the client after success or failure to release connection resources.
    if client is not None:
        client.close()
