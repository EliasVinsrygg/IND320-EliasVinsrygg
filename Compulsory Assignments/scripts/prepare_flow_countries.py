"""Prepare the six Natural Earth land polygons used by the Explore map."""

import json
from pathlib import Path

import requests
from shapely.geometry import shape


SOURCE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
          "v5.1.1/geojson/ne_50m_admin_0_countries.geojson")
COUNTRIES = {
    "DNK": ("DK", "Denmark"),
    "FIN": ("FI", "Finland"),
    "DEU": ("DE", "Germany"),
    "NLD": ("NL", "Netherlands"),
    "SWE": ("SE", "Sweden"),
    "GBR": ("GB", "United Kingdom"),
}
MAX_BYTES = 5_000_000
OUTPUT = Path(__file__).resolve().parents[1] / "assets/flow_countries.geojson"


def prepare_flow_countries():
    """Read a versioned GeoJSON file and write a validated local subset."""
    # Reading only the pinned HTTPS resource as data, without following redirects.
    with requests.get(SOURCE, timeout=(10, 30), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected response from Natural Earth.")
        payload = bytearray()
        for chunk in response.iter_content(65536):
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise ValueError("Natural Earth file exceeds the expected size.")
    data = json.loads(payload)
    if data.get("type") != "FeatureCollection":
        raise ValueError("Expected a Natural Earth FeatureCollection.")

    # Keeping the geometry and our own labels, matched to the CA2 country names.
    features = {}
    for feature in data["features"]:
        source_code = feature["properties"]["ADM0_A3"]
        if source_code not in COUNTRIES:
            continue
        code, country = COUNTRIES[source_code]
        geometry = shape(feature["geometry"])
        if (code in features or geometry.geom_type not in {"Polygon", "MultiPolygon"}
                or geometry.is_empty or not geometry.is_valid):
            raise ValueError(f"Unexpected polygon for {country}.")
        west, south, east, north = geometry.bounds
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError(f"Unexpected coordinate bounds for {country}.")
        features[code] = {"type": "Feature", "id": code, "properties": {"country": country},
                          "geometry": geometry.__geo_interface__}
    if features.keys() != {code for code, _ in COUNTRIES.values()}:
        raise ValueError("Missing one or more expected country polygons.")

    collection = {"type": "FeatureCollection", "features": list(features.values())}
    OUTPUT.write_text(json.dumps(collection, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"Saved {len(features)} polygons ({OUTPUT.stat().st_size:,} bytes) from Natural Earth v5.1.1.")


if __name__ == "__main__":
    prepare_flow_countries()
