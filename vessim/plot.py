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
    include_system_power: bool = True,
    include_storage: bool = True,
    height: int = 600,
    actor_colors: Optional[dict] = None,
    layout: str = "detailed",
) -> Figure:
    """Plot microgrid trace with actors, system power, and battery state.

    Creates a visualization with configurable layout:
    - "detailed": 3 subplots (actors, system power, storage) - comprehensive view
    - "overview": 2 subplots (actors+system power combined, storage) - compact view

    Args:
        df: Simulation results DataFrame with time index and power columns
        actors: List of actor names to plot. If None, auto-detects from columns ending in '.p'
        include_system_power: Whether to include the system power (p_delta, p_grid)
        include_storage: Whether to include the storage subplot (storage.soc)
        height: Total plot height in pixels
        actor_colors: Dict mapping actor names to colors. If None, uses default Plotly colors
        layout: "detailed" for 3 subplots, "overview" for 2 subplots (default: "detailed")

    Returns:
        Plotly Figure with interactive subplots

    Examples:
        >>> # Detailed 3-subplot view (default)
        >>> fig = plot_microgrid_trace(df)
        >>> fig.show()

        >>> # Compact 2-subplot overview (like notebook)
        >>> fig = plot_microgrid_trace(df, layout="overview")
        >>> fig.show()

        >>> # Plot only specific actors
        >>> fig = plot_microgrid_trace(df, actors=["server", "solar_panel"])
        >>> fig.show()
    """
    # Auto-detect actors if not specified
    if actors is None:
        actors = [col.replace(".p", "") for col in df.columns if col.endswith(".p")]

    # Handle layout options
    if layout == "overview":
        # Use overview layout: combine actors and system power in one subplot
        has_storage = include_storage and "storage.soc" in df.columns
        subplot_count = 2 if has_storage else 1

        subplot_titles = ["Power Overview"]
        if has_storage:
            subplot_titles.append("Battery State of Charge")

        row_heights = [0.67, 0.33] if subplot_count == 2 else [1.0]

    else:  # detailed layout
        # Determine subplot configuration - separate subplots
        subplot_count = 1  # Always include actors
        if include_system_power:
            subplot_count += 1
        if include_storage and "storage.soc" in df.columns:
            subplot_count += 1

        # Create subplot titles
        subplot_titles = ["Actor Power"]
        if include_system_power:
            subplot_titles.append("System Power")
        if include_storage and "storage.soc" in df.columns:
            subplot_titles.append("Battery State of Charge")

        # Calculate height ratios - give more space to actors plot
        row_heights = (
            [0.5] + [0.5 / (subplot_count - 1)] * (subplot_count - 1) if subplot_count > 1 else [1]
        )

    # Create subplots
    fig = make_subplots(
        rows=subplot_count,
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

    current_row = 1

    # 1. Actor Power Plot (and system power if overview layout)
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
        if layout == "overview":
            # Match notebook naming
            if "server" in actor.lower():
                display_name = f"{display_name} power"
            elif "solar" in actor.lower():
                display_name = f"{display_name} power"

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[actor_col],
                name=display_name,
                line=dict(color=color) if color else {},
                hovertemplate=f"{actor}: %{{y:.1f}} W<extra></extra>",
            ),
            row=current_row,
            col=1,
        )

    # Add system power to first subplot if overview layout
    if layout == "overview" and include_system_power:
        if "p_delta" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=df["p_delta"], name="Delta power", line=dict(color="gray")
                ),
                row=current_row,
                col=1,
            )

        if "p_grid" in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df["p_grid"], name="Grid power", line=dict(color="blue")),
                row=current_row,
                col=1,
            )

    # Format first subplot
    fig.update_yaxes(title_text="Power (W)", row=current_row, col=1)
    fig.update_xaxes(
        showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=current_row, col=1
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=current_row, col=1
    )

    current_row += 1

    # 2. System Power Plot (detailed layout only)
    if layout == "detailed" and include_system_power and current_row <= subplot_count:
        if "p_delta" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["p_delta"],
                    name="Delta Power",
                    line=dict(color="gray"),
                    hovertemplate="Delta Power: %{y:.1f} W<extra></extra>",
                ),
                row=current_row,
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
                row=current_row,
                col=1,
            )

        fig.update_yaxes(title_text="Power (W)", row=current_row, col=1)
        fig.update_xaxes(
            showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=current_row, col=1
        )
        fig.update_yaxes(
            showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=current_row, col=1
        )

        current_row += 1

    # 3. Battery State of Charge Plot
    if include_storage and "storage.soc" in df.columns and current_row <= subplot_count:
        # Main SoC trace
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["storage.soc"] * 100,
                name="Battery SoC",
                line=dict(color="green"),
                fill="tonexty" if len(fig.data) == 0 else "tozeroy",
                fillcolor="rgba(0,128,0,0.1)",
                hovertemplate="SoC: %{y:.1f}%<extra></extra>",
            ),
            row=current_row,
            col=1,
        )

        # Add minimum SoC line if available
        if "storage.min_soc" in df.columns:
            min_soc_value = df["storage.min_soc"].iloc[0] * 100
            fig.add_hline(
                y=min_soc_value,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Min SoC ({min_soc_value:.0f}%)",
                annotation_position="top right",
                row=current_row,
                col=1,
            )

        fig.update_yaxes(title_text="State of Charge (%)", range=[0, 100], row=current_row, col=1)
        fig.update_xaxes(
            showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=current_row, col=1
        )
        fig.update_yaxes(
            showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.3)", row=current_row, col=1
        )

    # Update overall layout
    fig.update_layout(
        height=height,
        hovermode="x unified",
        showlegend=True,
        legend=(
            dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            if layout == "detailed"
            else None
        ),
        margin=dict(l=0, t=60, b=0, r=0) if layout == "overview" else None,
    )

    # Format x-axis for bottom subplot only
    fig.update_xaxes(title_text="Time", row=subplot_count, col=1)

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
