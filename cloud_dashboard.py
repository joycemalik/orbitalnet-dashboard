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
    .stApp { background-color: #020617; color: #e2e8f0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3, h4 { color: #38bdf8 !important; font-family: 'Courier New', Courier, monospace; letter-spacing: -0.5px; }
    .stButton>button { background-color: #0ea5e9; color: #ffffff !important; font-weight: bold; border-radius: 2px; border: 1px solid #38bdf8; width: 100%; text-transform: uppercase; letter-spacing: 1px; }
    .stButton>button:hover { background-color: #0284c7; box-shadow: 0 0 10px rgba(56,189,248,0.5); }
    .metric-box { background-color: #0f172a; padding: 15px; border-radius: 2px; border: 1px solid #1e293b; margin-bottom: 10px; border-left: 4px solid #0ea5e9; font-family: 'Courier New', Courier, monospace; box-shadow: inset 0 0 20px rgba(0,0,0,0.5); }
    .stDataFrame { border: 1px solid #1e293b; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h2>ORBITAL_NET / <span style='color:#0ea5e9'>TELEMETRY ROOT</span></h2>", unsafe_allow_html=True)

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
        body {{ margin: 0; background-color: #020617; display: flex; justify-content: center; align-items: center; height: 600px; color: #38bdf8; font-family: 'Courier New', Courier, monospace; overflow: hidden; }}
        canvas {{ background: #020617; border-radius: 4px; border: 1px solid #1e293b; box-shadow: inset 0 0 50px rgba(0,0,0,0.8); }}
    </style>
    </head>
    <body>
    <canvas id="orbitCanvas" width="800" height="600"></canvas>
    <script>
        const canvas = document.getElementById('orbitCanvas');
        const ctx = canvas.getContext('2d');
        
        // 1. Data injected from Python
        const swarmData = {json.dumps(nodes, cls=DecimalEncoder)};
        const orbitalSpeed = {ORBITAL_SPEED_DEG_PER_SEC}; 
        
        // 2. Record the exact millisecond this UI frame loaded
        const initTime = Date.now(); 
        
        const cx = 400; const cy = 300; const rOrbit = 200;

        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 3. Calculate how many seconds have passed since Python sent the data
            const elapsedSec = (Date.now() - initTime) / 1000.0;

            // Draw Subtle Grid Background
            ctx.strokeStyle = "rgba(15, 23, 42, 0.5)";
            ctx.lineWidth = 1;
            for(let x=0; x<canvas.width; x+=50) {{ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,canvas.height); ctx.stroke(); }}
            for(let y=0; y<canvas.height; y+=50) {{ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(canvas.width,y); ctx.stroke(); }}

            // Draw Sunlit Hemisphere Zone (Irradiance Area)
            const sunGrad = ctx.createLinearGradient(cx, cy, cx + rOrbit + 50, cy);
            sunGrad.addColorStop(0, "rgba(251, 191, 36, 0.0)");
            sunGrad.addColorStop(1, "rgba(251, 191, 36, 0.12)");
            
            ctx.beginPath();
            ctx.arc(cx, cy, rOrbit + 50, -Math.PI/2, Math.PI/2); 
            ctx.fillStyle = sunGrad;
            ctx.fill();

            // Terminator line (Day/Night boundary)
            ctx.beginPath();
            ctx.moveTo(cx, cy - rOrbit - 50);
            ctx.lineTo(cx, cy + rOrbit + 50);
            ctx.strokeStyle = "rgba(251, 191, 36, 0.3)";
            ctx.setLineDash([5, 10]);
            ctx.stroke();
            ctx.setLineDash([]);
            
            // Draw Solar Vector (Arrows instead of Emoji)
            ctx.fillStyle = "#fbbf24";
            ctx.font = "10px monospace";
            ctx.fillText("SOLAR IRRADIANCE VECTOR →", cx + rOrbit + 30, cy - 20);
            ctx.strokeStyle = "rgba(251, 191, 36, 0.3)";
            for(let scanY = cy - 10; scanY <= cy + 10; scanY += 10) {{
                ctx.beginPath(); ctx.moveTo(cx + rOrbit + 30, scanY); ctx.lineTo(cx + rOrbit + 70, scanY); ctx.stroke();
            }}

            // Draw Earth (Atmospheric Glow + Wireframe)
            ctx.beginPath(); // Inner deep core
            ctx.arc(cx, cy, 38, 0, Math.PI * 2);
            ctx.fillStyle = "#020617"; ctx.fill();
            
            ctx.beginPath(); // Outer atmosphere
            ctx.arc(cx, cy, 40, 0, Math.PI * 2);
            ctx.strokeStyle = "#0ea5e9"; ctx.lineWidth = 2; ctx.stroke();
            ctx.shadowBlur = 15; ctx.shadowColor = "#0ea5e9"; ctx.stroke(); ctx.shadowBlur = 0;
            
            // Earth Wireframe Lines
            ctx.beginPath(); ctx.ellipse(cx, cy, 20, 40, 0, 0, Math.PI*2); ctx.strokeStyle="rgba(14, 165, 233, 0.3)"; ctx.lineWidth=1; ctx.stroke();
            ctx.beginPath(); ctx.ellipse(cx, cy, 40, 20, 0, 0, Math.PI*2); ctx.stroke();

            // Draw Orbital Ring (HUD Style with ticks)
            ctx.beginPath();
            ctx.arc(cx, cy, rOrbit, 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(30, 41, 59, 0.8)"; ctx.stroke();
            for(let t=0; t<360; t+=10) {{
                let tr = t * Math.PI/180;
                let tLen = (t%30===0) ? 6 : 3;
                ctx.beginPath(); ctx.moveTo(cx + Math.cos(tr)*(rOrbit-tLen), cy + Math.sin(tr)*(rOrbit-tLen));
                ctx.lineTo(cx + Math.cos(tr)*(rOrbit+tLen), cy + Math.sin(tr)*(rOrbit+tLen));
                ctx.strokeStyle = (t%30===0) ? "#334155" : "rgba(30, 41, 59, 0.5)"; ctx.stroke();
            }}

            // Draw Sector Dividers (Crosshairs)
            for(let i=0; i<6; i++) {{
                const ang = (i * Math.PI / 3) - Math.PI/2;
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(ang)*50, cy + Math.sin(ang)*50);
                ctx.lineTo(cx + Math.cos(ang)*240, cy + Math.sin(ang)*240);
                ctx.strokeStyle = "rgba(30, 41, 59, 0.3)"; ctx.stroke();
                
                // Sector Labels
                ctx.fillStyle = "#475569"; ctx.font = "9px monospace";
                ctx.fillText('[SEC_0' + (i+1) + ']', cx + Math.cos(ang + 0.5)*210 - 20, cy + Math.sin(ang + 0.5)*210);
            }}

            // Draw Satellites based on TRUE Projected Angle
            swarmData.forEach(sat => {{
                // Predict the current angle
                const predictedAngle = typeof sat.current_angle !== 'undefined' ? sat.current_angle + (orbitalSpeed * elapsedSec) : 0;
                
                const angleRad = (predictedAngle - 90) * (Math.PI / 180);
                const sx = cx + Math.cos(angleRad) * rOrbit;
                const sy = cy + Math.sin(angleRad) * rOrbit;

                // Charging Aura
                if (predictedAngle % 360 >= 0 && predictedAngle % 360 <= 180) {{
                    ctx.shadowBlur = 10;
                    ctx.shadowColor = "rgba(251, 191, 36, 0.5)";
                }}

                // Draw Data Link if Executing
                if (sat.status === "EXECUTING" || sat.status === "BIDDING") {{
                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(sx, sy);
                    ctx.strokeStyle = sat.status === "EXECUTING" ? "rgba(245, 158, 11, 0.8)" : "rgba(56, 189, 248, 0.3)";
                    ctx.lineWidth = sat.status === "EXECUTING" ? 2 : 1;
                    ctx.setLineDash(sat.status === "EXECUTING" ? [] : [2, 2]);
                    ctx.stroke();
                    ctx.setLineDash([]);
                }}

                // Draw Node (Technical Triangle/Marker instead of a plain dot)
                ctx.translate(sx, sy);
                ctx.rotate(angleRad + Math.PI/2);
                ctx.beginPath();
                ctx.moveTo(0, -6); ctx.lineTo(4, 0); ctx.lineTo(0, 6); ctx.lineTo(-4, 0); ctx.closePath();
                ctx.fillStyle = sat.status === "EXECUTING" ? "#f59e0b" : "#38bdf8"; ctx.fill();
                ctx.strokeStyle = sat.status === "EXECUTING" ? "#fbbf24" : "#7dd3fc"; ctx.lineWidth = 1; ctx.stroke();
                ctx.rotate(-(angleRad + Math.PI/2));
                ctx.translate(-sx, -sy);
                ctx.shadowBlur = 0;
                
                // Draw Callout Line
                ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + 15, sy - 15); ctx.lineTo(sx + 50, sy - 15);
                ctx.strokeStyle = "rgba(51, 65, 85, 0.8)"; ctx.lineWidth = 1; ctx.stroke();

                // Draw Technical Labels
                ctx.fillStyle = "#f8fafc"; ctx.font = "9px monospace";
                const shortId = sat.node_id.replace('satellite-node-', 'SAT-');
                ctx.fillText('> ' + shortId, sx + 15, sy - 20);
                
                ctx.fillStyle = sat.status === "EXECUTING" ? "#fbbf24" : "#38bdf8";
                ctx.fillText('[PWR: ' + parseFloat(sat.battery).toFixed(1) + '%]', sx + 15, sy - 6);
                
                // Status tag
                ctx.fillStyle = sat.status === "EXECUTING" ? "#fbbf24" : (sat.status === "BIDDING" ? "#e2e8f0" : "#64748b");
                ctx.fillText('[STS: ' + sat.status + ']', sx + 15, sy + 4);
            }});

            // Draw HUD Overlays
            ctx.fillStyle = "#38bdf8"; ctx.font = "10px monospace";
            ctx.fillText('SYS.T: ' + new Date().toISOString(), 10, 20);
            ctx.fillText('ORB.V: ' + orbitalSpeed.toFixed(1) + ' DEG/S', 10, 35);
            ctx.fillText('ACT.N: ' + swarmData.length, 10, 50);

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
        time.sleep(1.5)
        st.rerun()

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
# Fast refresh (2s) while tasks are active, calm refresh (15s) when idle
active_swarm_states = sum(1 for n in nodes if n.get('status') in ['EXECUTING', 'BIDDING'])
time.sleep(2 if active_swarm_states > 0 else 15)
st.rerun()