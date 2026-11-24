"""OrbitalNet OS — single-entry console. Routes every view (live ops + research) through one app on :8501."""

import datetime

import streamlit as st

from ui.theme import apply_theme, sidebar_brand

st.set_page_config(page_title="OrbitalNet OS", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")
apply_theme()


@st.cache_data(ttl=3, show_spinner=False)
def bus_status():
    try:
        from mission_control.config import get_redis_client
        r = get_redis_client()
        r.ping()
        sats = sum(1 for _ in r.scan_iter("STARLINK-*", count=2000))
        return True, sats, r.hlen("MISSIONS_LEDGER")
    except Exception:
        return False, 0, 0


online, n_sats, n_missions = bus_status()
sidebar_brand([("UTC", datetime.datetime.utcnow().strftime("%H:%M:%S")),
               ("ASSETS", f"{n_sats:,}"), ("MISSIONS", str(n_missions))], online)

R = "research/app/pages/"
nav = st.navigation({
    "Command": [
        st.Page("ui/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
    ],
    "Operations": [
        st.Page("mission_control/pages/1_visualization.py", title="Orbital View", icon=":material/public:", url_path="orbital-view"),
        st.Page("mission_control/pages/2_ground_station.py", title="Mission Dispatch", icon=":material/satellite_alt:", url_path="dispatch"),
        st.Page("mission_control/pages/3_under_the_hood.py", title="Auction Internals", icon=":material/memory:", url_path="internals"),
    ],
    "Discovery": [
        st.Page(R + "1_🔭_Event_Lab.py", title="Event Lab", icon=":material/science:", url_path="event-lab"),
        st.Page(R + "2_📊_Scorecard.py", title="Evidence", icon=":material/fact_check:", url_path="evidence"),
        st.Page("research/app/viewer.py", title="Experiment Archive", icon=":material/inventory_2:", url_path="archive"),
        st.Page(R + "3_🛰️_Anomaly_Tracker.py", title="Anomaly Watch", icon=":material/radar:", url_path="anomaly"),
    ],
})
nav.run()
