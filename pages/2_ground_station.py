import streamlit as st
import redis
import json
import pandas as pd
import random
import time
from scenario_engine import ScenarioManager, SCENARIOS

st.set_page_config(layout="wide", page_title="Ground Station | OrbitalNet")
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
director = ScenarioManager()

st.title("📡 Tactical Ground Station")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### Mission Deployment")
    scenario_choice = st.selectbox("Select Mission Profile", list(SCENARIOS.keys()))
    
    # Display mission intel
    st.info(SCENARIOS[scenario_choice]["description"])
    st.write(f"**Required Nodes (M):** {SCENARIOS[scenario_choice]['m_required']}")
    st.write(f"**Risk Profile:** {SCENARIOS[scenario_choice]['risk_profile']}")

    if st.button("🚀 BROADCAST RFP (Initiate Consensus)", type="primary", width='stretch'):
        director.dispatch_mission(scenario_choice)
        st.success("RFP Broadcasted. Swarm is evaluating capability math.")

    st.markdown("---")
    st.markdown("### Chaos Engineering")
    if st.button("🚨 Simulate Node Jamming (Force Hot-Swap)", type="primary"):
        director.inject_chaos()
        st.error("EMP INJECTED: Awaiting swarm self-healing response...")

    st.markdown("---")

    # Constellation Health (preserved from original)
    st.markdown("### Constellation Health")
    keys = r.keys('STARLINK-*')
    total_nodes = len(keys) if keys else 0
    st.metric("Total Active Nodes", total_nodes)

with col2:
    st.markdown("### Active Enclave Telemetry")
    mission_raw = r.get("ACTIVE_MISSION")
    
    if mission_raw:
        mission = json.loads(mission_raw)
        st.write(f"**Mission:** `{mission.get('name', 'CUSTOM')}`")
        st.write(f"**Current Status:** `{mission['status']}`")
        
        if mission['status'] == "EXECUTING" and mission.get('enclave'):
            st.markdown("#### 🔒 Locked Satellites (Enclave)")
            
            # Fetch real-time data for the executing satellites
            enclave_data = r.mget(mission['enclave'])
            fleet = [json.loads(item) for item in enclave_data if item]
            
            if fleet:
                df = pd.DataFrame([{
                    "Node ID": s['id'],
                    "Role": s.get('role', 'UNKNOWN'),
                    "Capability Score (C_i)": round(s.get('current_score', 0), 4),
                    "Battery (SoC)": f"{s['telemetry']['P0_Gatekeepers']['soc'] * 100:.1f}%"
                } for s in fleet])
                
                st.dataframe(df, width='stretch')
            else:
                st.warning("Enclave nodes not responding. Possible network fault.")
                
        elif mission['status'] == "OPEN_AUCTION":
            st.warning("⏳ Auction open. Plane Leads are bidding...")
        else:
            st.info(f"Mission status: {mission['status']}")
    else:
        st.write("No active missions. Fleet is holding idle consensus.")

    st.markdown("---")

    # Contract Ledger
    st.markdown("### Contract Ledger")
    st.markdown("A live-scrolling table showing every open bid, who won it, and the execution status.")

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
        active_mission = {
            "status": "OPEN_AUCTION",
            "name": "CUSTOM_MISSION",
            "target": {"x": target_x, "y": target_y, "z": target_z},
            "required_nodes": nodes_required,
            "weights": {
                "soc": w_battery,
                "mean_motion": w_speed,
                "sensor_calibrated": w_resolution
            },
            "enclave": []
        }
        r.set("ACTIVE_MISSION", json.dumps(active_mission))
        st.success("RFP Broadcasted to Fleet! Awaiting Enclave Formation...")
