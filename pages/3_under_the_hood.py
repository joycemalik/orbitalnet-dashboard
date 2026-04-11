import streamlit as st
import redis
import json
import pandas as pd

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

st.set_page_config(page_title="Logic Engine Analytics", layout="wide", initial_sidebar_state="expanded")
st.title("🧠 View 3: Logic Engine Analytics (LEA)")
st.markdown("Detailed breakdown of autonomous decision-making logic and realtime behavior analytics.")

# 1. Fetch Fleet Data
keys = r.keys('STARLINK-*')
if keys:
    raw_data = r.mget(keys)
    fleet = [json.loads(item) for item in raw_data if item]
    
    # 2. Top Level Metrics
    total_nodes = len(fleet)
    plane_leads = len([s for s in fleet if s.get('role') == 'PLANE_LEAD'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Active Logic Nodes", total_nodes)
    col2.metric("Elected Plane Leads (Consensus)", plane_leads)
    
    # 3. The Node Inspector (Proving the 30 Parameters)
    st.markdown("---")
    st.header("Decision Engine Inspector")
    st.markdown("Select a specific satellite to view the exact 30-parameter vector driving its real-time $C_i$ capability score.")
    
    sat_names = [s['id'] for s in fleet]
    # Default to a plane lead if one exists to make it look cool instantly
    lead_sats = [s['id'] for s in fleet if s.get('role') == 'PLANE_LEAD']
    default_idx = sat_names.index(lead_sats[0]) if lead_sats else 0
    
    selected_sat = st.selectbox("Select Target Node for Deep Scan", sat_names, index=default_idx)
    
    if selected_sat:
        # Find the specific satellite data
        sat_data = next((s for s in fleet if s['id'] == selected_sat), None)
        
        if sat_data:
            role = sat_data.get('role', 'FOLLOWER')
            score = sat_data.get('current_score', 0.0)
            
            c1, c2 = st.columns(2)
            c1.info(f"**Current Capability Score ($C_i$):** `{score:.4f}`")
            if role == 'PLANE_LEAD':
                c2.success(f"**Consensus Role:** `👑 {role}`")
            else:
                c2.warning(f"**Consensus Role:** `{role}`")
            
            # Extract the 30 parameters and display them as a clean dataframe
            # Provide fallbacks if mock telemetry isn't populated yet
            telem = sat_data.get('telemetry', {})
            
            # Flatten for the table
            flat_telem = {}
            for group, params in telem.items():
                for k, v in params.items():
                    flat_telem[f"[{group.split('_')[0]}] {k.replace('_', ' ').title()}"] = v
                    
            if flat_telem:
                df = pd.DataFrame(list(flat_telem.items()), columns=["Parameter Trigger", "Normalized Value"])
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("Telemetry vector empty. Simulation clock may be halted.")
else:
    st.warning("No telemetry data found. Ensure the Physics Gateway is active.")
