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

st.markdown("""
**Research layer (runs on http://localhost:8502):**
- 🔭 **Event Lab** — inject your own space event; the constellation plans observations and tests it against known physics *and* the null hypothesis h0 ("none of the known models").
- 📊 **Scorecard** — preregistered hypothesis results on real ZTF transients and the real Starlink fleet.
- 🛰️ **Anomaly Tracker** — maneuver and fragmentation detection from Space-Track history (work in progress).
""")
st.link_button("Open research dashboard ↗", "http://localhost:8502")
st.caption("Fully local stack: Python engines ↔ Redis (Memurai) ↔ Streamlit + Three.js. No cloud services required.")
