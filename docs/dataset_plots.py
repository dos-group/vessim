import plotly.io
import vessim as vs
from vessim.plot import plot_trace

# Generate carbon intensity plot
carbon_trace = vs.Trace.load("watttime2023_caiso-north")
fig_carbon = plot_trace(carbon_trace, dataset_name="watttime2023_caiso-north")
fig_carbon.update_layout(margin={"l": 0, "t": 0, "b": 0, "r": 0})
plotly.io.write_html(fig_carbon, "./_static/watttime2023_caiso-north_plot.html")

# Generate solar plots
solcast_datasets = ["global", "germany"]
for dataset in solcast_datasets:
    dataset_name = f"solcast2022_{dataset}"
    trace = vs.Trace.load(dataset_name)
    fig = plot_trace(trace, default_visible="Berlin", dataset_name=dataset_name)
    fig.update_layout(
        margin={"l": 0, "t": 0, "b": 0, "r": 0},
        legend_y=0.5,
        legend_yanchor="middle"
    )
    plotly.io.write_html(fig, f"./_static/solcast2022_{dataset}_plot.html")
