"""Interactive Plotly-chart page for the IND320 reservoir statistics app."""

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from modules.data_loader import MEASUREMENT_COLUMNS, load_reservoir_data


PLOT_SETTINGS = {
    "fill_level_ratio": {
        "label": "Fill level",
        "y_title": "Fill level (%)",
        "multiplier": 100,
        "unit": "%",
        "can_stack": False,
    },
    "capacity_twh": {
        "label": "Capacity",
        "y_title": "Capacity (TWh)",
        "multiplier": 1,
        "unit": "TWh",
        "can_stack": True,
    },
    "stored_energy_twh": {
        "label": "Stored energy",
        "y_title": "Stored energy (TWh)",
        "multiplier": 1,
        "unit": "TWh",
        "can_stack": True,
    },
    "previous_week_fill_level_ratio": {
        "label": "Previous-week fill level",
        "y_title": "Previous-week fill level (%)",
        "multiplier": 100,
        "unit": "%",
        "can_stack": False,
    },
    "weekly_fill_level_change": {
        "label": "Weekly fill-level change",
        "y_title": "Weekly change (percentage points)",
        "multiplier": 100,
        "unit": "percentage points",
        "can_stack": False,
    },
}

ALL_MEASUREMENTS = "all_measurements"
NATIONAL_LABEL = "Norway (NO-0)"
REGIONAL_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


def turn_off_vass_when_el_is_enabled() -> None:
    """Keep the two alternative regional systems mutually exclusive."""
    if st.session_state["show_el_areas"]:
        st.session_state["show_vass_areas"] = False


def turn_off_el_when_vass_is_enabled() -> None:
    """Keep the two alternative regional systems mutually exclusive."""
    if st.session_state["show_vass_areas"]:
        st.session_state["show_el_areas"] = False


def add_measurement_traces(
    figure: go.Figure,
    data,
    measurement: str,
    row: int,
    area_type: str | None,
    show_legend: bool,
) -> None:
    """Add regional traces and the emphasised national reference trace.

    Capacity and stored energy can be added across regions, and are therefore
    shown as stacked areas. Fill levels and weekly changes are shown as lines,
    because adding those values would not be meaningful.
    """
    settings = PLOT_SETTINGS[measurement]

    if area_type is not None:
        regional_data = data.loc[data["area_type"] == area_type]
        for color_index, (area_number, area_data) in enumerate(
            regional_data.groupby("area_number", sort=True)
        ):
            area_label = f"{area_type}-{area_number}"
            trace_arguments = {
                "x": area_data["date"],
                "y": area_data[measurement] * settings["multiplier"],
                "name": area_label,
                "legendgroup": area_label,
                "showlegend": show_legend,
                "mode": "lines",
                "line": {
                    "color": REGIONAL_COLORS[color_index % len(REGIONAL_COLORS)],
                    "width": 1.5,
                },
                "hovertemplate": (
                    f"Date: %{{x|%d %b %Y}}<br>{area_label}: "
                    f"%{{y:.3f}} {settings['unit']}<extra></extra>"
                ),
            }

            if settings["can_stack"]:
                trace_arguments["stackgroup"] = f"{area_type}_{measurement}"
                trace_arguments["fillcolor"] = REGIONAL_COLORS[
                    color_index % len(REGIONAL_COLORS)
                ]

            figure.add_trace(go.Scatter(**trace_arguments), row=row, col=1)

    national_data = data.loc[
        (data["area_type"] == "NO") & (data["area_number"] == 0)
    ]
    figure.add_trace(
        go.Scatter(
            x=national_data["date"],
            y=national_data[measurement] * settings["multiplier"],
            name=NATIONAL_LABEL,
            legendgroup=NATIONAL_LABEL,
            showlegend=show_legend,
            mode="lines",
            # A thick, solid, black line makes NO-0 easy to distinguish from regions.
            line={"color": "black", "width": 3},
            hovertemplate=(
                f"Date: %{{x|%d %b %Y}}<br>{NATIONAL_LABEL}: "
                f"%{{y:.3f}} {settings['unit']}<extra></extra>"
            ),
        ),
        row=row,
        col=1,
    )


