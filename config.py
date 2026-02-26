"""
Configuration for USOS (OrbitalNet OS) - Distributed Satellite Autonomy Prototype
"""

# Network Configuration
LOCALHOST = "127.0.0.1"
SATELLITE_PORTS = [5001, 5002, 5003]
SATELLITE_IDS = ["SAT_01", "SAT_02", "SAT_03"]

# Simulation Parameters
MAX_BATTERY = 100
MIN_BATTERY = 0
BATTERY_DRAIN_RATE = 2  # % per second at idle
BATTERY_DRAIN_TASK = 10  # % per task execution
BATTERY_RECHARGE_RATE = 0.5  # % per second in sunlight

# Orbit & Sectors
SECTORS = ["SECTOR_1", "SECTOR_2", "SECTOR_3", "SECTOR_4", "SECTOR_5", "SECTOR_6"]

# Bidding & Consensus
BID_TIMEOUT = 2.0  # seconds to wait for peer bids
BID_WEIGHT_BATTERY = 0.5
BID_WEIGHT_POSITION = 100.0

# Task Parameters
TASK_EXECUTION_TIME = 3  # seconds
MAX_RETRIES = 2

# Logging & State
STATE_FILE = "swarm_state.json"
LOG_FILE = "swarm_events.log"

# Communication
BROADCAST_PORT = 9999  # for ground_station to broadcast tasks
HEARTBEAT_INTERVAL = 0.5  # seconds
MESSAGE_BUFFER_SIZE = 4096
