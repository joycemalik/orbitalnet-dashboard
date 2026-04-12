from sgp4.api import Satrec, jday
import redis
from redis.exceptions import ConnectionError as RedisConnectionError
import time
import json
import math
from datetime import datetime
from hal_simulator import MockHAL
from scoring_engine import compute_final_score
from config import get_redis_client

def ecef_to_latlon(x, y, z):
    """Convert TEME/ECEF Cartesian coordinates (km) to geodetic Latitude/Longitude.

    Uses a simplified spherical Earth model for calculation speed.
    Sufficient for the 15-degree look-window check used in lead election.
    
    Parameters
    ----------
    x, y, z : float
        Position components in km (TEME frame from SGP4).

    Returns
    -------
    tuple[float, float]
        (latitude_degrees, longitude_degrees)
    """
    r = math.sqrt(x**2 + y**2 + z**2)
    if r == 0:
        return 0.0, 0.0
    lat = math.degrees(math.asin(z / r))
    lon = math.degrees(math.atan2(y, x))
    return lat, lon

def load_satellites(filepath):
    satellites = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        # Parse TLEs in chunks of 3: Name, Line 1, Line 2
        for i in range(0, len(lines), 3):
            if i+2 < len(lines):
                name = lines[i].strip()
                line1 = lines[i+1].strip()
                line2 = lines[i+2].strip()
                # Create SGP4 satellite object
                satrec = Satrec.twoline2rv(line1, line2)
                satellites[name] = satrec
    return satellites

def start_engine():
    fleet = load_satellites('satellites.txt')
    
    # Initialize HAL instances for dynamic telemetry
    hal_instances = {name: MockHAL(name) for name in fleet.keys()}
    
    print(f"Loaded {len(fleet)} satellites. Booting SGP4 engine...")
    
    # Dummy weights for an "Earth Observation" mission
    default_weights = {
        "mean_motion": 0.8, "look_angle": 1.0, "cloud_cover": 0.5, 
        "soc": 0.3, "memory_buffer": 0.7, "isl_throughput": 0.9
    }

    r = get_redis_client()

    while True:
        try:
            now = datetime.utcnow()
            # SGP4 requires Julian Date
            jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
            
            # ── Read the current geographic mission from Redis ──
            mission_raw = r.get("CURRENT_MISSION")
            mission = json.loads(mission_raw) if mission_raw else None

            # Tracking for lead election
            best_satellite = None
            highest_score = -999
            fleet_data = {}
            
            for name, sat in fleet.items():
                # e is error code, position is (X, Y, Z) in km
                e, position, velocity = sat.sgp4(jd, fr)
                
                if e == 0:
                    # 1. Generate dynamic telemetry based on current position
                    telem = hal_instances[name].generate_telemetry(position[2])
                    
                    # Calculate the C_i score in real-time
                    current_score = compute_final_score(telem, default_weights)
                    
                    # 2. Convert ECEF to Lat/Lon for geographic awareness
                    sat_lat, sat_lon = ecef_to_latlon(position[0], position[1], position[2])
                    
                    # 3. If there is an active geographic mission, calculate Look Angle
                    if mission and mission.get("active"):
                        lat_diff = abs(sat_lat - mission["target_lat"])
                        lon_diff = abs(sat_lon - mission["target_lon"])
                        
                        # Satellite is within a 15-degree "Look Window" (roughly overhead)
                        if lat_diff < 15 and lon_diff < 15:
                            # Boost score based on proximity (closer is better)
                            distance_penalty = (lat_diff + lon_diff) * 0.1
                            mission_score = current_score - distance_penalty
                            
                            # Elect the lead
                            if mission_score > highest_score:
                                highest_score = mission_score
                                best_satellite = name
                    
                    # 4. Construct the full enriched state JSON
                    fleet_data[name] = {
                        "id": name,
                        "position": {"x": position[0], "y": position[1], "z": position[2]},
                        "velocity": {"vx": velocity[0], "vy": velocity[1], "vz": velocity[2]},
                        "lat": round(sat_lat, 4),
                        "lon": round(sat_lon, 4),
                        "telemetry": telem,
                        "current_score": current_score,
                        "is_active_lead": False  # Default; winner flagged after loop
                    }
            
            # ── The Enclave Logic: Assign the task to the best candidate ──
            if best_satellite and best_satellite in fleet_data:
                fleet_data[best_satellite]["is_active_lead"] = True

            # 5. Push all enriched state vectors to Redis using one highly efficient MSET
            if fleet_data:
                mset_dict = {name: json.dumps(data) for name, data in fleet_data.items()}
                r.mset(mset_dict)
                    
            time.sleep(1) # Update at 1 Hertz

        except (RedisConnectionError, ConnectionRefusedError, ConnectionResetError, OSError) as e:
            print(f"⚠️ Physics Engine lost Redis connection: {e.__class__.__name__}. Reconnecting in 2s...")
            time.sleep(2)
            try:
                r = get_redis_client()
                r.ping()
                print("✅ Physics Engine reconnected to Redis.")
            except Exception:
                pass  # Will retry next loop iteration
        except Exception as e:
            print(f"⚠️ Physics Engine unexpected error: {e}. Retrying in 1s...")
            time.sleep(1)

if __name__ == '__main__':
    start_engine()
