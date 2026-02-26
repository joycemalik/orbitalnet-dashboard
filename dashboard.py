"""
Real-time Dashboard for USOS Swarm Visualization
Streamlit app to monitor satellite network autonomy and consensus
Usage: streamlit run dashboard.py
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import LOG_FILE, SATELLITE_IDS, STATE_FILE


def read_swarm_state():
    """Read current swarm state from JSON file."""
    try:
        state_path = Path(STATE_FILE)
        if state_path.exists():
            with open(state_path, "r") as f:
                return json.load(f)
    except Exception as e:
        st.warning(f"Could not read state file: {e}")
    return {}


def read_logs(lines: int = 50):
    """Read recent log entries from log file."""
    try:
        log_path = Path(LOG_FILE)
        if log_path.exists():
            with open(log_path, "r") as f:
                all_lines = f.readlines()
                return [line.strip() for line in all_lines[-lines:]]
    except Exception as e:
        st.warning(f"Could not read log file: {e}")
    return []


def get_status_color(status: str) -> str:
    """Get color for status badge."""
    status_colors = {
        "IDLE": "🟢",
        "BIDDING": "🟡",
        "EXECUTING": "🔵",
        "OFFLINE": "⚫",
    }
    return status_colors.get(status, "⚪")


def format_battery_bar(battery: float) -> str:
    """Create a text-based battery bar."""
    percentage = int(battery / 10)
    bar = "█" * percentage + "░" * (10 - percentage)
    return f"{bar} {battery:.1f}%"


def main():
    st.set_page_config(
        page_title="USOS Swarm Dashboard",
        page_icon="🛰️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .satellite-card {
            border: 2px solid #1f77b4;
            border-radius: 10px;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .winner-badge {
            background-color: #ffd700;
            padding: 10px 15px;
            border-radius: 5px;
            font-weight: bold;
            text-align: center;
            color: black;
        }
        .log-container {
            background-color: #1e1e1e;
            color: #00ff00;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            max-height: 400px;
            overflow-y: auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🛰️ USOS Orbital Network - Real-time Swarm Dashboard")
    st.markdown(
        "**Distributed Satellite Autonomy | Consensus-based Task Allocation**"
    )

    # Auto-refresh
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with col2:
        if st.button("🔄 Refresh Now", key="refresh_btn"):
            st.rerun()
    with col3:
        st.markdown("")

    # Read current state
    swarm_state = read_swarm_state()

    # System Status
    st.markdown("## 📊 System Status")
    status_col1, status_col2, status_col3 = st.columns(3)

    active_nodes = sum(1 for state in swarm_state.values() if state.get("battery", 0) > 0)
    with status_col1:
        st.metric("🛰️ Active Nodes", f"{active_nodes}/{len(SATELLITE_IDS)}")
    with status_col2:
        avg_battery = (
            sum(state.get("battery", 0) for state in swarm_state.values())
            / len(SATELLITE_IDS)
            if swarm_state
            else 0
        )
        st.metric("🔋 Avg Battery", f"{avg_battery:.1f}%")
    with status_col3:
        total_tasks = sum(
            1
            for state in swarm_state.values()
            if state.get("current_task") is not None
        )
        st.metric("📋 Active Tasks", total_tasks)

    # Satellite Status Cards
    st.markdown("## 🛰️ Satellite Status")
    st.markdown(
        "Each satellite calculates a **Bid Score** = (Battery × 0.5) + (100 if position matches task)"
    )

    sat_cols = st.columns(3)

    for idx, sat_id in enumerate(SATELLITE_IDS):
        with sat_cols[idx]:
            sat_state = swarm_state.get(sat_id, {})

            if not sat_state:
                st.warning(f"{sat_id}: OFFLINE")
                continue

            # Winner Badge
            if sat_state.get("is_winner"):
                st.markdown(
                    f'<div class="winner-badge">⭐ WINNER ⭐</div>',
                    unsafe_allow_html=True,
                )

            # Basic Info
            st.markdown(f"### {sat_id}")
            status = sat_state.get("status", "OFFLINE")
            st.markdown(f"{get_status_color(status)} **Status:** {status}")

            # Battery
            battery = sat_state.get("battery", 0)
            st.markdown(f"**Battery:** {format_battery_bar(battery)}")
            if battery < 20:
                st.warning("⚠️ Low battery")

            # Position
            position = sat_state.get("position", "UNKNOWN")
            st.markdown(f"**Position:** {position}")

            # Current Task
            current_task = sat_state.get("current_task")
            if current_task:
                st.markdown(
                    f"**Task:** {current_task.get('task')} @ {current_task.get('location')}"
                )

            # Last Bid Scores
            bid_scores = sat_state.get("last_bid_scores", {})
            if bid_scores:
                st.markdown("**Last Bid Scores:**")
                for node, score in sorted(bid_scores.items(), key=lambda x: x[1], reverse=True):
                    st.text(f"  {node}: {score:.2f}")

            st.divider()

    # Event Log
    st.markdown("## 📜 Live Event Log")
    st.markdown(
        "_Shows the 'thought process' of the swarm: bids, consensus decisions, task execution_"
    )

    logs = read_logs(lines=100)

    if logs:
        log_html = "<div class='log-container'>"
        for log in logs:
            # Highlight key events with colors
            if "WINNER" in log or "Bid sent" in log:
                log_html += f'<span style="color: #ffff00;">{log}</span><br>'
            elif "Yielding" in log or "CONSENSUS" in log:
                log_html += f'<span style="color: #00ff00;">{log}</span><br>'
            elif "ERROR" in log or "Failed" in log:
                log_html += f'<span style="color: #ff0000;">{log}</span><br>'
            else:
                log_html += f"{log}<br>"
        log_html += "</div>"
        st.markdown(log_html, unsafe_allow_html=True)
    else:
        st.info("Waiting for satellite activity...")

    # Footer
    st.markdown("---")
    st.markdown(
        """
        **How It Works:**
        1. Ground Station broadcasts a task (e.g., "Image SECTOR_4")
        2. Each satellite calculates a bid score based on battery and position
        3. Satellites broadcast bids to peers (2-second consensus window)
        4. Satellite with highest score **automatically becomes executor** (no ground intervention)
        5. Other satellites yield and return to IDLE
        6. **Fault Tolerance:** If executor fails, next-best node executes on next task broadcast
        """
    )


if __name__ == "__main__":
    # Auto-refresh every 1 second
    st.markdown(
        """
        <script>
        const interval = setInterval(() => {
            const button = document.querySelector('button[key="refresh_btn"]');
            if (button) button.click();
        }, 1000);
        </script>
        """,
        unsafe_allow_html=True,
    )

    main()
