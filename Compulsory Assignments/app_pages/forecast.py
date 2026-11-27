"""Forecast NO3 filling with the CA4 River model and a quantile uncertainty band."""

from bisect import bisect_left, bisect_right

import pandas as pd
import streamlit as st
from pymongo.errors import PyMongoError

from modules.forecasting import EXOGENOUS_LABELS, minimum_history_weeks
from modules.forecast_loader import load_forecast_data, run_calibrated_forecast
from modules.forecast_update import update_weeks
from modules.forecast_plotting import build_forecast_figure


# Using the available page width for the historical curve and forecast.
st.set_page_config(layout="wide")
st.title("NO3 forecast", icon=":material/trending_up:")
st.write("The blue line shows the measured reservoir filling in NO3. The red line shows the forecast, "
         "and the shaded band shows uncertainty based on past forecast errors.")

# Keeping the forecast and its controls together in the first row.
chart, controls = st.columns([2, 1], gap="medium")

# Refreshing sources only on an explicit click and reloading any completed batches.
refresh_panel = controls.expander("Observation data")
refreshed = refresh_panel.button("Update data", icon=":material/download:")
if refreshed:
    notice = refresh_panel.empty()
    try:
        notice.info(update_weeks(progress=notice.info))
    except (ValueError, KeyError, PyMongoError) as error:
        notice.warning(str(error) if isinstance(error, ValueError) else "Check the database connection and source configuration.")
    finally:
        load_forecast_data.clear()

# Reading the prepared weekly observations for NO3.
try:
    data = load_forecast_data()
except PyMongoError:
    st.error("Could not read the NO3 observations from MongoDB. Try again shortly.")
    st.stop()
except (OSError, ValueError) as error:
    st.error(f"The prepared forecast data could not be loaded: {error}")
    st.stop()
# Starting training in March, after all eight flow series have a past observation.
dates = list(data.loc["2016-03-06":].index.date)
if not dates:
    st.info("No complete NO3 observations are available from March 2016 onwards.")
    st.stop()
refresh_panel.caption(f"Latest complete NO3 observation: {dates[-1]:%d %b %Y}.")
# Following newly available observations when the user was viewing the latest forecast.
prior_latest = st.session_state.get("forecast_latest_week")
selected_window = st.session_state.get("analysis_period")
if selected_window and selected_window[1] == prior_latest and dates[-1] > prior_latest:
    st.session_state["analysis_period"] = (selected_window[0] + (dates[-1] - prior_latest), dates[-1])
st.session_state["forecast_latest_week"] = dates[-1]


# Preserving period/horizon across pages, ready for the future map's shared time controls.
step = controls.segmented_control("Forecast interval", [1, 4], format_func={4: "Every four weeks", 1: "Weekly"}.get,
    default=1, required=True, label_visibility="collapsed", key="forecast_step_weeks", persist_state="session")
