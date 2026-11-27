"""Applying the CA3 outlier methods to the selected hourly weather property."""

import plotly.graph_objects as go
import numpy as np
import pandas as pd
import streamlit as st
from scipy.fft import dct, idct
from scipy.stats import median_abs_deviation, trim_mean
from sklearn.neighbors import LocalOutlierFactor


WEATHER_PROPERTIES = {"temperature_2m": ("Temperature", "°C"), "precipitation": ("Precipitation", "mm/hour")}


def weather_figure(series, outliers):
    """Show the hourly observations and the measurements flagged by the chosen method."""
    label, unit = WEATHER_PROPERTIES[series.name]
    figure = go.Figure(go.Scattergl(x=series.index, y=series, name=label, line={"width": 1}))
    figure.add_trace(go.Scattergl(x=outliers.index, y=outliers[series.name], name="Flagged hours",
                                  mode="markers", marker={"color": "red", "size": 6}))
    figure.update_layout(xaxis_title="Time (UTC)", yaxis_title=f"{label} ({unit})", height=390)
    return figure


@st.cache_data(ttl=600, max_entries=16)
def weather_spc(weather, variable, cutoff=1 / 30, n_std=3):
    """Estimate robust SPC limits from short-term variation in the selected series."""
    series = weather.groupby("time")[variable].mean().sort_index()
    if not 0 < cutoff < 12 or n_std <= 0:
        raise ValueError("cutoff must be between 0 and 12 cycles/day; n_std must be positive.")

    # Removing low frequencies using the course's type-1 DCT and matching inverse.
    coefficients = dct(series.to_numpy(), type=1, norm="forward")
    frequencies = np.arange(len(series)) / (2 * (len(series) - 1) / 24)
    coefficients[frequencies < cutoff] = 0
    satv = idct(coefficients, type=1, norm="forward")

    # Estimating robust location and spread from the selected filtered period.
    center = trim_mean(satv, 0.05)
    sigma = 1.4826 * median_abs_deviation(satv)
    if sigma == 0:
        raise ValueError("MAD is zero; robust SPC limits cannot be estimated.")
    baseline = series - satv
    lower = baseline + center - n_std * sigma
    upper = baseline + center + n_std * sigma
    outside = (series < lower) | (series > upper)
    outliers = pd.DataFrame({variable: series, "lower": lower, "upper": upper}).loc[outside]
    summary = pd.Series({"hours": len(series), "outlier_hours": int(outside.sum()),
                         "outlier_percent": 100 * outside.mean(), "robust_sigma": sigma})

    # Displaying the limits on the original hourly scale.
    fig = weather_figure(series, outliers)
    for name, limit in (("Lower limit", lower), ("Upper limit", upper)):
        fig.add_trace(go.Scattergl(x=series.index, y=limit, name=name,
                                   line={"color": "gray", "dash": "dash", "width": 1}))
    return fig, outliers, summary


@st.cache_data(ttl=600, max_entries=16)
def weather_lof(weather, variable, outlier_fraction=0.01):
    """Fit LOF to hourly values of the selected property over the available period."""
    series = weather.groupby("time")[variable].mean().sort_index()

    # Following the course's 20-neighbour LOF, with a configurable anomaly fraction.
    model = LocalOutlierFactor(n_neighbors=20, contamination=outlier_fraction)
    anomalous = model.fit_predict(series.to_numpy().reshape(-1, 1)) == -1
    results = pd.DataFrame({variable: series,
                            "lof_score": -model.negative_outlier_factor_})
    outliers = results.loc[anomalous].sort_values("lof_score", ascending=False)
    summary = pd.Series({"hours": len(series), "outlier_hours": int(anomalous.sum()),
                         "outlier_percent": 100 * anomalous.mean()})

    return weather_figure(series, outliers), outliers, summary
