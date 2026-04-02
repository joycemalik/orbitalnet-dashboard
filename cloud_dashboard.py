import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import boto3
import time
import json
import os
from decimal import Decimal

# Try to load .env for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# --- DEMO ORBITAL MECHANICS ---
# 1 full orbit takes 60 seconds (6 degrees per second)
ORBITAL_SPEED_DEG_PER_SEC = 6.0 

# Battery dies in 100 seconds in the dark (1% per sec)
PASSIVE_DRAIN_PER_SEC = 1.0

# Battery charges in 33 seconds in the sun (3% per sec)
SOLAR_CHARGE_PER_SEC = 3.0

# --- SECURE CLOUD CONFIGURATION ---
AWS_REGION = "ap-south-1"

# Streamlit Cloud will inject these safely, or use local .env
try:
    AWS_ACCESS_KEY = st.secrets["AWS_ACCESS_KEY"]
    AWS_SECRET_KEY = st.secrets["AWS_SECRET_KEY"]
except (KeyError, FileNotFoundError):
    AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
    AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")

TASKS_TOPIC_ARN = "arn:aws:sns:ap-south-1:253103780996:usos-tasks"

# --- AWS CLIENTS ---
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
sns = boto3.client('sns', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
table = dynamodb.Table("SwarmState")

# --- UI STYLING ---
st.set_page_config(page_title="OrbitalNet OS", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0a0a0a; color: #ffffff; }
    .stButton>button { background-color: #fbbf24; color: #000000 !important; font-weight: bold; border-radius: 4px; border: none; width: 100%; }
    .stButton>button:hover { background-color: #f59e0b; }
    .metric-box { background-color: #151515; padding: 15px; border-radius: 8px; border: 1px solid #333; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h2>OrbitalNet OS <span style='color:#fbbf24'>|</span> Live Orbit Tracker</h2>", unsafe_allow_html=True)

# --- FETCH & CLEAN LIVE DATA ---
current_time = time.time()
response = table.scan()
items = response.get('Items', [])

unique_nodes = {}
for item in items:
    if item['node_id'] == 'satellite-node-default': continue
    
    # Base data from DynamoDB
    nid = item['node_id']
    last_updated = float(item.get('last_updated', current_time))
    elapsed_sec = current_time - last_updated
    
    # 1. Project Real-Time Angle
    base_angle = float(item.get('current_angle', 0.0))
    real_angle = (base_angle + (ORBITAL_SPEED_DEG_PER_SEC * elapsed_sec)) % 360.0
    item['current_angle'] = real_angle
    
    # 2. Project Real-Time Battery
    battery = float(item.get('battery', 100.0))
    battery -= PASSIVE_DRAIN_PER_SEC * elapsed_sec
    
    # Sunlit Zone is 0 to 180 degrees (Right side of screen)
    if 0 <= real_angle <= 180:
        battery += SOLAR_CHARGE_PER_SEC * elapsed_sec
        
    item['battery'] = max(0.0, min(100.0, battery))
    
    # 3. Update Sector text based on angle
    sector_idx = int(real_angle // 60) + 1
    item['position'] = f"SECTOR_{sector_idx}"
    
    # Zombie Cleanup (Clear stuck states)
    if item.get('status') in ['BIDDING', 'EXECUTING'] and elapsed_sec > 15:
        item['status'] = 'IDLE'

    # Deduplicate: Only keep the freshest record
    if nid not in unique_nodes or last_updated > float(unique_nodes[nid].get('last_updated', 0)):
        unique_nodes[nid] = item

nodes = list(unique_nodes.values())
nodes.sort(key=lambda x: x['node_id'])

# --- LAYOUT (Control Room) ---
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.metric(label="Swarm Health", value="Optimal", delta="85%")
    st.write("☀️ Solar Charging: **Active** (Sectors 1-3)")

with col2:
    active_tasks = sum(1 for n in nodes if n.get('status') == 'EXECUTING')
    st.metric(label="Active Tasks", value=str(active_tasks))

with col3:
    avg_rep = sum(int(n.get('reputation', 0)) for n in nodes) / max(len(nodes), 1)
    st.metric(label="Avg. Reputation", value=f"{avg_rep:.1f} pts")

st.markdown("### Satellite Registry")
df = pd.DataFrame(nodes)
if not df.empty:
    st.dataframe(df[['node_id', 'status', 'battery', 'reputation', 'position']], use_container_width=True)

st.markdown("---")

col_sim, col_ctrl = st.columns([2.5, 1])

# --- INTERACTIVE HTML5 CANVAS SIMULATOR ---
with col_sim:
    # We inject the live Python data into the Javascript using json.dumps
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; background-color: #0a0a0a; display: flex; justify-content: center; align-items: center; height: 500px; color: white; font-family: sans-serif; overflow: hidden; }}
        canvas {{ background: radial-gradient(circle, #111 0%, #050505 100%); border-radius: 12px; border: 1px solid #222; box-shadow: 0 0 20px rgba(0,0,0,0.5); }}
    </style>
    </head>
    <body>
    <canvas id="orbitCanvas" width="700" height="500"></canvas>
    <script>
        const canvas = document.getElementById('orbitCanvas');
        const ctx = canvas.getContext('2d');
        
        // 1. Data injected from Python
        const swarmData = {json.dumps(nodes, cls=DecimalEncoder)};
        const orbitalSpeed = {ORBITAL_SPEED_DEG_PER_SEC}; 
        
        // 2. Record the exact millisecond this UI frame loaded
        const initTime = Date.now(); 
        
        const cx = 350; const cy = 250; const rOrbit = 180;

        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 3. Calculate how many seconds have passed since Python sent the data
            const elapsedSec = (Date.now() - initTime) / 1000.0;

            // Draw Sunlit Hemisphere (Sectors 1, 2, 3)
            ctx.beginPath();
            ctx.arc(cx, cy, rOrbit + 20, -Math.PI/2, Math.PI/2); 
            ctx.strokeStyle = "rgba(251, 191, 36, 0.15)";
            ctx.lineWidth = 40;
            ctx.stroke();

            // Draw Sun Icon
            ctx.fillStyle = "#fbbf24";
            ctx.font = "30px Arial";
            ctx.fillText("☀️", cx + rOrbit + 40, cy - 10);

            // Draw Earth
            ctx.beginPath();
            ctx.arc(cx, cy, 40, 0, Math.PI * 2);
            ctx.fillStyle = "#0f172a"; ctx.fill();
            ctx.strokeStyle = "#38bdf8"; ctx.lineWidth = 2; ctx.stroke();

            // Draw Orbital Ring
            ctx.beginPath();
            ctx.arc(cx, cy, rOrbit, 0, Math.PI * 2);
            ctx.setLineDash([4, 6]); ctx.strokeStyle = "#333"; ctx.stroke();
            ctx.setLineDash([]);

            // Draw Sector Dividers
            for(let i=0; i<6; i++) {{
                const ang = (i * Math.PI / 3) - Math.PI/2;
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(ang)*50, cy + Math.sin(ang)*50);
                ctx.lineTo(cx + Math.cos(ang)*220, cy + Math.sin(ang)*220);
                ctx.strokeStyle = "#222"; ctx.stroke();
                
                // Sector Labels
                ctx.fillStyle = "#444"; ctx.font = "10px Arial";
                ctx.fillText("SECTOR " + (i+1), cx + Math.cos(ang + 0.5)*200 - 20, cy + Math.sin(ang + 0.5)*200);
            }}

            // Draw Satellites
            swarmData.forEach(sat => {{
                // 4. THE MAGIC: Predict the current angle based on elapsed time
                const predictedAngle = typeof sat.current_angle !== 'undefined' ? sat.current_angle + (orbitalSpeed * elapsedSec) : 0;
                
                const angleRad = (predictedAngle - 90) * (Math.PI / 180);
                const sx = cx + Math.cos(angleRad) * rOrbit;
                const sy = cy + Math.sin(angleRad) * rOrbit;

                // Visual feedback if charging
                if (predictedAngle % 360 >= 0 && predictedAngle % 360 <= 180) {{
                    ctx.shadowBlur = 15;
                    ctx.shadowColor = "#fbbf24";
                }}

                // Draw Data Link if Executing
                if (sat.status === "EXECUTING" || sat.status === "BIDDING") {{
                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(sx, sy);
                    ctx.strokeStyle = sat.status === "EXECUTING" ? "rgba(251, 191, 36, 0.8)" : "rgba(255, 255, 255, 0.3)";
                    ctx.lineWidth = sat.status === "EXECUTING" ? 3 : 1;
                    ctx.stroke();
                }}

                // Draw Node
                ctx.beginPath();
                ctx.arc(sx, sy, 8, 0, Math.PI * 2);
                ctx.fillStyle = sat.status === "EXECUTING" ? "#fbbf24" : (sat.status === "BIDDING" ? "#fff" : "#888");
                ctx.fill();
                ctx.shadowBlur = 0;
                
                // Draw Labels
                ctx.fillStyle = "#fff"; ctx.font = "12px Arial";
                ctx.fillText(sat.node_id, sx + 15, sy - 5);
                ctx.fillStyle = sat.status === "EXECUTING" ? "#fbbf24" : "#aaa";
                ctx.fillText(parseFloat(sat.battery).toFixed(1) + "%", sx + 15, sy + 10);
            }});

            requestAnimationFrame(draw);
        }}
        draw();
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=520)

with col_ctrl:
    st.markdown("<div class='metric-box'><h3>Ground Station</h3></div>", unsafe_allow_html=True)
    target_sector = st.selectbox("Target Sector", ["SECTOR_1", "SECTOR_2", "SECTOR_3", "SECTOR_4", "SECTOR_5", "SECTOR_6"])
    
    if st.button("BROADCAST TASK"):
        sns.publish(
            TopicArn=TASKS_TOPIC_ARN,
            Message=json.dumps({"type": "TASK", "location": target_sector, "task_id": str(time.time())})
        )
        st.success(f"Signal Transmitted to {target_sector}")

    st.markdown("<br><h4>Live Telemetry</h4>", unsafe_allow_html=True)
    for node in nodes:
        status_color = "#fbbf24" if node.get('status') == 'EXECUTING' else ("#ff4444" if "STALE" in node.get('status', '') else "#888")
        st.markdown(f"""
        <div class='metric-box' style='border-left: 3px solid {status_color};'>
            <b>{node['node_id']}</b> - <span style='color:{status_color}'>{node.get('status', 'IDLE')}</span><br>
            <span style='font-size:12px; color:#aaa;'>Battery: {float(node.get('battery', 0)):.1f}% | Sector: {node.get('position')}</span>
        </div>
        """, unsafe_allow_html=True)

# Auto-refresh to keep data synced
time.sleep(2)
st.rerun()