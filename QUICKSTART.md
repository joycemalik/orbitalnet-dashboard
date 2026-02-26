# Quick Start Guide - USOS Satellite Swarm

## ⚡ 30-Second Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the Swarm
**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### 3. Send a Task (From New Terminal)
```bash
python ground_station.py --task IMAGING --location SECTOR_4
```

### 4. Watch the Dashboard
Open `http://localhost:8501` in your browser. You'll see:
- 3 satellites bidding for the task
- One satellite wins based on battery & position
- Winner executes, others yield
- Live event log shows consensus decisions

---

## 🎬 What to Expect

**Terminal Output (Satellites):**
```
[SAT_01] INFO: Received task: IMAGING at SECTOR_4
[SAT_01] INFO: My bid score: 140.00
[SAT_02] INFO: My bid score: 30.00
[SAT_03] INFO: My bid score: 45.00
[SAT_01] INFO: CONSENSUS REACHED: WINNER!
[SAT_01] INFO: Executing task...
[SAT_02] INFO: CONSENSUS REACHED: Yielding to SAT_01
[SAT_03] INFO: CONSENSUS REACHED: Yielding to SAT_01
```

**Dashboard (Browser):**
- ⭐ SAT_01 highlighted as WINNER
- Battery bars showing drain during execution
- Status changing from IDLE → BIDDING → EXECUTING → IDLE
- Event log scrolling in real-time

---

## 🧪 Try These Scenarios

### Scenario 1: Multiple Tasks
```bash
python ground_station.py --task IMAGING --location SECTOR_1 --repeat 5 --interval 5
```
Watch different satellites win different tasks based on their battery/position!

### Scenario 2: Node Failure
```bash
# 1. Let swarm run (terminals showing all 3 satellites)
# 2. Close SAT_01 terminal
# 3. Send new task:
python ground_station.py --task SURVEILLANCE --location SECTOR_2

# Result: SAT_02 or SAT_03 automatically takes over!
```

### Scenario 3: Battery Depletion
```bash
# Run for 10+ minutes without injecting tasks
# Watch battery recharge in idle satellites
# Execute a task - watch winner's battery drain
# Next task goes to satellite with best battery!
```

---

## 🔍 Understanding the Bid Score

```
Bid Score = (Battery Level × 0.5) + (100 if at task location else 0)
```

**Example:**
- SAT_01: 80% battery at SECTOR_4, task at SECTOR_4 → 40 + 100 = **140** ✅ WINNER
- SAT_02: 60% battery at SECTOR_1, task at SECTOR_4 → 30 + 0 = **30**
- SAT_03: 90% battery at SECTOR_2, task at SECTOR_4 → 45 + 0 = **45**

---

## 🛑 Stopping the Simulation

**Windows:** Close each satellite terminal and dashboard window

**Linux/Mac:** Press `Ctrl+C` in the main terminal running `start.sh`

---

## 📋 Advanced Commands

### Custom Sectors
Available: SECTOR_1, SECTOR_2, SECTOR_3, SECTOR_4, SECTOR_5, SECTOR_6

```bash
python ground_station.py --task COMMUNICATION --location SECTOR_3
```

### Help & Options
```bash
# Satellite node options:
python satellite_node.py --help

# Ground station options:
python ground_station.py --help
```

### Manual Satellite Node (For Testing)
```bash
python satellite_node.py --id SAT_CUSTOM --port 5004 --peers 5001,5002,5003
```

### Manual Dashboard
```bash
streamlit run dashboard.py
```

---

## ❓ FAQ

**Q: Dashboard shows OFFLINE nodes?**
A: Make sure you ran `start.bat` (Windows) or `start.sh` (Linux). Nodes take 2-3 seconds to initialize.

**Q: Tasks aren't showing in the log?**
A: The dashboard auto-refreshes every 1 second. Check the satellite terminals (command prompts) for debug logs.

**Q: Can I customize battery drain rates?**
A: Yes! Edit `config.py`:
```python
BATTERY_DRAIN_RATE = 5  # Faster drain
BATTERY_RECHARGE_RATE = 1.0  # Faster recharge
```

**Q: How many satellites can I simulate?**
A: Edit `config.py` and add more ports/IDs, then update `start.bat`/`start.sh`. Currently designed for 3, but scales to ~10 before performance issues.

**Q: Can I use this for production?**
A: No! This is a prototype. For production:
- Use real spacecraft APIs
- Replace JSON files with a proper database
- Replace UDP with ZMQ or gRPC
- Add security/authentication
- Implement stronger consensus (Raft, PBFT)

---

**Happy swarming! 🛰️**
