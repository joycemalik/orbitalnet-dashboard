import streamlit as st
import random

st.set_page_config(page_title="Hardware Edge", layout="wide", initial_sidebar_state="expanded")
st.title("🔌 Route 4: /hardware-edge (The Reality Check)")
st.markdown("This bridges the simulation with reality by isolating the physical microcontrollers you are testing on.")

col1, col2 = st.columns(2)

with col1:
    st.header("Physical Telemetry")
    st.markdown("Readouts directly from the physical hardware limits.")
    cpu_usage = random.randint(40, 70)
    st.metric("Microcontroller CPU Usage", f"{cpu_usage}%")
    mem_usage = random.randint(60, 80)
    st.metric("Local Memory State", f"{mem_usage}% (used)")
    temp = random.randint(35, 45)
    st.metric("Operating Temperature", f"{temp} °C")

with col2:
    st.header("Hardware Serial Output")
    st.markdown("Split-screen showing the virtual target assigned to the physical node, and the serial output from the node.")
    st.code("""
[10:42:01] BOOT: EDGE_NODE_ALPHA_001
[10:42:01] CONNECTED_TO_MQTT: OK
[10:42:01] STARTING CNP LISTENER
[10:42:05] TASK RECEIVED: TARGET_ZONE_ALPHA
[10:42:05] CALCULATING PROXIMITY...
[10:42:06] BID SUBMITTED: 89.4
[10:42:10] CONTRACT WON! EXECUTION STARTED.
[10:42:12] SENSOR CPU GOVERNOR ACTUATING...
[10:42:15] EXECUTION_COMPLETED. WAITING_STATE_RESTORED.
""", language="log")

st.markdown("---")
st.video("https://www.w3schools.com/html/mov_bbb.mp4")  # Just a placeholder for actual physical camera feed.
st.caption("Optional placeholder for physical webcam overlooking the microcontroller circuit.")
