# USOS (OrbitalNet OS) - Distributed Satellite Autonomy Prototype

A distributed systems simulation demonstrating autonomous satellite swarms with consensus-based task allocation, fault tolerance, and real-time visualization.

## 🎯 Overview

USOS is a prototype for a distributed satellite operating system where:
- **Satellites are autonomous agents** that self-organize without ground intervention
- **Tasks are allocated via consensus** using a Bidding/Contract Net protocol
- **Fault tolerance is built-in**: If the winning satellite fails, the next-best node automatically takes over
- **Real-time visualization** shows the "thought process" of the swarm

## 🏗️ Architecture

```
Ground Station (you) ─────────┐
                              │
                    ┌─────────┴─────────┐
                    │                   │
              SAT_01 (5001)      SAT_02 (5002)      SAT_03 (5003)
              - Battery          - Battery          - Battery
              - Position         - Position         - Position
              - Bidding Logic    - Bidding Logic    - Bidding Logic
              
              All satellites simultaneously calculate bids and reach consensus
              Winner executes; losers yield and return to idle
```

## 📁 Project Structure

```
.
├── config.py               # Configuration constants (ports, battery params, sectors)
├── satellite_node.py       # Main satellite agent (bidding consensus + state mgmt)
├── ground_station.py       # CLI tool to broadcast tasks to swarm
├── dashboard.py            # Streamlit real-time visualization
├── start.bat               # Windows launcher (3 nodes + dashboard)
├── start.sh                # Linux/Mac launcher (3 nodes + dashboard)
├── swarm_state.json        # Shared state file (read by dashboard)
└── swarm_events.log        # Event log file (read by dashboard)
```

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.9+
python --version

# Required packages
pip install streamlit
```

### Windows

```bash
# Simply double-click start.bat
# OR run in terminal:
start.bat
```

This will:
1. Launch 3 satellite nodes in separate terminal windows
2. Launch Streamlit dashboard in your browser (http://localhost:8501)
3. All nodes ready for task injection

### Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

## 🎮 Usage

### 1. **Launch the Swarm** (All Nodes + Dashboard)

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
./start.sh
```

This opens:
- 3 terminals with satellite nodes running on ports 5001, 5002, 5003
- Dashboard at `http://localhost:8501` in your default browser

### 2. **Inject Tasks** (From Another Terminal)

The ground station broadcasts tasks to the swarm. Satellites will autonomously bid and elect a winner:

```bash
# Single task
python ground_station.py --task IMAGING --location SECTOR_4

# Repeated tasks
python ground_station.py --task SURVEILLANCE --location SECTOR_2 --repeat 3 --interval 5

# Available sectors: SECTOR_1 through SECTOR_6
python ground_station.py --task COMMUNICATION --location SECTOR_1
```

### 3. **Monitor the Dashboard**

Open `http://localhost:8501` to see:
- **Battery levels** (progress bars) for each satellite
- **Current status** (IDLE, BIDDING, EXECUTING, OFFLINE)
- **Winner highlights** (⭐ badge on executor)
- **Live event log** showing bids, consensus, and task execution

### 4. **Simulate Node Failure** (Fault Tolerance Demo)

To demonstrate fault tolerance:

```bash
# Close one satellite terminal (e.g., SAT_01)
# Then inject a new task:
python ground_station.py --task IMAGING --location SECTOR_3

# The remaining 2 satellites will re-bid, and one will become the new executor
# This shows automatic failover without ground intervention
```

## 🧠 The Consensus Algorithm

### Bid Calculation

Each satellite calculates a **Bid Score** when it receives a task:

```
Score = (Battery × 0.5) + (100 if Position == TaskLocation else 0)
```

**Example:**
- SAT_01: Battery 80%, Position SECTOR_4, Task at SECTOR_4 → Score = 40 + 100 = **140**
- SAT_02: Battery 60%, Position SECTOR_1, Task at SECTOR_4 → Score = 30 + 0 = **30**
- SAT_03: Battery 90%, Position SECTOR_2, Task at SECTOR_4 → Score = 45 + 0 = **45**

→ **SAT_01 wins** and executes the task

### Consensus Protocol (2-second window)

1. **Broadcast** - Each satellite sends its score to peers via UDP
2. **Collect** - Wait 2 seconds for peer responses (lossy network tolerance)
3. **Decide** - Compare scores; highest score wins
4. **Execute** - Winner executes task; others yield and rest

## 📊 Real-Time State

Both the satellites and dashboard read/write from shared state files:

### `swarm_state.json`
```json
{
  "SAT_01": {
    "timestamp": "2024-02-26T10:30:45.123456",
    "battery": 75.5,
    "position": "SECTOR_4",
    "status": "EXECUTING",
    "is_winner": true,
    "current_task": {
      "type": "TASK_BROADCAST",
      "task": "IMAGING",
      "location": "SECTOR_4"
    },
    "last_bid_scores": {
      "SAT_01": 140.0,
      "SAT_02": 30.0,
      "SAT_03": 45.0
    }
  },
  "SAT_02": {...},
  "SAT_03": {...}
}
```

### `swarm_events.log`
```
2024-02-26 10:30:45,123 [SAT_01] INFO: Received task: IMAGING at SECTOR_4
2024-02-26 10:30:45,234 [SAT_01] INFO: My bid score: 140.00
2024-02-26 10:30:45,345 [SAT_02] INFO: My bid score: 30.00
2024-02-26 10:30:45,456 [SAT_03] INFO: My bid score: 45.00
2024-02-26 10:30:47,567 [SAT_01] INFO: CONSENSUS REACHED: WINNER! Score 140.00 beats [('SAT_02', 30.0), ('SAT_03', 45.0)]
2024-02-26 10:30:50,678 [SAT_01] INFO: Task execution complete...
```

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Ports for 3 satellites
SATELLITE_PORTS = [5001, 5002, 5003]

