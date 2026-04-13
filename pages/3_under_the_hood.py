import streamlit as st
import json
import pandas as pd
import math
from config import get_redis_client

st.set_page_config(layout="wide", page_title="Under the Hood | OrbitalNet OS", page_icon="⚙️")

r = get_redis_client()

st.markdown("""
<style>
    .metric-card { background: rgba(5,8,15,0.8); border: 1px solid rgba(0,255,136,0.2); 
                   border-radius: 8px; padding: 16px; }
    .won  { color: #00ff88; font-weight: bold; }
    .lost { color: #ff3344; }
    .formula-box { background: rgba(0,170,255,0.07); border-left: 3px solid #00aaff; 
                   padding: 12px 16px; border-radius: 4px; font-family: monospace; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ Swarm Intelligence Forensics")
st.markdown("Breaking the black box. Every number, every decision, in real time.")

tab1, tab2, tab3 = st.tabs(["🧾 Auction Ledger", "🔍 Node Deep Scan", "📊 Fleet Statistics"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — AUCTION LEDGER
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Contract Net Protocol (CNP) — Auction Forensics")
    st.markdown("""
    This tab shows the **exact mathematics** the consensus engine used to select every winning satellite.
    Dispatch a mission from the Ground Station and return here to see the full bidder scorecard.
    """)

    st.markdown('<div class="formula-box">'
        '📐 <b>Auction Score Formula:</b><br>'
        'auction_score = (proximity_score × 0.7) + (battery × 0.3)<br>'
        'proximity_score = max(0, (max_view_distance − actual_distance) / 100)<br>'
        'max_view_distance = operational_radius + 1000 km  (LEO slew margin)'
        '</div>', unsafe_allow_html=True)

    st.markdown("---")

    try:
        logs_raw = r.hgetall("AUCTION_LOGS")
    except Exception:
        logs_raw = {}

    if not logs_raw:
        st.info("⏳ No auction logs yet. Go to **Ground Station → Mission Deployment** and broadcast a scenario. The engine will log the full decision here the moment an enclave forms.")
    else:
        # Sort newest last (mission IDs are timestamped by hash, show all)
        for mission_id, log_json in reversed(list(logs_raw.items())):
            log = json.loads(log_json)
            bidders = log.get("bidders", [])
            winners = [b for b in bidders if b.get("Result") == "WON"]
            losers  = [b for b in bidders if b.get("Result") == "LOST"]

            sensor_icons = {"SAR": "🔵", "EO": "🟣", "SIGINT": "🟡", "MW": "🟠", "RELAY": "⚫"}
            icon = sensor_icons.get(log.get("sensor", ""), "⚪")

            with st.expander(
                f"{icon} **{mission_id}** — {log.get('sensor')} Sensor | "
                f"{log.get('total_bidders', 0)} bidders → {log.get('winners', 0)} selected",
                expanded=True
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Sensor Type",    log.get("sensor", "?"))
                c2.metric("Target Lat/Lon", f"{log.get('target_lat', 0):.2f}°, {log.get('target_lon', 0):.2f}°")
                c3.metric("Zone Radius",    f"{log.get('radius', 0)} km")
                c4.metric("Slew Margin",    f"+1000 km = {log.get('radius', 0)+1000} km total")

                st.markdown("#### Scoring Breakdown (All Eligible Bidders)")
                st.markdown(f"*{len(bidders)} satellites were within sensor range. "
                            f"Top {log.get('winners')} by Auction Score won the contract.*")

                if bidders:
                    df = pd.DataFrame(bidders)
                    # Reorder for clarity
                    col_order = ["Result", "Node ID", "Payload", "Distance (km)",
                                 "Battery (%)", "Prox Score", "Auction Score"]
                    df = df[[c for c in col_order if c in df.columns]]

                    def style_row(row):
                        base = [""] * len(row)
                        if row.get("Result") == "WON":
                            return [
                                "background-color: rgba(0,255,136,0.08); color:#00ff88; font-weight:bold"
                                if i == 0 else
                                "background-color: rgba(0,255,136,0.05)"
                                for i in range(len(row))
                            ]
                        else:
                            return ["color:#ff3344" if i == 0 else "color:#8899aa"
                                    for i in range(len(row))]

                    styled = df.style.apply(style_row, axis=1)
                    st.dataframe(styled, use_container_width=True)

                    # Show the margin of victory
                    if len(winners) > 0 and len(losers) > 0:
                        best_winner = max(winners, key=lambda b: b["Auction Score"])
                        best_loser  = max(losers,  key=lambda b: b["Auction Score"])
                        margin = best_winner["Auction Score"] - best_loser["Auction Score"]
                        st.success(f"**Winning margin:** {best_winner['Node ID']} scored "
                                   f"`{best_winner['Auction Score']}` vs "
                                   f"nearest loser `{best_loser['Auction Score']}` — margin: `{margin:.4f}`")

        if st.button("🗑️ Clear Auction Logs"):
            r.delete("AUCTION_LOGS")
            st.warning("Auction logs cleared.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — NODE DEEP SCAN
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Node Deep Scan — Full Telemetry Vector")
    st.markdown("Select any satellite to see its complete 30-parameter state vector and real-time $C_i$ score computation.")

    try:
        sample_keys = r.keys('STARLINK-*')[:500]  # Sample for the selector
        raw_data = r.mget(sample_keys) if sample_keys else []
        fleet = [json.loads(item) for item in raw_data if item]
    except Exception:
        fleet = []

    if not fleet:
        st.warning("No telemetry available. Ensure the Physics Engine is running.")
    else:
        # Put mission-active and plane leads at top of list
        def sort_key(s):
            role = s.get('role', 'MEMBER')
            if role == 'MISSION_ACTIVE': return 0
            if role == 'PLANE_LEAD':    return 1
            return 2
        fleet_sorted = sorted(fleet, key=sort_key)

        sat_options = [f"{s['id']} [{s.get('payload_type','?')}] {s.get('role','MEMBER')}" for s in fleet_sorted]
        selected = st.selectbox("Select Target Node for Deep Scan", sat_options)

        if selected:
            sat_id = selected.split(" ")[0]
            sat_data = next((s for s in fleet_sorted if s['id'] == sat_id), None)

            if sat_data:
                score = sat_data.get('current_score', 0.0)
                role  = sat_data.get('role', 'FOLLOWER')
                ptype = sat_data.get('payload_type', '?')

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Capability Score (Cᵢ)", f"{score:.4f}")
                col2.metric("Hardware", ptype)
                col3.metric("Role", role)
                col4.metric("Ground Track", f"{sat_data.get('lat',0):.2f}°, {sat_data.get('lon',0):.2f}°")

                st.markdown("---")
                st.markdown("#### Full Telemetry State Vector")
                telem = sat_data.get('telemetry', {})

                rows = []
                for group, params in telem.items():
                    group_label = group.replace('_', ' ')
                    for k, v in params.items():
                        param_name = k.replace('_', ' ').title()
                        bar = "█" * int(max(0, min(v, 1.0)) * 20) + "░" * (20 - int(max(0, min(v, 1.0)) * 20))
                        rows.append({
                            "Group":     group_label,
                            "Parameter": param_name,
                            "Value":     round(v, 4),
                            "Bar":       bar
                        })

                if rows:
                    df_telem = pd.DataFrame(rows)
                    st.dataframe(df_telem, use_container_width=True)
                else:
                    st.warning("Telemetry vector empty.")

                st.markdown("---")
                st.markdown("#### Score Composition")
                st.markdown("""
                The $C_i$ **Capability Score** is computed by the Scoring Engine as a weighted dot product
                of all telemetry parameters against the mission's priority weights:

                $$C_i = \\sum_{k} w_k \\cdot p_k$$

                Where $w_k$ is the weight for parameter $k$ (e.g. `look_angle`, `soc`, `isl_throughput`)
                and $p_k$ is the satellite's normalized parameter value.
                """)

                # Check if this satellite won any mission
                try:
                    logs_raw = r.hgetall("AUCTION_LOGS")
                    won_in = []
                    for mid, ljson in logs_raw.items():
                        log = json.loads(ljson)
                        match = next((b for b in log.get("bidders", []) if b["Node ID"] == sat_id and b["Result"] == "WON"), None)
                        if match:
                            won_in.append((mid, match))
                    if won_in:
                        st.success(f"✅ This node won **{len(won_in)}** mission auction(s):")
                        for mid, match in won_in:
                            st.write(f"- **{mid}** | Auction Score: `{match['Auction Score']}` | Distance: `{match['Distance (km)']} km`")
                    else:
                        st.info("This node has not participated in any completed auction yet.")
                except Exception:
                    pass

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — FLEET STATISTICS
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Fleet Statistics — Real-Time Constellation Health")

    try:
        all_keys = r.keys('STARLINK-*')
        raw = r.mget(all_keys[:2000]) if all_keys else []
        full_fleet = [json.loads(item) for item in raw if item]
    except Exception:
        full_fleet = []

    if not full_fleet:
        st.warning("No fleet data. Ensure Physics Engine is active.")
    else:
        total = len(full_fleet)
        by_payload = {}
        by_role    = {}
        scores     = []

        for s in full_fleet:
            pt = s.get('payload_type', 'UNKNOWN')
            role = s.get('role', 'MEMBER')
            by_payload[pt]   = by_payload.get(pt, 0) + 1
            by_role[role]    = by_role.get(role, 0) + 1
            scores.append(s.get('current_score', 0))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Visible Nodes", total)
        c2.metric("Avg Score Cᵢ",  f"{sum(scores)/len(scores):.4f}" if scores else "—")
        c3.metric("Max Score",      f"{max(scores):.4f}" if scores else "—")
        c4.metric("Mission Active", by_role.get('MISSION_ACTIVE', 0))

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Hardware Distribution")
            hw_df = pd.DataFrame(
                [(k, v, f"{v/total*100:.1f}%") for k, v in sorted(by_payload.items(), key=lambda x: -x[1])],
                columns=["Hardware Type", "Count", "% of Fleet"]
            )
            st.dataframe(hw_df, use_container_width=True)

        with col2:
            st.markdown("#### Role Distribution")
            role_df = pd.DataFrame(
                [(k, v, f"{v/total*100:.1f}%") for k, v in sorted(by_role.items(), key=lambda x: -x[1])],
                columns=["Role", "Count", "% of Fleet"]
            )
            st.dataframe(role_df, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Score Distribution")
        buckets = {"Critical (0–1)": 0, "Warning (1–2)": 0, "Nominal (2–3)": 0, "Optimal (3+)": 0}
        for s in scores:
            if s < 1: buckets["Critical (0–1)"] += 1
            elif s < 2: buckets["Warning (1–2)"] += 1
            elif s < 3: buckets["Nominal (2–3)"] += 1
            else: buckets["Optimal (3+)"] += 1

        score_df = pd.DataFrame(
            [(k, v, f"{v/total*100:.1f}%") for k, v in buckets.items()],
            columns=["Score Band", "Count", "% of Fleet"]
        )
        st.dataframe(score_df, use_container_width=True)
