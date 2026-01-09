"""Plotting utilities for Vessim datasets and signals."""

from typing import Any, Optional, cast

import pandas as pd
import plotly.graph_objects as go
from plotly.graph_objects import Figure
from plotly.subplots import make_subplots

from vessim.signal import Trace


def plot_trace(
    trace: Trace,
    title: Optional[str] = None,
    default_visible: Optional[str] = None,
    scale: Optional[float] = None,
    y_axis_title: Optional[str] = None,
    dataset_name: Optional[str] = None,
) -> Figure:
    """Plot a Vessim Trace using Plotly.

    Args:
        trace: Vessim Trace object to plot
        title: Plot title. If None, auto-generated from dataset name.
        default_visible: Column name to show by default. Others will be in legend-only mode.
        scale: Optional scaling factor for values
        y_axis_title: Y-axis label. If None, auto-detected based on dataset type.
        dataset_name: Optional dataset name for auto-generating titles and labels

    Returns:
        Plotly Figure object
    """
    # Reconstruct DataFrame from trace's internal data
    df_data = {}
    for col_name in trace.columns():
        times, values = trace._actual[col_name]
        df_data[col_name] = pd.Series(values, index=pd.to_datetime(times))

    df = pd.DataFrame(df_data)

    # Apply scaling if specified
    if scale is not None:
        df = df * scale

    # Auto-generate title if not provided
    if title is None:
        title = _generate_title(dataset_name or "Dataset")

    # Auto-detect y-axis title if not provided
    if y_axis_title is None:
        y_axis_title = _detect_y_axis_title(dataset_name or "", scale)

    # Create figure
    fig = go.Figure()

    # Handle single-column datasets (like carbon intensity) or datasets with "value" column
    if len(df.columns) == 1 or "value" in df.columns:
        column_name = "value" if "value" in df.columns else df.columns[0]
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[column_name],
                name=column_name if len(df.columns) == 1 else "Carbon Intensity",
            )
        )
        showlegend = False
    else:
        # Multi-column datasets (like solar data)
        for col in df.columns:
            visible = True if col == default_visible else "legendonly"
            fig.add_trace(go.Scatter(x=df.index, y=df[col], visible=visible, name=col))
        showlegend = True

    # Update layout
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_axis_title,
        showlegend=showlegend,
        hovermode="x unified" if len(df.columns) > 1 else "x",
        margin={"l": 0, "t": 40, "b": 0, "r": 0},
        autosize=True,
    )

    return fig


