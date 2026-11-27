"""Explore weekly reservoir filling and weather across Norwegian area systems."""
import json
from pathlib import Path

import plotly.graph_objects as go
import requests
import streamlit as st
from pymongo.errors import PyMongoError

from modules.flow_loader import get_flow_years_by_country
from modules.flow_view import show_cross_border_flows
from modules.map_weather import latest_map_weather_week, map_weather
from modules.reservoir_loader import load_reservoir_data
from modules.reservoir_statistics import show_reservoir_statistics


st.set_page_config(layout="wide")
st.title("Explore", icon=":material/map:")
st.write("Click a Norwegian area for reservoir statistics or a connected country for electricity flows.")
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
# Offering a wider view with country polygons only where the flow page has a year to show.
countries = {}
flow_years = {}
show_connections = controls.toggle("Show connections", value=True)
if show_connections:
    try:
        flow_years = get_flow_years_by_country()
    except (PyMongoError, OSError, KeyError):
        controls.warning("Flow connections could not be loaded.")
    else:
        world = json.loads(path.with_name("flow_countries.geojson").read_text(encoding="utf-8"))
        countries = {feature["id"]: feature for feature in world["features"]
                     if feature["properties"]["country"] in flow_years}
        if countries:
            controls.caption("Land boundaries: Natural Earth")
        else:
            controls.info("No flow connections are available for 2024 or 2025.")

# Using the same area IDs for both the outlines and the selected measurement.
area_types = {"Price areas": "EL", "Water areas": "VASS", "Norway": "NO"}
kind = area_types[controls.selectbox("Areas", list(area_types), key="map_area_type")]
measures = {"Reservoir filling": "filling", "Mean temperature": "temperature_2m",
            "Total precipitation": "precipitation"}
options = ["Reservoir filling"] if kind == "NO" else list(measures)
variable = measures[controls.selectbox("Colour by", options, disabled=kind == "NO")]
if kind == "NO":
    controls.caption("Only reservoir filling is available at national level.")
# Limiting the map's week selector to the project period from 2016 onwards.
weeks = sorted(data.loc[data.date.ge("2016-01-01"), "date"].unique().tolist())
if not weeks:
    controls.info("No reservoir weeks are available from 2016 onwards.")
    st.stop()
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

# Styling the polygons directly keeps the full interior clickable, including grey areas.
selected = st.session_state.get("map_selected")
def area_marker(regions):
    """Give the selected polygon a contrasting outline."""
    return {"opacity": 0.65, "line": {
        "width": [4 if region == selected else 1.5 for region in regions],
        "color": ["#c23822" if region == selected else "#233c53" for region in regions]}}

figure = go.Figure()
valid = values.dropna()
if not valid.empty:
    figure.add_trace(go.Choroplethmap(geojson=geo, locations=valid.index.tolist(), customdata=valid.index.tolist(), z=valid.tolist(),
        colorscale=scale, **limits, marker=area_marker(valid.index),
        colorbar={"title": unit, "thickness": 12}, hovertemplate="%{location}: %{z:.1f} " + unit + "<extra></extra>"))
missing = values.index[values.isna()].tolist()
if missing:
    controls.caption("Grey areas have no complete observations for this week.")
    figure.add_trace(go.Choroplethmap(geojson=geo, locations=missing, customdata=missing, z=[0]*len(missing),
        colorscale=[[0, "#aaa"], [1, "#aaa"]], showscale=False, marker=area_marker(missing),
        hovertemplate="%{location}: no data<extra></extra>"))

# Drawing the connections in one neutral colour, independent of the Norwegian data scale.
if countries:
    figure.add_trace(go.Choroplethmap(
        geojson={"type": "FeatureCollection", "features": list(countries.values())},
        locations=list(countries),
        customdata=list(countries),
        text=[feature["properties"]["country"] for feature in countries.values()],
        z=[0] * len(countries), zmin=0, zmax=1,
        colorscale=[[0, "#c4b698"], [1, "#c4b698"]],
        showscale=False, marker=area_marker(countries),
        hovertemplate="%{text}<extra></extra>",
    ))


def select_area():
    """Select a map feature and share Norwegian regions with the analysis pages."""
    points = st.session_state["reservoir_map"]["selection"]["points"]
    if points:
        point = points[0]
        region = point.get("location") or point.get("customdata")
        if region in countries:
            st.session_state["map_selected"] = region
        elif region in layers[kind]:
            st.session_state["map_selected"] = region
            if region != "NO-0":
                st.session_state["selected_region"] = region

# Resetting the viewport when switching between Norway and the wider connections view.
center = {"lat": 60.5, "lon": 12} if show_connections else {"lat": 65, "lon": 15}
figure.update_layout(map={"style": "carto-positron", "center": center,
                          "zoom": 2.8 if show_connections else 3.4},
                     clickmode="event+select", height=610, margin=dict(l=0,r=0,t=0,b=0),
                     uirevision="connections" if show_connections else "norway")
chart.plotly_chart(figure, width="stretch", key="reservoir_map", on_select=select_area, selection_mode="points")
controls.dataframe(values.rename(f"{label} ({unit})").round(1).rename_axis("Area"))

# Showing details only for an area in the visible map layer.
if selected in layers[kind]:
    show_reservoir_statistics(data, selected)
elif selected in countries:
    country = countries[selected]["properties"]["country"]
    show_cross_border_flows(country, flow_years[country])
