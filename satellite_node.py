"""
Autonomous Satellite Node - Part of USOS (OrbitalNet OS)
Runs as independent process for each satellite
Usage: python satellite_node.py --id SAT_01 --port 5001 --peers 5002,5003
"""

import argparse
import json
import logging
import random
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    BATTERY_DRAIN_RATE,
    BATTERY_DRAIN_TASK,
    BATTERY_RECHARGE_RATE,
    BID_TIMEOUT,
    BID_WEIGHT_BATTERY,
    BID_WEIGHT_POSITION,
    BROADCAST_PORT,
    HEARTBEAT_INTERVAL,
    LOCALHOST,
    LOG_FILE,
    MAX_BATTERY,
    MESSAGE_BUFFER_SIZE,
    SECTORS,
    STATE_FILE,
    TASK_EXECUTION_TIME,
)


class SatelliteNode:
    """Autonomous satellite node with bidding consensus protocol."""

    def __init__(self, node_id: str, port: int, peer_ports: List[int]):
        """
        Initialize a satellite node.

        Args:
            node_id: Unique identifier (e.g., "SAT_01")
            port: Port for receiving bids
            peer_ports: List of peer satellite ports
        """
        self.node_id = node_id
        self.port = port
        self.peer_ports = peer_ports
        self.is_running = False

        # State
        self.battery = random.uniform(50, 100)
        self.position = random.choice(SECTORS)
        self.status = "IDLE"
        self.current_task = None
        self.is_winner = False
        self.last_bid_scores = {}

        # Communication
        self.udp_socket = None
        self.task_socket = None

        # Synchronization
        self.state_lock = threading.Lock()
        self.bid_event = threading.Event()

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Setup logging to console and file."""
        self.logger = logging.getLogger(self.node_id)
        self.logger.setLevel(logging.INFO)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter(
            f"%(asctime)s [{self.node_id}] %(levelname)s: %(message)s"
        )
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # File handler
        file_handler = logging.FileHandler(LOG_FILE, mode="a")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def start(self):
        """Start the satellite node with all threads."""
        self.is_running = True
        self.logger.info(f"Starting node on port {self.port} with peers {self.peer_ports}")

        # Setup sockets
        self.setup_sockets()

        # Start threads
        listener_thread = threading.Thread(target=self._listen_for_tasks, daemon=True)
        heartbeat_thread = threading.Thread(target=self._heartbeat, daemon=True)
        battery_thread = threading.Thread(target=self._simulate_battery, daemon=True)
        orbit_thread = threading.Thread(target=self._simulate_orbit, daemon=True)

        listener_thread.start()
        heartbeat_thread.start()
        battery_thread.start()
        orbit_thread.start()

        try:
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.logger.info("Shutdown signal received")
            self.stop()

    def setup_sockets(self):
        """Setup UDP sockets for communication."""
        try:
            # Socket for receiving tasks from ground station
            self.task_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.task_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.task_socket.bind((LOCALHOST, self.port))
            self.task_socket.settimeout(1.0)

            # Socket for peer-to-peer bidding
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            self.logger.debug(f"Sockets setup complete")
        except Exception as e:
            self.logger.error(f"Failed to setup sockets: {e}")
            raise

    def _listen_for_tasks(self):
        """Thread: Listen for incoming UDP messages (tasks or bids)."""
        self.logger.info(f"Listener thread started on port {self.port}")

        while self.is_running:
            try:
                data, addr = self.task_socket.recvfrom(MESSAGE_BUFFER_SIZE)
                message = json.loads(data.decode("utf-8"))
                mtype = message.get("type")

                if mtype == "TASK_BROADCAST":
                    self.logger.info(f"Received task: {message['task']} at {message['location']}")
                    # handle in separate thread to avoid blocking listener
                    threading.Thread(
                        target=self._handle_task,
                        args=(message,),
                        daemon=True,
                    ).start()
                elif mtype == "BID":
                    peer_id = message.get("node_id")
                    peer_score = message.get("score")
                    with self.state_lock:
                        self.last_bid_scores[peer_id] = peer_score
                    self.logger.debug(f"Received bid from {peer_id}: {peer_score:.2f}")
                # ignore other message types
            except socket.timeout:
                continue
            except Exception as e:
                self.logger.error(f"Listener error: {e}")

    def _handle_task(self, task_msg: Dict):
        """
        Handle incoming task: calculate bid and run consensus protocol.

        Args:
            task_msg: Task message with 'task' and 'location' keys
        """
        with self.state_lock:
            self.current_task = task_msg
            self.status = "BIDDING"
            self.is_winner = False
            self.last_bid_scores = {}

        self.logger.info(f"Task received: {task_msg['task']} at {task_msg['location']}")

        # Calculate bid score
        bid_score = self._calculate_bid_score(task_msg)
        self.logger.info(f"My bid score: {bid_score:.2f}")

        # Broadcast bid to peers
        self._broadcast_bid(bid_score)

        # Wait for peer responses
        time.sleep(BID_TIMEOUT)

        # Determine winner based on scores
        self._determine_winner(bid_score)

        # If winner, execute task
        if self.is_winner:
            self._execute_task()
        else:
            with self.state_lock:
                self.status = "IDLE"

        self._update_swarm_state()

    def _calculate_bid_score(self, task_msg: Dict) -> float:
        """
        Calculate bidding score for the task.

        Score = (Battery * 0.5) + (100 if position matches task location else 0)

        Args:
            task_msg: Task message

        Returns:
            Bid score (0-150)
        """
        battery_component = self.battery * BID_WEIGHT_BATTERY
        position_bonus = (
            BID_WEIGHT_POSITION
            if self.position == task_msg.get("location")
            else 0
        )
        score = battery_component + position_bonus
        return score

    def _broadcast_bid(self, bid_score: float):
        """
        Broadcast bid score to all peers.

        Args:
            bid_score: The calculated bid score
        """
        bid_msg = {
            "type": "BID",
            "node_id": self.node_id,
            "score": bid_score,
            "battery": self.battery,
            "position": self.position,
            "timestamp": datetime.now().isoformat(),
        }

        for peer_port in self.peer_ports:
            try:
                data = json.dumps(bid_msg).encode("utf-8")
                self.udp_socket.sendto(data, (LOCALHOST, peer_port))
                self.logger.debug(f"Bid sent to SAT port {peer_port}: score={bid_score:.2f}")
            except Exception as e:
                self.logger.warning(f"Failed to send bid to port {peer_port}: {e}")

        # Also record own score
        with self.state_lock:
            self.last_bid_scores[self.node_id] = bid_score


    def _determine_winner(self, my_score: float):
        """
        Determine if this node is the winner based on bid scores.

        Args:
            my_score: This node's bid score
        """
        with self.state_lock:
            all_scores = self.last_bid_scores.copy()

        all_scores[self.node_id] = my_score
        winner_id = max(all_scores, key=all_scores.get)
        winner_score = all_scores[winner_id]

        if winner_id == self.node_id:
            self.is_winner = True
            self.status = "EXECUTING"
            self.logger.info(
                f"CONSENSUS REACHED: WINNER! Score {my_score:.2f} beats "
                f"{[(k, v) for k, v in all_scores.items() if k != self.node_id]}"
            )
        else:
            self.is_winner = False
            self.status = "IDLE"
            self.logger.info(
                f"CONSENSUS REACHED: Yielding to {winner_id} (score {winner_score:.2f} > {my_score:.2f})"
            )

    def _execute_task(self):
        """Execute the assigned task."""
        self.logger.info(f"Executing task: {self.current_task}")

        # Simulate task execution
        time.sleep(TASK_EXECUTION_TIME)

        # Drain battery
        with self.state_lock:
            self.battery = max(0, self.battery - BATTERY_DRAIN_TASK)
            self.status = "IDLE"

        self.logger.info(
            f"Task execution complete. Battery: {self.battery:.1f}%, Status: IDLE"
        )

    def _simulate_battery(self):
        """Thread: Simulate battery drain and recharge."""
        while self.is_running:
            with self.state_lock:
                if self.status == "IDLE":
                    self.battery = min(MAX_BATTERY, self.battery + BATTERY_RECHARGE_RATE)
                else:
                    self.battery = max(0, self.battery - BATTERY_DRAIN_RATE)

            time.sleep(1.0)

    def _simulate_orbit(self):
        """Thread: Move the satellite through orbit sectors periodically."""
        while self.is_running:
            time.sleep(10)  # advance sector every 10 seconds
            with self.state_lock:
                try:
                    idx = SECTORS.index(self.position)
                except ValueError:
                    idx = 0
                self.position = SECTORS[(idx + 1) % len(SECTORS)]

    def _heartbeat(self):
        """Thread: Periodically update swarm state."""
        while self.is_running:
            self._update_swarm_state()
            time.sleep(HEARTBEAT_INTERVAL)

    def _update_swarm_state(self):
        """Update the shared swarm state file."""
        try:
            with self.state_lock:
                state_data = {
                    "timestamp": datetime.now().isoformat(),
                    "node_id": self.node_id,
                    "battery": round(self.battery, 2),
                    "position": self.position,
                    "status": self.status,
                    "is_winner": self.is_winner,
                    "current_task": self.current_task,
                    "last_bid_scores": self.last_bid_scores,
                }

            # Read existing state
            state_path = Path(STATE_FILE)
            if state_path.exists():
                with open(state_path, "r") as f:
                    try:
                        all_states = json.load(f)
                    except:
                        all_states = {}
            else:
                all_states = {}

            # Update this node's state
            all_states[self.node_id] = state_data

            # Write back
            with open(state_path, "w") as f:
                json.dump(all_states, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to update swarm state: {e}")

    def stop(self):
        """Stop the satellite node."""
        self.is_running = False
        self.logger.info(f"Node {self.node_id} shutting down")

        if self.task_socket:
            self.task_socket.close()
        if self.udp_socket:
            self.udp_socket.close()


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Satellite Node for USOS"
    )
    parser.add_argument("--id", required=True, help="Node ID (e.g., SAT_01)")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument(
        "--peers",
        type=str,
        default="",
        help="Comma-separated peer ports (e.g., 5002,5003)",
    )

    args = parser.parse_args()
    peer_ports = [int(p) for p in args.peers.split(",") if p]

    node = SatelliteNode(args.id, args.port, peer_ports)
    node.start()


if __name__ == "__main__":
    main()