# Battery simulation
MAX_BATTERY = 100
BATTERY_DRAIN_RATE = 2  # % per second at idle
BATTERY_DRAIN_TASK = 10  # % per task execution
BATTERY_RECHARGE_RATE = 0.5  # % per second idle

# Consensus window
BID_TIMEOUT = 2.0  # seconds to wait for peer bids

# Bidding weights
BID_WEIGHT_BATTERY = 0.5  # weight for battery in score calc
BID_WEIGHT_POSITION = 100.0  # bonus for position match

# Sectors (orbit zones)
SECTORS = ["SECTOR_1", "SECTOR_2", "SECTOR_3", "SECTOR_4", "SECTOR_5", "SECTOR_6"]

# Task simulation
TASK_EXECUTION_TIME = 3  # seconds

# Heartbeat (how often state updates)
HEARTBEAT_INTERVAL = 0.5  # seconds
```

## 📡 Network Communication

### UDP Packet Format

**Task Broadcast (Ground → Satellites)**
```json
{
  "type": "TASK_BROADCAST",
  "task": "IMAGING",
  "location": "SECTOR_4",
  "timestamp": "2024-02-26T10:30:45.123456",
  "priority": 1
}
```

**Bid Message (Satellite → Satellite)**
```json
{
  "type": "BID",
  "node_id": "SAT_01",
  "score": 140.0,
  "battery": 80.0,
  "position": "SECTOR_4",
  "timestamp": "2024-02-26T10:30:45.234567"
}
```

## 🛡️ Fault Tolerance Demo

### Scenario: Node Failure During Consensus

1. **Start** → All 3 nodes running
2. **Inject Task** → All nodes start bidding
3. **Kill SAT_01** (highest bidder) → Close its terminal
4. **Dashboard Updates** → SAT_01 shows OFFLINE
5. **Inject Another Task** → SAT_02 or SAT_03 becomes winner
6. **Proof** → No ground intervention, swarm self-heals

### Key Features:
- **Graceful Degradation**: Peers with socket errors are silently skipped
- **No Single Point of Failure**: Any satellite can execute any task
- **Automatic Failover**: Next task broadcast will select best remaining node

## 📈 Scalability Notes

The current prototype uses:
- **UDP broadcasts** (synchronous, 2-second consensus windows)
- **JSON state files** (simple, not for production)

To scale to dozens of satellites:
- Replace UDP with **ZMQ** (pub/sub for broadcasts)
- Replace JSON files with **time-series database** (InfluxDB, Prometheus)
- Add **distributed consensus** algorithm (Raft, PBFT)
- Implement **partial mesh** networking (not full broadcast)

## 📚 Example Workflows

### Workflow 1: Single Task Execution
```bash
# Terminal 1: Launch swarm
start.bat

# Terminal 2: Send task
python ground_station.py --task IMAGING --location SECTOR_4

# Dashboard: See SAT_01 or SAT_02 get selected based on battery/position
```

### Workflow 2: Sequential Tasks
```bash
python ground_station.py --task IMAGING --location SECTOR_1 --repeat 3 --interval 10
# Tasks injected every 10 seconds; each gets a new bidding round
```

### Workflow 3: Fault Tolerance
```bash
# Terminal 1: Start swarm
start.bat

# Terminal 2: Send task
python ground_station.py --task IMAGING --location SECTOR_4

# Terminal 1: Kill SAT_01 (close its window)

# Terminal 2: Send another task
python ground_station.py --task SURVEILLANCE --location SECTOR_2

# Result: SAT_02 or SAT_03 executes (automatic failover)
```

### Workflow 4: Battery Awareness
```bash
# Run simulation for 10+ minutes
# Watch battery deplete on executing satellites
# Idle satellites recharge
# Next task goes to satellite with best battery + position
```

## 🐛 Debugging

### Check Logs
```bash
# View real-time satellite logs
tail -f swarm_events.log

# Windows: Use Notepad or VS Code to follow swarm_events.log
```

### Check State
```bash
# Pretty-print current swarm state
type swarm_state.json   # Windows
cat swarm_state.json    # Linux/Mac
```

### Manual Communication Test
```bash
# Send a test task from Python shell
python
>>> import socket, json
>>> msg = {"type": "TASK_BROADCAST", "task": "TEST", "location": "SECTOR_1"}
>>> sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
>>> sock.sendto(json.dumps(msg).encode(), ("127.0.0.1", 5001))
```

## 🎓 Learning Outcomes

By running this prototype, you'll understand:
- **Distributed Consensus** without centralized control
- **Autonomous Agent Behavior** (bids, negotiations, self-organization)
- **Fault Tolerance** (graceful degradation, automatic failover)
- **Real-time Visualization** of swarm intelligence
- **Socket Programming** and UDP broadcasts
- **JSON-based Inter-Process Communication**

## 📝 License

MIT License - Use freely for learning and development

## 🤝 Contributing

Feel free to extend with:
- Stronger consensus algorithms (Raft, PBFT)
- Network simulation (latency, packet loss, Byzantine nodes)
- Multi-satellite formation flying tasks
- Machine learning-based bidding strategies
- Cloud backend integration

---

**Questions?** Review the code comments in each `.py` file. The satellite nodes are designed to be self-documenting.

**Happy swarming! 🛰️🛰️🛰️**
