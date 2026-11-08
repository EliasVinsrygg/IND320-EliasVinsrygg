"""Reusing CA3's weekly reservoir analyses for the Streamlit app."""

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
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

    # Following the course's fit-and-plot workflow with adjustable smoothers.
    result = STL(filling, period=52, seasonal=seasonal, trend=trend, robust=robust).fit()
    fig = result.plot()
    fig.set_size_inches(12, 8)
    fig.tight_layout()
    return fig


@st.cache_data(ttl=3600, max_entries=16)
def reservoir_spectrogram(filling, window_length=260, window_overlap=208):
    """Return a spectrogram of weekly filling percentages; window sizes are weeks."""
    # Keeping the same regular weekly timeline as STL, including ISO week 53.
    filling = filling.sort_index().asfreq("7D")
    if not np.isfinite(filling.to_numpy()).all():
        raise ValueError("The filling series must contain complete, finite weekly observations.")
    if not 2 <= window_length <= len(filling) or not 0 <= window_overlap < window_length:
        raise ValueError("Use 2 <= window_length <= series length and 0 <= overlap < window_length.")

    # Following the course's specgram example; centring each window removes its mean level.
    fig, ax = plt.subplots(figsize=(12, 5))
    _, _, _, image = ax.specgram(
        filling.to_numpy(), Fs=1, NFFT=window_length, noverlap=window_overlap,
        detrend="mean", scale="dB"
    )
    ax.set(title="Reservoir filling spectrogram", xlabel="Weeks since start",
           ylabel="Frequency (cycles/week)")
    fig.colorbar(image, ax=ax, label="Power spectral density (dB)")
    fig.tight_layout()
    return fig
