import streamlit as st

st.set_page_config(page_title="OrbitalNet OS", layout="wide", initial_sidebar_state="expanded")
st.title("🛰️ OrbitalNet Operating System")
st.markdown("### Welcome to the Command Interface")
st.info("👈 Please select a route from the sidebar on the left to navigate the system.")

st.markdown("""
**Available Operational Views:**
- **View 1: Global Asset Persistance (GAP)** - High-fidelity WebGL orbital asset visualization.
- **View 2: Network Operations Center (NOC)** - Fleet telemetry, operational ledgers, and anomaly injection interface.
- **View 3: Logic Engine Analytics (LEA)** - Decision-making variables and real-time behavioral data.
- **View 4: HIL Operational Verification** - Hardware-in-the-Loop simulated telemetry and edge device diagnostics.
""")
