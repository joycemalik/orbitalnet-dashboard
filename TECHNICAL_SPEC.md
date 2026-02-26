# USOS Technical Specification

## System Architecture

### Overview
USOS is a distributed satellite autonomy system implementing decentralized task allocation through consensus-based bidding. The system comprises three main components:

1. **Satellite Nodes** - Autonomous agents with local state and decision-making
2. **Ground Station** - Task injector (human/automated command center)
3. **Dashboard** - Real-time monitoring and visualization

### Design Principles
- **Decentralized**: No central coordinator; each satellite makes decisions independently
- **Fault-Tolerant**: System continues operating if any single node fails
- **Autonomous**: Satellites execute tasks without ground intervention (post-allocation)
- **Real-Time**: All decisions made within bounded time windows (2 seconds)

---

## Component Specifications

### 1. Satellite Node (`satellite_node.py`)

#### State Model
Each satellite maintains:
```python
{
    "battery": float,           # 0-100%, represents available energy
    "position": str,            # Current orbit sector (SECTOR_1 to SECTOR_6)
    "status": str,              # IDLE, BIDDING, EXECUTING, OFFLINE
    "current_task": dict,       # Active task or None
    "is_winner": bool,          # True if last consensus winner
    "last_bid_scores": dict,    # {node_id: score} from last bidding round
}
```

#### Process Model
```
┌─────────────────────────────────────────────────────────┐
│          SATELLITE NODE STATE MACHINE                   │
└─────────────────────────────────────────────────────────┘

IDLE ◄──────────────────────────────────────┐
  │                                           │
  │ (Task received)                           │ (Consensus failed /
  │                                           │  Yielding)
  ▼                                           │
BIDDING ◄───────────────────────────────────┤
  │ (Calculate score)                         │
  │ (Broadcast bid)                           │
  │ (Wait 2 seconds)                          │
  │ (Compare scores)                          │
  │                                           │
  ├─ (My score high) ──> EXECUTING ──┐       │
  │                                  │       │
  │                                  ▼       │
  └───────────────────────────────── IDLE ◄──┤ (Task complete)
                                            │
                              (Node offline) ▼
                                    OFFLINE
```

#### Bid Calculation Algorithm
```python
def calculate_bid_score(battery, position, task_location):
    """
    Calculates competitiveness for task execution.
    
    Factors:
    - Battery (0.5x weight): Reflects available energy
    - Position (100 bonus): Perfect location match gives advantage
    
    Score Range: 0 (dead battery) to 150 (full battery + location match)
    """
    battery_component = battery * 0.5
    position_bonus = 100.0 if position == task_location else 0.0
    return battery_component + position_bonus
```

#### Consensus Protocol (2-Second Window)

**Phase 1: Bid Calculation (Immediate)**
```
On task receipt:
  1. Parse task message (task type, target location)
  2. Calculate local bid score
  3. Log calculation for dashboard monitoring
```

**Phase 2: Broadcast (t=0ms)**
```
Upon calculation complete:
  1. Create BID message packet (JSON)
  2. Send UDP packet to all peer ports
  3. Record own score in shared state
  4. Transition to BIDDING status
```

**Phase 3: Collection (t=0 to t=2000ms)**
```
During 2-second window:
  1. Listen for incoming BID packets from peers
  2. Validate packet format and node_id
  3. Store {node_id: score} pairs
  4. Handle peer offline gracefully (silent skip)
```

**Phase 4: Decision (t=2000ms)**
```
After timeout:
  1. Compile all scores (own + received)
  2. Find node with max score
  3. If my node won:
     - Set is_winner = true
     - Transition to EXECUTING
     - Drain battery by BATTERY_DRAIN_TASK
  4. Else:
     - Log "Yielding to [winner]"
     - Transition to IDLE
  5. Update shared state for dashboard
```

#### Fault Tolerance Mechanism

**Network Failure Handling:**
```python
for peer_port in peer_ports:
    try:
        socket.sendto(bid_message, (localhost, peer_port))
    except OSError:
        # Peer offline - continue with other peers
        # This peer's bid will be missing in consensus round
        continue
```

**Implication**: If a satellite is offline:
- Others don't receive its bid
- Winner selection happens among active nodes only
- Provides automatic failover (next-best node takes over)

**Node Restart Recovery:**
```
Upon restart:
  1. Initialize with random battery (50-100%)
  2. Generate random position (random sector)
  3. Join existing consensus rounds
  4. Next task will include this node in bidding
```

#### Battery Simulation Thread

```
Battery dynamics:
- IDLE satellites: Recharge +0.5% per second (solar power)
- EXECUTING satellites: Drain -2% per second base
- Task execution: Additional -10% per completed task
- Minimum: 0% (dead)
- Maximum: 100% (fully charged)

This models:
- Sun-facing satellites recharging
- Communication/computation drain
- Task-specific energy consumption
```

### 2. Ground Station (`ground_station.py`)

#### Task Injection Protocol

