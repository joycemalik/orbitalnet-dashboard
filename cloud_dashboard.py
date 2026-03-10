import streamlit as st
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

# --- FETCH LIVE DATA ---
response = table.scan()
items = response.get('Items', [])
nodes = [i for i in items if i['node_id'] != 'satellite-node-default']
nodes.sort(key=lambda x: x['node_id'])

# --- LAYOUT ---
col1, col2 = st.columns([1, 2.5])

# --- GROUND STATION CONTROLS ---
with col1:
    st.markdown("<div class='metric-box'><h3>Ground Station</h3></div>", unsafe_allow_html=True)
    target_sector = st.selectbox("Target Sector", ["SECTOR_1", "SECTOR_2", "SECTOR_3", "SECTOR_4", "SECTOR_5", "SECTOR_6"])
    
    if st.button("BROADCAST TASK"):
        sns.publish(
            TopicArn=TASKS_TOPIC_ARN,
            Message=json.dumps({"type": "TASK", "location": target_sector})
        )
        st.success(f"Signal Transmitted to {target_sector}")

    st.markdown("<br><h4>Live Telemetry</h4>", unsafe_allow_html=True)
    for node in nodes:
        status_color = "#fbbf24" if node.get('status') == 'EXECUTING' else "#888"
        st.markdown(f"""
        <div class='metric-box' style='border-left: 3px solid {status_color};'>
            <b>{node['node_id']}</b> - <span style='color:{status_color}'>{node.get('status', 'IDLE')}</span><br>
            <span style='font-size:12px; color:#aaa;'>Battery: {float(node.get('battery', 0)):.1f}% | Sector: {node.get('position')}</span>
        </div>
        """, unsafe_allow_html=True)

# --- INTERACTIVE HTML5 CANVAS SIMULATOR ---
with col2:
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
        const swarmData = {json.dumps(nodes, cls=DecimalEncoder)};
        
        const cx = 350; const cy = 250; const rOrbit = 180;
        const sectors = {{"SECTOR_1": 0, "SECTOR_2": 1, "SECTOR_3": 2, "SECTOR_4": 3, "SECTOR_5": 4, "SECTOR_6": 5}};

        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Sync rotation to the global clock so it doesn't stutter on Python reload
            const timeSec = Date.now() / 1000; 

            // Draw Earth
            ctx.beginPath();
            ctx.arc(cx, cy, 40, 0, Math.PI * 2);
            ctx.fillStyle = "#0f172a"; ctx.fill();
            ctx.lineWidth = 2; ctx.strokeStyle = "#38bdf8"; ctx.stroke();
            
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
                const secIdx = sectors[sat.position || "SECTOR_1"];
                const baseAngle = (secIdx * Math.PI / 3) - Math.PI/2;
                const angle = baseAngle + (timeSec * 0.15); // Slow orbit speed

                const sx = cx + Math.cos(angle) * rOrbit;
                const sy = cy + Math.sin(angle) * rOrbit;

                // Draw Data Link if EXECUTING
                if (sat.status === "EXECUTING" || sat.status === "BIDDING") {{
                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(sx, sy);
                    ctx.strokeStyle = sat.status === "EXECUTING" ? "rgba(251, 191, 36, 0.8)" : "rgba(255, 255, 255, 0.3)";
                    ctx.lineWidth = sat.status === "EXECUTING" ? 3 : 1;
                    ctx.stroke();
                }}

                // Draw Satellite Dot
                ctx.beginPath();
                ctx.arc(sx, sy, 8, 0, Math.PI * 2);
                ctx.fillStyle = sat.status === "EXECUTING" ? "#fbbf24" : (sat.status === "BIDDING" ? "#fff" : "#888");
                ctx.shadowBlur = sat.status === "EXECUTING" ? 15 : 0;
                ctx.shadowColor = "#fbbf24";
                ctx.fill();
                ctx.shadowBlur = 0; // reset

                // Draw Label & Battery
                ctx.fillStyle = "#fff"; ctx.font = "12px Arial";
                ctx.fillText(sat.node_id, sx + 15, sy - 5);
                ctx.fillStyle = sat.status === "EXECUTING" ? "#fbbf24" : "#aaa";
                ctx.fillText(parseFloat(sat.battery).toFixed(0) + "%", sx + 15, sy + 10);
            }});

            requestAnimationFrame(draw);
        }}
        draw();
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=520)

# Auto-refresh to keep data synced
time.sleep(2)
st.rerun()