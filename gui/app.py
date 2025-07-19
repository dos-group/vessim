import streamlit as st
import pandas as pd
import requests
import time
from typing import Dict, Any

API_BASE = "http://localhost:8502"

def main():
    st.set_page_config(
        page_title="Vessim Dashboard",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("⚡ Vessim Dashboard")

    # Get microgrids from API
    microgrids = get_microgrids()
    
    with st.sidebar:
        st.header("Control Panel")
        
        if microgrids:
            # Microgrid selection
            if len(microgrids) > 1:
                st.subheader("🏢 Select Microgrid")
                selected_microgrid = st.selectbox(
                    "Choose microgrid to control:",
                    microgrids,
                    format_func=lambda x: x.replace('_', ' ').title()
                )
            else:
                selected_microgrid = microgrids[0]

            if selected_microgrid:
                st.subheader(f"🔋 {selected_microgrid.replace('_', ' ').title()} Battery")
                
                min_soc_target = st.slider("Min SoC (%)", 0, 100, 20, 5)
                if st.button("Set Min SoC", key="set_min_soc_btn"):
                    set_min_soc(selected_microgrid, min_soc_target / 100.0)
                    st.success(f"Min SoC set to {min_soc_target}%")

        # Status
        st.subheader("ℹ️ Status")
        status = get_status()
        if status:
            st.json(status)

    # Main dashboard
    if microgrids:
        if len(microgrids) > 1:
            tabs = st.tabs([mg.replace('_', ' ').title() for mg in microgrids])
            for i, microgrid in enumerate(microgrids):
                with tabs[i]:
                    display_microgrid(microgrid)
        else:
            display_microgrid(microgrids[0])

    time.sleep(1)
    st.rerun()

def get_microgrids():
    response = requests.get(f"{API_BASE}/api/microgrids")
    if response.status_code == 200:
        return response.json().get("microgrids", [])
    return []

def get_status():
    response = requests.get(f"{API_BASE}/api/status")
    if response.status_code == 200:
        return response.json()
    return None

def set_min_soc(microgrid: str, value: float):
    requests.put(f"{API_BASE}/api/microgrids/{microgrid}/storage/min_soc", 
                json={"min_soc": value})

def display_microgrid(microgrid: str):
    # Get latest data
    response = requests.get(f"{API_BASE}/api/microgrids/{microgrid}/latest")
    if response.status_code == 200:
        latest = response.json()
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if 'p_delta' in latest:
                st.metric("Net Power", f"{latest['p_delta']:.1f} W")
        with col2:
            if 'p_grid' in latest:
                st.metric("Grid Power", f"{latest['p_grid']:.1f} W")
        with col3:
            soc_keys = [k for k in latest.keys() if 'soc' in k and 'min_soc' not in k]
            if soc_keys:
                soc_value = latest[soc_keys[0]] * 100
                st.metric("Battery SoC", f"{soc_value:.1f}%")
        with col4:
            if 'p_delta' in latest and 'p_grid' in latest:
                efficiency = (1 - abs(latest['p_grid']) / (abs(latest['p_delta']) + 1e-6)) * 100
                st.metric("System Efficiency", f"{efficiency:.1f}%")

        # History chart
        history_response = requests.get(f"{API_BASE}/api/microgrids/{microgrid}/history")
        if history_response.status_code == 200:
            history_data = history_response.json().get("data", [])
            if history_data:
                df = pd.DataFrame(history_data)
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                
                # Plot key metrics
                chart_data = df[['p_delta', 'p_grid']].dropna()
                if not chart_data.empty:
                    st.line_chart(chart_data)
    else:
        st.info(f"⏳ Waiting for data from {microgrid.replace('_', ' ').title()}...")

if __name__ == "__main__":
    main()