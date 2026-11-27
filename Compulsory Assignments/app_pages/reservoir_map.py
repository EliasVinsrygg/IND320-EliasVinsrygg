"""Explore weekly reservoir filling and weather across Norwegian area systems."""
import json
from pathlib import Path

import plotly.graph_objects as go
import requests
import streamlit as st
from pymongo.errors import PyMongoError

from modules.map_weather import latest_map_weather_week, map_weather
from modules.reservoir_loader import load_reservoir_data


st.set_page_config(layout="wide")
st.title("Reservoir map", icon=":material/map:")
st.write("Choose an area type, a value to colour by and a week. Click an area to select it.")
path = Path(__file__).resolve().parents[1] / "assets/reservoir_areas.geojson"
geo = json.loads(path.read_text(encoding="utf-8"))
layers = {kind: [f["id"] for f in geo["features"] if f["properties"]["area_type"] == kind]
          for kind in ("EL", "VASS", "NO")}
try:
    data = load_reservoir_data()
except (requests.RequestException, ValueError):
    st.error("Reservoir observations could not be loaded from NVE.")
    st.stop()

chart, controls = st.columns([3, 1])
# Using the same area IDs for both the outlines and the selected measurement.
area_types = {"Price areas": "EL", "Water areas": "VASS", "Norway": "NO"}
kind = area_types[controls.selectbox("Areas", list(area_types))]
measures = {"Reservoir filling": "filling", "Mean temperature": "temperature_2m",
            "Total precipitation": "precipitation"}
options = ["Reservoir filling"] if kind == "NO" else list(measures)
variable = measures[controls.selectbox("Colour by", options, disabled=kind == "NO")]
if kind == "NO":
    controls.caption("Only reservoir filling is available at national level.")
weeks = sorted(data.date.unique().tolist())
default_week = weeks[-1]
week_key = "map_week"
if variable != "filling":
    # Opening on a common weather week while keeping older dates available for exploration.
    try:
        common = latest_map_weather_week(tuple(layers[kind]), default_week)
    except PyMongoError:
        st.error("Could not read weather coverage from MongoDB.")
        st.stop()
    if common in weeks:
        default_week = common
    week_key = f"map_weather_week_{kind}"
week = controls.select_slider("Week ending", options=weeks, value=default_week,
                              format_func=lambda day: day.strftime("%d %b %Y"), key=week_key)
# Reading values for the selected layer's geography and week.
if variable != "filling":
    try:
        values = map_weather(week, tuple(layers[kind]), variable)
    except PyMongoError:
        st.error("Could not read weather observations from MongoDB.")
        st.stop()
    temperature = variable == "temperature_2m"
    label, unit = ("Mean temperature", "\u00b0C") if temperature else ("Total precipitation", "mm")
    scale = "RdBu_r" if temperature else "Blues"
    limits = {"zmid": 0} if temperature else {"zmin": 0, "zmax": max(1., values.max())}
else:
    series = data.loc[data.date.eq(week) & data.area_type.eq(kind)].set_index("area_number").fill_level_ratio
    ids = layers[kind]
    numbers = [f["properties"]["area_number"] for f in geo["features"] if f["id"] in ids]
    values = series.reindex(numbers).set_axis(ids) * 100
    values = values.where(values.between(0, 100))
    label, unit, scale, limits = "Filling", "%", "Blues", {"zmin": 0, "zmax": 100}

figure = go.Figure()
valid = values.dropna()
if not valid.empty:
    figure.add_trace(go.Choroplethmap(geojson=geo, locations=valid.index.tolist(), z=valid.tolist(),
        colorscale=scale, **limits, marker={"opacity": 0.65, "line": {"width": 0}},
        colorbar={"title": unit, "thickness": 12}, hovertemplate="%{location}: %{z:.1f} " + unit + "<extra></extra>"))
missing = values.index[values.isna()].tolist()
if missing:
    controls.caption("Grey areas have no complete observations for this week.")
    figure.add_trace(go.Choroplethmap(geojson=geo, locations=missing, z=[0]*len(missing),
        colorscale=[[0, "#aaa"], [1, "#aaa"]], showscale=False, marker_opacity=0.5,
        hovertemplate="%{location}: no data<extra></extra>"))

# Drawing outlines as separate lines so hovering over a coloured area still reveals its value.
selected = st.session_state.get("map_selected", st.session_state.get("selected_region"))
for feature in geo["features"]:
    region = feature["id"]
    if region not in layers[kind]:
        continue
    geometry = feature["geometry"]
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    lon, lat = [], []
    for polygon in polygons:
        for ring in polygon:
            lon.extend([point[0] for point in ring] + [None])
            lat.extend([point[1] for point in ring] + [None])
    figure.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", name=region,
        customdata=[region]*len(lon), showlegend=False,
        line={"width": 4 if region == selected else 1.5, "color": "#c23822" if region == selected else "#233c53"},
        hovertemplate=region + "<extra></extra>"))

def select_area():
    """Share the clicked area with the other regional pages when supported."""
    points = st.session_state["reservoir_map"]["selection"]["points"]
    if points:
        point = points[0]
        region = point.get("location") or point.get("customdata")
        if region in layers[kind]:
            st.session_state["map_selected"] = region
            if region != "NO-0":
                st.session_state["selected_region"] = region

figure.update_layout(map={"style": "carto-positron", "center": {"lat": 65, "lon": 15}, "zoom": 3.4},
                     clickmode="event+select", height=610, margin=dict(l=0,r=0,t=0,b=0), uirevision="norway")
chart.plotly_chart(figure, width="stretch", key="reservoir_map", on_select=select_area, selection_mode="points")
controls.dataframe(values.rename(f"{label} ({unit})").round(1).rename_axis("Area"))