def build_chart(data, measurements: list[str], area_type: str | None) -> go.Figure:
    """Build one Plotly figure with one row for each requested measurement."""
    subplot_titles = [PLOT_SETTINGS[measurement]["label"] for measurement in measurements]
    figure = make_subplots(
        rows=len(measurements),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=subplot_titles,
    )

    for row, measurement in enumerate(measurements, start=1):
        add_measurement_traces(
            figure,
            data,
            measurement,
            row,
            area_type,
            show_legend=row == 1,
        )
        figure.update_yaxes(
            title_text=PLOT_SETTINGS[measurement]["y_title"],
            rangemode="tozero" if PLOT_SETTINGS[measurement]["can_stack"] else "normal",
            row=row,
            col=1,
        )

    figure.update_xaxes(title_text="Date", row=len(measurements), col=1)
    # The range slider gives a second, plot-native way to focus on a time period.
    figure.update_xaxes(rangeslider_visible=True, row=len(measurements), col=1)
    figure.update_layout(
        title="Reservoir statistics",
        height=500 if len(measurements) == 1 else 250 * len(measurements),
        hovermode="x unified",
        dragmode="zoom",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.03},
        margin={"l": 30, "r": 30, "t": 95, "b": 35},
    )
    return figure


st.header("Interactive reservoir chart")
st.write(
    "Choose one measurement or view all measurements. Norway (NO-0) is always "
    "shown as a thick, solid black reference line."
)
st.caption(
    "Capacity and stored energy are stacked for regional views. Fill levels and "
    "weekly changes are shown as separate regional lines because they cannot be added."
)

# The cached loader reads the local CSV only once per data change.
reservoir_data = load_reservoir_data().copy()
reservoir_data["month"] = reservoir_data["date"].dt.to_period("M").astype(str)
national_data = reservoir_data.loc[
    (reservoir_data["area_type"] == "NO")
    & (reservoir_data["area_number"] == 0)
].copy()
month_options = national_data["month"].drop_duplicates().tolist()

# A fresh visitor sees the final 36 months in the new range-slider control.
default_month_range = (
    month_options[max(0, len(month_options) - 36)],
    month_options[-1],
)

st.session_state.setdefault("show_el_areas", False)
st.session_state.setdefault("show_vass_areas", False)

# Keep every control above the chart, so it never moves with chart output.
with st.container(border=True):
    st.subheader("Chart controls")
    selected_measurement = st.selectbox(
        "Choose a measurement",
        options=[ALL_MEASUREMENTS, *MEASUREMENT_COLUMNS],
        format_func=lambda option: (
            "All measurement columns"
            if option == ALL_MEASUREMENTS
            else PLOT_SETTINGS[option]["label"]
        ),
        key="selected_measurement",
    )

    with st.container(horizontal=True):
        show_el = st.toggle(
            "Show electricity price areas (EL)",
            key="show_el_areas",
            on_change=turn_off_vass_when_el_is_enabled,
        )
        show_vass = st.toggle(
            "Show watercourse areas (VASS)",
            key="show_vass_areas",
            on_change=turn_off_el_when_vass_is_enabled,
        )

    start_month, end_month = st.select_slider(
        "Choose a period of months",
        options=month_options,
        value=default_month_range,
        key="selected_month_range_last_three_years",
    )

selected_data = reservoir_data.loc[
    (reservoir_data["month"] >= start_month)
    & (reservoir_data["month"] <= end_month)
].copy()
selected_area_type = "EL" if show_el else "VASS" if show_vass else None
selected_measurements = (
    list(MEASUREMENT_COLUMNS)
    if selected_measurement == ALL_MEASUREMENTS
    else [selected_measurement]
)

st.caption(
    "Hover to inspect values. Use the mouse wheel or the toolbar to zoom, drag "
    "to pan, and use point, box or lasso selection in the toolbar to select data."
)

selection_event = st.plotly_chart(
    build_chart(selected_data, selected_measurements, selected_area_type),
    width="stretch",
    key="reservoir_plot",
    on_select="rerun",
    selection_mode=("points", "box", "lasso"),
    config={"scrollZoom": True, "displaylogo": False},
)

selected_points = selection_event.selection.points
if selected_points:
    st.caption(
        f"You selected {len(selected_points)} data point(s). Double-click the chart "
        "to clear the selection."
    )
