"""Main entrypoint and navigation for the IND320 Streamlit app."""

import streamlit as st


# Configure shared browser settings before any page content is displayed.
st.set_page_config(
    page_title="IND320 Reservoir Statistics",
    page_icon=":material/water_drop:",
)

# Define all pages in one place. This gives the sidebar clear, explicit labels.
selected_page = st.navigation(
    [
        st.Page(
            "app_pages/front_page.py",
            title="Front Page",
            icon=":material/home:",
        ),
        st.Page(
            "app_pages/data_table.py",
            title="Data table",
            icon=":material/table_chart:",
        ),
        st.Page(
            "app_pages/interactive_chart.py",
            title="Interactive chart",
            icon=":material/analytics:",
        ),
        st.Page(
            "app_pages/project_information.py",
            title="Project information",
            icon=":material/info:",
        ),
    ],
    position="sidebar",
)

# Run the page selected in the sidebar.
selected_page.run()
