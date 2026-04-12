import uuid
import json
from config import get_redis_client


class ScenarioManager:
    def __init__(self):
        self.r = get_redis_client()

    SCENARIOS = {
        "OPERATION SANKALP (Piracy Overwatch)": {
            "description": "Continuous tracking of hostile fast-attack craft in the Arabian Sea. Requires cloud-penetrating radar to track 'dark' vessels at night.",
            "m_required": 4,
            "sensor": "SAR",
            "lat": 15.0,
            "lon": 65.0,
            "target_radius": 800,
            "risk_profile": "EXTREME",
            "code": "SANKALP"
        },
        "PROJECT AMOGHA (Border Incursion)": {
            "description": "High-altitude signal sweeping over the Himalayas to detect unauthorized radar emplacements. Requires electronic warfare nodes.",
            "m_required": 3,
            "sensor": "SIGINT",
            "lat": 34.1,
            "lon": 77.5,
            "target_radius": 500,
            "risk_profile": "HIGH",
            "code": "AMOGHA"
        },
        "CYCLONE PRECOGNITION (Bay of Bengal)": {
            "description": "Swarm deployment to track rapid pressure drops inside a forming super-cyclone. Requires constant rolling-enclave handoffs as nodes cross the storm.",
            "m_required": 5,
            "sensor": "MW",
            "lat": 12.5,
            "lon": 87.5,
            "target_radius": 1200,
            "risk_profile": "MODERATE",
            "code": "CYCLONE"
        },
        "MEGA-CITY GRID COLLAPSE (Mumbai)": {
            "description": "Complete power failure in Mumbai. Deploying high-res optical nodes to assess infrastructure damage and traffic bottlenecks in real-time.",
            "m_required": 2,
            "sensor": "EO",
            "lat": 18.9,
            "lon": 72.8,
            "target_radius": 300,
            "risk_profile": "LOW",
            "code": "GRID_DOWN"
        }
    }

    def dispatch_mission(self, scenario_name):
        """Pushes a predefined complex scenario into the Multi-Mission Ledger."""
        scenario = self.SCENARIOS[scenario_name]
        mission_id = f"OPS-{scenario['code']}-{uuid.uuid4().hex[:4].upper()}"

        active_mission = {
            "id": mission_id,
            "status": "OPEN_AUCTION",
            "name": scenario_name,
            "target_lat": scenario["lat"],
            "target_lon": scenario["lon"],
            "target_radius": scenario.get("target_radius", 1000),
            "active": True,
            "required_nodes": scenario["m_required"],
            "sensor_required": scenario["sensor"],
            "enclave": []
        }

        # Inject into the Hash Map so it runs concurrently with others
        self.r.hset("MISSIONS_LEDGER", mission_id, json.dumps(active_mission))
        return mission_id

    def inject_chaos(self):
        """Simulates EMP or Jamming for the live demo"""
        self.r.set("TRIGGER_CHAOS", "1")
