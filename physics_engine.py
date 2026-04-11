from sgp4.api import Satrec, jday
import redis
from redis.exceptions import ConnectionError as RedisConnectionError
import time
import json
from datetime import datetime
from hal_simulator import MockHAL
from scoring_engine import compute_final_score

def create_redis_connection():
    """Create a fresh Redis connection with retry settings."""
    return redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True
    )

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

    r = create_redis_connection()

    while True:
        try:
            now = datetime.utcnow()
            # SGP4 requires Julian Date
            jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
            
            # Pipeline batches Redis commands for massive speed
            pipe = r.pipeline()
            
            for name, sat in fleet.items():
                # e is error code, position is (X, Y, Z) in km
                e, position, velocity = sat.sgp4(jd, fr)
                
                if e == 0:
                    # 1. Generate dynamic telemetry based on current position
                    telem = hal_instances[name].generate_telemetry(position[2])
                    
                    # Calculate the C_i score in real-time
                    current_score = compute_final_score(telem, default_weights)
                    
                    # 2. Construct the full state JSON
                    state_vector = {
                        "id": name,
                        "position": {"x": position[0], "y": position[1], "z": position[2]},
                        "velocity": {"vx": velocity[0], "vy": velocity[1], "vz": velocity[2]},
                        "telemetry": telem,
                        "current_score": current_score
                    }
                    
                    # 3. Push to Redis as a JSON string
                    pipe.set(name, json.dumps(state_vector))
                    
            pipe.execute()
            time.sleep(1) # Update at 1 Hertz

        except (RedisConnectionError, ConnectionRefusedError, ConnectionResetError, OSError) as e:
            print(f"⚠️ Physics Engine lost Redis connection: {e.__class__.__name__}. Reconnecting in 2s...")
            time.sleep(2)
            try:
                r = create_redis_connection()
                r.ping()
                print("✅ Physics Engine reconnected to Redis.")
            except Exception:
                pass  # Will retry next loop iteration
        except Exception as e:
            print(f"⚠️ Physics Engine unexpected error: {e}. Retrying in 1s...")
            time.sleep(1)

if __name__ == '__main__':
    start_engine()
