"""Shared NO3 River model used by CA4 and the forecast page."""

import numpy as np
import pandas as pd

# Defining a small NO3-only forecast with explicit training and model settings.
from river import linear_model, optim, preprocessing, time_series

# Naming the supported variables so the interface never exposes target-derived measurements.
EXOGENOUS_LABELS = {
    "temperature_c": "Temperature (C)", "precipitation_mm": "Precipitation (mm/week)",
    "eur_nok": "EUR/NOK", "usd_nok": "USD/NOK",
}
for neighbour in ("se2", "no5", "no1", "no4"):
    for direction in ("import", "export"):
        EXOGENOUS_LABELS[f"no3_{neighbour}_{direction}_mwh"] = (
            f"{neighbour.upper()} {'to NO3' if direction == 'import' else 'from NO3'} (MWh/week)")

def normal_weather_scenario(history_weather, dates):
    """Use training-history ISO-week means as a NO3 weather scenario, not a weather forecast."""
    # Averaging only past observations; keeping precipitation as a weekly total in mm.
    means = history_weather.groupby(history_weather.index.isocalendar().week.to_numpy()).mean()
    # Estimating the occasional week 53 from the adjacent winter weeks in training.
    if 53 not in means.index and {52, 1}.issubset(means.index):
        means.loc[53] = means.loc[[52, 1]].mean()
    scenario = means.reindex(dates.isocalendar().week.to_numpy()).set_axis(dates)
    if scenario.isna().any().any():
        raise ValueError("No training-weather mean for a forecast ISO week; inspect week 53 if relevant.")
    return scenario


