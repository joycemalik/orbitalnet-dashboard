import streamlit as st
import pandas as pd
import random
import time

st.set_page_config(page_title="Command Center", layout="wide", initial_sidebar_state="expanded")
st.title("🎛️ Route 2: /ground-station (The Command Center)")
st.markdown("If the visualization proves the physics, the ground station proves the operational health of the swarm.")

st.header("Constellation Health")
col1, col2, col3 = st.columns(3)
# Mock data representing Redis/Dynamo state
col1.metric("Average Battery", "87%", "-2% (Solar Eclipse)")
col2.metric("Total Active Nodes", "950", "+12")
col3.metric("Total Dead Nodes", "50", "+2")

st.markdown("---")

st.header("The Chaos Panel")
st.warning("These controls inject massive disruption into the physical and virtual CNP simulation. Use with caution.")
col_a, col_b, col_c = st.columns(3)

if col_a.button("💥 Kill 10% of Fleet", use_container_width=True):
    st.error("Global Broadcast: 10% of fleet marked OFFLINE in Redis state.")
    
if col_b.button("☀️ Trigger Solar Storm (2x Drain)", use_container_width=True):
    st.warning("Global Broadcast: Environment variables updated. Battery drain doubled.")
    
if col_c.button("✂️ Cut Network", use_container_width=True):
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

st.dataframe(df, use_container_width=True)