if st.session_state.get("_forecast_previous_step") != step:
    st.session_state["forecast_p"] = 1 if step == 4 else 4
    st.session_state["forecast_m"] = 52 // step
    previous_horizon = st.session_state.get("forecast_horizon_weeks", 12)
    st.session_state["forecast_horizon_weeks"] = min(52, ((previous_horizon + step - 1) // step) * step)
    st.session_state["_forecast_previous_step"] = step

# Updating the forecast when a setting changes.
with controls:
    # Leaving the slider above the other controls while reading model parameters first.
    training_control = st.container()
    left, right = st.columns(2)
    with left:
        horizon = st.number_input("Forecast horizon (weeks)", min_value=step, max_value=52, step=step,
            key="forecast_horizon_weeks", persist_state="session")
    with right:
        coverage = st.selectbox("Nominal quantile band", [80, 90, 95],
            format_func=lambda value: f"{value}%", key="forecast_coverage", persist_state="session")
    # Selecting cross-area flows together while keeping each direction as its own model input.
    flow_columns = [name for name in EXOGENOUS_LABELS if name.endswith("_mwh")]
    choices = {label: [name] for name, label in EXOGENOUS_LABELS.items() if name not in flow_columns}
    choices["Energy flows to/from other areas"] = flow_columns
    selected = st.multiselect("Exogenous variables", options=list(choices), default=list(choices),
        key="forecast_source_choices", persist_state="session")
    variables = [column for choice in selected for column in choices[choice]]

    with st.expander("Model parameters", expanded=False):
        parameters = {}
        rows = [
            [("p", "Recent lags (p)", 1 if step == 4 else 4, 26),
             ("d", "Differencing (d)", 0, 2), ("q", "Error lags (q)", 0, 13)],
            [("m", "Season length in steps (m)", 52 // step, 104),
             ("sp", "Seasonal lags (P)", 0, 2), ("sd", "Seasonal differencing (D)", 1, 1),
             ("sq", "Seasonal error lags (Q)", 0, 2)],
        ]
        for row in [items[i:i + 2] for items in rows for i in range(0, len(items), 2)]:
            for column, (name, label, default, maximum) in zip(st.columns(len(row)), row):
                with column:
                    st.session_state.setdefault(f"forecast_{name}", default)
                    parameters[name] = int(st.number_input(label, min_value=1 if name == "m" else 0,
                        max_value=maximum, step=1,
                        key=f"forecast_{name}", persist_state="session"))
        learning_rate = st.number_input("Learning rate", min_value=0.0001, max_value=0.2,
            value=0.01, step=0.001, format="%.4f", key="forecast_learning_rate", persist_state="session")
        st.caption("Weekly uses p=4 by default. The best validation result used four-week steps and p=1. "
                   "An annual season is 13 four-week steps or 52 weekly steps.")

parameters["season_steps"] = parameters.pop("m")
minimum_weeks = max(52, minimum_history_weeks(**parameters, step_weeks=step))
if len(dates) < minimum_weeks:
    training_control.info(f"These model settings need {minimum_weeks} weeks, but only {len(dates)} are available. "
                          "Reduce the model orders or season length.")
    st.stop()

# Adjusting the training range before rendering, counting both selected endpoints.
default_weeks = min(len(dates), max(104, minimum_weeks))
start, end = st.session_state.get("analysis_period", (dates[-default_weeks], dates[-1]))
first = min(bisect_left(dates, start), len(dates) - 1)
last = max(first, bisect_right(dates, end) - 1)
if last - first + 1 < minimum_weeks:
    # Preserving the other handle when a user shortens the range, where possible.
    if start != st.session_state.get("last_training_start", start) or first + minimum_weeks > len(dates):
        first = max(0, last - minimum_weeks + 1)
    last = max(last, first + minimum_weeks - 1)
valid_period = (dates[first], dates[last])
if "analysis_period" in st.session_state and st.session_state["analysis_period"] != valid_period:
    st.session_state["analysis_period"] = valid_period
period = training_control.select_slider(f"Training period (minimum {minimum_weeks} weeks)", options=dates,
    value=valid_period, format_func=lambda value: value.strftime("%d %b %Y"),
    key="analysis_period", persist_state="session")
st.session_state["last_training_start"] = period[0]

# Using complete blocks within the selected timeframe and explaining any trimmed first weeks.
window = data.loc[pd.Timestamp(period[0]):pd.Timestamp(period[1])]
history_weeks = len(window) // step * step
effective_start, origin = window.index[-history_weeks], window.index[-1]
settings = dict(**parameters, step_weeks=step,
    history_weeks=history_weeks, horizon_weeks=int(horizon), learning_rate=learning_rate,
    exogenous_columns=tuple(variables))
try:
    with st.spinner("Checking historical forecast errors..."):
        result, count = run_calibrated_forecast(data, origin, coverage / 100, settings)
except (ValueError, OverflowError) as error:
    st.error(str(error))
    st.stop()

# Storing the applied timeframe, including the forecast end, for later map synchronization.
st.session_state["forecast_timeframe"] = {
    "region": "NO3", "training_start": effective_start.date(), "origin": origin.date(),
    "forecast_end": result.index[-1].date(), "horizon_weeks": int(horizon),
}
st.caption(f"Training: {effective_start:%d %b %Y} to {origin:%d %b %Y} "
           f"({history_weeks} weeks). Forecast through {result.index[-1]:%d %b %Y}.")
if len(window) != history_weeks:
    st.caption(f"Leaving out the first {len(window) - history_weeks} selected week(s) to use complete four-week blocks.")
show_reference = controls.checkbox("Show 52-week reference", value=False,
    key="forecast_show_reference", persist_state="session")
reference = None
if show_reference:
    reference = data["filling_percent"].reindex(result.index - pd.Timedelta(weeks=52))
    reference.index = result.index
figure = build_forecast_figure(data.loc[:origin, "filling_percent"], result, coverage / 100, reference)
chart.plotly_chart(figure, key="no3_forecast_chart", width="stretch")
if count < 5:
    chart.caption(f"Forecast only. Found {count} comparable past forecasts. The band needs at least five.")

with st.expander("Forecast assumptions and values"):
    st.markdown("Future weather uses historical ISO-week means from the training period. "
        "If week 53 is absent, its weather uses the mean of weeks 52 and 1. "
        "Currency and weekly flow energy repeat the last available values. Missing historical flows "
        "use earlier observations in a model copy. Publication delays are not simulated. "
        "All displayed filling predictions are limited to 0-100%.")
    st.caption("In validation, the nominal 80% band covered 70 of 96 weekly observations (73%) and 19 of 24 four-week observations (79%) with the tested settings.")
    st.dataframe(result.rename(columns={"prediction": "Prediction (%)", "lower": "Lower bound (%)",
                                       "upper": "Upper bound (%)"}).round(2))
