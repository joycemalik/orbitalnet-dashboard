import redis
import json
import time

r = redis.Redis(
    host='localhost', 
    port=6379, 
    db=0, 
    decode_responses=True, 
    health_check_interval=1, # Checks if connection is alive
    retry_on_timeout=True    # Auto-retries instead of crashing
)

def elect_plane_leaders():
    print("Initiating Swarm Consensus (Plane Lead Election)...")
    
    while True:
        keys = r.keys('STARLINK-*')
        if not keys:
            time.sleep(1)
            continue
            
        raw_data = r.mget(keys)
        fleet = [json.loads(item) for item in raw_data if item]
        
        # 1. Group Satellites by Orbital Plane
        # We use a rounded RAAN (Right Ascension) to group them into physical planes
        planes = {}
        for sat in fleet:
            # Assuming RAAN is in P2_Efficiency. 
            # If mock HAL uses dummy raan, we group by it.
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
        
        # --- NEW: TIER 3 ENCLAVE FORMATION ---
        mission_data_raw = r.get("ACTIVE_MISSION")
        if mission_data_raw:
            mission = json.loads(mission_data_raw)
            if mission.get("status") == "OPEN_AUCTION":
                print(f"Detected Open RFP for {mission['required_nodes']} nodes...")
                
                # 1. Only Plane Leaders can bid on missions
                eligible_bidders = [sat for sat in fleet if sat.get('role') == 'PLANE_LEAD' and sat['telemetry']['P0_Gatekeepers']['is_task_locked'] == 0.0]
                
                # 2. Sort them by their current capability score
                # (In a real scenario, you'd recalculate Ci here using the mission['weights'])
                eligible_bidders.sort(key=lambda x: x.get('current_score', 0.0), reverse=True)
                
                # 3. Select the Top M nodes to form the Enclave
                m_nodes = mission['required_nodes']
                winning_team = eligible_bidders[:m_nodes]
                
                # 4. Lock the nodes and change their role
                for sat in winning_team:
                    sat['role'] = 'MISSION_ACTIVE'
                    sat['telemetry']['P0_Gatekeepers']['is_task_locked'] = 1.0 # Lock them
                    r.set(sat['id'], json.dumps(sat))
                
                # 5. Close the Auction
                mission['status'] = "EXECUTING"
                mission['enclave'] = [sat['id'] for sat in winning_team]
                r.set("ACTIVE_MISSION", json.dumps(mission))
                print(f"Enclave Formed! Nodes {mission['enclave']} locked for execution.")
        
        # Run election every 5 seconds (doesn't need to be 1Hz like physics)
        time.sleep(5)

if __name__ == "__main__":
    elect_plane_leaders()
