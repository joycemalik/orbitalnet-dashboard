from sgp4.api import Satrec, jday
import redis
from redis.exceptions import ConnectionError as RedisConnectionError
import time
import json
import math
import hashlib
from datetime import datetime, timezone, timedelta
from hal_simulator import MockHAL
from scoring_engine import compute_final_score
from config import get_redis_client


# ─── DETERMINISTIC SATELLITE CLASSIFIER ───────────────────────────────────────
# Parses TLE names to assign real-world hardware payloads.
# Unknown satellites get a hash-based assignment (same every reboot).
def classify_satellite(name):
    """Categorizes hardware payload based on real-world satellite constellations."""
    n = name.upper()

    # 1. Communications / Relay backbone
    if any(x in n for x in ["STARLINK", "ONEWEB", "IRIDIUM", "GLOBALSTAR", "O3B", "ORBCOMM", "INMARSAT", "SES-"]):
        return "RELAY"

    # 2. Microwave / Weather
    elif any(x in n for x in ["NOAA", "GOES", "METEOR", "FENGYUN", "METOP", "DMSP", "TIROS", "SUOMI"]):
        return "MW"

    # 3. Synthetic Aperture Radar (cloud-penetrating)
    elif any(x in n for x in ["SENTINEL-1", "RADARSAT", "ICEYE", "CAPELLA", "TERRASAR", "COSMO", "PAZ", "RISAT"]):
        return "SAR"

    # 4. Electro-Optical (high-res visual)
    elif any(x in n for x in ["LANDSAT", "SENTINEL-2", "WORLDVIEW", "PLANET", "SKYSAT", "SPOT", "PLEIADES", "GEOEYE", "KOMPSAT"]):
        return "EO"

    # 5. Signals Intelligence / Military
    elif any(x in n for x in ["NROL", "USA ", "COSMOS", "YAOGAN", "LACROSSE", "MISTY"]):
        return "SIGINT"

    else:
        # Deterministic fallback: hash the name so the assignment is stable across reboots
        val = int(hashlib.md5(name.encode()).hexdigest(), 16)
        return ["EO", "SAR", "MW", "SIGINT", "RELAY"][val % 5]


# ─── ECI → LAT/LON CONVERSION ─────────────────────────────────────────────────
def eci_to_latlon(x, y, z, jd):
    """Converts Earth-Centered Inertial (ECI) km → geodetic Lat/Lon (degrees)."""
    # 1. Greenwich Mean Sidereal Time (degrees)
    t = jd - 2451545.0
    gmst_deg = (280.46061837 + 360.98564736629 * t) % 360.0
    gmst_rad = math.radians(gmst_deg)

    # 2. Rotate ECI → ECEF
    lon_eci = math.atan2(y, x)          # ECI longitude
    lon_ecef = lon_eci - gmst_rad       # subtract Earth's rotation
    lon = math.degrees(lon_ecef) % 360
    if lon > 180:
        lon -= 360                       # wrap to [-180, 180]

    # 3. Latitude (same in ECI and ECEF for a spherical model)
    r = math.sqrt(x**2 + y**2 + z**2)
    lat = math.degrees(math.asin(z / r))

    return lat, lon


def load_satellites(filepath):
    satellites = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i in range(0, len(lines), 3):
            if i + 2 < len(lines):
                name  = lines[i].strip()
                line1 = lines[i + 1].strip()
                line2 = lines[i + 2].strip()
                try:
                    satrec = Satrec.twoline2rv(line1, line2)
                    satellites[name] = satrec
                except Exception:
                    pass
    return satellites


def start_engine():
    r = get_redis_client()

    fleet = load_satellites('satellites.txt')
    print(f"Loaded {len(fleet)} satellites. Booting SGP4 engine...")

    # Pre-classify all hardware (stable across reboots via deterministic hash)
    fleet_hardware = {name: classify_satellite(name) for name in fleet.keys()}
    print(f"Hardware classified: {dict(list({v: sum(1 for h in fleet_hardware.values() if h==v) for v in set(fleet_hardware.values())}.items()))}")

    # Initialize HAL instances for dynamic telemetry
    hal_instances = {name: MockHAL(name) for name in fleet.keys()}

    # Default scoring weights (Earth Observation profile)
    default_weights = {
        "mean_motion": 0.8, "look_angle": 1.0, "cloud_cover": 0.5,
        "soc": 0.3, "memory_buffer": 0.7, "isl_throughput": 0.9
    }

    # Chronos time multiplier (controlled by Ground Station via Redis)
    sim_time = datetime.now(timezone.utc)

    while True:
        try:
            # Read time multiplier from Ground Station
            try:
                multiplier = float(r.get("CHRONOS_MULTIPLIER") or 1.0)
            except Exception:
                multiplier = 1.0

            sim_time += timedelta(seconds=multiplier)
            now = sim_time

            jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second + now.microsecond / 1e6)

            pipe = r.pipeline()

            for name, sat in fleet.items():
                e, position, velocity = sat.sgp4(jd, fr)

                if e == 0:
                    lat, lon = eci_to_latlon(position[0], position[1], position[2], jd + fr)

                    telem = hal_instances[name].generate_telemetry(position[2])
                    current_score = compute_final_score(telem, default_weights)

                    state_vector = {
                        "id":            name,
                        "position":      {"x": position[0], "y": position[1], "z": position[2]},
                        "velocity":      {"vx": velocity[0], "vy": velocity[1], "vz": velocity[2]},
                        "lat":           lat,
                        "lon":           lon,
                        "payload_type":  fleet_hardware[name],   # deterministic hardware
                        "telemetry":     telem,
                        "current_score": current_score,
                        "role":          "MEMBER",                # consensus engine sets MISSION_ACTIVE
                    }

                    pipe.set(name, json.dumps(state_vector))

            pipe.execute()
            time.sleep(1)  # 1 Hz physics loop

        except (RedisConnectionError, ConnectionRefusedError) as e:
            print(f"[WARN] Physics Engine lost Redis: {e}. Retrying in 3s...")
            time.sleep(3)
            try:
                r = get_redis_client()
            except Exception:
                pass
        except Exception as ex:
            print(f"[ERROR] Physics Engine: {ex}")
            time.sleep(2)


if __name__ == '__main__':
    start_engine()
