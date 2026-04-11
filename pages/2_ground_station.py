import streamlit as st
import pandas as pd
import random
import time
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

st.set_page_config(page_title="Network Operations Center", layout="wide", initial_sidebar_state="expanded")
st.title("🎛️ View 2: Network Operations Center (NOC)")
st.markdown("Operational interface for fleet telemetry and asset management.")

st.header("Constellation Health")
col1, col2, col3 = st.columns(3)
# Mock data representing Redis/Dynamo state
col1.metric("Average Battery", "87%", "-2% (Solar Eclipse)")
col2.metric("Total Active Nodes", "950", "+12")
col3.metric("Total Dead Nodes", "50", "+2")

st.markdown("---")

st.header("Anomaly Injection Interface")
st.warning("Authorized access only. These controls simulate severe operational anomalies.")
col_a, col_b, col_c = st.columns(3)

if col_a.button("💥 Kill 10% of Fleet", width='stretch'):
    st.error("Global Broadcast: 10% of fleet marked OFFLINE in Redis state.")
    
if col_b.button("☀️ Trigger Solar Storm (2x Drain)", width='stretch'):
    st.warning("Global Broadcast: Environment variables updated. Battery drain doubled.")
    
if col_c.button("✂️ Cut Network", width='stretch'):
    st.error("Global Broadcast: AWS SNS/MQTT message queues suspended. CNP halted.")

st.markdown("---")

st.header("Contract Ledger")
st.markdown("A live-scrolling table showing every open bid, who won it, and the execution status.")

# Mock DataFrame for open bids
data = {
    "Timestamp": [time.strftime('%H:%M:%S', time.gmtime(time.time() - i*15)) for i in range(10)],
    "Task ID": [f"USOS-TASK-{1052 - i}" for i in range(10)],
    "Winning Node": [f"STARLINK-{random.randint(1000, 3000)}" for _ in range(10)],
    "Winning Bid Score": [round(random.uniform(85.0, 99.9), 2) for _ in range(10)],
    "Status": ["COMPLETED" if i > 3 else "IN-PROGRESS" if i == 3 else "PENDING" for i in range(10)]
}
df = pd.DataFrame(data)

st.dataframe(df, width='stretch')

st.markdown("---")
st.markdown("### 🎯 Mission Control (Manual Override)")

with st.form("mission_dispatch"):
    col1, col2 = st.columns(2)
    with col1:
        target_x = st.number_input("Target X Coordinate", value=1500.0)
        target_y = st.number_input("Target Y Coordinate", value=-2000.0)
        target_z = st.number_input("Target Z Coordinate", value=5000.0)
        nodes_required = st.slider("Nodes Required (M)", 1, 5, 3)
    
    with col2:
        st.markdown("**Mission Parameter Weights**")
        w_battery = st.slider("Weight: Battery Preservation", 0.0, 1.0, 0.2)
        w_speed = st.slider("Weight: Speed/Proximity", 0.0, 1.0, 0.8)
        w_resolution = st.slider("Weight: Sensor Resolution", 0.0, 1.0, 0.5)

    submitted = st.form_submit_button("Broadcast Request For Proposal (RFP)")
    
    if submitted:
        # Create the Mission Object
        active_mission = {
            "status": "OPEN_AUCTION",
            "target": {"x": target_x, "y": target_y, "z": target_z},
            "required_nodes": nodes_required,
            "weights": {
                "soc": w_battery,
                "mean_motion": w_speed,
                "sensor_calibrated": w_resolution
            }
        }
        # Push to Redis so the Consensus Engine sees it
        r.set("ACTIVE_MISSION", json.dumps(active_mission))
        st.success("RFP Broadcasted to Fleet! Awaiting Enclave Formation...")
