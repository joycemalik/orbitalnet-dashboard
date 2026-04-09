import streamlit as st

st.set_page_config(page_title="OrbitalNet OS", layout="wide", initial_sidebar_state="expanded")
st.title("🛰️ OrbitalNet Operating System")
st.markdown("### Welcome to the Command Interface")
st.info("👈 Please select a route from the sidebar on the left to navigate the system.")

st.markdown("""
**Available Routes:**
- **Route 1: /visualization (The God Mode)** - High-speed WebGL orbital physics render.
- **Route 2: /ground-station (The Command Center)** - Live metrics, ledgers, and chaos disruption panel.
- **Route 3: /under-the-hood (The Brain View)** - Live mathematical variables and real-time JSON packets.
- **Route 4: /hardware-edge (The Reality Check)** - Simulated telemetry and serial output of physical edge devices.
""")
