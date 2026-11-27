"""Convert the CA3 shapefiles into lightweight reservoir map areas."""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def prepare_areas():
    """Return nine areas with the same type and number as the NVE observations."""
    folder = ROOT / "shapefiles"
    prices = gpd.read_file(folder / "Budområder/Budområder.shp", encoding="utf-8")
    water = gpd.read_file(folder / "NVE_Region/NVE_Region.shp", encoding="utf-8")

    # Matching source region codes before dissolving the five CA3 regions into three groups.
    prices["area_number"] = prices["budomr"].str.extract(r"^NO\s*([1-5])$", expand=False).astype(int)
    water["area_number"] = water["REGION"].map({"RS": 1, "RØ": 1, "RV": 2, "RM": 3, "RN": 3})
    if water["area_number"].isna().any():
        raise ValueError("Unknown NVE region code.")

    layers = []
    for area_type, source in (("EL", prices), ("VASS", water)):
        areas = source[["area_number", "geometry"]].dissolve("area_number").reset_index()
        # Simplifying shared edges together in metres, before converting to longitude/latitude.
        if areas.crs.to_epsg() != 25833 or not areas.geometry.is_valid_coverage():
            raise ValueError(f"Unexpected CRS or mismatched boundaries in {area_type}.")
        areas.geometry = areas.geometry.simplify_coverage(250)
        areas["area_type"] = area_type
        areas["region_id"] = ("NO" if area_type == "EL" else "VASS") + areas.area_number.astype(str)
        layers.append(areas)

    # Building the national display outline from exactly the same five simplified price areas.
    national = gpd.GeoDataFrame({"area_type": ["NO"], "area_number": [0], "region_id": ["NO-0"]},
                                geometry=[layers[0].geometry.union_all()], crs=prices.crs)
    return pd.concat([*layers, national], ignore_index=True).to_crs(4326)


if __name__ == "__main__":
    areas = prepare_areas()
    # Checking every feature against the saved Magasinstatistikk keys before writing GeoJSON.
    history = json.loads((ROOT / "data/ca4/2016_2025/reservoirs.json").read_text(encoding="utf-8"))
    keys = set(zip(areas.area_type, areas.area_number))
    if (len(areas) != 9 or not areas.region_id.is_unique or not areas.geometry.is_valid.all()
            or keys != {(row["omrType"], row["omrnr"]) for row in history}):
        raise ValueError("Invalid geometry or unexpected NVE area keys.")
    output = ROOT / "assets/reservoir_areas.geojson"
    # Retaining readable region IDs as both GeoJSON feature IDs and lookup properties.
    features = areas.set_index("region_id", drop=False).to_json(separators=(",", ":"))
    output.write_text(features, encoding="utf-8")
    print(f"Saved {len(areas)} features ({output.stat().st_size:,} bytes).")
