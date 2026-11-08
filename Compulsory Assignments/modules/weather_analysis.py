"""Reusing CA3's precipitation SPC and temperature LOF analyses for the app."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.fft import dct, idct
from scipy.stats import median_abs_deviation, trim_mean
from sklearn.neighbors import LocalOutlierFactor


@st.cache_data(ttl=600, max_entries=16)
def precipitation_spc(weather, cutoff=1 / 30, n_std=3):
    """Plot hourly regional precipitation with robust DCT-based SPC limits.

    Input contains one complete year of UTC hourly points or regional means.
    cutoff is in cycles/day; 1/30 removes periods longer than 30 days.
    Returns the figure, outlier table and whole-year summary.
    """
    # Averaging point data, or keeping existing hourly regional means unchanged, in mm.
    rain = weather.groupby("time")["precipitation"].mean().sort_index()
    if not 0 < cutoff < 12 or n_std <= 0:
        raise ValueError("cutoff must be between 0 and 12 cycles/day; n_std must be positive.")

    # Removing low frequencies using the course's type-1 DCT and matching inverse.
    coefficients = dct(rain.to_numpy(), type=1, norm="forward")
    frequencies = np.arange(len(rain)) / (2 * (len(rain) - 1) / 24)
    coefficients[frequencies < cutoff] = 0
    satv = idct(coefficients, type=1, norm="forward")

    # Estimating robust location and spread from the entire filtered year.
    center = trim_mean(satv, 0.05)
    sigma = 1.4826 * median_abs_deviation(satv)
    if sigma == 0:
        raise ValueError("MAD is zero; robust SPC limits cannot be estimated.")
    baseline = rain - satv
    lower = baseline + center - n_std * sigma
    upper = baseline + center + n_std * sigma
    outside = (rain < lower) | (rain > upper)
    outliers = pd.DataFrame({"precipitation": rain, "lower": lower, "upper": upper}).loc[outside]
    summary = pd.Series({"hours": len(rain), "outlier_hours": int(outside.sum()),
                         "outlier_percent": 100 * outside.mean(), "robust_sigma_mm": sigma})

    # Showing the original precipitation and shifted limits, without plotting SATV.
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(rain.index, rain, label="Mean precipitation", linewidth=0.7)
    ax.plot(rain.index, lower, "--", color="gray", label="SPC limits")
    ax.plot(rain.index, upper, "--", color="gray")
    ax.scatter(outliers.index, outliers["precipitation"], color="red", s=12, label="Outliers", zorder=3)
    ax.set(xlabel="Time (UTC)", ylabel="Precipitation (mm/hour)", title="Precipitation: DCT and robust SPC")
    ax.legend()
    fig.tight_layout()
    return fig, outliers, summary


@st.cache_data(ttl=600, max_entries=16)
def temperature_lof(weather, outlier_fraction=0.01):
    """Plot hourly mean temperature and return LOF anomalies and a summary.

    Neighbours are similar temperatures across the entire input period.
    Time is used for plotting only; no temporal or seasonal features are fitted.
    """
    # Averaging point data, or keeping existing hourly regional means unchanged.
    temperature = weather.groupby("time")["temperature_2m"].mean().sort_index()

    # Following the course's 20-neighbour LOF, with a configurable anomaly fraction.
    model = LocalOutlierFactor(n_neighbors=20, contamination=outlier_fraction)
    anomalous = model.fit_predict(temperature.to_numpy().reshape(-1, 1)) == -1
    results = pd.DataFrame({"temperature_2m": temperature,
                            "lof_score": -model.negative_outlier_factor_})
    outliers = results.loc[anomalous].sort_values("lof_score", ascending=False)
    summary = pd.Series({"hours": len(temperature), "outlier_hours": int(anomalous.sum()),
                         "outlier_percent": 100 * anomalous.mean()})

    # Highlighting anomalies on the original temperature curve in degrees Celsius.
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(temperature.index, temperature, label="Mean temperature", linewidth=0.7)
    ax.scatter(outliers.index, outliers["temperature_2m"], color="red", s=12, label="LOF anomalies", zorder=3)
    ax.set(xlabel="Time (UTC)", ylabel="Temperature (degrees C)", title="Temperature: Local Outlier Factor")
    ax.legend()
    fig.tight_layout()
    return fig, outliers, summary
