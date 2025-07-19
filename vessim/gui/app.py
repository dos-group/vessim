"""Standalone Streamlit app for Vessim GUI that connects via file-based communication."""

import streamlit as st
import pandas as pd
import time
import json
import tempfile
import sys
from pathlib import Path
from typing import Any, Dict

from vessim.plot import plot_microgrid_trace


def main() -> None:
    port = int(sys.argv[1])
    microgrids = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else []

    st.set_page_config(
        page_title="Vessim Dashboard",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state for data history
    if 'data_history' not in st.session_state:
        st.session_state.data_history = {}
        for microgrid in microgrids:
            st.session_state.data_history[microgrid] = []

    st.title("⚡ Vessim Dashboard")

    with st.sidebar:
        st.header("Control Panel")

        # Microgrid selection
        if len(microgrids) > 1:
            st.subheader("🏢 Select Microgrid")
            selected_microgrid = st.selectbox(
                "Choose microgrid to control:",
                microgrids,
                format_func=lambda x: x.replace('_', ' ').title()
            )
        else:
            selected_microgrid = microgrids[0] if microgrids else None

        if selected_microgrid:
            st.subheader(f"🔋 {selected_microgrid.replace('_', ' ').title()} Battery")

            soc_target = st.slider("Target SoC (%)", 0, 100, 50, 5)
            if st.button("Set Battery SoC", key="set_soc_btn"):
                _write_command_file({
                    "type": "set_parameter",
                    "parameter": f"{selected_microgrid}:storage:soc",
                    "value": soc_target / 100.0
                })
                mg_title = selected_microgrid.replace('_', ' ').title()
                st.success(f"{mg_title} battery SoC set to {soc_target}%")

            # Quick battery presets
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔴 Low (20%)", key="low_battery"):
                    _write_command_file({
                        "type": "set_parameter",
                        "parameter": f"{selected_microgrid}:storage:soc",
                        "value": 0.2
                    })
                    mg_title = selected_microgrid.replace('_', ' ').title()
                    st.success(f"{mg_title} battery set to 20%")

            with col2:
                if st.button("🟢 High (80%)", key="high_battery"):
                    _write_command_file({
                        "type": "set_parameter",
                        "parameter": f"{selected_microgrid}:storage:soc",
                        "value": 0.8
                    })
                    mg_title = selected_microgrid.replace('_', ' ').title()
                    st.success(f"{mg_title} battery set to 80%")

        # Simulation info
        st.subheader("ℹ️ Status")
        status_placeholder = st.empty()

    # Main dashboard area
    placeholder = st.empty()

    # Read data from shared file
    shared_data = _read_data_file()

    # Process data if available
    if shared_data:
        for microgrid, entries in shared_data.items():
            if microgrid in st.session_state.data_history:
                # Add new entries to history
                for entry in entries:
                    if entry not in st.session_state.data_history[microgrid]:
                        st.session_state.data_history[microgrid].append(entry)

                # Keep only last 100 data points
                if len(st.session_state.data_history[microgrid]) > 100:
                    st.session_state.data_history[microgrid] = (
                        st.session_state.data_history[microgrid][-100:]
                    )

    # Update status
    with status_placeholder:
        total_points = sum(len(history) for history in st.session_state.data_history.values())
        if total_points > 0:
            st.success(f"🟢 Active ({total_points} data points)")
        else:
            st.warning("🟡 Waiting for data from simulation...")

    # Display dashboard with tabs for multiple microgrids
    with placeholder.container():
        st.json(shared_data)
        # st.dataframe(data, column_config=config, use_container_width=True)

        if len(microgrids) > 1:
            # Use tabs for multiple microgrids
            tabs = st.tabs([mg_name.replace('_', ' ').title() for mg_name in microgrids])

            for i, microgrid in enumerate(microgrids):
                with tabs[i]:
                    _display_microgrid_data(microgrid, st.session_state.data_history)
        else:
            # Single microgrid - no tabs needed
            if microgrids:
                _display_microgrid_data(microgrids[0], st.session_state.data_history)


def _display_microgrid_data(mg_name: str, data_history: Dict[str, Any]) -> None:
    """Display data for a single microgrid."""
    if (
        mg_name in data_history
        and data_history[mg_name]
    ):
        # Convert data history to DataFrame
        df_data = []
        for entry in data_history[mg_name]:
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
                                             1 - abs(latest['p_grid']) / (
                                                 abs(latest['p_delta']) + 1e-6)
                                     ) * 100
                        st.metric("System Efficiency", f"{efficiency:.1f}%")

            # Create plot using vessim's plotting function
            fig = plot_microgrid_trace(df)
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("📊 No data available yet...")
    else:
        st.info(f"⏳ Waiting for data from {mg_name.replace('_', ' ').title()}...")


    # Auto-refresh
    time.sleep(10)
    st.rerun()


def _get_shared_data_path() -> Path:
    """Get the path for shared data files."""
    port = sys.argv[1]
    temp_dir = Path(tempfile.gettempdir()) / f"vessim_gui_{port}"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


def _read_data_file() -> Dict[str, Any]:
    """Read data from the shared data file."""
    data_file = _get_shared_data_path() / "data.json"
    try:
        if data_file.exists():
            with open(data_file, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _write_command_file(command: Dict[str, Any]) -> None:
    """Write a command to the shared command file."""
    command_file = _get_shared_data_path() / "commands.json"
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


if __name__ == "__main__":
    main()
