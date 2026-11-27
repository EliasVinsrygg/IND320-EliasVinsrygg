"""Share the regional choice between the analysis pages."""


def select_region(container, width="stretch"):
    """Display the area selector while keeping the same region across pages."""
    return container.selectbox(
        "Region", ["NO1", "NO2", "NO3", "NO4", "NO5", "VASS1", "VASS2", "VASS3"],
        index=2, key="selected_region", persist_state="session", width=width,
        help="NO1–NO5 are electricity price areas. VASS1–VASS3 are watercourse areas.",
    )
