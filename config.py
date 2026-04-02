"""
config.py
---------
Central configuration for the USOS Satellite Node Lambda function.

All sector definitions, battery limits, and AWS resource identifiers
are read from here. Topic ARNs and the DynamoDB table name are read
from environment variables so that the same deployment package can be
reused across different environments without code changes.
"""

import os

# ---------------------------------------------------------------------------
# Sector definitions
# ---------------------------------------------------------------------------

SECTORS = [
    "SECTOR_1",
    "SECTOR_2",
    "SECTOR_3",
    "SECTOR_4",
    "SECTOR_5",
    "SECTOR_6",
]

# ---------------------------------------------------------------------------
# Battery & Orbital Constants
# ---------------------------------------------------------------------------

MAX_BATTERY: int = 100
"""Maximum battery level (full charge)."""

BATTERY_DRAIN_TASK: int = 10
"""Amount of battery consumed when a node executes a task."""

# --- Orbital Constants ---
ORBITAL_PERIOD_MINS = 15.0  # Time for one full 360° orbit
ORBITAL_SPEED = 360.0 / ORBITAL_PERIOD_MINS # Degrees per minute

# --- Realistic Power Logic ---
# 100% / 15 mins = ~6.67% per minute base drain
PASSIVE_DRAIN_RATE = 6.67 

# If the satellite spends 7.5 mins in the sun, it needs to recover 
# the 15-min total drain (100%). Recharge rate must be ~13.33% / min.
SOLAR_RECHARGE_RATE = 20.0 # High enough to hit 100% comfortably

# Sectors 1, 2, 3 correspond to 0° - 180°
SUNLIT_ANGLE_RANGE = (0, 180)

# --- DEMO ORBITAL MECHANICS ---
# 1 full orbit takes 60 seconds (6 degrees per second)
ORBITAL_SPEED_DEG_PER_SEC = 6.0 

# Battery dies in 100 seconds in the dark (1% per sec)
PASSIVE_DRAIN_PER_SEC = 1.0

# Battery charges in 33 seconds in the sun (3% per sec)
SOLAR_CHARGE_PER_SEC = 3.0


# ---------------------------------------------------------------------------
# AWS resource identifiers (injected via Lambda environment variables)
# ---------------------------------------------------------------------------

TASKS_TOPIC_ARN: str = os.environ.get("TASKS_TOPIC_ARN", "")
"""SNS Topic ARN that broadcasts new task assignments to all satellite nodes."""

BIDS_TOPIC_ARN: str = os.environ.get("BIDS_TOPIC_ARN", "")
"""SNS Topic ARN that carries bid messages between satellite nodes."""

TABLE_NAME: str = os.environ.get("TABLE_NAME", "SwarmState")
"""DynamoDB table name used to persist per-node state (battery, position, status)."""
