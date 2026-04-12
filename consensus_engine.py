import redis
from redis.exceptions import ConnectionError as RedisConnectionError
import json
import time
from config import get_redis_client

def elect_plane_leaders():
    print("Initiating Swarm Consensus (Plane Lead Election)...")
    r = get_redis_client()
    cached_keys = None
    
    while True:
        try:
            if not cached_keys:
                keys = r.keys('STARLINK-*')
                if not keys:
                    time.sleep(1)
                    continue
                cached_keys = keys
                
            raw_data = r.mget(cached_keys)
            fleet = [json.loads(item) for item in raw_data if item]
            
            # 1. Group Satellites by Orbital Plane
            # We use a rounded RAAN (Right Ascension) to group them into physical planes
            planes = {}
            for sat in fleet:
                raan = sat['telemetry']['P2_Efficiency']['raan']
                plane_id = round(raan, 1) # Round to group them roughly
                
                if plane_id not in planes:
                    planes[plane_id] = []
                planes[plane_id].append(sat)
                
            # 2. Elect the Leader for each Plane
            leaders = []
            for plane_id, sats in planes.items():
                # Find the satellite with the absolute highest current_score (C_i)
                leader = max(sats, key=lambda x: x.get('current_score', 0.0))
                
                # Update its role in the JSON
                leader['role'] = 'PLANE_LEAD'
                leaders.append(leader)
                
                # Reset role for non-leaders to avoid stale leaders
                for sat in sats:
                    if sat['id'] != leader['id']:
                        sat['role'] = 'MEMBER'
                        r.set(sat['id'], json.dumps(sat))

                # Push the updated role back to Redis
                r.set(leader['id'], json.dumps(leader))
                
            print(f"Elected {len(leaders)} Plane Leaders across {len(planes)} active orbital planes.")
            
            # --- TIER 3: MULTI-MISSION SCHEDULER ---
            # 1. Get all missions from the Ledger
            all_missions_raw = r.hgetall("MISSIONS_LEDGER")
            
            for mission_id, mission_json in all_missions_raw.items():
                mission = json.loads(mission_json)
                
                if mission.get("status") == "OPEN_AUCTION":
                    required_sensor = mission.get("sensor_required", "EO")
                    print(f"Auction open for {mission_id} (Requires: {required_sensor})")
                    
                    # 2. P0 GATEKEEPER: Filter by Lock Status AND Hardware Type
                    eligible_bidders = []
                    for sat in fleet:
                        # Defensive check for P0 lock status
                        is_locked = sat.get('telemetry', {}).get('P0_Gatekeepers', {}).get('is_task_locked', 1.0)
                        
                        # Any IDLE satellite with the correct sensor can now bid!
                        if (is_locked == 0.0 and sat.get('payload_type') == required_sensor):
                            eligible_bidders.append(sat)
                    
                    # 3. Sort and Select
                    eligible_bidders.sort(key=lambda x: x.get('current_score', 0.0), reverse=True)
                    m_nodes = mission['required_nodes']
                    
                    if len(eligible_bidders) >= m_nodes:
                        winning_team = eligible_bidders[:m_nodes]
                        
                        # Lock nodes
                        for sat in winning_team:
                            sat['role'] = 'MISSION_ACTIVE'
                            sat['current_mission_id'] = mission_id
                            sat['telemetry']['P0_Gatekeepers']['is_task_locked'] = 1.0 
                            r.set(sat['id'], json.dumps(sat))
                        
                        # Close Auction
                        mission['status'] = "EXECUTING"
                        mission['enclave'] = [sat['id'] for sat in winning_team]
                        r.hset("MISSIONS_LEDGER", mission_id, json.dumps(mission))
                        print(f"Enclave Formed for {mission_id}! {m_nodes} {required_sensor} nodes locked.")
                    else:
                        print(f"AUCTION PENDING for {mission_id}: Not enough {required_sensor} nodes available yet.")
            
            # Run election every 5 seconds (doesn't need to be 1Hz like physics)
            time.sleep(5)

        except (RedisConnectionError, ConnectionRefusedError, ConnectionResetError, OSError) as e:
            print(f"⚠️ Consensus Engine lost Redis connection: {e.__class__.__name__}. Reconnecting in 3s...")
            time.sleep(3)
            try:
                r = get_redis_client()
                r.ping()
                print("✅ Consensus Engine reconnected to Redis.")
            except Exception:
                pass  # Will retry next loop iteration
        except Exception as e:
            print(f"⚠️ Consensus Engine unexpected error: {e}. Retrying in 2s...")
            time.sleep(2)

if __name__ == "__main__":
    elect_plane_leaders()
