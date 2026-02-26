"""
Ground Station - Task Broadcaster for USOS
Injects high-level tasks into the swarm network
Usage: python ground_station.py --task IMAGING --location SECTOR_4
"""

import argparse
import json
import socket
import time
from datetime import datetime

from config import BROADCAST_PORT, LOCALHOST, SATELLITE_PORTS


class GroundStation:
    """Ground station that broadcasts tasks to satellites."""

    def __init__(self):
        """Initialize ground station."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def broadcast_task(self, task: str, location: str) -> None:
        """
        Broadcast a task to all satellites.

        Args:
            task: Task type (e.g., IMAGING, SURVEILLANCE, COMMUNICATION)
            location: Target sector (e.g., SECTOR_1, SECTOR_4)
        """
        message = {
            "type": "TASK_BROADCAST",
            "task": task,
            "location": location,
            "timestamp": datetime.now().isoformat(),
            "priority": 1,
        }

        print(
            f"\n{'='*60}"
        )
        print(f"[GROUND STATION] Broadcasting Task at {datetime.now()}")
        print(f"Task: {task}")
        print(f"Target Location: {location}")
        print(f"{'='*60}\n")

        data = json.dumps(message).encode("utf-8")

        for port in SATELLITE_PORTS:
            try:
                self.socket.sendto(data, (LOCALHOST, port))
                print(f"✓ Task sent to SAT port {port}")
            except Exception as e:
                print(f"✗ Failed to send to port {port}: {e}")

        print()

    def close(self):
        """Close the socket."""
        self.socket.close()


def main():
    parser = argparse.ArgumentParser(description="Ground Station for USOS")
    parser.add_argument("--task", required=True, help="Task type (e.g., IMAGING)")
    parser.add_argument(
        "--location",
        required=True,
        help="Target sector (e.g., SECTOR_1, SECTOR_2)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to broadcast the task",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Interval between broadcasts in seconds",
    )

    args = parser.parse_args()

    station = GroundStation()

    try:
        for i in range(args.repeat):
            station.broadcast_task(args.task, args.location)
            if i < args.repeat - 1:
                print(f"Waiting {args.interval} seconds before next broadcast...")
                time.sleep(args.interval)
    finally:
        station.close()
        print("Ground station closed.")


if __name__ == "__main__":
    main()