**Command Line Interface:**
```bash
python ground_station.py --task TASK_TYPE --location SECTOR_N [--repeat N] [--interval SEC]
```

**Task Message Format (UDP Broadcast):**
```json
{
  "type": "TASK_BROADCAST",
  "task": "IMAGING",
  "location": "SECTOR_4",
  "timestamp": "2024-02-26T10:30:45.123456",
  "priority": 1
}
```

**Broadcast Mechanism:**
```
Ground Station ──UDP broadcast──> Port 5001 (SAT_01)
                              ├──> Port 5002 (SAT_02)
                              └──> Port 5003 (SAT_03)
                              
All satellites receive concurrently.
No acknowledgment required (fire-and-forget).
```

#### Task Parameters
- **task**: String identifier (IMAGING, SURVEILLANCE, COMMUNICATION, etc.)
- **location**: Target sector (SECTOR_1 through SECTOR_6)
- **priority**: Integer (1 = normal, higher values for urgent tasks - can extend)
- **timestamp**: ISO 8601 timestamp for logging

### 3. Dashboard (`dashboard.py`)

#### Data Flow

```
satellite_node.py ──┐
      │             │ (heartbeat every 0.5s)
      │             │ Updates swarm_state.json
      └────────────►swarm_state.json◄──────── dashboard.py
                    │                         (polls every 1s)
                    │ Auto-refresh
                    │ Display status
                    
satellite_node.py ──┐
      │             │ (logs decisions)
      │             │ Appends to file
      └────────────►swarm_events.log◄──────── dashboard.py
                    │                         (reads last 100 lines)
                    │ Show in log viewer
```

#### Visualization Elements

**1. System Metrics (Top Row)**
```
┌────────────────────┬──────────────────┬──────────────────┐
│ 🛰️ Active Nodes    │ 🔋 Avg Battery   │ 📋 Active Tasks  │
│ 3/3               │ 72.5%            │ 1                │
└────────────────────┴──────────────────┴──────────────────┘
```

**2. Satellite Cards (3 Columns)**
```
┌──────────────────────────────────────────────────────────┐
│ SAT_01                                    ⭐ WINNER      │
├──────────────────────────────────────────────────────────┤
│ 🟢 Status: EXECUTING                                     │
│ 🔋 Battery: ███████░░░░ 75.0%                            │
│ 📍 Position: SECTOR_4                                    │
│ 📋 Task: IMAGING @ SECTOR_4                              │
│ 📊 Last Bid Scores:                                      │
│    SAT_01: 140.00 (winner ✓)                             │
│    SAT_02: 30.00                                         │
│    SAT_03: 45.00                                         │
└──────────────────────────────────────────────────────────┘
```

**3. Event Log**
```
[green]2024-02-26 10:30:45 [SAT_01] INFO: Received task: IMAGING at SECTOR_4
[yellow]2024-02-26 10:30:45 [SAT_01] INFO: My bid score: 140.00
[green]2024-02-26 10:30:47 [SAT_01] INFO: CONSENSUS REACHED: WINNER!
[green]2024-02-26 10:30:50 [SAT_01] INFO: Task execution complete
```

---

## Communication Protocol

### Message Types

#### 1. Task Broadcast (Ground → All Satellites)
```
Protocol: UDP
Port: Dynamic (sent to all satellite ports)
Format: JSON
Direction: Unidirectional (no ACK)

Packet Structure:
{
  "type": "TASK_BROADCAST",
  "task": str,
  "location": str,
  "timestamp": ISO8601,
  "priority": int
}

Handling:
- Each satellite receives the broadcast
- Independently calculates bid
- Initiates consensus round
```

#### 2. Bid Message (Satellite ↔ Satellite)
```
Protocol: UDP
Port: Satellite's listening port
Format: JSON
Direction: Peer-to-peer broadcast

Packet Structure:
{
  "type": "BID",
  "node_id": str,
  "score": float,
  "battery": float,
  "position": str,
  "timestamp": ISO8601
}

Handling:
- Sender broadcasts to all peer ports
- Receivers listen and store scores
- Used only for consensus, not for ACK
```

### Network Constraints Handled

1. **Packet Loss**: If a satellite is offline, its bid is simply missing
2. **Latency**: 2-second consensus window accounts for network delays
3. **Out-of-Order Arrival**: Not handled (simplicity), but rare at 2s window
4. **Duplicate Packets**: Last-one-wins (stored in dictionary)

---

## Shared State Format

### swarm_state.json

```json
{
  "SAT_01": {
    "timestamp": "2024-02-26T10:30:50.123456",
    "node_id": "SAT_01",
    "battery": 65.8,
    "position": "SECTOR_4",
    "status": "IDLE",
    "is_winner": false,
    "current_task": null,
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

**Update Frequency**: Every 0.5 seconds (heartbeat)
**Read By**: Dashboard (polls every 1 second)
**Concurrency**: File locking handled by OS; Python's atomic writes minimize issues

### swarm_events.log

```
[TIMESTAMP] [NODE_ID] [LEVEL] [MESSAGE]

