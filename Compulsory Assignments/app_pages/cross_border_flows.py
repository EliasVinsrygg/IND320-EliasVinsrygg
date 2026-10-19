"""Explore cross-border physical flows saved by the CA2 notebook."""

import calendar

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.mongo_loader import get_available_flows, get_monthly_flows


def build_power_chart(monthly_flows, selected_months, country, year):
    """Draw one stepped MW line per direction for the selected UTC months."""
    figure = go.Figure()
    for direction, label in (
        ("import", "Into Norway"),
        ("export", "Out of Norway"),
    ):
        timestamps = []
        power_values = []
        for document in monthly_flows:
            if document["direction"] != direction or document["month"] not in selected_months:
                continue

            previous_end = None
            previous_power = None
            for block in sorted(document["blocks"], key=lambda item: item["timestamp_utc"]):
                # End an existing line before an unpublished interval or overlap.
                if previous_end is not None and block["timestamp_utc"] != previous_end:
                    timestamps.extend([previous_end, None])
                    power_values.extend([previous_power, None])
                timestamps.append(block["timestamp_utc"])
                power_values.append(block["power_mw"])
                previous_end = block["end_utc"]
                previous_power = block["power_mw"]

            if previous_end is not None:
                # The final point shows when this month's last power block ends.
                # None prevents a line across months the user did not select.
                timestamps.extend([previous_end, None])
                power_values.extend([previous_power, None])

        if timestamps:
            figure.add_trace(go.Scatter(
                x=timestamps,
                y=power_values,
                name=label,
                mode="lines",
                line_shape="hv",
                connectgaps=False,
            ))

    figure.update_layout(
        title=f"Norway and {country}, {year}",
        xaxis_title="Time (UTC)",
        yaxis_title="Power (MW)",
        legend_title_text="Direction",
        hovermode="x unified",
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
        )
        figure.update_traces(textinfo="label+percent")
        st.plotly_chart(figure, width="stretch")

with right_column:
    st.subheader("Monthly power")
    st.caption("Published average power for each UTC time block, in MW.")
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
        if not selected_months:
            st.info("Select at least one month to see the power lines.")
        else:
            power_chart = build_power_chart(
                monthly_flows, selected_months, selected_country, selected_year
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
