import streamlit as st
import json
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import get_redis_client

st.set_page_config(layout="wide", page_title="Under the Hood | OrbitalNet OS", page_icon="\u2699\ufe0f")

r = get_redis_client()

st.markdown("""
<style>
    .formula-box { background: #0d1117; border: 1px solid #3a4a5a; border-radius: 8px; padding: 16px;
                   font-family: monospace; font-size: 0.82rem; color: #c8d6e5; white-space: pre; }
    .metric-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
                   border-radius: 8px; padding: 14px; margin-bottom: 8px; }
    .won-row { background: rgba(0,255,136,0.08) !important; color: #00ff88 !important; }
    .lost-row { color: #ff3344 !important; }
</style>
""", unsafe_allow_html=True)

st.title("\u2699\ufe0f Swarm Intelligence Forensics")
st.caption("Breaking the black box. Every decision the swarm makes is logged, scored, and explained here.")

# Auto-refresh — evaluated AFTER all tabs render (at bottom of script)
col_r, col_s = st.columns([4, 1])
with col_s:
    auto_refresh = st.toggle("Auto-refresh", value=False)

# ── TABS ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "\U0001f3af Live Bidding Arena",
    "\U0001f9fe Auction Ledger",
    "\U0001f50d Node Deep Scan",
    "\U0001f4ca Fleet Statistics"
])

