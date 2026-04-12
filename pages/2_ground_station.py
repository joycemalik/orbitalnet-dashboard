import streamlit as st
import redis
import json
import pandas as pd
import random
import time
import uuid
from scenario_engine import ScenarioManager, SCENARIOS
from config import get_redis_client

st.set_page_config(layout="wide", page_title="Ground Station | OrbitalNet")
r = get_redis_client()
director = ScenarioManager()

st.title("📡 Tactical Ground Station")

st.markdown("---")
st.subheader("⏱️ Chronos Override (Time Control)")
# 1x = Real Time | 60x = 1 Minute per Second | 3600x = 1 Hour per Second
time_multiplier = st.slider("Simulation Speed Multiplier", min_value=1, max_value=7200, value=60)

# Instantly push the speed to the physics engine
r.set("TIME_MULTIPLIER", time_multiplier)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: Geographic Target Acquisition (writes to CURRENT_MISSION)
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown("### 🎯 Target Acquisition (Rolling Enclave)")
st.caption("Select a ground target. The physics engine will continuously elect the best-positioned satellite as Active Lead.")

tgt_col1, tgt_col2 = st.columns([1, 1])

with tgt_col1:
    # Real-world target examples
    targets = {
        "Jaipur (Test Site Alpha)": {"lat": 26.9124, "lon": 75.7873},
        "Bangalore (Test Site Beta)": {"lat": 12.9716, "lon": 77.5946},
        "Strait of Hormuz (Maritime)": {"lat": 26.5, "lon": 56.3},
        "Australian Bushfire Zone": {"lat": -33.8, "lon": 150.9},
        "Null Island (Reset)": {"lat": 0.0, "lon": 0.0},
        "Custom Coordinates": None
    }

    selected_target = st.selectbox("Select Monitoring Target", options=list(targets.keys()))

    if selected_target == "Custom Coordinates":
        custom_lat = st.number_input("Target Latitude", value=0.0, min_value=-90.0, max_value=90.0, step=0.1)
        custom_lon = st.number_input("Target Longitude", value=0.0, min_value=-180.0, max_value=180.0, step=0.1)
        target_coords = {"lat": custom_lat, "lon": custom_lon}
    else:
        target_coords = targets[selected_target]

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("🚀 EXECUTE: Task Swarm", type="primary", width='stretch'):
            mission_data = {
                "intent_id": f"MISSION_{int(time.time())}",
                "target_name": selected_target,
                "target_lat": target_coords["lat"],
                "target_lon": target_coords["lon"],
                "active": True
            }
            r.set("CURRENT_MISSION", json.dumps(mission_data))
            st.success(f"Mission Uploaded. Swarm routing to Lat: {target_coords['lat']:.4f}, Lon: {target_coords['lon']:.4f}")

    with btn_col2:
        if st.button("🛑 CANCEL MISSION", type="secondary", width='stretch'):
            r.delete("CURRENT_MISSION")
            st.warning("Mission cancelled. Fleet returning to idle consensus.")

