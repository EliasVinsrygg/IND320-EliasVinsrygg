# IND320 Compulsory Assignments 1–3

- [Public GitHub repository](https://github.com/EliasVinsrygg/IND320-EliasVinsrygg)
- [Published Streamlit app](https://ind320-eliasvinsrygg.streamlit.app/)

An interactive exploration of Norwegian reservoirs, regional weather and
cross-border electricity flows for the IND320 Data to Decision course.

## Contents

- Analysis notebooks in `notebooks/CA1.ipynb`, `CA2.ipynb` and `CA3.ipynb`.
- A seven-page Streamlit app with dataset previews, charts, STL, spectrograms,
  precipitation SPC and temperature LOF.
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
    assets/        # Fixed weather coordinates required by the app.
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

### Local ENTSO-E security token

In the repository root's `.streamlit/secrets.toml`, add your ENTSO-E security
token as the `security_token` value under `[entsoe]`. The section is already
present locally with an empty value ready to fill in. Keep the token out of
notebooks, outputs, screenshots, and commits. The local secrets file is ignored
by Git; if the hosted app needs the token later, add the same section in
Streamlit Community Cloud's secrets settings.

## Data

Reservoir data come directly from NVE and are cached for one hour. Country-pair
flow records are read from `ind320_ca2.monthly_flows` in MongoDB. Hourly regional
weather means are read from `ind320_ca3.weather_hourly` and cached for ten minutes.

Weather analysis supports completed years from 1940 onwards. Missing data require
confirmation in a dialog before an ERA5 request for 100 fixed points. Successful
results are saved in MongoDB for other users. The connection needs read/write
access to `ind320_ca3.weather_hourly` and `ind320_ca3.weather_download_control`.
The latter stores only timestamps, counts and timing measurements; all rules
and executable code are Python files in `modules/` and `app_pages/`.

App download limits are shared: 90 seconds after an attempt, a one-hour pause
after nine attempts within an hour, and at most 19 attempts in a rolling 24 hours.
Failed API attempts also count. Local responses are reused after interrupted
saves without another API call. HTTP 429 stops without automatic retries and
sets a shared pause. Usage by notebooks or other tools is not automatically
included in the app's counters; the external API can still reject requests.

The dialog's initial processing estimate is one minute; later estimates use the
last successful app download duration. These are estimates, not guaranteed times.
The app uses `assets/weather_locations.json` and does not import notebooks or
need shapefiles. Local raw-weather checkpoints under `data/weather/` are optional
for the app and are excluded from Git.
