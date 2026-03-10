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
# Battery constants
# ---------------------------------------------------------------------------

MAX_BATTERY: int = 100
"""Maximum battery level (full charge)."""

BATTERY_DRAIN_TASK: int = 10
"""Amount of battery consumed when a node executes a task."""

# ---------------------------------------------------------------------------
# AWS resource identifiers (injected via Lambda environment variables)
# ---------------------------------------------------------------------------

TASKS_TOPIC_ARN: str = os.environ.get("TASKS_TOPIC_ARN", "")
"""SNS Topic ARN that broadcasts new task assignments to all satellite nodes."""

BIDS_TOPIC_ARN: str = os.environ.get("BIDS_TOPIC_ARN", "")
"""SNS Topic ARN that carries bid messages between satellite nodes."""

TABLE_NAME: str = os.environ.get("TABLE_NAME", "SwarmState")
"""DynamoDB table name used to persist per-node state (battery, position, status)."""