with tgt_col2:
    # Show current mission status
    try:
        current_mission_raw = r.get("CURRENT_MISSION")
    except Exception:
        current_mission_raw = None
        
    if current_mission_raw:
        cm = json.loads(current_mission_raw)
        st.markdown(f"""
        <div style='background: rgba(0,255,136,0.08); border: 1px solid rgba(0,255,136,0.3); 
                    border-radius: 8px; padding: 16px; font-family: monospace;'>
            <span style='color: #00ff88; font-weight: bold; font-size: 0.9rem;'>● MISSION ACTIVE</span><br>
            <span style='color: #8899aa; font-size: 0.75rem;'>Intent: {cm.get('intent_id', 'N/A')}</span><br>
            <span style='color: #c8d6e5; font-size: 0.85rem;'>Target: {cm.get('target_name', 'Custom')}</span><br>
            <span style='color: #c8d6e5; font-size: 0.85rem;'>Lat: {cm.get('target_lat', 0):.4f} | Lon: {cm.get('target_lon', 0):.4f}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); 
                    border-radius: 8px; padding: 16px; font-family: monospace;'>
            <span style='color: #5a6e82; font-weight: bold; font-size: 0.9rem;'>○ NO ACTIVE MISSION</span><br>
            <span style='color: #5a6e82; font-size: 0.75rem;'>Fleet holding idle consensus. Select a target to begin.</span>
        </div>
        """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: Scenario Deployment (existing — writes to ACTIVE_MISSION)
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### Mission Deployment")
    scenario_choice = st.selectbox("Select Mission Profile", list(SCENARIOS.keys()))
    
    # Display mission intel
    st.info(SCENARIOS[scenario_choice]["description"])
    st.write(f"**Required Nodes (M):** {SCENARIOS[scenario_choice]['m_required']}")
    st.write(f"**Risk Profile:** {SCENARIOS[scenario_choice]['risk_profile']}")

    if st.button("🚀 BROADCAST RFP (Initiate Consensus)", type="primary", width='stretch'):
        result = director.dispatch_mission(scenario_choice)
        st.success(f"RFP Broadcasted ({result}). Swarm is evaluating capability math.")

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
    try:
        all_missions_raw = r.hgetall("MISSIONS_LEDGER")
    except Exception:
        all_missions_raw = {}
    
    if all_missions_raw:
        for mid, mjson in all_missions_raw.items():
            mission = json.loads(mjson)
            status_color = "🟢" if mission['status'] == "EXECUTING" else "🟡" if mission['status'] == "OPEN_AUCTION" else "⚪"
            with st.expander(f"{status_color} {mid} — {mission.get('name', 'CUSTOM')} [{mission.get('sensor_required', '?')}]", expanded=(mission['status'] == 'EXECUTING')):
                st.write(f"**Status:** `{mission['status']}`")
                st.write(f"**Sensor:** `{mission.get('sensor_required', 'EO')}` | **Nodes:** `{mission.get('required_nodes', '?')}`")
                st.write(f"**Target:** `{mission.get('target_lat', 0):.2f}°, {mission.get('target_lon', 0):.2f}°`")
                
                if mission['status'] == "EXECUTING" and mission.get('enclave'):
                    try:
                        enclave_data = r.mget(mission['enclave'])
                        fleet = [json.loads(item) for item in enclave_data if item]
                        if fleet:
                            df = pd.DataFrame([{
                                "Node ID": s['id'],
                                "Role": s.get('role', 'UNKNOWN'),
                                "Payload": s.get('payload_type', '?'),
                                "Score (C_i)": round(s.get('current_score', 0), 4),
                                "Battery": f"{s['telemetry']['P0_Gatekeepers']['soc'] * 100:.1f}%"
                            } for s in fleet])
                            st.dataframe(df, width='stretch')
                    except Exception:
                        st.warning("Enclave nodes not responding.")
                
                elif mission['status'] == "OPEN_AUCTION":
                    st.warning("⏳ Auction open. Plane Leads are bidding...")
        
        # Purge button
        if st.button("🗑️ Purge All Missions", type="secondary"):
            r.delete("MISSIONS_LEDGER")
            st.warning("All missions purged from ledger.")
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
        target_lat = st.number_input("Target Latitude", value=26.9) # Jaipur default
        target_lon = st.number_input("Target Longitude", value=75.8)
        nodes_required = st.slider("Nodes Required (M)", 1, 5, 3)
        
        # Hardware Selector
        sensor_type = st.selectbox("Required Sensor Payload", ["EO (Optical)", "SAR (Radar)", "SIGINT (Signals)", "MW (Weather)"])
    
    with col2:
        st.markdown("**Mission Parameter Weights**")
        w_battery = st.slider("Weight: Battery Preservation", 0.0, 1.0, 0.2)
        w_speed = st.slider("Weight: Speed/Proximity", 0.0, 1.0, 0.8)
        w_resolution = st.slider("Weight: Sensor Resolution", 0.0, 1.0, 0.5)

    submitted = st.form_submit_button("Broadcast Request For Proposal (RFP)")
    
    if submitted:
        # Unique Mission ID
        mission_id = f"OPS-{uuid.uuid4().hex[:6].upper()}"
        
        # Extract just the prefix (e.g., "EO", "SAR")
        sensor_code = sensor_type.split(" ")[0]
        
        active_mission = {
            "id": mission_id,
            "status": "OPEN_AUCTION",
            "name": f"MONITOR_{sensor_code}",
            "target_lat": target_lat,
            "target_lon": target_lon,
            "active": True,
            "required_nodes": nodes_required,
            "sensor_required": sensor_code,
            "weights": {
                "soc": w_battery,
                "mean_motion": w_speed,
                "sensor_calibrated": w_resolution
            },
            "enclave": []
        }
        # Use HSET to store multiple missions simultaneously
        r.hset("MISSIONS_LEDGER", mission_id, json.dumps(active_mission))
        st.success(f"RFP {mission_id} Broadcasted for {sensor_code} satellites!")
