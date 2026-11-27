# IND320 Energy and Weather

A Streamlit app and four coursework notebooks for the IND320 Data to Decision course. The app explores Norwegian reservoir filling, regional weather and cross-border electricity flows.

[GitHub repository](https://github.com/EliasVinsrygg/IND320-EliasVinsrygg) · [Hosted Streamlit app](https://ind320-eliasvinsrygg.streamlit.app/)

## App pages

| Page | What you can do |
| --- | --- |
| **Home** | Open Explore, Analyse or Forecast from the preview cards. |
| **Explore** | Choose a week from 2016 onwards and colour the map by reservoir filling, temperature or precipitation. Click a Norwegian area for reservoir statistics or a connected country for annual energy and monthly power flows. |
| **Analyse** | Choose a region and switch between Filling STL, Filling Spectrogram, Weather SATV, Weather LOF and Weather and reservoir correlation. |
| **Forecast** | Adjust the training period, forecast horizon, model settings and sources for NO3. The River forecast opens in weekly steps and shows an animated prediction and an uncertainty band estimated from past forecast errors. |
| **Project information** | Find the project links, data sources and methods. |

## Run locally

Use Python 3.12 and uv. Run the commands from the repository root so Streamlit finds the shared theme and local secrets.

```powershell
uv sync
uv run streamlit run "Compulsory Assignments/streamlit_app.py"
```

Create `.streamlit/secrets.toml` in the repository root. Set your MongoDB connection string and, to enable the forecast's source updates, your ENTSO-E token.

```toml
[mongo]
uri = "YOUR_MONGODB_CONNECTION_STRING"

[entsoe]
security_token = "YOUR_ENTSO_E_TOKEN"
```

The local secrets file is ignored by Git. For Streamlit Community Cloud, enter these values in the app's secrets settings. Use read access for the saved datasets and grant write access to the relevant collections if you enable downloads or forecast updates.

## Data and updates

| Source | How the app uses it |
| --- | --- |
| **NVE Magasinstatistikk** | Reservoir observations come from the API and are cached for one hour. |
| **ENTSO-E Transparency Platform** | Explore reads monthly country-pair energy and power records for 2024 and 2025 from `ind320_ca2.monthly_flows`. |
| **Open-Meteo ERA5** | Analyse reads hourly means for 100 fixed points per region from `ind320_ca3.weather_hourly`. Explore and correlation can use the prepared weekly weather in `ind320_ca4.map_weather_weekly`. Where needed, the app uses the available hourly data to calculate weekly means and totals. |
| **NO3 forecast inputs** | The forecast reads the weekly NVE, Open-Meteo, Norges Bank and ENTSO-E values from `ind320_ca4.no3_weekly`. |

In **Analyse**, the weather tabs can show saved hourly data for the current year. Downloads for missing historical years require confirmation and are subject to shared limits recorded in `ind320_ca3.weather_download_control`.

In **Forecast**, **Observation data → Update data** checks the four sources and appends complete weeks. The app records one completed check per window beginning Monday at 06:00 Oslo time in `ind320_ca4.refresh_status`. Its default forecast starts at the latest complete week available to the model.

The Norwegian overlays are based on the original boundaries in `assets/shapefiles/`. The six country overlays use [Natural Earth Vector v5.1.1](https://github.com/nvkelso/natural-earth-vector/blob/v5.1.1/geojson/ne_50m_admin_0_countries.geojson). The app reads the prepared GeoJSON files in `assets/`.

## Repository layout

- `notebooks/` contains CA1 to CA4, including the modelling experiments and design sketch.
- `app_pages/` contains the five Streamlit pages. `modules/` contains the data loaders, chart functions and analysis code.
- `assets/` contains the map polygons, fixed weather coordinates and home page previews.
- `data/ca4/no3_weekly.csv` contains the historical forecast seed. Large raw weather and ENTSO-E checkpoints stay local. Some older weather files were already tracked and remain in the repository.
- `scripts/` contains optional data preparation tools that are run separately from the Streamlit app.

## Data preparation

Run the scripts from the repository root. For example, this command rebuilds the Norwegian map layer from the local shapefiles.

```powershell
uv run python "Compulsory Assignments/scripts/prepare_map_areas.py"
```

| Script | Purpose |
| --- | --- |
| [prepare_map_areas.py](scripts/prepare_map_areas.py) | Rebuild the Norwegian area GeoJSON from `assets/shapefiles/`. |
| [prepare_flow_countries.py](scripts/prepare_flow_countries.py) | Fetch the pinned Natural Earth source and rebuild the six country polygons. |
| [seed_no3_history.py](scripts/seed_no3_history.py) | Seed the weekly NO3 history in MongoDB from the local CSV. |
| [prepare_map_weather.py](scripts/prepare_map_weather.py) | Prepare the latest shared weather week for the map. |
| [backfill_price_weather.py](scripts/backfill_price_weather.py) | Fill missing 2026 weather weeks for the four price areas outside NO3. Use `--water-areas` for the three VASS areas. |

The two weather scripts can call Open-Meteo and write to MongoDB. The NO3 seed script also writes to MongoDB. All three use the existing app secrets.
