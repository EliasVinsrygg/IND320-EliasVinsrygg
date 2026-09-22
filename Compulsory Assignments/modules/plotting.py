"""Reusable plotting functions for the IND320 reservoir analysis."""

import matplotlib.pyplot as plt
import pandas as pd


def plot_national_overview(data: pd.DataFrame, title: str) -> None:
    """Plot national reservoir measurements in two aligned panels.

    The upper panel combines fill levels in percent with energy measurements in
    TWh on a second y-axis. The lower panel shows weekly fill-level change in
    percentage points. The caller decides which time period to provide.
    """
    fig, (ax_levels, ax_change) = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        sharex=True,
        height_ratios=[3, 1],
    )

    # Plot fill levels as percentages on the left axis of the upper panel.
    fill_line = ax_levels.plot(
        data["date"],
        data["fill_level_ratio"] * 100,
        color="#1f77b4",
        label="Fill level",
        linewidth=1.8,
    )[0]
    previous_fill_line = ax_levels.plot(
        data["date"],
        data["previous_week_fill_level_ratio"] * 100,
        color="#ff7f0e",
        label="Previous-week fill level",
        linewidth=1.3,
        linestyle="--",
    )[0]
    ax_levels.set_ylabel("Fill level (%)")
    ax_levels.grid(alpha=0.3)

    # Plot stored energy and the constant capacity in TWh on the right axis.
    ax_energy = ax_levels.twinx()
    stored_energy_line = ax_energy.plot(
        data["date"],
        data["stored_energy_twh"],
        color="#2ca02c",
        label="Stored energy",
        linewidth=1.8,
    )[0]
    capacity_line = ax_energy.plot(
        data["date"],
        data["capacity_twh"],
        color="#555555",
        label="Capacity",
        linewidth=1.5,
        linestyle=":",
    )[0]
    ax_energy.set_ylabel("Energy (TWh)")

    # Place the shared legend between panels to avoid covering data.
    top_lines = [fill_line, previous_fill_line, stored_energy_line, capacity_line]
    ax_levels.legend(
        top_lines,
        [line.get_label() for line in top_lines],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=2,
        frameon=False,
    )
    ax_levels.set_title(title)

    # Plot weekly fill-level change in its own lower panel.
    ax_change.plot(
        data["date"],
        data["weekly_fill_level_change"] * 100,
        color="#9467bd",
        linewidth=1.5,
    )
    ax_change.axhline(0, color="black", linewidth=0.8)
    ax_change.set_xlabel("Date")
    ax_change.set_ylabel("Weekly change (percentage points)")
    ax_change.grid(alpha=0.3)

    fig.autofmt_xdate()
    plt.tight_layout()
    fig.subplots_adjust(hspace=0.55)
    plt.show()
