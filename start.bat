@echo off
REM Start USOS Satellite Swarm Simulation
REM This script launches 3 satellite nodes and the Streamlit dashboard

echo ========================================
echo USOS OrbitalNet OS - Swarm Simulator
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Create log and state files if they don't exist
if not exist swarm_state.json (
    echo {} > swarm_state.json
)
if not exist swarm_events.log (
    echo Swarm simulation started at %date% %time% > swarm_events.log
)

echo Launching satellite nodes...
echo.

REM Launch Satellite 1 (SAT_01 on port 5001)
echo [1/3] Starting SAT_01 on port 5001...
start "SAT_01" cmd /k python satellite_node.py --id SAT_01 --port 5001 --peers 5002,5003

REM Small delay to prevent port conflicts
timeout /t 1 /nobreak

REM Launch Satellite 2 (SAT_02 on port 5002)
echo [2/3] Starting SAT_02 on port 5002...
start "SAT_02" cmd /k python satellite_node.py --id SAT_02 --port 5002 --peers 5001,5003

REM Small delay
timeout /t 1 /nobreak

REM Launch Satellite 3 (SAT_03 on port 5003)
echo [3/3] Starting SAT_03 on port 5003...
start "SAT_03" cmd /k python satellite_node.py --id SAT_03 --port 5003 --peers 5001,5002

REM Wait for nodes to start
timeout /t 2 /nobreak

REM Launch Streamlit Dashboard
echo.
echo Starting Streamlit Dashboard...
timeout /t 2 /nobreak

start "USOS Dashboard" cmd /k streamlit run dashboard.py

echo.
echo ========================================
echo Swarm simulation is now running!
echo ========================================
echo.
echo Dashboard will open in your browser at:
echo http://localhost:8501
echo.
echo To inject a task, open a new command prompt and run:
echo python ground_station.py --task IMAGING --location SECTOR_4
echo.
echo To stop all nodes, close each terminal window individually.
echo ========================================
echo.

pause
