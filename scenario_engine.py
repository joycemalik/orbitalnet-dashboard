import redis
import json

SCENARIOS = {
    "HORMUZ_OVERWATCH": {
        "target": {"x": 3500.0, "y": 4000.0, "z": 2600.0},
        "weights": {
            "look_angle": 1.0,
            "sensor_calibrated": 0.9,
            "isl_throughput": 0.9,
            "soc": 0.4
        },
        "m_required": 3,
        "risk_profile": "HIGH",
        "description": "Continuous high-resolution monitoring of contested maritime chokepoint."
    },
    "WILDFIRE_PROTOCOL": {
        "target": {"x": -2500.0, "y": 4500.0, "z": -4000.0},
        "weights": {
            "thermal_margin": 1.0,
            "cloud_cover": 0.9,
            "look_angle": 0.8,
            "soc": 0.8
        },
        "m_required": 4,
        "risk_profile": "LOW",
        "description": "Unbroken infrared perimeter tracking of active mega-fire."
    }
}

class ScenarioManager:
    def __init__(self):
        self.r = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True,
            health_check_interval=1,
            retry_on_timeout=True
        )

    def dispatch_mission(self, scenario_name):
        config = SCENARIOS.get(scenario_name)
        if not config:
            return False

        active_mission = {
            "status": "OPEN_AUCTION",
            "name": scenario_name,
            "target": config["target"],
            "required_nodes": config["m_required"],
            "weights": config["weights"],
            "enclave": []
        }

        # Push to the Redis Brain for Consensus Engine to pick up
        self.r.set("ACTIVE_MISSION", json.dumps(active_mission))
        return config["description"]

    def inject_chaos(self):
        """Simulates EMP or Jamming for the live demo"""
        self.r.set("TRIGGER_CHAOS", "1")
