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

## Data

The app reads the local `data/reservoirs.csv` dataset. It caches the source
data and translates the supplied Norwegian column names for presentation.
