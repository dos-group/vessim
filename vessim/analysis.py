"""Utility functions for data analysis and plotting."""

import matplotlib.pyplot as plt  # type: ignore
import pandas as pd


def plot_basic_evaluation(data: pd.DataFrame, title: str = "Evaluation"):
    """Simple function for plotting of the simulation data.

    Args:
        data: The dataframe containing the simulation data.
        title: The title of the plot. Defaults to `Evaluation`.
    """
    data.index = pd.to_datetime(data.index)

    # Setup graph
    fig, axs = plt.subplots(ncols=1, nrows=5, sharex="col",sharey="row", figsize=(10,5.5))
    fig.tight_layout(pad=0)
    fig.align_ylabels()
    axs[0].set_title(title)

    # Create plots from data
    plot_production_and_consumption(axs[0], data["p_solar"], data["p_computing_system"])

    plot_production_consumption_delta(axs[1], data["p_solar"], data["p_computing_system"])

    plot_battery_soc(axs[2], data["battery_soc"], data["battery_min_soc"])

    plot_grid_power_usage(axs[3], data["p_grid"])

    ax3_twin = axs[3].twinx()
    plot_carbon_intensity(ax3_twin, data["carbon_intensity"])
    h1, l1 = axs[3].get_legend_handles_labels()
    h2, l2 = ax3_twin.get_legend_handles_labels()
    axs[3].legend(
        [h1[0], h2[0]], ["grid power usage", "carbon emission"], loc="best", frameon=False
    )

    plot_accumulated_emissions(axs[4], data["p_grid"], data["carbon_intensity"])


def plot_production_and_consumption(
        ax, p_prod, p_cons, prod_color="#6B9A6E", cons_color="#D65D62"
) -> None:
    """Create plot for showing production and consumption."""
    p_prod.plot(ax=ax, color=prod_color, label="production")
    (- p_cons).plot(ax=ax, color=cons_color, label="consumption", linestyle=":")
    ax.set_ylabel("power (W)")
    ax.legend(loc="best", frameon=False)


def plot_production_consumption_delta(
    ax, p_prod, p_cons, pos_color="#79AE7C", neg_color="#D65D62"
) -> None:
    """Create a plot for the power delta from production and consumption."""
    power_delta = p_prod + p_cons
    power_delta.plot(ax=ax, alpha=0)
    ax.fill_between(power_delta.index, 0, power_delta.values,
                        where=power_delta.values > 0, color=pos_color)  # type: ignore
    ax.fill_between(power_delta.index, 0, power_delta.values,
                        where=power_delta.values < 0, color=neg_color)  # type: ignore
    ax.set_ylabel("power\ndelta (W)")


def plot_battery_soc(
    ax, battery_soc, battery_min_soc, soc_color="#79AE7C", min_soc_color="black"
) -> None:
    """Create plot for battery state of charge with maximum discharge."""
    battery_soc.plot(ax=ax, alpha=0)
    ax.fill_between(battery_soc.index, 0, battery_soc.values * 100, color=soc_color)
    ax.set_ylim(0, 100)
    ax.set_ylabel("battery state\nof charge (%)")
    (battery_min_soc * 100).plot(
        ax=ax,
        linestyle="--",
        linewidth=.8,
        color=min_soc_color,
        label="minimum state of charge"
    )
    handles, lables = ax.get_legend_handles_labels()
    ax.legend(handles[1:], lables[1:], frameon=False)


def plot_grid_power_usage(ax, p_grid, power_color="#D65D62") -> None:
    """Create plot of used power from grid over time."""
    p_grid[p_grid > 0] = 0
    (-p_grid).plot(ax=ax, color=power_color, linestyle="-")
    ax.fill_between(p_grid.index, 0, (-p_grid).values.astype(float), color=power_color)
    ax.set_ylabel("grid power\nusage (W)")


def plot_carbon_intensity(ax, carbon_intensity, carbon_color="#333") -> None:
    """Create plot of carbon intensity over time."""
    carbon_intensity.plot(ax=ax, color=carbon_color, linewidth=.8)
    ax.set_ylabel("carbon intensity\n(gCO2/kWh)")


def plot_accumulated_emissions(
    ax, p_grid, carbon_intensity, carbon_color="#999"
) -> float:
    """Create plot of total carbon emission over time.

    Returns:
        The total emission over the whole simulation as float.
    """
    emissions = (-p_grid) * carbon_intensity  # 60 Ws * gCO2/kWh
    emissions /= 60000
    emissions.cumsum().plot(ax=ax, color="#555", linewidth=.8)
    ax.fill_between(emissions.index, emissions.cumsum().values, color=carbon_color)
    ax.set_ylabel("accumulated\nemissions\n(gCO2)")
    return emissions.sum()