def four_week_inputs(table):
    """Aggregate four weekly inputs, keeping rates/temperature as means and energy/rain as sums."""
    # Using blocks ending on the existing Sunday labels, rather than inventing calendar months.
    if not len(table.columns):
        return table.iloc[3::4]
    rules = {c: "sum" if c == "precipitation_mm" or c.endswith("_mwh") else "mean" for c in table}
    return table.groupby(np.arange(len(table)) // 4).agg(rules).set_axis(table.index[3::4])


def forecast_no3(data, origin, p=4, sp=0, history_weeks=260, horizon_weeks=13,
                 learning_rate=0.01, sd=0, use_weather=False, use_currency=False, use_flows=False,
                 step_weeks=1, d=0, q=0, sq=0, season_steps=None,
                 exogenous_columns=None, quantile=None):
    """Forecast NO3 with selected sources at weekly or four-week intervals."""
    # Requiring whole blocks and enough history for seasonal differencing and lag inputs.
    if step_weeks not in (1, 4) or history_weeks % step_weeks or horizon_weeks % step_weeks:
        raise ValueError("Use step_weeks=1 or 4 and history/horizon divisible by that step.")
    season = int(season_steps) if season_steps is not None else 52 // step_weeks
    if season < 1:
        raise ValueError("The seasonal period must be positive.")
    history = data.loc[:origin, "filling_percent"].tail(history_weeks)
    if sd not in (0, 1) or history_weeks // step_weeks <= d + season * sd + max(p, q, season * sp, season * sq) or horizon_weeks < 1:
        raise ValueError("Use sd=0 or 1, sufficient history for differencing/lags, and a positive horizon.")
    if len(history) != history_weeks or history.isna().any():
        raise ValueError("The training history must contain all requested weekly values.")

    # Selecting sources and filling missing flow inputs from earlier observations in a copy.
    weather_columns = ["temperature_c", "precipitation_mm"] if use_weather else []
    currency_columns = ["eur_nok", "usd_nok"] if use_currency else []
    flow_columns = [c for c in data if c.startswith("no3_") and c.endswith("_mwh")] if use_flows else []
    if use_flows and len(flow_columns) != 8:
        raise ValueError("Expected the eight NO3 neighbour-flow columns.")
    columns = weather_columns + currency_columns + flow_columns
    if exogenous_columns is not None:
        columns = list(exogenous_columns)
        if not set(columns).issubset(EXOGENOUS_LABELS):
            raise ValueError("Choose only the supported weather, currency and NO3 flow inputs.")
        weather_columns = [c for c in columns if c in ("temperature_c", "precipitation_mm")]
        flow_columns = [c for c in columns if c.endswith("_mwh")]
        use_weather = bool(weather_columns)
    inputs = data.loc[:origin, columns].copy()
    inputs[flow_columns] = inputs[flow_columns].ffill()
    inputs = inputs.loc[history.index]
    if inputs.isna().any().any():
        raise ValueError("An input has no past value; choose a later origin or shorter history.")

    # Building weekly scenarios first, preserving the original calendar-week weather assumptions.
    dates = pd.date_range(history.index[-1] + pd.Timedelta(weeks=1),
                          periods=horizon_weeks, freq="W-SUN", name="date")
    future = pd.DataFrame({c: inputs[c].iloc[-1] for c in columns}, index=dates)
    if use_weather:
        future[weather_columns] = normal_weather_scenario(inputs[weather_columns], dates)
    if step_weeks == 4:
        # Keeping filling as an end-of-period snapshot; aggregating the other input quantities.
        history = history.groupby(np.arange(len(history)) // 4).last().set_axis(history.index[3::4])
        inputs, future = four_week_inputs(inputs), four_week_inputs(future)
        dates = dates[3::4]

    # Learning on levels or seasonal differences, then forecasting recursively without future truth.
    target = history.copy()
    for _ in range(sd):
        target = target.diff(season)
    for _ in range(d):
        target = target.diff()
    # Initializing quantile models on training quantiles, rather than the point model's mean.
    initial_value = target.quantile(quantile) if quantile is not None else target.mean()
    loss = optim.losses.Quantile(quantile) if quantile is not None else None
    regressor = preprocessing.StandardScaler() | linear_model.LinearRegression(
        optimizer=optim.SGD(learning_rate), intercept_init=float(initial_value), loss=loss)
    model = time_series.SNARIMAX(p=p, d=d, q=q, m=season, sp=sp, sd=sd, sq=sq, regressor=regressor)
    for date, filling in history.items():
        model.learn_one(float(filling), x=inputs.loc[date].to_dict() if columns else None)
    forecast = pd.Series(model.forecast(horizon=len(dates),
                         xs=future.to_dict("records") if columns else None), index=dates, name="prediction")
    # Applying physical bounds to returned predictions; keeping River's internal recursion unchanged.
    return forecast.clip(lower=0, upper=100), model


def forecast_quantiles(data, origin, coverage=0.8, **settings):
    """Estimate each horizon's error radius from completed historical forecasts."""
    if not 0 < coverage < 1:
        raise ValueError("Choose coverage between zero and one.")
    past = data.loc[:origin]
    point, _ = forecast_no3(past, origin, **settings)
    if not np.isfinite(point).all():
        raise ValueError("Unstable forecast. Reduce the model orders or learning rate.")

    # Replaying the same model at up to 20 earlier origins spaced four weeks apart.
    history = settings.get("history_weeks", 260)
    horizon = settings.get("horizon_weeks", 13)
    origins = past.index[history - 1:-horizon][::-4][:20]
    errors = []
    for earlier in origins:
        try:
            predicted, _ = forecast_no3(past, earlier, **settings)
        except ValueError as error:
            # Skipping origins with unavailable past flows or a missing weather week.
            if str(error).startswith(("An input has no past value", "No training-weather mean")):
                continue
            raise
        absolute_errors = (past.loc[predicted.index, "filling_percent"] - predicted).abs()
        if np.isfinite(absolute_errors).all():
            errors.append(absolute_errors.to_numpy())

    # Fitting a constant radius per horizon by minimizing River quantile loss on observed errors.
    radius = np.full(len(point), np.nan)
    if len(errors) >= 5:
        loss = optim.losses.Quantile(coverage)
        for i, samples in enumerate(np.asarray(errors).T):
            # Finding the first error where the right-hand quantile-loss slope reaches zero.
            for candidate in sorted(samples):
                right = np.nextafter(float(candidate), np.inf)
                if sum(loss.gradient(float(e), right) for e in samples) >= -1e-10:
                    radius[i] = candidate
                    break
    result = pd.DataFrame({"prediction": point, "lower": (point - radius).clip(lower=0),
                           "upper": (point + radius).clip(upper=100)})
    result.attrs["calibration_origins"] = len(errors)
    return result
