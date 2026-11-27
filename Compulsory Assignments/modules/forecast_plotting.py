"""Draw NO3 history and progressively reveal the recursive forecast with Plotly."""

import pandas as pd
import plotly.graph_objects as go


def build_forecast_figure(history, forecast, coverage=0.8, reference=None):
    """Connect the historical line to a red forecast and an animated quantile band."""
    origin, last_value = history.index[-1], float(history.iloc[-1])

    def forecast_traces(count):
        # Anchoring every forecast path at the final observed value keeps the lines connected.
        part = forecast.iloc[:count]
        dates = [origin, *part.index]
        return [
            go.Scatter(x=dates, y=[last_value, *part["lower"]], mode="lines",
                       line={"width": 0}, showlegend=False, hoverinfo="skip"),
            go.Scatter(x=dates, y=[last_value, *part["upper"]], mode="lines",
                       line={"width": 0}, fill="tonexty", fillcolor="rgba(214,39,40,0.16)",
                       name=f"Nominal {coverage:.0%} quantile band", hoverinfo="skip"),
            go.Scatter(x=dates, y=[last_value, *part["prediction"]], mode="lines+markers",
                       line={"color": "#d62728", "width": 3}, marker={"size": 6},
                       name="Prediction", hovertemplate="%{x|%d %b %Y}: %{y:.1f}%<extra>Prediction</extra>"),
        ]

    # Keeping the full historical curve fixed while only the forecast traces are animated.
    figure = go.Figure(go.Scatter(x=history.index, y=history.values, mode="lines",
        line={"color": "#2878a6", "width": 2}, name="Observed fill level",
        hovertemplate="%{x|%d %b %Y}: %{y:.1f}%<extra>Observed</extra>"))
    figure.add_traces(forecast_traces(len(forecast)))
    if reference is not None:
        figure.add_trace(go.Scatter(x=reference.index, y=reference.values, mode="lines",
            line={"color": "#888888", "dash": "dot"}, name="52-week reference"))
    figure.frames = [go.Frame(name=str(i), data=forecast_traces(i), traces=[1, 2, 3])
                     for i in range(len(forecast) + 1)]
    # Opening on the final two historical years while retaining the full slider range.
    visible_start = max(history.index[0], origin - pd.DateOffset(years=2))
    axis_end = forecast.index[-1] + pd.Timedelta(days=7)
    figure.update_layout(
        height=540, hovermode="x unified",
        margin={"t": 30, "b": 80}, yaxis={"title": "Fill level (%)", "range": [0, 100]},
        xaxis={"title": "Week ending", "range": [visible_start, axis_end],
               "rangeslider": {"visible": True, "thickness": 0.08, "range": [history.index[0], axis_end]}},
        legend={"orientation": "h", "y": 1.12},
        updatemenus=[{"type": "buttons", "direction": "left", "x": 0, "y": -0.24,
            "buttons": [
                {"label": "Play forecast", "method": "animate", "args": [None,
                    {"frame": {"duration": 700, "redraw": False}, "transition": {"duration": 0},
                     "fromcurrent": False, "mode": "immediate"}]},
                {"label": "Pause", "method": "animate", "args": [[None],
                    {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]},
            ]}],
    )
    figure.add_vline(x=origin.timestamp() * 1000, line_dash="dash", line_color="#888888")
    return figure