Examples:
2024-02-26 10:30:45,567 [SAT_01] INFO: Listener thread started on port 5001
2024-02-26 10:30:45,678 [SAT_01] INFO: Received task: IMAGING at SECTOR_4
2024-02-26 10:30:45,789 [SAT_01] INFO: My bid score: 140.00
2024-02-26 10:30:45,890 [SAT_02] INFO: My bid score: 30.00
2024-02-26 10:30:47,901 [SAT_01] INFO: CONSENSUS REACHED: WINNER!
2024-02-26 10:30:47,912 [SAT_02] INFO: CONSENSUS REACHED: Yielding to SAT_01
2024-02-26 10:30:50,923 [SAT_01] INFO: Task execution complete
```

**Write Pattern**: Append-only; thread-safe via logging module
**Read By**: Dashboard (tail -f pattern; reads last N lines)

---

## Timing Specifications

| Event | Duration | Notes |
|-------|----------|-------|
| Task broadcast to all nodes | <10ms | UDP, local network |
| Bid calculation | <1ms | Simple arithmetic |
| Bid broadcast to peers | ~5ms each | Sequential or parallel |
| Consensus decision window | 2000ms | Accounts for jitter, retransmits |
| Task execution | 3000ms | Configurable simulation |
| Battery update | 1000ms | Per-second granularity |
| Dashboard refresh | 1000ms | Streamlit auto-refresh |
| Heartbeat update | 500ms | swarm_state.json write |

---

## Scalability Considerations

### Current Limitations
- **Broadcast Protocol**: All nodes hear all tasks (O(n) communication)
- **Consensus Window**: Fixed 2 seconds (doesn't adapt to network conditions)
- **State Storage**: JSON file (not suitable for >10 nodes)
- **Bidding**: Simple linear score (doesn't model constraints like fuel, thermal limits)

### Path to Production (10-1000 satellites)
1. **Networking**: Replace UDP with ZMQ pub/sub for pub/subscribe pattern
2. **State**: Use InfluxDB or Prometheus for time-series state
3. **Consensus**: Implement Raft or PBFT for byzantine fault tolerance
4. **Bidding**: Add goal/priority weighting, multi-objective optimization
5. **Monitoring**: Replace Streamlit with Grafana for production dashboards

---

## Security Considerations

### Current Implementation
- **No authentication**: Any entity can broadcast tasks
- **No encryption**: All traffic in plaintext
- **No Byzantine tolerance**: Assumes all nodes are honest

### For Production
1. **Digital Signatures**: Sign all messages with satellite certificates
2. **TLS/DTLS**: Encrypt all UDP communications
3. **Byzantine Consensus**: Use PBFT or Tendermint for adversarial nodes
4. **Task Validation**: Cryptographic validation of task source
5. **Rate Limiting**: Prevent task injection DoS attacks

---

## Testing & Validation

### Test Cases Included

1. **Normal Operation**
   - Task injection → consensus → execution

2. **Fault Tolerance**
   - Kill satellite → system continues with remaining nodes

3. **Battery Depletion**
   - Low-battery satellites deprioritized in bidding

4. **Position-Based Allocation**
   - Satellite at target sector wins despite lower battery

### Metrics to Validate
- Consensus reaches decision in <2.1 seconds
- No two satellites execute same task (mutual exclusion)
- Fault-tolerated node recovers on restart
- Battery model exhibits expected behavior

---

## Configuration Parameters (config.py)

```python
# Network
LOCALHOST = "127.0.0.1"
SATELLITE_PORTS = [5001, 5002, 5003]

# Battery
MAX_BATTERY = 100
BATTERY_DRAIN_RATE = 2  # % per second
BATTERY_DRAIN_TASK = 10  # % per task
BATTERY_RECHARGE_RATE = 0.5  # % per second

# Consensus
BID_TIMEOUT = 2.0  # seconds
BID_WEIGHT_BATTERY = 0.5  # score multiplier
BID_WEIGHT_POSITION = 100.0  # bonus

# Orbits
SECTORS = ["SECTOR_1", ..., "SECTOR_6"]

# Task
TASK_EXECUTION_TIME = 3  # seconds

# Monitoring
HEARTBEAT_INTERVAL = 0.5  # seconds
```

---

## Appendix: Glossary

- **Bid Score**: Numerical value representing a satellite's suitability for a task
- **Consensus**: Agreement process where satellites collectively decide winner
- **Contract Net**: Bidding-based allocation protocol (from agent systems theory)
- **Byzantine Fault**: Node that behaves arbitrarily (not implemented in prototype)
- **Fault Tolerance**: System continues functioning despite node failures
- **Heartbeat**: Periodic status update (here: 0.5s)
- **Mutual Exclusion**: Only one satellite executes a given task
- **Raft/PBFT**: Distributed consensus algorithms (for future work)

---

**Document Version**: 1.0  
**Last Updated**: 2024-02-26  
**Status**: Prototype / Research
