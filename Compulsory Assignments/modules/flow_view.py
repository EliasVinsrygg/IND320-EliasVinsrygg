"""Display the CA2 flow charts for a country selected in Explore."""

import calendar

import numpy as np
import streamlit as st
from pymongo.errors import PyMongoError

from modules.flow_plotting import build_energy_pie_chart, build_power_chart
from modules.flow_loader import get_monthly_flows


def show_cross_border_flows(country: str, years: list[int]):
    """Display annual energy and selected months of power for the clicked country."""
    st.header(f"Cross-border flows between Norway and {country}")

    left_column, right_column = st.columns(2)
    with left_column:
        st.subheader("Annual energy")
        # Reusing the availability already loaded by Explore.
        selected_year = st.selectbox("Year", years)

        # Checking that all months are present before drawing an annual total.
        try:
            monthly_flows = get_monthly_flows(country, selected_year)
        except (PyMongoError, OSError, KeyError):
            st.warning("The selected connection could not be loaded from MongoDB.")
            return
        expected_months = {(month, direction)
                           for month in range(1, 13)
                           for direction in ("import", "export")}
        actual_months = {(row["month"], row["direction"]) for row in monthly_flows}
        if actual_months != expected_months:
            st.warning("This connection does not have a complete year in MongoDB.")
        else:
            pie_chart = build_energy_pie_chart(monthly_flows, country, selected_year)
            st.plotly_chart(pie_chart, width="stretch")

    with right_column:
        st.subheader("Monthly power")
        st.caption(
            f"Norway and {country}, {selected_year}. "
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
            # The choices advance by one block at first, then by larger amounts.
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

    # Placing the source note under both charts.
    with st.expander("About the data"):
        st.markdown(
            "Source: [ENTSO-E Transparency Platform, Physical Flows (12.1.G)]"
            "(https://transparency.entsoe.eu/transmission/physicalFlows). "
            "The data has been uploaded to a separate MongoDB database, and is"
            " not automatically updated."
        )
