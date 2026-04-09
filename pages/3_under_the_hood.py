import streamlit as st
import json
import time

st.set_page_config(page_title="Logic Engine Analytics", layout="wide", initial_sidebar_state="expanded")
st.title("🧠 View 3: Logic Engine Analytics (LEA)")
st.markdown("Detailed breakdown of autonomous decision-making logic and realtime behavior analytics.")

st.header("Decision Engine Inspector")
st.markdown("Select a specific satellite to view the exact mathematical formula calculating its current bid score in real-time.")

node = st.selectbox("Live Targeting Node", ["STARLINK-1008", "STARLINK-2231", "STARLINK-0912", "STARLINK-3132"])

st.subheader(f"Bid Math: {node}")
st.latex(r"\text{Bid\_Score} = (W_{prox} \times \text{Proximity}) - (W_{batt} \times \frac{100}{\text{Battery}})")

# Dummy real-time mathematical representation
proximity = 0.92
battery = 85.0
w_prox = 100
w_batt = 10
score = (w_prox * proximity) - (w_batt * (100 / battery))

st.markdown(f"**Current Parameters for {node}:** Proximity = {proximity}, Battery = {battery}%, $W_{{prox}}$ = {w_prox}, $W_{{batt}}$ = {w_batt}")
st.info(f"### Live Score: **{score:.2f}**")

st.markdown("---")

st.header("Raw Network Packets (AWS / MQTT Stream)")
st.markdown("A live terminal window spitting out the raw JSON packets passing through your system.")

st.code(
    json.dumps(
        {
            "timestamp": time.time(),
            "topic": "usos-bids",
            "node_id": node,
            "ttl": 300,
            "payload": {
                "target_assigned": "TASK-1005",
                "bid_score": round(score, 2),
                "eci_coordinates": {"x": -2534.34, "y": 6432.22, "z": 890.31}
            }
        }, 
        indent=4
    ), 
    language="json"
)
