import streamlit as st
import json
import time
import pandas as pd
from config import get_redis_client

st.set_page_config(layout="wide", page_title="Under the Hood | OrbitalNet OS", page_icon="⚙️")

r = get_redis_client()

st.markdown("""
<style>
  .formula-box { background: rgba(0,170,255,0.07); border-left: 3px solid #00aaff;
  padding: 12px 16px; border-radius: 4px; font-family: monospace; font-size: 0.85rem; }
  .won-badge  { background: rgba(0,255,136,0.15); color: #00ff88; padding: 2px 8px;
  border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
  .lost-badge { background: rgba(255,51,68,0.12); color: #ff3344; padding: 2px 8px;
  border-radius: 4px; font-size: 0.8rem; }
  .mission-executing { border-left: 3px solid #00ff88; padding-left: 10px; }
  .mission-auction  { border-left: 3px solid #ffcc1a; padding-left: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ Swarm Intelligence Forensics")
st.caption("Breaking the black box. Every number, every decision, in real time.")

#  Auto-refresh control  
col_r1, col_r2 = st.columns([5, 1])
with col_r2:
  auto_refresh = st.checkbox("Auto-refresh", value=True)
if auto_refresh:
  st.empty()  # placeholder, real refresh via rerun below

tab1, tab2, tab3, tab4 = st.tabs([
  "🎯 Live Bidding Arena",
  "🧾 Auction Ledger",
  "🔍 Node Deep Scan",
  "📊 Fleet Statistics"
])

#  
# TAB 1  LIVE BIDDING ARENA
#  
with tab1:
  st.markdown("### 🎯 Live Bidding Arena")
  st.markdown("Every active mission, its current enclave, and how long each satellite has been on contract.")

  try:
  missions_raw = r.hgetall("MISSIONS_LEDGER")
  logs_raw  = r.hgetall("AUCTION_LOGS")
  except Exception:
  missions_raw = {}
  logs_raw  = {}

  if not missions_raw:
  st.info("3 No active missions. Go to **Ground Station** and dispatch a scenario.")
  else:
  executing = [(mid, json.loads(mj)) for mid, mj in missions_raw.items()
  if json.loads(mj).get("status") == "EXECUTING"]
  pending  = [(mid, json.loads(mj)) for mid, mj in missions_raw.items()
  if json.loads(mj).get("status") == "OPEN_AUCTION"]

  #  Summary bar  
  c1, c2, c3 = st.columns(3)
  c1.metric("Missions Executing", len(executing))
  c2.metric("Auctions Open",  len(pending))
  c3.metric("Total Missions",  len(missions_raw))

  st.markdown("---")

  #  EXECUTING missions  
  if executing:
  st.markdown("####  Currently Executing Missions")
  for mission_id, mission in executing:
  enclave  = mission.get("enclave", [])
  sensor  = mission.get("sensor_required", "?")
  lat  = mission.get("target_lat", 0)
  lon  = mission.get("target_lon", 0)
  radius  = mission.get("target_radius", 500)
  req_nodes = mission.get("required_nodes", 1)
  name  = mission.get("name", mission_id)

  sensor_color = {"SAR": "#cc33ff", "EO": "#3399ff", "SIGINT": "#ffcc1a",
  "MW": "#ff8000", "RELAY": "#666"}.get(sensor, "#00ff88")

  label = (f"{' ' if len(enclave) >= req_nodes else ''} **{name}** "
  f"| {sensor} | {len(enclave)}/{req_nodes} nodes locked "
  f"| Target: {lat:.1f}deg, {lon:.1f}deg | Zone: {radius} km")

  with st.expander(label, expanded=True):
  # Pull the auction log for this mission
  log = json.loads(logs_raw.get(mission_id, "{}")) if mission_id in logs_raw else {}
  all_bidders = log.get("bidders", [])
  winners_set = set(enclave)

  mc1, mc2, mc3, mc4 = st.columns(4)
  mc1.metric("Sensor", sensor)
  mc2.metric("Zone Radius", f"{radius} km")
  mc3.metric("Nodes Locked", f"{len(enclave)} / {req_nodes}")
  mc4.metric("Coordination", "Max Vote Distance")

  #  Enclave roster  
  st.markdown("**  Active Enclave (Nodes Currently Imaging)**")
  if enclave:
  now = time.time()
  roster_rows = []
  for sat_id in enclave:
  try:
  sat_raw = r.get(sat_id)
  sat = json.loads(sat_raw) if sat_raw else {}
  except Exception:
  sat = {}

  gk  = sat.get("telemetry", {}).get("P0_Gatekeepers", {})
  battery = round(gk.get("soc", 0) * 100, 1)
  score  = round(sat.get("current_score", 0), 4)
  lat_s  = round(sat.get("lat", 0), 2)
  lon_s  = round(sat.get("lon", 0), 2)
  ptype  = sat.get("payload_type", "?")

  # Get their auction score from the log
  bid = next((b for b in all_bidders if b.get("Node ID") == sat_id), {})
  auction_sc = bid.get("Auction Score", "  ")
  dist_km  = bid.get("Distance (km)", "  ")

  roster_rows.append({
  "Node ID":  sat_id,
  "Hardware":  ptype,
  "Lat / Lon":  f"{lat_s}deg, {lon_s}deg",
  "Battery (%)":  battery,
  "C Score":  score,
  "Auction Score":  auction_sc,
  "Dist to Target": dist_km,
  "Status":  " ACTIVE"
  })

  roster_df = pd.DataFrame(roster_rows)

  def style_roster(row):
  return ["background-color: rgba(0,255,136,0.07)"] * len(row)

  st.dataframe(roster_df.style.apply(style_roster, axis=1),
  width='stretch')
  else:
  st.warning("Enclave is forming  no satellites locked yet.")

  #  Full bidder history from auction log  
  if all_bidders:
  st.markdown("**  Original Auction  Full Bidder Scorecard**")
  st.caption(f"{len(all_bidders)} satellites competed * Top {req_nodes} by score won")

  df_bid = pd.DataFrame(all_bidders)
  col_order = ["Result", "Node ID", "Payload", "Distance (km)",
  "Battery (%)", "Prox Score", "Auction Score"]
  df_bid = df_bid[[c for c in col_order if c in df_bid.columns]]

  def color_result(val):
  if val == "WON":  return "background-color:rgba(0,255,136,0.1);color:#00ff88;font-weight:bold"
  return "color:#ff3344"

  styled = df_bid.style.map(color_result, subset=["Result"])
  st.dataframe(styled, width='stretch')

  # Margin of victory
  won  = [b for b in all_bidders if b.get("Result") == "WON"]
  lost = [b for b in all_bidders if b.get("Result") == "LOST"]
  if won and lost:
  best_w = max(won,  key=lambda b: b.get("Auction Score", 0))
  best_l = max(lost, key=lambda b: b.get("Auction Score", 0))
  margin = best_w["Auction Score"] - best_l["Auction Score"]
  st.success(
  f"**Winning margin:** `{best_w['Node ID']}` scored "
  f"`{best_w['Auction Score']:.4f}` vs nearest loser "
  f"`{best_l['Auction Score']:.4f}`  margin `{margin:.4f}`"
  )
  else:
  st.info("Auction log not yet written for this mission. Will appear after first enclave formation.")

  #  PENDING auctions  
  if pending:
  st.markdown("####  Open Auctions (Searching for Satellites)")
  for mission_id, mission in pending:
  sensor  = mission.get("sensor_required", "?")
  lat  = mission.get("target_lat", 0)
  lon  = mission.get("target_lon", 0)
  radius  = mission.get("target_radius", 500)
  name  = mission.get("name", mission_id)
  with st.expander(f" **{name}** | Seeking {mission.get('required_nodes')} -  {sensor} within {radius+1000} km"):
  st.write(f"**Target:** {lat:.2f}deg, {lon:.2f}deg | **Radius:** {radius} km")
  st.info("Consensus Engine is scanning the fleet for eligible nodes. Check back in 5 seconds.")


#  
# TAB 2  AUCTION LEDGER (Historical)
#  
with tab2:
  st.markdown("### Contract Net Protocol (CNP)  Historical Auction Records")
  st.markdown("Every completed auction, permanently logged with full mathematical transparency.")

  st.markdown('<div class="formula-box">'
  '  <b>Normalized Auction Score (max = 1.0):</b><br>'
  'auction_score = (proximity_score  -  W<sub>prox</sub>) + (battery  -  W<sub>batt</sub>)<br>'
  'proximity_score = max(0, (max_view_dist  actual_dist) / max_view_dist)  [0.0, 1.0]<br>'
  'max_view_dist = zone_radius + 1000 km  |  W defaults: proximity=0.7, battery=0.3'
  '</div>', unsafe_allow_html=True)

  st.markdown("---")

  try:
  logs_raw2 = r.hgetall("AUCTION_LOGS")
  except Exception:
  logs_raw2 = {}

  if not logs_raw2:
  st.info("3 No completed auctions yet. Dispatch a mission from the Ground Station.")
  else:
  for mission_id, log_json in reversed(list(logs_raw2.items())):
  log  = json.loads(log_json)
  bidders = log.get("bidders", [])
  winners = [b for b in bidders if b.get("Result") == "WON"]
  losers  = [b for b in bidders if b.get("Result") == "LOST"]

  icons = {"SAR": "[SAR]", "EO": "[EO]", "SIGINT": "[SIG]", "MW": "[MW]", "RELAY": "[RLY]"}
  icon  = icons.get(log.get("sensor", ""), "[?]")

  with st.expander(
  f"{icon} {mission_id} | {log.get('sensor','?')} | "
  f"{log.get('total_bidders',0)} bidders | {log.get('winners',0)} selected",
  expanded=False
  ):
  c1, c2, c3, c4 = st.columns(4)
  c1.metric("Sensor",  log.get("sensor", "?"))
  c2.metric("Target",  f"{log.get('target_lat',0):.2f}deg, {log.get('target_lon',0):.2f}deg")
  c3.metric("Zone Radius",  f"{log.get('radius',0)} km")
  c4.metric("Max Slew Dist",f"{log.get('radius',0)+1000} km")

  if bidders:
  df  = pd.DataFrame(bidders)
  col_order = ["Result","Node ID","Payload","Distance (km)","Battery (%)","Prox Score","Auction Score"]
  df  = df[[c for c in col_order if c in df.columns]]

  def style_bid(row):
  if row.get("Result") == "WON":
  return ["background-color:rgba(0,255,136,0.08);color:#00ff88;font-weight:bold"
  if i == 0 else "background-color:rgba(0,255,136,0.04)"
  for i in range(len(row))]
  return ["color:#ff3344" if i == 0 else "color:#8899aa" for i in range(len(row))]

  st.dataframe(df.style.apply(style_bid, axis=1), width='stretch')

  if winners and losers:
  bw = max(winners, key=lambda b: b.get("Auction Score", 0))
  bl = max(losers,  key=lambda b: b.get("Auction Score", 0))
  margin = bw["Auction Score"] - bl["Auction Score"]
  st.success(f"**Winning margin:** {bw['Node ID']} scored `{bw['Auction Score']:.4f}` "
  f"vs `{bl['Auction Score']:.4f}` (nearest loser) | delta = `{margin:.4f}`")

  if st.button("Clear Auction Logs"):
  r.delete("AUCTION_LOGS")
  st.rerun()


#  
# TAB 3  NODE DEEP SCAN
#  
with tab3:
  st.markdown("### 🔍 Node Deep Scan  -  Full Telemetry Vector")
  st.caption("Select any satellite to inspect every parameter driving its real-time C capability score.")

  try:
  # Prioritize mission-active satellites from the ledger for the top of the list
  mission_sat_ids = set()
  for mj in r.hvals("MISSIONS_LEDGER"):
  m = json.loads(mj)
  mission_sat_ids.update(m.get("enclave", []))

  sample_keys = list(mission_sat_ids)[:50]
  sample_keys += [k for k in r.keys('STARLINK-*')[:450] if k not in mission_sat_ids]
  raw_data = r.mget(sample_keys) if sample_keys else []
  fleet_ds = [json.loads(item) for item in raw_data if item]
  except Exception:
  fleet_ds = []

  if not fleet_ds:
  st.warning("No telemetry available. Ensure the Physics Engine is running.")
  else:
  def sort_ds(s):
  role = s.get('role', '')
  if role == 'MISSION_ACTIVE': return 0
  return 1
  fleet_ds.sort(key=sort_ds)

  options = [f"{s['id']} [{s.get('payload_type','?')}]  {s.get('role','MEMBER')}" for s in fleet_ds]
  selected = st.selectbox("Select Target Node for Deep Scan", options)

  if selected:
  sat_id  = selected.split(" ")[0]
  sat_data = next((s for s in fleet_ds if s['id'] == sat_id), None)

  if sat_data:
  score = sat_data.get('current_score', 0.0)
  role  = sat_data.get('role', 'MEMBER')
  ptype = sat_data.get('payload_type', '?')
  gk  = sat_data.get('telemetry', {}).get('P0_Gatekeepers', {})
  battery = gk.get('soc', 0) * 100

  col1, col2, col3, col4, col5 = st.columns(5)
  col1.metric("C Score",  f"{score:.4f}")
  col2.metric("Hardware",  ptype)
  col3.metric("Role",  role)
  col4.metric("Battery",  f"{battery:.1f}%")
  col5.metric("Ground Track", f"{sat_data.get('lat',0):.2f}deg, {sat_data.get('lon',0):.2f}deg")

  st.markdown("---")
  st.markdown("#### Full Telemetry State Vector")
  telem = sat_data.get('telemetry', {})
  rows = []
  for group, params in telem.items():
  for k, v in params.items():
  try:
  norm_v = max(0, min(float(v), 1.0))
  filled = int(norm_v * 20)
  bar = "[" + "#" * filled + "-" * (20 - filled) + "]  " + f"{norm_v:.2f}"
  except Exception:
  bar = "[------------------]  N/A"
  rows.append({
  "Group":  group.replace('_', ' '),
  "Parameter": k.replace('_', ' ').title(),
  "Value":  round(v, 4),
  "Visual":  bar
  })

  if rows:
  st.dataframe(pd.DataFrame(rows), width='stretch')

  st.markdown("---")
  st.markdown("#### Score Composition Formula")
  st.latex(r"C_i = \sum_{k} w_k \cdot p_k")
  st.caption("w  -  = parameter weight from scoring engine | p  -  = normalized telemetry value")

  try:
  all_logs = r.hgetall("AUCTION_LOGS")
  won_in  = []
  for mid, lj in all_logs.items():
  lg = json.loads(lj)
  match = next((b for b in lg.get("bidders", [])
  if b.get("Node ID") == sat_id and b.get("Result") == "WON"), None)
  if match:
  won_in.append((mid, match))
  if won_in:
  st.success(f"  This node won **{len(won_in)}** mission auction(s):")
  for mid, match in won_in:
  st.write(f"- **{mid}** | Score: `{match.get('Auction Score','?')}` | Dist: `{match.get('Distance (km)','?')} km`")
  else:
  st.info("Node has not won any auction in the current log. (Logs clear between sessions.)")
  except Exception:
  pass


#  
# TAB 4  FLEET STATISTICS (Fixed + Charted)
#  
with tab4:
  st.markdown("### Fleet Statistics - Real-Time Constellation Health")

  try:
  #  Get active roles from the authoritative MISSIONS_LEDGER  
  active_enclave_ids = set()
  missions_for_stats = {}
  for mid, mj in r.hgetall("MISSIONS_LEDGER").items():
  m = json.loads(mj)
  missions_for_stats[mid] = m
  if m.get("status") == "EXECUTING":
  active_enclave_ids.update(m.get("enclave", []))

  #  Sample fleet (up to 5000 nodes) for stats  
  all_keys  = r.keys('STARLINK-*')
  sample  = all_keys[:5000]
  raw_fleet  = r.mget(sample) if sample else []
  full_fleet = [json.loads(item) for item in raw_fleet if item]
  except Exception:
  full_fleet = []
  active_enclave_ids = set()
  missions_for_stats = {}

  if not full_fleet:
  st.warning("No fleet data. Ensure Physics Engine is active.")
  else:
  total  = len(full_fleet)
  n_active = len(active_enclave_ids)

  by_payload = {}
  scores  = []
  batteries  = []
  isl_vals  = []
  thermal_vals = []

  for s in full_fleet:
  pt = s.get('payload_type', 'UNKNOWN')
  by_payload[pt] = by_payload.get(pt, 0) + 1
  scores.append(s.get('current_score', 0))
  gk = s.get('telemetry', {}).get('P0_Gatekeepers', {})
  batteries.append(gk.get('soc', 0) * 100)
  eff = s.get('telemetry', {}).get('P2_Efficiency', {})
  isl_vals.append(eff.get('isl_throughput', 0) * 100)
  thermal_vals.append(gk.get('thermal_margin', 0) * 100)

  avg_score  = sum(scores) / len(scores)  if scores  else 0
  avg_battery = sum(batteries) / len(batteries)  if batteries else 0
  avg_isl  = sum(isl_vals) / len(isl_vals)  if isl_vals  else 0

  #  KPI row  
  k1, k2, k3, k4, k5 = st.columns(5)
  k1.metric("Visible Nodes",  f"{total:,}")
  k2.metric("Mission-Active",  n_active,  delta=f"{n_active/total*100:.1f}%" if total else "0%")
  k3.metric("Avg C Score",  f"{avg_score:.4f}")
  k4.metric("Avg Battery",  f"{avg_battery:.1f}%")
  k5.metric("Avg ISL Throughput",f"{avg_isl:.1f}%")

  st.markdown("---")

  #  Charts row 1  
  try:
  import plotly.graph_objects as go
  import plotly.express as px

  hw_labels = list(by_payload.keys())
  hw_values = list(by_payload.values())
  hw_colors = {"SAR":"#cc33ff","EO":"#3399ff","SIGINT":"#ffcc1a",
  "MW":"#ff8000","RELAY":"#555555","UNKNOWN":"#00ff88"}

  c1, c2 = st.columns(2)

  with c1:
  st.markdown("#### Hardware Distribution")
  fig_hw = go.Figure(go.Pie(
  labels=hw_labels, values=hw_values,
  marker_colors=[hw_colors.get(l, "#888") for l in hw_labels],
  hole=0.55,
  textinfo="label+percent",
  textfont_color="white"
  ))
  fig_hw.update_layout(
  paper_bgcolor="rgba(0,0,0,0)",
  plot_bgcolor="rgba(0,0,0,0)",
  font_color="white",
  showlegend=True,
  legend=dict(font=dict(color="white")),
  margin=dict(t=10,b=10,l=10,r=10),
  height=280
  )
  st.plotly_chart(fig_hw, width='stretch', config={"displayModeBar": False})

  with c2:
  st.markdown("#### C Score Distribution")
  fig_sc = go.Figure(go.Histogram(
  x=scores, nbinsx=30,
  marker_color="#00aaff",
  marker_line=dict(color="#003366", width=0.5),
  opacity=0.85
  ))
  fig_sc.update_layout(
  paper_bgcolor="rgba(0,0,0,0)",
  plot_bgcolor="rgba(5,8,15,0.6)",
  font_color="white",
  xaxis=dict(title="C Score", color="white", gridcolor="#1a2a3a"),
  yaxis=dict(title="Node Count", color="white", gridcolor="#1a2a3a"),
  margin=dict(t=10,b=10,l=10,r=10),
  height=280
  )
  st.plotly_chart(fig_sc, width='stretch', config={"displayModeBar": False})

  #  Charts row 2  
  c3, c4 = st.columns(2)

  with c3:
  st.markdown("#### Battery SOC Distribution")
  fig_bat = go.Figure(go.Histogram(
  x=batteries, nbinsx=25,
  marker_color="#00ff88",
  marker_line=dict(color="#003322", width=0.5),
  opacity=0.85
  ))
  fig_bat.update_layout(
  paper_bgcolor="rgba(0,0,0,0)",
  plot_bgcolor="rgba(5,8,15,0.6)",
  font_color="white",
  xaxis=dict(title="Battery %", color="white", gridcolor="#1a2a3a"),
  yaxis=dict(title="Node Count", color="white", gridcolor="#1a2a3a"),
  margin=dict(t=10,b=10,l=10,r=10),
  height=260
  )
  st.plotly_chart(fig_bat, width='stretch', config={"displayModeBar": False})

  with c4:
  st.markdown("#### ISL Throughput Distribution")
  fig_isl = go.Figure(go.Histogram(
  x=isl_vals, nbinsx=25,
  marker_color="#ffcc1a",
  marker_line=dict(color="#332200", width=0.5),
  opacity=0.85
  ))
  fig_isl.update_layout(
  paper_bgcolor="rgba(0,0,0,0)",
  plot_bgcolor="rgba(5,8,15,0.6)",
  font_color="white",
  xaxis=dict(title="ISL Throughput %", color="white", gridcolor="#1a2a3a"),
  yaxis=dict(title="Node Count",  color="white", gridcolor="#1a2a3a"),
  margin=dict(t=10,b=10,l=10,r=10),
  height=260
  )
  st.plotly_chart(fig_isl, width='stretch', config={"displayModeBar": False})

  except ImportError:
  st.warning("Install plotly for charts: `pip install plotly`")

  #  Score health bands table  
  st.markdown("---")
  st.markdown("#### Score Health Band Breakdown")
  bands = {"  Critical (0  1)":0, " Warning (1  2)":0, " Nominal (2  3)":0, "  Optimal (3+)":0}
  for s in scores:
  if s < 1:  bands["  Critical (0  1)"] += 1
  elif s < 2: bands[" Warning (1  2)"]  += 1
  elif s < 3: bands[" Nominal (2  3)"]  += 1
  else:  bands["  Optimal (3+)"]  += 1

  band_df = pd.DataFrame(
  [(k, v, f"{v/total*100:.1f}%" if total else "0%") for k, v in bands.items()],
  columns=["Health Band", "Node Count", "% of Fleet"]
  )
  st.dataframe(band_df, width='stretch')

  #  Hardware breakdown table (exact counts)  
  st.markdown("#### Hardware Roster Count")
  hw_table = pd.DataFrame(
  sorted([(k, v, f"{v/total*100:.1f}%") for k,v in by_payload.items()], key=lambda x:-x[1]),
  columns=["Sensor Type", "Count", "% of Fleet"]
  )
  st.dataframe(hw_table, width='stretch')

# Auto-refresh every 5 seconds
if auto_refresh:
  time.sleep(5)
  st.rerun()


