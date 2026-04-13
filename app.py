import streamlit as st

st.set_page_config(page_title="OrbitalNet OS", layout="wide", initial_sidebar_state="expanded")
st.title("🛰️ OrbitalNet Operating System")
st.markdown("### Welcome to the Command Interface")
st.info("👈 Please select a route from the sidebar on the left to navigate the system.")

st.markdown("""
**Available Operational Views:**
- **Visualization** - High-fidelity WebGL orbital asset visualization with hardware color coding.
- **Ground Station** - Mission dispatch, Target Acquisition, Rolling Enclave control, Chaos Engineering.
- **Under the Hood** - Live Bidding Arena, Auction Ledger, Node Deep Scan, Fleet Statistics.
""")
