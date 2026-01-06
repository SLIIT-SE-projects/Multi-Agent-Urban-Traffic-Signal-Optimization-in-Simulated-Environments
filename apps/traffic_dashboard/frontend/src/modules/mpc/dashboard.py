"""
Commander Dashboard for Traffic MPC.
Features:
- Start/Stop Simulation Controls
- Real-Time "Traffic Health" Diagnostics
- Saturation Gauge
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
import subprocess
import signal
import sys

# --- Configuration ---
LOG_DIR = "data/logs"
MPC_LOG = os.path.join(LOG_DIR, "mpc", "simulation_data.csv")
BASE_LOG = os.path.join(LOG_DIR, "baseline", "simulation_data.csv")

# Set page config
st.set_page_config(page_title="🚦 Traffic Command Center", layout="wide", page_icon="🚦")

# --- Session State for Process Management ---
if 'sim_process' not in st.session_state:
    st.session_state.sim_process = None
if 'simulation_status' not in st.session_state:
    st.session_state.simulation_status = "STOPPED"
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = "None"

# --- Helper Functions ---
def load_data(filepath):
    if not os.path.exists(filepath): return pd.DataFrame()
    try: return pd.read_csv(filepath)
    except: return pd.DataFrame()

def start_simulation(mode_name):
    # Stop any running process first
    stop_simulation()
    
    # Determine flags
    is_mpc = (mode_name == "AI Optimized (MPC)")
    log_path = "data/logs/mpc" if is_mpc else "data/logs/baseline"
    control_flag = "control_enabled=True" if is_mpc else "control_enabled=False"
    
    # Clear old log to prevent graphing stale data
    csv_path = os.path.join(log_path, "simulation_data.csv")
    if os.path.exists(csv_path):
        os.remove(csv_path)
    
    # Build Command
    cmd = [
        "poetry", "run", "python", "-m", "traffic_mpc.main",
        control_flag,
        f"logging.log_dir={log_path}",
        "sumo.use_gui=True" # Force GUI for visual verification
    ]
    
    # Launch Background Process
    # use creationflags to allow clean killing on Windows
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        
    proc = subprocess.Popen(cmd, creationflags=creation_flags)
    
    st.session_state.sim_process = proc
    st.session_state.simulation_status = "RUNNING"
    st.session_state.current_mode = mode_name
    st.toast(f"🚀 Simulation Started: {mode_name}")

def stop_simulation():
    if st.session_state.sim_process:
        proc = st.session_state.sim_process
        if proc.poll() is None: # If running
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.kill()
            else:
                proc.terminate()
            proc.wait()
            st.toast("🛑 Simulation Stopped")
    
    st.session_state.sim_process = None
    st.session_state.simulation_status = "STOPPED"

# --- Sidebar: Mission Control ---
with st.sidebar:
    st.title("🎛️ Mission Control")
    st.markdown("---")
    
    # Status Indicator
    status_color = "green" if st.session_state.simulation_status == "RUNNING" else "red"
    st.markdown(f"**Status:** :{status_color}[{st.session_state.simulation_status}]")
    if st.session_state.simulation_status == "RUNNING":
        st.caption(f"Mode: {st.session_state.current_mode}")
    
    st.markdown("---")
    
    # Controls
    selected_mode = st.radio("Select Controller:", ["AI Optimized (MPC)", "Fixed Time (Baseline)"])
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("▶️ START", use_container_width=True):
            start_simulation(selected_mode)
            st.rerun()
            
    with col_btn2:
        if st.button("⏹️ STOP", use_container_width=True):
            stop_simulation()
            st.rerun()

    st.markdown("---")
    st.info("💡 **Tip:** 'AI Optimized' uses Phase Split logic to prevent gridlock.")

# --- Main Dashboard ---
st.title("🚦 Smart City Traffic Operations")

# Determine which log file to read based on what's running or last selected
active_log = MPC_LOG if "AI" in st.session_state.current_mode else BASE_LOG
# If stopped, default to MPC for analysis
if st.session_state.simulation_status == "STOPPED" and not os.path.exists(active_log):
    active_log = MPC_LOG

df = load_data(active_log)
df_base = load_data(BASE_LOG)

if df.empty:
    st.info("⚠️ No simulation data found. Use the sidebar to START a simulation.")
else:
    # --- 1. HEALTH HUD (Heads Up Display) ---
    latest = df.iloc[-1]
    max_q = latest['max_queue']
    avg_green = latest.get('avg_split', 0)
    
    # Interpretation
    health_status = "🟢 Healthy"
    if max_q > 15: health_status = "🟠 Busy"
    if max_q > 25: health_status = "🔴 Gridlock Risk"
    
    # Layout Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Network Status", health_status)
    with col2:
        st.metric("Max Queue", f"{max_q:.0f} veh", help="Longest line of cars in the city")
    with col3:
        st.metric("Avg Green Duration", f"{avg_green:.1f} s", help="Average time a phase stays green")
    with col4:
        # Comparison Math
        if not df_base.empty and len(df_base) > len(df) and max_q > 0:
            base_q = df_base.iloc[len(df)-1]['max_queue']
            imp = ((base_q - max_q) / base_q) * 100
            st.metric("Efficiency Gain", f"{imp:.1f}%", delta=f"{imp:.1f}%" if imp>0 else None)
        else:
            st.metric("Efficiency Gain", "--")

    st.markdown("---")

    # --- 2. ADVANCED VISUALIZATIONS ---
    row2_1, row2_2 = st.columns([2, 1])
    
    with row2_1:
        st.subheader("📉 Congestion Timeline")
        fig = go.Figure()
        
        # Draw Baseline Reference (if available)
        if not df_base.empty:
             fig.add_trace(go.Scatter(x=df_base['time'], y=df_base['max_queue'],
                                    mode='lines', name='Baseline (Fixed)',
                                    line=dict(color='gray', width=1, dash='dot')))
        
        # Draw Active Run
        line_color = '#00FF00' if "AI" in st.session_state.current_mode else '#FF4B4B'
        fig.add_trace(go.Scatter(x=df['time'], y=df['max_queue'],
                                mode='lines', name='Current Simulation',
                                fill='tozeroy', 
                                line=dict(color=line_color, width=3)))
        
        fig.update_layout(height=350, margin=dict(l=0,r=0,t=0,b=0),
                         xaxis_title="Simulation Time (s)", yaxis_title="Max Queue Length")
        st.plotly_chart(fig, key="main_chart", use_container_width=True)

    with row2_2:
        st.subheader("🔋 Network Saturation")
        # Gauge Chart: How close are we to "Game Over" (Queue=30)?
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = max_q,
            title = {'text': "Traffic Load"},
            gauge = {
                'axis': {'range': [None, 40]}, # 40 is assumed capacity
                'bar': {'color': "black"},
                'steps': [
                    {'range': [0, 15], 'color': "lightgreen"},
                    {'range': [15, 25], 'color': "orange"},
                    {'range': [25, 40], 'color': "red"}],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 30}}))
        
        fig_gauge.update_layout(height=350, margin=dict(l=20,r=20,t=0,b=0))
        st.plotly_chart(fig_gauge, key="gauge_chart", use_container_width=True)

    # --- 3. LIVE DATA LOG ---
    with st.expander("🔍 Inspect Live Data Logs"):
        st.dataframe(df.tail(15).sort_values(by="time", ascending=False), use_container_width=True)

# Auto-Refresh
if st.session_state.simulation_status == "RUNNING":
    time.sleep(2)
    st.rerun()