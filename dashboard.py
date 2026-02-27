"""
Real-time Dashboard & Ground Station for USOS Swarm
Professional UI with graphical orbit map and task injection.
Usage: streamlit run dashboard.py
"""

import json
import socket
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go

from config import LOG_FILE, SATELLITE_IDS, STATE_FILE, SATELLITE_PORTS, LOCALHOST, SECTORS


def read_swarm_state():
    """Read current swarm state from shared JSON file."""
    try:
        state_path = Path(STATE_FILE)
        if state_path.exists():
            with open(state_path, "r") as f:
                return json.load(f)
    except Exception:
        # ignore parse errors
        return {}
    return {}


def send_task(task: str, location: str):
    """Broadcast a task message to all satellite ports via UDP."""
    msg = {
        "type": "TASK_BROADCAST",
        "task": task,
        "location": location,
        "timestamp": datetime.utcnow().isoformat(),
    }
    data = json.dumps(msg).encode("utf-8")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for port in SATELLITE_PORTS:
        try:
            sock.sendto(data, (LOCALHOST, port))
        except Exception:
            pass
    sock.close()


def batch_send_task(task: str, location: str, repeats: int, interval: float):
    """Send multiple tasks in background, waiting between each."""
    for i in range(repeats):
        send_task(task, location)
        print(f"[GroundStation] broadcast {task} to {location} ({i+1}/{repeats})")
        if i < repeats - 1:
            time.sleep(interval)


def read_logs(lines: int = 50):
    """Return the last `lines` entries from the event log."""
    try:
        log_path = Path(LOG_FILE)
        if log_path.exists():
            with open(log_path, "r") as f:
                all_lines = f.readlines()
                return [l.strip() for l in all_lines[-lines:]]
    except Exception:
        pass
    return []


def status_to_color(status: str) -> str:
    """Map satellite status to a plotly marker color."""
    mapping = {
        "IDLE": "blue",
        "BIDDING": "yellow",
        "EXECUTING": "red",
        "OFFLINE": "gray",
    }
    return mapping.get(status, "black")




def main():
    st.set_page_config(
        page_title="USOS Swarm Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # --- Sidebar Ground Station Control ---
    with st.sidebar.form("ground_station_form"):
        st.header("Ground Station Control")
        task_type = st.selectbox("Task Type", ["IMAGING", "SURVEILLANCE", "COMMUNICATION"])
        sector = st.selectbox("Target Sector", SECTORS)
        repeat_count = st.number_input("Repeat Count", min_value=1, max_value=10, value=1)
        interval = st.number_input("Interval (Seconds)", min_value=1.0, value=5.0)
        submitted = st.form_submit_button("Broadcast Task")
        if submitted:
            threading.Thread(
                target=batch_send_task,
                args=(task_type, sector, repeat_count, interval),
                daemon=True,
            ).start()
            st.sidebar.success(f"Scheduled {repeat_count} x {task_type} to {sector}")

    # --- Read state and logs ---
    swarm_state = read_swarm_state()
    logs = read_logs(lines=100)

    # --- Plotly Polar Orbit Map ---
    angle_map = {
        "SECTOR_1": 0,
        "SECTOR_2": 60,
        "SECTOR_3": 120,
        "SECTOR_4": 180,
        "SECTOR_5": 240,
        "SECTOR_6": 300,
    }

    thetas = []
    rs = []
    colors = []
    sizes = []
    texts = []

    for sat in SATELLITE_IDS:
        state = swarm_state.get(sat, {})
        pos = state.get("position", "SECTOR_1")
        angle = angle_map.get(pos, 0)
        thetas.append(angle)
        rs.append(1)
        battery = state.get("battery", 0)
        sizes.append(10 + battery * 0.5)
        status = state.get("status", "OFFLINE")
        colors.append(status_to_color(status))
        texts.append(f"{sat}\n{status}\n{battery:.1f}%")

    fig = go.Figure(
        go.Scatterpolar(
            r=rs,
            theta=thetas,
            mode="markers+text",
            marker=dict(size=sizes, color=colors, opacity=0.8),
            text=list(SATELLITE_IDS),
            textposition="top center",
        )
    )
    fig.update_layout(
        polar=dict(
            angularaxis=dict(direction="clockwise", tickmode="array", tickvals=list(angle_map.values()), ticktext=list(angle_map.keys()))
        ),
        showlegend=False,
        margin=dict(l=40, r=40, t=40, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Live Consensus & Bidding Tracker ---
    st.subheader("Live Consensus & Bidding Tracker")
    bidding_info = []
    winning = None
    for sat, state in swarm_state.items():
        status = state.get("status")
        if status in ("BIDDING", "EXECUTING"):
            bids = state.get("last_bid_scores", {})
            bidding_info.append((sat, status, bids))
            if status == "EXECUTING":
                winning = sat
    if bidding_info:
        cols = st.columns(len(bidding_info))
        for idx, (sat, status, bids) in enumerate(bidding_info):
            with cols[idx]:
                st.write(f"**{sat}**")
                st.write(status)
                scores = bids.get(sat, 0)
                st.progress(min(scores / 150, 1.0))
                st.write(f"Score: {scores:.2f}")
        if winning:
            st.success(f"{winning} is executing")
    else:
        st.write("No active bidding at the moment.")

    # --- Data table ---
    table_rows = []
    for sat in SATELLITE_IDS:
        state = swarm_state.get(sat, {})
        current_task = state.get("current_task")
        task_str = (
            f"{current_task.get('task')} @ {current_task.get('location')}"
            if current_task
            else "-"
        )
        table_rows.append(
            {
                "Satellite": sat,
                "Battery": state.get("battery", 0),
                "Status": state.get("status", "OFFLINE"),
                "Position": state.get("position", ""),
                "Current Task": task_str,
                "Last Bid Scores": state.get("last_bid_scores", {}),
            }
        )
    st.dataframe(table_rows)

    # --- Event log ---
    st.subheader("Event Log")
    for line in logs:
        st.text(line)

    # --- Automatic refresh via JS hack (1 second) ---
    st.markdown(
        """
        <script>
        setTimeout(function(){window.location.reload();}, 1000);
        </script>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
