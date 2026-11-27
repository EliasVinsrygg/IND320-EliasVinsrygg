"""Explore changes in the relationship between weather and weekly reservoir filling."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pymongo.errors import PyMongoError
from requests import RequestException
import streamlit as st

from modules.weather_correlation import correlation_inputs, window_series

st.title("Weather and reservoir correlation")
region = st.session_state["selected_region"]
st.write(f"Compare weather in {region} with the weekly change in reservoir filling. "
         "A positive correlation means higher weather values tend to coincide with a larger rise in filling.")
# Expressing the lag in calendar weeks, with earlier weather aligned to the reservoir date.
left, middle, right = st.columns(3)
property_name = left.selectbox("Weather property", ["Precipitation", "Temperature"])
lag = middle.slider("Weather lag (weeks)", 0, 12, 1)
window = right.slider("Window length (weeks)", 4, 52, 26)
variable, unit = ("precipitation_mm", "mm/week") if property_name == "Precipitation" else ("temperature_c", "°C")
try:
    data = correlation_inputs(region)
except (ValueError, RequestException, PyMongoError):
    st.error("Could not load the regional weather and reservoir observations.")
    st.stop()
series = window_series(data, variable, lag, window)
st.caption(f"Each date pairs the change in filling with weather {lag} week(s) earlier. "
           f"Each correlation uses the {window} consecutive pairs ending on that date.")
# Sharing the date axis and retaining gaps wherever a full correlation window is unavailable.
fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
    subplot_titles=(f"{property_name} aligned to the reservoir week", "Weekly change in reservoir filling",
                    "Sliding window correlation"))
for row, (column, label, colour) in enumerate([("weather", unit, "#3174a4"), ("change_pp", "pp", "#358575"),
                                               ("r", "Pearson r", "#99501c")], 1):
    fig.add_trace(go.Scatter(x=series.index, y=series[column], mode="lines", name=label,
                             line=dict(color=colour)), row=row, col=1)
    fig.update_yaxes(title_text=label, row=row, col=1)
fig.update_yaxes(range=[-1, 1], row=3, col=1)
fig.add_hline(y=0, line_dash="dot", row=3, col=1)
fig.update_layout(height=650, showlegend=False, hovermode="x unified")
st.plotly_chart(fig, width="stretch")
if series.r.notna().sum() == 0:
    st.info("No complete window with variation in both series. Try a shorter window or a different region.")
