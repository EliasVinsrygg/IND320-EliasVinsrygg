"""Explore cross-border physical flows saved by the CA2 notebook."""

import calendar

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.mongo_loader import get_available_flows, get_monthly_flows


# Keep each transfer direction the same colour in both charts.
DIRECTION_COLORS = {"Into Norway": "#D62728", "Out of Norway": "#315D8C"}


def gaussian_smooth(values, sigma):
    """Average nearby power blocks with Gaussian weights, keeping edge values valid."""
    offsets = np.arange(-4 * sigma, 4 * sigma + 1)
    weights = np.exp(-offsets**2 / (2 * sigma**2))
    weights /= weights.sum()

    # Divide by the available weights at each edge, where neighbours are missing.
    padding = 4 * sigma
    weighted_power = np.convolve(np.pad(values, padding), weights, mode="valid")
    available_weight = np.convolve(
        np.pad(np.ones(len(values)), padding), weights, mode="valid"
    )
    return weighted_power / available_weight


def add_power_segment(timestamps, power_values, blocks, sigma):
    """Append one uninterrupted set of blocks without joining it to the next."""
    if not blocks:
        return
    values = [block["power_mw"] for block in blocks]
    if sigma > 0:
        values = gaussian_smooth(values, sigma)
    timestamps.extend([block["timestamp_utc"] for block in blocks])
    power_values.extend(values)
    # Extend the last value to the end of its published block, then break the line.
    timestamps.extend([blocks[-1]["end_utc"], None])
    power_values.extend([values[-1], None])


def build_power_chart(monthly_flows, selected_months, sigma=0):
    """Draw published or Gaussian-smoothed MW lines for selected UTC months."""
    figure = go.Figure()
    for direction, label in (
        ("import", "Into Norway"),
        ("export", "Out of Norway"),
    ):
        timestamps = []
        power_values = []
        selected_blocks = []
        for document in monthly_flows:
            if document["direction"] == direction and document["month"] in selected_months:
                selected_blocks.extend(document["blocks"])

        # Join adjacent blocks across month boundaries before smoothing.
        # Actual gaps, overlaps, and unselected months still break the line.
        segment = []
        for block in sorted(selected_blocks, key=lambda item: item["timestamp_utc"]):
            if segment and block["timestamp_utc"] != segment[-1]["end_utc"]:
                add_power_segment(timestamps, power_values, segment, sigma)
                segment = []
            segment.append(block)
        add_power_segment(timestamps, power_values, segment, sigma)

        if timestamps:
            figure.add_trace(go.Scatter(
                x=timestamps,
                y=power_values,
                name=label,
                mode="lines",
                line={"color": DIRECTION_COLORS[label]},
                line_shape="linear" if sigma > 0 else "hv",
                connectgaps=False,
            ))

    figure.update_layout(
        xaxis_title="Time (UTC)",
        legend_title_text="Direction",
        # Place the direction key above the plot instead of beside it.
        legend={"orientation": "h", "x": 1, "xanchor": "right",
                "y": 1.03, "yanchor": "bottom"},
        margin={"l": 45, "r": 10, "t": 75, "b": 45},
        hovermode="x unified",
    )
    # A horizontal unit label leaves the left margin for tick values.
    figure.add_annotation(
        text="Power (MW)", x=0, y=1.03, xref="paper", yref="paper",
        xanchor="left", yanchor="bottom", showarrow=False,
    )
    return figure


st.header("Cross-border flows")
st.write("Compare physical electricity flows into and out of Norway.")

# A complete calendar year is needed for a full-year energy comparison.
complete_years = {2024, 2025}
available_pairs = [
    (country, year)
    for country, year in get_available_flows()
    if year in complete_years
]
countries = sorted({country for country, _ in available_pairs})
if not countries:
    st.warning("No complete calendar years are available in MongoDB.")
    st.stop()

left_column, right_column = st.columns(2)
with left_column:
    st.subheader("Annual energy")
    selected_country = st.radio("Connection", countries)
    years = sorted(
        {year for country, year in available_pairs if country == selected_country},
        reverse=True,
    )
    selected_year = st.selectbox("Year", years)

    # The notebook stored one MWh total per month and direction. Add twelve
    # months, then convert MWh to TWh before drawing the pie chart.
    monthly_flows = get_monthly_flows(selected_country, selected_year)
    expected_months = {(month, direction)
                       for month in range(1, 13)
                       for direction in ("import", "export")}
    actual_months = {(row["month"], row["direction"]) for row in monthly_flows}
    if actual_months != expected_months:
        st.warning("This connection does not have a complete year in MongoDB.")
    else:
        pie_data = pd.DataFrame([
            {
                "flow": "Into Norway" if direction == "import" else "Out of Norway",
                "energy_twh": sum(
                    row["energy_mwh"] for row in monthly_flows
                    if row["direction"] == direction
                ) / 1_000_000,
            }
            for direction in ("import", "export")
        ])
        figure = px.pie(
            pie_data,
            names="flow",
            values="energy_twh",
            title=f"Norway and {selected_country}, {selected_year}",
            labels={"flow": "Direction", "energy_twh": "Energy (TWh)"},
            color="flow",
            color_discrete_map=DIRECTION_COLORS,
        )
        figure.update_traces(textinfo="label+percent")
        st.plotly_chart(figure, width="stretch")

with right_column:
    st.subheader("Monthly power")
    st.caption(
        f"Norway and {selected_country}, {selected_year}. "
        "Published average power for each UTC time block, in MW."
    )
    available_months = sorted({row["month"] for row in monthly_flows})
    if not available_months:
        st.warning("No monthly power data is available for this selection.")
    else:
        selected_months = st.pills(
            "Months",
            options=available_months,
            selection_mode="multi",
            default=[available_months[0]],
            format_func=lambda month: calendar.month_abbr[month],
            key="flow_months",
            wrap=True,
        )
        # Equal slider steps represent small changes first and larger changes later.
        sigma_values = [0, *sorted({int(value) for value in np.geomspace(1, 200, 50).round()})]
        sigma = st.select_slider(
            "Gaussian smoothing (0 = off)",
            options=sigma_values,
            value=0,
            width="stretch",
            help="Sigma counts published time blocks. Steps grow toward 200. Only the displayed power lines change.",
        )
        if sigma > 0:
            st.caption(f"Smoothed trend (sigma = {sigma} blocks); the annual energy chart uses original data.")
        if not selected_months:
            st.info("Select at least one month to see the power lines.")
        else:
            power_chart = build_power_chart(
                monthly_flows, selected_months, sigma=sigma
            )
            if power_chart.data:
                st.plotly_chart(power_chart, width="stretch")
            else:
                st.warning("No power blocks are available for these months.")

# Keep the source explanation below both charts, available when needed.
with st.expander("About the data"):
    st.markdown(
        "Source: [ENTSO-E Transparency Platform, Physical Flows (12.1.G)]"
        "(https://transparency.entsoe.eu/transmission/physicalFlows). "
        "A connection on this page is a pair of countries, not an individual cable. "
        "The CA2 notebook retrieves flows between Norway and six foreign countries. "
        "It converts published average power (MW) and interval length into energy "
        "(MWh), stores the data in Cassandra with Spark, extracts the plot columns "
        "with Spark, and saves monthly documents in MongoDB. This page reads those "
        "saved documents. The pie chart sums import and export energy for a complete "
        "calendar year (TWh); the lines show power in the selected months (MW). "
        "Times are UTC. These values describe cross-border transfers, not electricity "
        "production. The page reflects the latest data saved by the notebook."
    )
