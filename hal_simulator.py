import random
import math
import json

class MockHAL:
    def __init__(self, sat_id):
        self.sat_id = sat_id
        # Initialize realistic starting states
        self.soc_raw = random.uniform(0.7, 1.0)
        self.thermal_raw = random.uniform(20.0, 40.0) # Celsius
        self.memory_raw = random.uniform(0.1, 0.5)

    def generate_telemetry(self, position_z):
        # 1. Physics Proxies (Make the data look real)
        # If Z coordinate is negative, satellite is roughly over the southern hemisphere.
        # We can simulate "Eclipse" (nighttime) to drain the battery.
        in_eclipse = position_z < 0 
        
        if in_eclipse:
            self.soc_raw -= random.uniform(0.0001, 0.0005) # Battery drains
        else:
            self.soc_raw += random.uniform(0.0005, 0.001)  # Solar panels charge
        
        # Clamp battery between 0 and 1
        self.soc_raw = max(0.0, min(1.0, self.soc_raw))

        # Memory fills up slowly
        self.memory_raw += random.uniform(0.001, 0.01)
        if self.memory_raw > 1.0: self.memory_raw = 0.0 # Simulates a downlink clearing the buffer

        # 2. Build the Normalized State Vector
        telemetry = {
            "P0_Gatekeepers": {
                "soc": round(self.soc_raw, 4),
                "thermal_margin": round(1.0 - ((self.thermal_raw - 10) / 70), 4), # 80C is max
                "reaction_wheel_rpm": round(random.uniform(0.6, 0.9), 4),
                "sensor_calibrated": 1.0 if random.random() > 0.01 else 0.0, # 1% chance of failure
                "conjunction_prob": round(random.uniform(0.0, 0.005), 5),
                "is_task_locked": 0.0 
            },
            "P1_Mission": {
                "mean_motion": round(random.uniform(0.8, 1.0), 4),
                "mean_anomaly": round(random.uniform(0.0, 1.0), 4),
                "look_angle": round(random.uniform(0.5, 1.0), 4),
                "cloud_cover": round(random.random(), 4), # Completely random for mockup
                "processing_load": round(random.uniform(0.1, 0.4), 4),
                "slew_energy": round(self.soc_raw * 0.8, 4) # Correlated to battery
            },
            "P2_Efficiency": {
                "inclination": 1.0, "raan": 1.0, "dod": round(1.0 - self.soc_raw, 4), 
                "memory_buffer": round(1.0 - self.memory_raw, 4), "isl_throughput": round(random.uniform(0.7, 1.0), 4), 
                "bus_voltage": round(self.soc_raw, 4)
            },
            "P3_Efficiency": {
                "eccentricity": 1.0, "settling_time": round(random.uniform(0.6, 0.9), 4), 
                "sun_glint": round(random.uniform(0.0, 1.0), 4), "radiation_flux": round(random.uniform(0.0, 0.2), 4), 
                "snr": round(random.uniform(0.8, 1.0), 4), "t_gs": round(random.uniform(0.5, 0.9), 4)
            },
            "P4_Maintenance": {
                "propellant": 0.95, "bstar": 0.99, "gdop": 0.99, "epoch_age": 1.0, 
                "solar_activity": 0.5, "encryption": 1.0
            }
        }
        return telemetry
