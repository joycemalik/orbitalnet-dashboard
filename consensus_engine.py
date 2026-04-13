import redis
from redis.exceptions import ConnectionError as RedisConnectionError
import json
import math
import time
from config import get_redis_client


def haversine(lat1, lon1, lat2, lon2):
    """Calculates ground distance in km between two lat/lon points using the Haversine formula."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


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
            planes = {}
            for sat in fleet:
                raan = sat['telemetry']['P2_Efficiency']['raan']
                plane_id = round(raan, 1)
                if plane_id not in planes:
                    planes[plane_id] = []
                planes[plane_id].append(sat)

            # 2. Elect the Leader for each Plane
            leaders = []
            for plane_id, sats in planes.items():
                leader = max(sats, key=lambda x: x.get('current_score', 0.0))
                leader['role'] = 'PLANE_LEAD'
                leaders.append(leader)
                for sat in sats:
                    if sat['id'] != leader['id']:
                        sat['role'] = 'MEMBER'
                        r.set(sat['id'], json.dumps(sat))
                r.set(leader['id'], json.dumps(leader))

            print(f"Elected {len(leaders)} Plane Leaders across {len(planes)} active orbital planes.")

            # --- TIER 3: MULTI-MISSION SCHEDULER (Geographic + Hardware Aware) ---
            all_missions_raw = r.hgetall("MISSIONS_LEDGER")

            for mission_id, mission_json in all_missions_raw.items():
                mission = json.loads(mission_json)

                if mission.get("status") == "OPEN_AUCTION":
                    required_sensor = mission.get("sensor_required", "EO")
                    target_lat      = mission.get("target_lat", 0)
                    target_lon      = mission.get("target_lon", 0)
                    zone_radius     = mission.get("target_radius", 500)

                    # LEO satellites can slew their sensors — add a 1000 km margin
                    max_view_distance = zone_radius + 1000

                    print(f"Auction: {mission_id} | Sensor: {required_sensor} | Zone: {zone_radius} km | Max: {max_view_distance} km")

                    # P0 GATEKEEPER: Hardware + Lock + Geographic proximity
                    eligible_bidders = []
                    for sat in fleet:
                        is_locked = sat.get('telemetry', {}).get('P0_Gatekeepers', {}).get('is_task_locked', 1.0)

                        if is_locked == 0.0 and sat.get('payload_type') == required_sensor:
                            sat_lat = sat.get('lat', 0)
                            sat_lon = sat.get('lon', 0)
                            distance = haversine(sat_lat, sat_lon, target_lat, target_lon)

                            # Gatekeeper: must be physically close enough to image the target
                            if distance <= max_view_distance:
                                # Proximity-weighted auction score: closer = better
                                proximity_score = max(0, (max_view_distance - distance) / 100)
                                battery = sat.get('telemetry', {}).get('P0_Gatekeepers', {}).get('soc', 1.0)
                                sat['auction_score'] = (proximity_score * 0.7) + (battery * 0.3)
                                eligible_bidders.append(sat)

                    # Sort by combined proximity + battery score
                    eligible_bidders.sort(key=lambda x: x.get('auction_score', 0.0), reverse=True)
                    m_nodes = mission['required_nodes']

                    if len(eligible_bidders) >= m_nodes:
                        winning_team = eligible_bidders[:m_nodes]
                        winning_ids  = {sat['id'] for sat in winning_team}

                        for sat in winning_team:
                            sat['role'] = 'MISSION_ACTIVE'
                            sat['current_mission_id'] = mission_id
                            sat['telemetry']['P0_Gatekeepers']['is_task_locked'] = 1.0
                            r.set(sat['id'], json.dumps(sat))

                        mission['status'] = "EXECUTING"
                        mission['enclave'] = [sat['id'] for sat in winning_team]
                        r.hset("MISSIONS_LEDGER", mission_id, json.dumps(mission))
                        print(f"[OK] Enclave Formed: {mission_id} -- {m_nodes} x {required_sensor} within {max_view_distance:.0f} km locked.")

                        # --- EXPORT TRANSPARENCY DATA (Auction Forensics) ---
                        auction_log = {
                            "mission_id":  mission_id,
                            "sensor":      required_sensor,
                            "target_lat":  target_lat,
                            "target_lon":  target_lon,
                            "radius":      zone_radius,
                            "total_bidders": len(eligible_bidders),
                            "winners":       m_nodes,
                            "bidders": [
                                {
                                    "Node ID":       b['id'],
                                    "Payload":       b.get('payload_type', '?'),
                                    "Distance (km)": round(haversine(b.get('lat', 0), b.get('lon', 0), target_lat, target_lon), 1),
                                    "Battery (%)":   round(b.get('telemetry', {}).get('P0_Gatekeepers', {}).get('soc', 1.0) * 100, 1),
                                    "Prox Score":    round((max_view_distance - haversine(b.get('lat', 0), b.get('lon', 0), target_lat, target_lon)) / 100, 4),
                                    "Auction Score": round(b.get('auction_score', 0), 4),
                                    "Result":        "WON" if b['id'] in winning_ids else "LOST"
                                }
                                for b in eligible_bidders
                            ]
                        }
                        r.hset("AUCTION_LOGS", mission_id, json.dumps(auction_log))
                    else:
                        print(f"[PENDING] AUCTION: {mission_id} -- {len(eligible_bidders)}/{m_nodes} {required_sensor} nodes in range.")

            # Run election every 5 seconds
            time.sleep(5)

        except (RedisConnectionError, ConnectionRefusedError, ConnectionResetError, OSError) as e:
            print(f"[WARN] Consensus Engine lost Redis connection: {e.__class__.__name__}. Reconnecting in 3s...")
            time.sleep(3)
            try:
                r = get_redis_client()
                r.ping()
                print("[OK] Consensus Engine reconnected to Redis.")
            except Exception:
                pass
        except Exception as e:
            print(f"[WARN] Consensus Engine unexpected error: {e}. Retrying in 2s...")
            time.sleep(2)


if __name__ == "__main__":
    elect_plane_leaders()
