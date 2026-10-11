# IND320 Compulsory Assignment 1

- [Public GitHub repository](https://github.com/EliasVinsrygg/IND320-EliasVinsrygg)
- [Published Streamlit app](https://ind320-eliasvinsrygg.streamlit.app/)

An interactive exploration of weekly Norwegian reservoir statistics for the
IND320 Data to Decision course.

## Contents

- A Jupyter Notebook for the analysis in `notebooks/reservoirs_analysis.ipynb`.
- A four-page Streamlit app with data table and interactive Plotly charts.
- Regional electricity price-area (EL) and watercourse-area (VASS) views,
  alongside the national Norway (NO-0) reference series.

## Run locally

From the repository root:

```powershell
uv sync
uv run streamlit run "Compulsory Assignments/streamlit_app.py"
```

Always start Streamlit from `IND320/`, rather than `Compulsory Assignments/`.
Project settings are kept together in the repository root:

```text
IND320/
  .streamlit/
    config.toml
    secrets.toml  # Local credentials; ignored by Git.
  pyproject.toml
  uv.lock
  Compulsory Assignments/
    streamlit_app.py
    app_pages/
    modules/
    notebooks/
    data/
```

### Local MongoDB credentials

Edit `.streamlit/secrets.toml` in the repository root and set the `[mongo]`
section's `uri` value to your Atlas connection string. Replace the database
password placeholder locally. The initial empty value must be filled before
connecting to MongoDB. Do not share the file or include credentials in notebook
outputs. This format follows the course's MongoDB example using
`st.secrets["mongo"]["uri"]`.

For the hosted app, enter the same TOML configuration in Streamlit Community
Cloud's secrets settings; the local file is not uploaded through Git.

## Data

The app reads the local `data/reservoirs.csv` dataset. It caches the source
data and translates the supplied Norwegian column names for presentation.