# ============================================================
# TAB 1 - LIVE BIDDING ARENA
# ============================================================
with tab1:
    st.markdown("### \U0001f3af Live Bidding Arena")
    st.markdown("Every active mission, its current enclave, and how long each satellite has been on contract.")

    try:
        missions_raw = r.hgetall("MISSIONS_LEDGER")
        logs_raw     = r.hgetall("AUCTION_LOGS")
    except Exception:
        missions_raw = {}
        logs_raw     = {}

    if not missions_raw:
        st.info("No active missions. Go to **Ground Station** and dispatch a scenario.")
    else:
        executing = [(mid, json.loads(mj)) for mid, mj in missions_raw.items()
                     if json.loads(mj).get("status") == "EXECUTING"]
        pending   = [(mid, json.loads(mj)) for mid, mj in missions_raw.items()
                     if json.loads(mj).get("status") == "OPEN_AUCTION"]

        # Summary metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Missions Executing",  len(executing))
        c2.metric("Auctions Open",       len(pending))
        c3.metric("Total Missions",      len(missions_raw))

        st.markdown("---")

        # ── EXECUTING missions ──────────────────────────────
        if executing:
            st.markdown("#### Currently Executing Missions")
            for mid, mission in executing:
                sensor  = mission.get("sensor_required", "?")
                enclave = mission.get("enclave", [])
                req     = mission.get("required_nodes", 1)
                st.markdown(
                    f"<div class='metric-card'>"
                    f"<b style='color:#00ff88'>\u25cf {mid}</b> &nbsp; "
                    f"<span style='color:#ffcc1a'>[{sensor}]</span> &nbsp; "
                    f"Target: {mission.get('target_lat',0):.2f}\u00b0, {mission.get('target_lon',0):.2f}\u00b0 &nbsp;|&nbsp; "
                    f"Enclave: <b style='color:#3399ff'>{len(enclave)}/{req} nodes</b><br>"
                    f"<small style='color:#5a6e82'>Zone radius: {mission.get('target_radius',0)} km</small>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                if enclave:
                    try:
                        enclave_data = r.mget(enclave)
                        fleet = [json.loads(item) for item in enclave_data if item]
                        if fleet:
                            df_enc = pd.DataFrame([{
                                "Node ID":     s["id"],
                                "Payload":     s.get("payload_type", "?"),
                                "Score":       round(s.get("current_score", 0), 4),
                                "Battery (%)": round(s.get("telemetry", {}).get("P0_Gatekeepers", {}).get("soc", 0) * 100, 1),
                                "Role":        s.get("role", "?"),
                            } for s in fleet])
                            st.dataframe(df_enc, width="stretch")
                    except Exception:
                        st.caption("Enclave nodes not responding.")

        # ── PENDING auctions ────────────────────────────────
        if pending:
            st.markdown("#### Open Auctions (Bidding in Progress)")
            for mid, mission in pending:
                sensor = mission.get("sensor_required", "?")
                st.markdown(
                    f"<div class='metric-card' style='border-color:rgba(255,204,26,0.3)'>"
                    f"<b style='color:#ffcc1a'>\u25cb {mid}</b> &nbsp; [{sensor}] &nbsp;"
                    f"Waiting for {mission.get('required_nodes',1)} {sensor} nodes within "
                    f"{mission.get('target_radius',0)+1000} km"
                    f"</div>",
                    unsafe_allow_html=True
                )

    # (auto-refresh handled at bottom of script)

# ============================================================
# TAB 2 - AUCTION LEDGER
# ============================================================
with tab2:
    st.markdown("### \U0001f9fe Contract Net Protocol (CNP) - Historical Auction Records")
    st.markdown("Every completed auction, permanently logged with full mathematical transparency.")

    st.markdown("""
<div class='formula-box'>Ci Normalized Auction Score (max = 1.0):
  auction_score = (proximity_score x W_prox) + (battery x W_batt)
  proximity_score = max(0, (max_view_dist - actual_dist) / max_view_dist)  in [0, 1]
  max_view_dist = zone_radius + 1000 km  |  W defaults: proximity=0.7, battery=0.3
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    try:
        logs_raw2 = r.hgetall("AUCTION_LOGS")
    except Exception:
        logs_raw2 = {}

    if not logs_raw2:
        st.info("No completed auctions yet. Dispatch a mission from the Ground Station.")
    else:
        for mission_id, log_json in reversed(list(logs_raw2.items())):
            log     = json.loads(log_json)
            bidders = log.get("bidders", [])
            winners = [b for b in bidders if b.get("Result") == "WON"]
            losers  = [b for b in bidders if b.get("Result") == "LOST"]
            sensor  = log.get("sensor", "?")
            icons   = {"SAR": "[SAR]", "EO": "[EO]", "SIGINT": "[SIG]", "MW": "[MW]", "RELAY": "[RLY]"}
            icon    = icons.get(sensor, "[?]")

            with st.expander(
                f"{icon} {mission_id} | {sensor} | "
                f"{log.get('total_bidders',0)} bidders | {log.get('winners',0)} selected",
                expanded=False
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Sensor",        sensor)
                c2.metric("Target",        f"{log.get('target_lat',0):.2f}\u00b0, {log.get('target_lon',0):.2f}\u00b0")
                c3.metric("Zone Radius",   f"{log.get('radius',0)} km")
                c4.metric("Max Slew Dist", f"{log.get('radius',0)+1000} km")

                if bidders:
                    df_bid    = pd.DataFrame(bidders)
                    col_order = ["Result", "Node ID", "Payload", "Distance (km)", "Battery (%)", "Prox Score", "Auction Score"]
                    df_bid    = df_bid[[c for c in col_order if c in df_bid.columns]]

                    def color_result(val):
                        if val == "WON":
                            return "background-color:rgba(0,255,136,0.1);color:#00ff88;font-weight:bold"
                        return "color:#ff3344"

                    styled = df_bid.style.map(color_result, subset=["Result"])
                    st.dataframe(styled, width="stretch")

                    if winners and losers:
                        bw     = max(winners, key=lambda b: b.get("Auction Score", 0))
                        bl     = max(losers,  key=lambda b: b.get("Auction Score", 0))
                        margin = bw["Auction Score"] - bl["Auction Score"]
                        st.success(
                            f"**Winning margin:** {bw['Node ID']} scored `{bw['Auction Score']:.4f}` "
                            f"vs `{bl['Auction Score']:.4f}` (nearest loser) | delta = `{margin:.4f}`"
                        )

        if st.button("Clear Auction Logs"):
            r.delete("AUCTION_LOGS")
            st.rerun()

# ============================================================
# TAB 3 - NODE DEEP SCAN
# ============================================================
with tab3:
    st.markdown("### \U0001f50d Node Deep Scan - Full Telemetry Vector")
    st.caption("Select any satellite to inspect every parameter driving its real-time Ci capability score.")

    try:
        all_keys = r.keys("STARLINK-*")
    except Exception:
        all_keys = []

    if not all_keys:
        st.warning("No satellite telemetry in Redis. Ensure the Physics Engine is running.")
    else:
        try:
            missions_raw3 = r.hgetall("MISSIONS_LEDGER")
        except Exception:
            missions_raw3 = {}

        # Build enclave lookup for role decoration
        enclave_lookup = {}
        for mid, mj in missions_raw3.items():
            m = json.loads(mj)
            for nid in m.get("enclave", []):
                enclave_lookup[nid] = m.get("sensor_required", "?")

        try:
            sample_raw = r.mget(all_keys[:500])
        except Exception:
            sample_raw = []

        sat_list = [json.loads(s) for s in sample_raw if s]

        def label(s):
            hw   = s.get("payload_type", "?")
            role = "ACTIVE" if s["id"] in enclave_lookup else s.get("role", "MEMBER")
            return f"{s['id']} [{hw}] - {role}"

        options = sorted([label(s) for s in sat_list])
        chosen  = st.selectbox("Select Target Node for Deep Scan", options)
        chosen_id = chosen.split(" [")[0]

        sat_raw = r.get(chosen_id)
        if sat_raw:
            sat_data = json.loads(sat_raw)
            hw       = sat_data.get("payload_type", "?")
            role     = "MISSION_ACTIVE" if chosen_id in enclave_lookup else sat_data.get("role", "MEMBER")
            battery  = sat_data.get("telemetry", {}).get("P0_Gatekeepers", {}).get("soc", 0) * 100
            score    = sat_data.get("current_score", 0)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Ci Score",    round(score, 4))
            col2.metric("Hardware",    hw)
            col3.metric("Role",        role)
            col4.metric("Battery",     f"{battery:.1f}%")
            col5.metric("Ground Track", f"{sat_data.get('lat',0):.2f}\u00b0, {sat_data.get('lon',0):.2f}\u00b0")

            st.markdown("---")
            st.markdown("#### Full Telemetry State Vector")
            telem = sat_data.get("telemetry", {})
            rows  = []
            for group, params in telem.items():
                for k, v in params.items():
                    try:
                        norm_v = max(0.0, min(float(v), 1.0))
                        filled = int(norm_v * 20)
                        bar    = "[" + "#" * filled + "-" * (20 - filled) + "]  " + f"{norm_v:.2f}"
                    except Exception:
                        bar = "[--------------------]  N/A"
                    rows.append({
                        "Group":     group.replace("_", " "),
                        "Parameter": k.replace("_", " ").title(),
                        "Value":     round(v, 4),
                        "Visual":    bar
                    })

            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch")

            st.markdown("---")
            st.markdown("#### Score Composition Formula")
            st.latex(r"C_i = \sum_{k} w_k \cdot p_k")
            st.caption("w_k = parameter weight from scoring engine | p_k = normalized telemetry value")

            try:
                score_raw = r.hgetall("SCORING_WEIGHTS")
                if score_raw:
                    w_df = pd.DataFrame([{"Parameter": k, "Weight": float(v)} for k, v in score_raw.items()])
                    st.dataframe(w_df, width="stretch")
            except Exception:
                pass

# ============================================================
# TAB 4 - FLEET STATISTICS
# ============================================================
with tab4:
    st.markdown("### Fleet Statistics - Real-Time Constellation Health")

    try:
        all_keys4 = r.keys("STARLINK-*")
    except Exception:
        all_keys4 = []

    try:
        all_missions_raw4 = r.hgetall("MISSIONS_LEDGER")
    except Exception:
        all_missions_raw4 = {}

    # Resolve active satellite IDs from enclaves
    active_ids = set()
    for mid, mj in all_missions_raw4.items():
        m = json.loads(mj)
        if m.get("status") == "EXECUTING":
            active_ids.update(m.get("enclave", []))

    try:
        sample_raw4 = r.mget(all_keys4[:1000]) if all_keys4 else []
    except Exception:
        sample_raw4 = []

    fleet_data = [json.loads(s) for s in sample_raw4 if s]

    if not fleet_data:
        st.warning("No telemetry data available. Ensure the Physics Engine is running.")
    else:
        # -- Summary metrics --
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total Nodes Online",   len(fleet_data))
        mc2.metric("Nodes in Active Role", len(active_ids))
        avg_bat = sum(
            s.get("telemetry", {}).get("P0_Gatekeepers", {}).get("soc", 0)
            for s in fleet_data
        ) / max(len(fleet_data), 1) * 100
        mc3.metric("Avg Battery",          f"{avg_bat:.1f}%")
        avg_score = sum(s.get("current_score", 0) for s in fleet_data) / max(len(fleet_data), 1)
        mc4.metric("Avg Ci Score",         f"{avg_score:.3f}")

        st.markdown("---")

        # Build per-hardware breakdown
        hw_counts  = {}
        hw_scores  = {}
        hw_battery = {}
        isl_vals   = []
        score_vals = []
        bat_vals   = []

        for s in fleet_data:
            hw  = s.get("payload_type", "UNKNOWN")
            sc  = s.get("current_score", 0)
            bat = s.get("telemetry", {}).get("P0_Gatekeepers", {}).get("soc", 0) * 100
            isl = s.get("telemetry", {}).get("P2_Efficiency", {}).get("isl_throughput", 0)

            hw_counts[hw]  = hw_counts.get(hw, 0) + 1
            hw_scores[hw]  = hw_scores.get(hw, []) + [sc]
            hw_battery[hw] = hw_battery.get(hw, []) + [bat]
            score_vals.append(sc)
            bat_vals.append(bat)
            isl_vals.append(isl)

        col_l, col_r = st.columns(2)

        with col_l:
            # Hardware distribution pie
            fig_hw = go.Figure(go.Pie(
                labels=list(hw_counts.keys()),
                values=list(hw_counts.values()),
                hole=0.4,
                marker=dict(colors=["#cc33ff", "#3399ff", "#ffcc1a", "#ff8000", "#666666"])
            ))
            fig_hw.update_layout(
                title="Hardware Distribution",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c8d6e5"),
                legend=dict(font=dict(color="#c8d6e5")),
                margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_hw, width="stretch", config={"displayModeBar": False})

            # Avg Ci score by hardware type
            avg_scores_by_hw = {k: sum(v)/len(v) for k, v in hw_scores.items()}
            fig_sc = go.Figure(go.Bar(
                x=list(avg_scores_by_hw.keys()),
                y=list(avg_scores_by_hw.values()),
                marker_color=["#cc33ff", "#3399ff", "#ffcc1a", "#ff8000", "#666666"]
            ))
            fig_sc.update_layout(
                title="Avg Ci Score by Hardware Type",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(5,8,15,0.8)",
                font=dict(color="#c8d6e5"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_sc, width="stretch", config={"displayModeBar": False})

        with col_r:
            # Battery health histogram
            fig_bat = go.Figure(go.Histogram(
                x=bat_vals,
                nbinsx=30,
                marker_color="#3399ff",
                opacity=0.8
            ))
            fig_bat.update_layout(
                title="Fleet Battery Health Distribution",
                xaxis_title="State of Charge (%)",
                yaxis_title="Node Count",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(5,8,15,0.8)",
                font=dict(color="#c8d6e5"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_bat, width="stretch", config={"displayModeBar": False})

            # ISL Throughput histogram
            fig_isl = go.Figure(go.Histogram(
                x=isl_vals,
                nbinsx=30,
                marker_color="#00ff88",
                opacity=0.8
            ))
            fig_isl.update_layout(
                title="ISL Throughput Distribution",
                xaxis_title="ISL Throughput (normalized)",
                yaxis_title="Node Count",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(5,8,15,0.8)",
                font=dict(color="#c8d6e5"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_isl, width="stretch", config={"displayModeBar": False})

        st.markdown("---")

        # Bandwidth table per hardware type
        band_rows = []
        for hw, scores in hw_scores.items():
            bats = hw_battery[hw]
            band_rows.append({
                "Hardware":      hw,
                "Node Count":    hw_counts[hw],
                "Avg Ci Score":  round(sum(scores)/len(scores), 4),
                "Min Ci":        round(min(scores), 4),
                "Max Ci":        round(max(scores), 4),
                "Avg Battery %": round(sum(bats)/len(bats), 1),
            })
        band_df = pd.DataFrame(band_rows).sort_values("Node Count", ascending=False)
        st.markdown("#### Hardware Capability Summary")
        st.dataframe(band_df, width="stretch")

        # per-hardware table
        hw_rows = []
        for hw in hw_counts:
            hw_rows.append({
                "Type":          hw,
                "Count":         hw_counts[hw],
                "Active":        sum(1 for s in fleet_data if s.get("payload_type") == hw and s["id"] in active_ids),
                "Avg Score":     round(sum(hw_scores[hw])/len(hw_scores[hw]), 4),
                "Avg Battery %": round(sum(hw_battery[hw])/len(hw_battery[hw]), 1)
            })
        hw_table = pd.DataFrame(hw_rows).sort_values("Count", ascending=False)
        st.markdown("#### Per-Type Operational Readiness")
        st.dataframe(hw_table, width="stretch")

# ============================================================
# AUTO-REFRESH - runs AFTER all 4 tabs have rendered
# Default OFF so users can browse freely; enable to get live updates
# ============================================================
if auto_refresh:
    time.sleep(4)
    st.rerun()
