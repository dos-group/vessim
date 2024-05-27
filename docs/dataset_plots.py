import pandas as pd
import plotly.io
import plotly.graph_objects as go

import vessim as vs

signal = vs.HistoricalSignal.from_dataset("watttime2023_caiso-north")
df = pd.read_csv("~/.cache/vessim/watttime2023_caiso-north_actual.csv", index_col=0)
df.index = pd.to_datetime(df.index)
fig = go.Figure()
fig.add_trace(go.Scatter(x=df.index, y=df["value"]))
fig.update_layout(
    {
        "margin": {"l": 0, "t": 0, "b": 0, "r": 0},
        "autosize": True,
        "yaxis_title": "g/kWh",
    }
)
plotly.io.write_html(fig, "./_static/watttime2023_caiso-north_plot.html")

solcast = ["global", "germany"]
for s in solcast:
    signal = vs.HistoricalSignal.from_dataset(f"solcast2022_{s}")
    df = pd.read_csv(f"~/.cache/vessim/solcast2022_{s}_actual.csv", index_col=0)
    df.index = pd.to_datetime(df.index)
    fig = go.Figure()
    for col in df.columns:
        visible = True if col == "Berlin" else "legendonly"
        fig.add_trace(
            go.Scatter(x=df.index, y=df[col], visible=visible, name=col)
        )
    fig.update_layout(
        {
            "margin": {"l": 0, "t": 0, "b": 0, "r": 0},
            "autosize": True,
            "showlegend": True,
            "yaxis_title": r"% of max output",
            "legend_y": 0.5,
            "legend_yanchor": "middle",
        }
    )
    plotly.io.write_html(fig, f"./_static/solcast2022_{s}_plot.html")
