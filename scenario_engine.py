import redis
import json
import uuid

SCENARIOS = {
    "HORMUZ_OVERWATCH": {
        "target": {"x": 3500.0, "y": 4000.0, "z": 2600.0},
        "target_lat": 26.5,    # Strait of Hormuz approximate latitude
        "target_lon": 56.3,    # Strait of Hormuz approximate longitude
        "weights": {
            "look_angle": 1.0,
            "sensor_calibrated": 0.9,
            "isl_throughput": 0.9,
            "soc": 0.4
        },
        "sensor_required": "SAR",
        "m_required": 3,
        "risk_profile": "HIGH",
        "description": "Continuous high-resolution monitoring of contested maritime chokepoint."
    },
    "WILDFIRE_PROTOCOL": {
        "target": {"x": -2500.0, "y": 4500.0, "z": -4000.0},
        "target_lat": -33.8,   # Australian bushfire zone approximate latitude
        "target_lon": 150.9,   # Australian bushfire zone approximate longitude
        "weights": {
            "thermal_margin": 1.0,
            "cloud_cover": 0.9,
            "look_angle": 0.8,
            "soc": 0.8
        },
        "sensor_required": "MW",
        "m_required": 4,
        "risk_profile": "LOW",
        "description": "Unbroken infrared perimeter tracking of active mega-fire."
    }
}

from config import get_redis_client

class ScenarioManager:
    def __init__(self):
        self.r = get_redis_client()

    def dispatch_mission(self, scenario_name):
        config = SCENARIOS.get(scenario_name)
        if not config:
            return False

        mission_id = f"SCN-{uuid.uuid4().hex[:6].upper()}"

        active_mission = {
            "id": mission_id,
            "status": "OPEN_AUCTION",
            "name": scenario_name,
            "target_lat": config["target_lat"],
            "target_lon": config["target_lon"],
            "active": True,
            "required_nodes": config["m_required"],
            "sensor_required": config.get("sensor_required", "EO"),
            "weights": config["weights"],
            "enclave": []
        }

        # Push to the MISSIONS_LEDGER hash map for multi-mission support
        self.r.hset("MISSIONS_LEDGER", mission_id, json.dumps(active_mission))
        return f"{mission_id}: {config['description']}"

    def inject_chaos(self):
        """Simulates EMP or Jamming for the live demo"""
        self.r.set("TRIGGER_CHAOS", "1")
