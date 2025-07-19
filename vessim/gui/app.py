"""Standalone Streamlit app for Vessim GUI that connects via file-based communication."""

import streamlit as st
import pandas as pd
import time
import json
import tempfile
import sys
from pathlib import Path
from typing import Any, Dict


def get_shared_data_path() -> Path:
    """Get the path for shared data files."""
    # Use temp directory with a consistent name based on port
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8501
    temp_dir = Path(tempfile.gettempdir()) / f"vessim_gui_{port}"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


def read_data_file() -> Dict[str, Any]:
    """Read data from the shared data file."""
    data_file = get_shared_data_path() / "data.json"
    try:
        if data_file.exists():
            with open(data_file, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    return {}


def write_command_file(command: Dict[str, Any]) -> None:
    """Write a command to the shared command file."""
    command_file = get_shared_data_path() / "commands.json"
    try:
        # Read existing commands
        commands = []
        if command_file.exists():
            with open(command_file, 'r') as f:
                commands = json.load(f)

        # Add new command
        commands.append(command)

        # Write back
        with open(command_file, 'w') as f:
            json.dump(commands, f)
    except Exception as e:
        st.error(f"Failed to write command: {e}")


def main() -> None:
    """Main dashboard application."""
    # Get command line arguments
    if len(sys.argv) > 1:
        int(sys.argv[1])  # Parse port but don't use it in this version
        microgrid_names = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else []
    else:
        microgrid_names = ["test_microgrid"]

    # Configure streamlit page
    st.set_page_config(
        page_title="Vessim Real-time Dashboard",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state for data history
    if 'data_history' not in st.session_state:
        st.session_state.data_history = {}
        for mg_name in microgrid_names:
            st.session_state.data_history[mg_name] = []

    # Header with simulation controls
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("⚡ Vessim Dashboard")

    with col2:
        if st.button("📁 Export", key="export_btn", help="Export current data"):
            write_command_file({"type": "export_data"})
            st.success("Export command sent!")

    # Sidebar with parameter controls
    with st.sidebar:
        st.header("🎛️ Control Panel")

        # Battery controls
        st.subheader("🔋 Battery Settings")

        soc_target = st.slider("Target SoC (%)", 0, 100, 50, 5)
        if st.button("Set Battery SoC", key="set_soc_btn"):
            write_command_file({
                "type": "set_parameter",
                "parameter": "storage:soc",
                "value": soc_target / 100.0
            })
            st.success(f"Battery SoC set to {soc_target}%")

        # Quick battery presets
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔴 Low (20%)", key="low_battery"):
                write_command_file({
                    "type": "set_parameter",
                    "parameter": "storage:soc",
                    "value": 0.2
                })
                st.success("Battery set to 20%")

        with col2:
            if st.button("🟢 High (80%)", key="high_battery"):
                write_command_file({
                    "type": "set_parameter",
                    "parameter": "storage:soc",
                    "value": 0.8
                })
                st.success("Battery set to 80%")

        # Simulation info
        st.subheader("ℹ️ Status")
        status_placeholder = st.empty()

    # Main dashboard area
    placeholder = st.empty()

    # Read data from shared file
    shared_data = read_data_file()

    # Process data if available
    if shared_data:
        for mg_name, entries in shared_data.items():
            if mg_name in st.session_state.data_history:
                # Add new entries to history
                for entry in entries:
                    if entry not in st.session_state.data_history[mg_name]:
                        st.session_state.data_history[mg_name].append(entry)

                # Keep only last 100 data points
                if len(st.session_state.data_history[mg_name]) > 100:
                    st.session_state.data_history[mg_name] = (
                        st.session_state.data_history[mg_name][-100:]
                    )

    # Update status
    with status_placeholder:
        total_points = sum(len(history) for history in st.session_state.data_history.values())
        if total_points > 0:
            st.success(f"🟢 Active ({total_points} data points)")
        else:
            st.warning("🟡 Waiting for data from simulation...")

    # Display dashboard for each microgrid
    with placeholder.container():
        for mg_name in microgrid_names:
            if (
                mg_name in st.session_state.data_history
                and st.session_state.data_history[mg_name]
            ):
                st.subheader(f"📊 {mg_name.replace('_', ' ').title()}")

                # Convert data history to DataFrame
                df_data = []
                for entry in st.session_state.data_history[mg_name]:
                    flat_entry = {'time': entry['time']}

                    # Flatten the nested state structure
                    def flatten_dict(d: dict, prefix: str = '') -> None:
                        for k, v in d.items():
                            if k == 'time':  # Skip time to avoid conflicts
                                continue
                            if isinstance(v, dict):
                                flatten_dict(v, f"{prefix}{k}.")
                            else:
                                flat_entry[f"{prefix}{k}"] = v

                    flatten_dict(entry)
                    df_data.append(flat_entry)

                if df_data:
                    df = pd.DataFrame(df_data)
                    df['time'] = pd.to_datetime(df['time'])
                    df.set_index('time', inplace=True)

                    # Create plot using vessim's plotting function
                    try:
                        from vessim.plot import plot_microgrid_trace
                        fig = plot_microgrid_trace(df)
                        st.plotly_chart(fig, use_container_width=True)
                    except ImportError:
                        st.warning(
                            "📊 Plotting not available - install vessim[vis] for charts"
                        )
                        # Show raw data table as fallback
                        st.dataframe(df.tail(10), use_container_width=True)

                    # Show current metrics
                    if len(df) > 0:
                        latest = df.iloc[-1]
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            if 'p_delta' in latest:
                                delta = latest['p_delta']
                                st.metric("Net Power", f"{delta:.1f} W", delta_color="inverse")
                        with col2:
                            if 'p_grid' in latest:
                                grid = latest['p_grid']
                                st.metric("Grid Power", f"{grid:.1f} W", delta_color="normal")
                        with col3:
                            soc_cols = [
                                col
                                for col in latest.index
                                if 'soc' in col and 'min_soc' not in col
                            ]
                            if soc_cols:
                                soc_value = latest[soc_cols[0]] * 100
                                st.metric("Battery SoC", f"{soc_value:.1f}%")
                        with col4:
                            # Calculate efficiency or other derived metrics
                            if 'p_delta' in latest and 'p_grid' in latest:
                                efficiency = (
                                    1 - abs(latest['p_grid']) / (abs(latest['p_delta']) + 1e-6)
                                ) * 100
                                st.metric("System Efficiency", f"{efficiency:.1f}%")
                else:
                    st.info("📊 No data available yet...")
            else:
                st.info(f"⏳ Waiting for data from {mg_name}...")

    # Auto-refresh
    time.sleep(0.5)
    st.rerun()


if __name__ == "__main__":
    main()
