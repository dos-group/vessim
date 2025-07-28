"""Plotting utilities for Vessim datasets and signals."""

from typing import Optional, List
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


def plot_microgrid_trace(
    df: pd.DataFrame,
    *,
    actors: Optional[List[str]] = None,
    actor_colors: Optional[dict] = None,
) -> Figure:
    """Plot microgrid trace with 3 rows: actors, system power, and battery SoC.

    Args:
        df: Simulation results DataFrame with time index and power columns
        actors: List of actor names to plot. If None, auto-detects from columns ending in '.p'
        actor_colors: Dict mapping actor names to colors. If None, uses default Plotly colors

    Returns:
        Plotly Figure with 3 subplots
    """
    # Auto-detect actors if not specified
    if actors is None:
        actors = [col.replace(".p", "") for col in df.columns if col.endswith(".p")]

    # Always create 3 subplots
    subplot_titles = ["Actor Power", "System Power", "Battery State of Charge"]
    row_heights = [0.4, 0.3, 0.3]

    # Create subplots
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=subplot_titles,
        row_heights=row_heights,
        vertical_spacing=0.08,
    )

    # Define default colors for common actor types
    default_colors = {
        "server": "#d62728",  # red
        "solar_panel": "#ff7f0e",  # orange
        "solar": "#ff7f0e",  # orange
        "wind": "#2ca02c",  # green
        "storage": "#9467bd",  # purple
        "load": "#8c564b",  # brown
        "battery": "#9467bd",  # purple
    }

    # 1. Actor Power Plot (Row 1)
    for actor in actors:
        actor_col = f"{actor}.p"
        if actor_col not in df.columns:
            continue

        # Determine color
        color = None
        if actor_colors and actor in actor_colors:
            color = actor_colors[actor]
        elif actor in default_colors:
            color = default_colors[actor]

        # Create display name
        display_name = actor.replace("_", " ").title()

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[actor_col],
                name=display_name,
                line=dict(color=color) if color else {},
                hovertemplate=f"{actor}: %{{y:.1f}} W<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # Format first subplot
    fig.update_yaxes(title_text="Power (W)", row=1, col=1)
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=1, col=1)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=1, col=1)

    # 2. System Power Plot (Row 2)
    if "p_delta" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_delta"],
                name="Delta Power",
                line=dict(color="gray"),
                hovertemplate="Delta Power: %{y:.1f} W<extra></extra>",
            ),
            row=2,
            col=1,
        )

    if "p_grid" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["p_grid"],
                name="Grid Power",
                line=dict(color="blue"),
                hovertemplate="Grid Power: %{y:.1f} W<extra></extra>",
            ),
            row=2,
            col=1,
        )

    fig.update_yaxes(title_text="Power (W)", row=2, col=1)
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=2, col=1)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=2, col=1)

    # 3. Battery State of Charge Plot (Row 3)
    # Find SoC columns (handle both old and new naming patterns)
    soc_columns = [
        col for col in df.columns if col.endswith(".storage.soc") or col == "storage.soc"
    ]
    min_soc_columns = [
        col for col in df.columns if col.endswith(".storage.min_soc") or col == "storage.min_soc"
    ]

    if soc_columns:
        # Plot SoC traces for each storage system
        for soc_col in soc_columns:
            # Extract microgrid name from column if hierarchical naming
            if "." in soc_col and soc_col != "storage.soc":
                mg_name = soc_col.split(".")[0]
                display_name = f"{mg_name} Battery SoC"
            else:
                display_name = "Battery SoC"

            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[soc_col] * 100,
                    name=display_name,
                    line=dict(color="green"),
                    fill="tozeroy",
                    fillcolor="rgba(0,128,0,0.1)",
                    hovertemplate="SoC: %{y:.1f}%<extra></extra>",
                ),
                row=3,
                col=1,
            )

        # Add minimum SoC lines if available
        for min_soc_col in min_soc_columns:
            if min_soc_col in df.columns:
                min_soc_value = df[min_soc_col].iloc[0] * 100
                fig.add_hline(
                    y=min_soc_value,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text=f"Min SoC ({min_soc_value:.0f}%)",
                    annotation_position="top right",
                    row=3,
                    col=1,
                )

        fig.update_yaxes(title_text="State of Charge (%)", range=[0, 100], row=3, col=1)
        fig.update_xaxes(
            showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=3, col=1
        )
        fig.update_yaxes(
            showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=3, col=1
        )

    # Update overall layout
    fig.update_layout(
        height=800,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # Format x-axis for bottom subplot only
    fig.update_xaxes(title_text="Time", row=3, col=1)

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
