import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import redis
import time
from datetime import datetime

# Optional fallback logic using sgp4 directly if Redis is not running
try:
    from sgp4.api import Satrec, jday
    SGP4_AVAILABLE = True
except ImportError:
    SGP4_AVAILABLE = False

st.set_page_config(page_title="Satellite 3D Dashboard", layout="wide")
st.title("🛰️ Live Satellite 3D Viewer")

@st.cache_resource
def get_redis_client():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        return r
    except redis.ConnectionError:
        return None

def load_satellites_local(filepath="satellites.txt"):
    satellites = {}
    if not SGP4_AVAILABLE:
        return satellites
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            for i in range(0, len(lines), 3):
                if i+2 < len(lines):
                    name = lines[i].strip()
                    line1 = lines[i+1].strip()
                    line2 = lines[i+2].strip()
                    satrec = Satrec.twoline2rv(line1, line2)
                    satellites[name] = satrec
    except Exception as e:
        st.warning(f"Could not load local satellites: {e}")
    return satellites

r = get_redis_client()
local_satellites = None

if r is None:
    st.warning("⚠️ Redis not running or reachable. Falling back to local physics engine mode.")
    local_satellites = load_satellites_local()
else:
    st.success("✅ Connected to Redis physics engine feed.")

placeholder = st.empty()

def get_positions():
    positions = []
    
    if r is not None:
        try:
            # Get all keys from Redis
            keys = r.keys('*')
            if keys:
                pipe = r.pipeline()
                for k in keys:
                    pipe.get(k)
                values = pipe.execute()
                
                for k, v in zip(keys, values):
                    if v and isinstance(v, str):
                        try:
                            parts = v.split(',')
                            if len(parts) == 3:
                                positions.append({
                                    "Name": k,
                                    "X": float(parts[0]),
                                    "Y": float(parts[1]),
                                    "Z": float(parts[2])
                                })
                        except ValueError:
                            pass
        except redis.ConnectionError:
            pass

    # Fallback to local calculation if no Redis data
    if not positions and local_satellites:
        now = datetime.utcnow()
        jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
        for name, sat in local_satellites.items():
            e, pos, vel = sat.sgp4(jd, fr)
            if e == 0:
                positions.append({
                    "Name": name,
                    "X": pos[0],
                    "Y": pos[1],
                    "Z": pos[2]
                })

    return positions

# Main loop
for _ in range(100): # Just a reasonable loop for demo purposes in Streamlit
    positions = get_positions()
    
    with placeholder.container():
        if positions:
            df = pd.DataFrame(positions)
            
            # Create Plotly 3D scatter (Optimized for thousands of points)
            fig = go.Figure(data=[go.Scatter3d(
                x=df['X'],
                y=df['Y'],
                z=df['Z'],
                mode='markers',
                marker=dict(size=2, color='cyan', opacity=0.8),
                hovertext=df['Name'],
                hoverinfo='text'
            )])
            
            # Draw Earth as a sphere for reference (approx radius 6371 km)
            import numpy as np
            r_earth = 6371
            u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
            x_earth = r_earth * np.cos(u) * np.sin(v)
            y_earth = r_earth * np.sin(u) * np.sin(v)
            z_earth = r_earth * np.cos(v)
            
            fig.add_trace(go.Surface(
                x=x_earth, y=y_earth, z=z_earth,
                colorscale='Blues',
                opacity=0.5,
                showscale=False
            ))
            
            fig.update_layout(
                title="Live Orbiting Swarm",
                scene=dict(
                    xaxis=dict(title='X (km)', backgroundcolor="black", gridcolor="gray"),
                    yaxis=dict(title='Y (km)', backgroundcolor="black", gridcolor="gray"),
                    zaxis=dict(title='Z (km)', backgroundcolor="black", gridcolor="gray"),
                    bgcolor='black'
                ),
                paper_bgcolor='black',
                font=dict(color='white'),
                margin=dict(l=0, r=0, b=0, t=40)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No satellite data available. Run `physics_engine.py` or check `satellites.txt`.")
            
    time.sleep(1)
    # Streamlit rerun to update UI continuously
    st.rerun()
