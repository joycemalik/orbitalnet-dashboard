#!/bin/bash

# Start USOS Satellite Swarm Simulation
# This script launches 3 satellite nodes and the Streamlit dashboard

echo "========================================"
echo "USOS OrbitalNet OS - Swarm Simulator"
echo "========================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    exit 1
fi

# Create log and state files if they don't exist
if [ ! -f swarm_state.json ]; then
    echo "{}" > swarm_state.json
fi
if [ ! -f swarm_events.log ]; then
    echo "Swarm simulation started at $(date)" > swarm_events.log
fi

echo "Launching satellite nodes..."
echo ""

# Launch Satellite 1 (SAT_01 on port 5001)
echo "[1/3] Starting SAT_01 on port 5001..."
python3 satellite_node.py --id SAT_01 --port 5001 --peers 5002,5003 &
SAT1_PID=$!

# Small delay to prevent port conflicts
sleep 1

# Launch Satellite 2 (SAT_02 on port 5002)
echo "[2/3] Starting SAT_02 on port 5002..."
python3 satellite_node.py --id SAT_02 --port 5002 --peers 5001,5003 &
SAT2_PID=$!

# Small delay
sleep 1

# Launch Satellite 3 (SAT_03 on port 5003)
echo "[3/3] Starting SAT_03 on port 5003..."
python3 satellite_node.py --id SAT_03 --port 5003 --peers 5001,5002 &
SAT3_PID=$!

# Wait for nodes to start
sleep 2

# Launch Streamlit Dashboard
echo ""
echo "Starting Streamlit Dashboard..."
streamlit run dashboard.py

# Clean up background processes on exit
trap "kill $SAT1_PID $SAT2_PID $SAT3_PID 2>/dev/null" EXIT

echo ""
echo "========================================"
echo "Swarm simulation is now running!"
echo "========================================"
echo ""
echo "Dashboard will open in your browser at:"
echo "http://localhost:8501"
echo ""
echo "To inject a task, open a new terminal and run:"
echo "python3 ground_station.py --task IMAGING --location SECTOR_4"
echo ""
echo "Press Ctrl+C to stop the simulation"
echo "========================================"
echo ""

wait
