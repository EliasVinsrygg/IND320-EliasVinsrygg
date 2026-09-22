"""Data-table page for the IND320 reservoir statistics app."""

import streamlit as st

from modules.data_loader import build_column_summary, load_reservoir_data


st.header("Reservoir data table")
st.write(
    "Each row represents one imported data column. The sparklines show the "
    "first calendar month for Norway as a whole (NO-0)."
)
st.caption(
    "Only measurement columns receive a line chart. Dates, labels and identifiers "
    "remain visible as rows, but are not converted into misleading numeric charts."
)

# Reserve the table location before loading; the cached loader avoids repeated disk reads.
table_slot = st.container()
with table_slot.skeleton():
    reservoir_data = load_reservoir_data()
    column_summary, first_month = build_column_summary(reservoir_data)

table_slot.dataframe(
    column_summary,
    column_config={
        "Column": st.column_config.TextColumn("Column", pinned=True),
        "Description": st.column_config.TextColumn("Description", width="medium"),
        "First month series": st.column_config.LineChartColumn(
            f"{first_month.strftime('%B %Y')} series",
            help="Four weekly observations from the national reservoir series.",
            width="medium",
            color="blue",
        ),
        "Chart note": st.column_config.TextColumn("Chart note", width="medium"),
    },
    hide_index=True,
    key="column_summary_table",
)
