"""Reusing CA3's weekly reservoir analyses for the Streamlit app."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from scipy.signal import spectrogram
from statsmodels.tsa.seasonal import STL


@st.cache_data(ttl=3600, max_entries=16)
def reservoir_stl(filling, seasonal=7, trend=101, robust=True):
    """Return STL plot for a weekly filling series expressed in percent.

    seasonal smooths across annual cycles; trend is measured in weeks.
    Both smoother lengths must be odd; trend must exceed the 52-week period.
    """
    # Keeping all weeks, including week 53; 52 weeks approximates an annual cycle.
    filling = filling.sort_index().asfreq("7D")
    if len(filling) < 104 or not np.isfinite(filling.to_numpy()).all():
        raise ValueError("STL needs at least two years of complete weekly observations.")

    # Fitting the same STL model and displaying its four components on a shared time axis.
    result = STL(filling, period=52, seasonal=seasonal, trend=trend, robust=robust).fit()
    components = [
        ("Observed filling", result.observed, "%"),
        ("Trend", result.trend, "%"),
        ("Seasonal", result.seasonal, "pp"),
        ("Residual", result.resid, "pp"),
    ]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.065,
                        subplot_titles=[label for label, _, _ in components])
    for row, (label, values, unit) in enumerate(components, start=1):
        fig.add_trace(go.Scatter(x=filling.index, y=values, name=label, mode="lines",
                                 hovertemplate=f"%{{x|%d %b %Y}}<br>{label}: %{{y:.2f}} {unit}<extra></extra>"),
                      row=row, col=1)
        fig.update_yaxes(title_text=unit, row=row, col=1)
    fig.update_xaxes(title_text="Week ending", row=4, col=1)
    fig.update_layout(height=700, showlegend=False, margin=dict(t=42, b=50))
    return fig


@st.cache_data(ttl=3600, max_entries=16)
def reservoir_spectrogram(filling, window_length=260, window_overlap=208):
    """Return a spectrogram of weekly filling percentages; window sizes are weeks."""
    # Keeping the same regular weekly timeline as STL, including ISO week 53.
    filling = filling.sort_index().asfreq("7D")
    if not np.isfinite(filling.to_numpy()).all():
        raise ValueError("The filling series must contain complete, finite weekly observations.")
    if not 3 <= window_length <= len(filling) or not 0 <= window_overlap < window_length:
        raise ValueError("Use a window of at least three weeks and no more than the available series length. "
                         "Overlap must be shorter than the window.")

    # Matching the previous specgram's Hann window, mean removal and one-sided density.
    frequencies, weeks, power = spectrogram(
        filling.to_numpy(), fs=1, window=np.hanning(window_length), nperseg=window_length,
        noverlap=window_overlap, detrend="constant", scaling="density", mode="psd")
    # Leaving zero power blank because it has no finite value in decibels.
    power_db = 10 * np.log10(np.where(power > 0, power, np.nan))
    if not np.isfinite(power_db).any():
        raise ValueError("No spectral power is visible for this window and filling series.")
    fig = go.Figure(go.Heatmap(
        x=weeks, y=frequencies, z=power_db, colorscale="Viridis",
        colorbar=dict(title="PSD (dB)", thickness=14),
        hovertemplate=("Window centre: week %{x:g}<br>Frequency: %{y:.4f} cycles/week"
                       "<br>Power spectral density: %{z:.1f} dB<extra></extra>"),
        hoverongaps=False,
    ))
    # Letting the heatmap fill the page width with a shorter height for a rectangular view.
    fig.update_layout(title="Reservoir filling spectrogram", xaxis_title="Weeks since start",
                      yaxis_title="Frequency (cycles/week)", height=380, margin=dict(l=65, r=30, t=55, b=55))
    return fig