def plot_result_df(
    df: pd.DataFrame,
    microgrid_name: Optional[str] = None,
) -> Figure:
    """Plot microgrid results with 4 rows: actors, delta power, SoC, and grid power.

    Args:
        df: Simulation results as a pandas DataFrame (e.g., from MemoryLogger.to_dataframe()).
        microgrid_name: Name of the microgrid to plot. Optional if the dataframe
            contains only one microgrid.

    Returns:
        Plotly Figure with 4 subplots

    Raises:
        ValueError: If multiple microgrids are present in the dataframe and
            `microgrid_name` is not specified.
    """
    # Detect microgrid name if not provided
    if microgrid_name is None:
        microgrids: Any = None
        if "microgrid" in df.index.names:
            microgrids = df.index.get_level_values("microgrid").unique()
        elif "microgrid" in df.columns:
            microgrids = df["microgrid"].unique()

        if microgrids is not None:
            if len(microgrids) == 1:
                microgrid_name = microgrids[0]
            elif len(microgrids) > 1:
                raise ValueError(
                    f"Found multiple microgrids: {list(microgrids)}. "
                    "Please specify `microgrid_name`."
                )

    # Extract specific microgrid data
    if microgrid_name is not None:
        try:
            df = cast(pd.DataFrame, df.xs(microgrid_name, level="microgrid"))
        except (KeyError, ValueError):
            # Fallback for dataframes that are not multi-indexed by (time, microgrid)
            # e.g. if the user manually filtered or loaded from CSV without multi-index
            if "microgrid" in df.columns:
                df = df[df["microgrid"] == microgrid_name].set_index("time")
            else:
                 # Try to find columns with prefix
                 prefix = f"{microgrid_name}."
                 if any(col.startswith(prefix) for col in df.columns):
                     cols = [col for col in df.columns if col.startswith(prefix)]
                     df = df[cols].rename(columns={c: c[len(prefix):] for c in cols})

    # Determine availability of data
    has_storage = "storage_state.soc" in df.columns

    # Configure subplots (Always 4 rows)
    subplot_titles = [
        "Actor Power",
        "Delta Power",
        "Battery State of Charge",
        "Grid Power",
    ]
    row_heights = [0.25, 0.25, 0.25, 0.25]

    # Create subplots
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        subplot_titles=subplot_titles,
        row_heights=row_heights,
        vertical_spacing=0.08,
    )

    # 1. Actor Power Plot
    actor_p_cols = [
        col for col in df.columns if col.startswith("actor_states.") and col.endswith(".power")
    ]
    for col in actor_p_cols:
        # Extract actor name: actor_states.{name}.p
        actor_name = col.split(".")[1]
        display_name = actor_name.replace("_", " ").title()

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[col],
                name=display_name,
                legendgroup="actors",
                legendgrouptitle_text="Actors",
                hovertemplate=f"{display_name}: %{{y:.1f}} W<extra></extra>",
            ),
            row=1,
            col=1,
        )

    fig.update_yaxes(title_text="Power (W)", row=1, col=1)

    # 2. Delta Power Plot (Green > 0, Red < 0, No Legend)
    if "p_delta" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_delta"].clip(lower=0),
                name="Delta Power (Positive)",
                showlegend=False,
                line=dict(color="green", width=0),
                fill="tozeroy",
                fillcolor="rgba(0, 128, 0, 0.5)",
                hovertemplate="Delta Power: %{y:.1f} W<extra></extra>",
            ),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_delta"].clip(upper=0),
                name="Delta Power (Negative)",
                showlegend=False,
                line=dict(color="red", width=0),
                fill="tozeroy",
                fillcolor="rgba(255, 0, 0, 0.5)",
                hovertemplate="Delta Power: %{y:.1f} W<extra></extra>",
            ),
            row=2,
            col=1,
        )
        # Add a transparent line for the actual values to ensure continuity in hover
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_delta"],
                name="Delta Power",
                showlegend=False,
                line=dict(color="gray", width=1),
                hoverinfo="skip", # Hover handled by filled areas or we can switch it
            ),
            row=2,
            col=1,
        )

    fig.update_yaxes(title_text="Power (W)", row=2, col=1)

    # 3. Battery State of Charge (No Legend)
    if has_storage:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["storage_state.soc"] * 100,
                name="Battery SoC",
                showlegend=False,
                line=dict(color="green"),
                fill="tozeroy",
                fillcolor="rgba(0,128,0,0.1)",
                hovertemplate="SoC: %{y:.1f}%<extra></extra>",
            ),
            row=3,
            col=1,
        )

        if "storage_state.min_soc" in df.columns:
            min_soc = df["storage_state.min_soc"].iloc[0] * 100
            fig.add_hline(
                y=min_soc,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Min SoC ({min_soc:.0f}%)",
                annotation_position="top right",
                row=3,
                col=1,
            )
        fig.update_yaxes(title_text="SoC (%)", range=[0, 100], row=3, col=1)
    else:
        # Add dummy trace to ensure x-axis alignment and subplot initialization
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=[0] * len(df),
                showlegend=False,
                visible=False,  # Invisible but establishes axis existence
                hoverinfo="skip",
            ),
            row=3,
            col=1,
        )

        # Gray out the plot and add annotation
        # Note: We use data coordinates for y (0-1) since we set range below,
        # and x domain for width.
        fig.add_shape(
            type="rect",
            xref="x domain",
            yref="y domain",
            x0=0,
            y0=0,
            x1=1,
            y1=1,
            fillcolor="lightgray",
            opacity=0.5,
            layer="below",
            line_width=0,
            row=3,
            col=1,
        )
        fig.add_annotation(
            text="No Storage",
            xref="x domain",
            yref="y domain",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="gray"),
            row=3,
            col=1,
        )
        # Fix y-range to 0-1 for the shape/text to work in domain-like fashion
        # and hide ticks
        fig.update_yaxes(
            showticklabels=False,
            range=[0, 1],
            visible=True,  # Keep axis frame/grid if desired, or False to hide line
            row=3,
            col=1,
        )

    # 4. Grid Power Plot (No Legend, Green > 0, Red < 0)
    if "p_grid" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_grid"].clip(lower=0),
                name="Grid Power (Positive)",
                showlegend=False,
                line=dict(color="green", width=0),
                fill="tozeroy",
                fillcolor="rgba(0, 128, 0, 0.5)",
                hovertemplate="Grid Power: %{y:.1f} W<extra></extra>",
            ),
            row=4,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_grid"].clip(upper=0),
                name="Grid Power (Negative)",
                showlegend=False,
                line=dict(color="red", width=0),
                fill="tozeroy",
                fillcolor="rgba(255, 0, 0, 0.5)",
                hovertemplate="Grid Power: %{y:.1f} W<extra></extra>",
            ),
            row=4,
            col=1,
        )
        # Continuous line for visual clarity
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_grid"],
                name="Grid Power",
                showlegend=False,
                line=dict(color="blue", width=1),
                hoverinfo="skip",
            ),
            row=4,
            col=1,
        )
    fig.update_yaxes(title_text="Power (W)", row=4, col=1)
    fig.update_xaxes(title_text="Time", row=4, col=1)

    # Update overall layout
    fig.update_layout(
        height=800,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def _generate_title(dataset_name: str) -> str:
    """Generate a title from dataset name."""
    if "solcast2022_global" in dataset_name:
        return "Solar Irradiance - Global Cities (June 2022)"
    elif "solcast2022_germany" in dataset_name:
        return "Solar Irradiance - German Cities (July-August 2022)"
    elif "watttime2023_caiso-north" in dataset_name:
        return "Grid Carbon Intensity - CAISO North (June-July 2023)"
    else:
        # Fallback: capitalize and replace underscores
        return dataset_name.replace("_", " ").title()


def _detect_y_axis_title(dataset_name: str, scale: Optional[float] = None) -> str:
    """Detect appropriate y-axis title based on dataset."""
    if "solcast" in dataset_name.lower():
        if scale is not None:
            return f"Power (W, scaled by {scale})"
        else:
            return "% of max output"
    elif "watttime" in dataset_name.lower():
        return "g/kWh"
    else:
        return "Value"
