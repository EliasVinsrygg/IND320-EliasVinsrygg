"""Build the two charts on the cross-border flows page."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# Keep each transfer direction the same colour in both charts.
DIRECTION_COLORS = {"Into Norway": "#D62728", "Out of Norway": "#315D8C"}


def build_energy_pie_chart(monthly_flows, country, year):
    """Add twelve monthly MWh totals per direction and show the year in TWh."""
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
        title=f"Norway and {country}, {year}",
        labels={"flow": "Direction", "energy_twh": "Energy (TWh)"},
        color="flow",
        color_discrete_map=DIRECTION_COLORS,
    )
    figure.update_traces(textinfo="label+percent")
    return figure


def gaussian_smooth(values, sigma):
    """Replace each MW value with a weighted average of nearby time blocks."""
    # Sigma sets the width in time blocks; distant blocks get less weight.
    offsets = np.arange(-4 * sigma, 4 * sigma + 1)
    weights = np.exp(-offsets**2 / (2 * sigma**2))
    weights /= weights.sum()

    # At the ends of a series, divide only by weights for blocks that exist.
    padding = 4 * sigma
    weighted_power = np.convolve(np.pad(values, padding), weights, mode="valid")
    available_weight = np.convolve(
        np.pad(np.ones(len(values)), padding), weights, mode="valid"
    )
    return weighted_power / available_weight


def add_power_segment(timestamps, power_values, blocks, sigma):
    """Add one uninterrupted stretch of MW blocks to a Plotly line."""
    if not blocks:
        return
    # Sigma zero keeps the published values; other choices affect only the chart.
    values = [block["power_mw"] for block in blocks]
    if sigma > 0:
        values = gaussian_smooth(values, sigma)
    timestamps.extend([block["timestamp_utc"] for block in blocks])
    power_values.extend(values)
    # Extend the last value to the end of its published block, then break the line.
    timestamps.extend([blocks[-1]["end_utc"], None])
    power_values.extend([values[-1], None])


def build_power_chart(monthly_flows, selected_months, sigma=0):
    """Draw import and export MW for selected months, with optional smoothing."""
    figure = go.Figure()
    for direction, label in (
        ("import", "Into Norway"),
        ("export", "Out of Norway"),
    ):
        timestamps = []
        power_values = []
        # Collect this direction across selected months before looking for gaps.
        selected_blocks = []
        for document in monthly_flows:
            if document["direction"] == direction and document["month"] in selected_months:
                selected_blocks.extend(document["blocks"])

        # Smooth across month borders only when the next block starts on time.
        # A missing or overlapping block ends the current line.
        segment = []
        for block in sorted(selected_blocks, key=lambda item: item["timestamp_utc"]):
            if segment and block["timestamp_utc"] != segment[-1]["end_utc"]:
                add_power_segment(timestamps, power_values, segment, sigma)
                segment = []
            segment.append(block)
        add_power_segment(timestamps, power_values, segment, sigma)

        if timestamps:
            # Raw blocks are steps; smoothed values make a continuous trend line.
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
