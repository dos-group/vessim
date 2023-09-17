"""Utility functions for data analysis and plotting."""

import matplotlib.pyplot as plt  # type: ignore
import pandas as pd

RED = "#D65D62"
GREEN = "#79AE7C"
DARK_GRAY = "#333"
LIGHT_GRAY = "#ddd"


def plot_evaluation(data: pd.DataFrame, title: str = "Evaluation"):
    """Simple function for plotting of the simulation data.

    Args:
        data: The dataframe containing the simulation data.
        title: The title of the plot. Defaults to `Evaluation`
    """
    data.index = pd.to_datetime(data.index)

    # Setup graph
    fig, axs = plt.subplots(ncols=1, nrows=5, sharex="col",sharey="row", figsize=(10,5.5))
    fig.tight_layout(pad=0)
    fig.align_ylabels()
    axs[0].set_title(title)

    # Unpack data
    p_prod = data["p_solar"]
    p_computing_system = - data["p_computing_system"]
    p_grid = -data["p_grid"]
    battery_soc = data["battery_soc"]
    battery_min_soc = data["battery_min_soc"] * 100
    carbon = data["carbon_intensity"]

    # Plot Production and Consumption
    p_prod.plot(ax=axs[0], color="#6b9a6e", label="production")
    p_computing_system.plot(ax=axs[0], color="RED", label="consumption", linestyle=":")
    axs[0].set_ylabel("power (W)")
    axs[0].legend(loc="best", frameon=False)

    # Plot Production/Consumption delta
    power_delta = p_prod - p_computing_system
    power_delta.plot(ax=axs[1], alpha=0)
    axs[1].fill_between(power_delta.index, 0, power_delta.values,
                        where=power_delta.values > 0, color=GREEN)  # type: ignore
    axs[1].fill_between(power_delta.index, 0, power_delta.values,
                        where=power_delta.values < 0, color=RED)  # type: ignore
    axs[1].set_ylabel("power\ndelta (W)")

    # Plot Battery State of Charge
    battery_soc.plot(ax=axs[2], alpha=0)
    axs[2].fill_between(battery_soc.index, 0, battery_soc.values * 100,  # type: ignore
                        color=GREEN)
    axs[2].set_ylim(0, 100)
    axs[2].set_ylabel("battery state\nof charge (%)")
    battery_min_soc.plot(
        ax=axs[2], linestyle="--", linewidth=.8, color="black", label="min_soc"
    )
    handles, lables = axs[2].get_legend_handles_labels()
    axs[2].legend(handles[1:], lables[1:], frameon=False)

    # Plot grid power and carbon emission
    p_grid[p_grid < 0] = 0
    p_grid.plot(ax=axs[3], color=RED, linestyle="-")
    axs[3].fill_between(p_grid.index, 0, p_grid.values.astype(float), color=RED)
    axs[3].set_ylabel("grid power\nusage (W)")
    ax3_twin = axs[3].twinx()
    carbon.plot(ax=ax3_twin, color=DARK_GRAY, linewidth=.8)
    ax3_twin.set_ylabel("carbon intensity\n(gCO2/kWh)")
    h1, l1 = axs[3].get_legend_handles_labels()
    h2, l2 = ax3_twin.get_legend_handles_labels()
    axs[3].legend(
        [h1[0], h2[0]], ["grid power usage", "carbon emission"], loc="best", frameon=False
    )

    # Plot accumulated carbon emission
    emissions = p_grid * carbon  # 60 Ws * gCO2/kWh  //  gCO2/60000 // kgCO2/60000/1000
    emissions /= 60000
    emissions.cumsum().plot(ax=axs[4], color="black", linewidth=.8)
    axs[4].fill_between(emissions.index, emissions.cumsum().values, color=LIGHT_GRAY)
    axs[4].set_ylabel("accumulated\nemissions (gCO2)")
