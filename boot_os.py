import subprocess
import time
import sys

def boot_system():
    print("🚀 Booting OrbitalNet OS Unified Platform...")
    
    processes = []
    try:
        # --- NEW: THE FOREVER FIX ---
        # This tells Windows to use WSL as root and start Redis automatically.
        # Using '-u root' bypasses the annoying password prompt!
        print("🧠 Kickstarting Redis Database in WSL...")
        subprocess.run(["wsl", "-u", "root", "service", "redis-server", "start"], check=False)
        time.sleep(2) # Give Redis 2 seconds to fully wake up
        # ----------------------------

        # 1. Start the Physics Engine (The Brain)
        print("Starting Physics Engine...")
        physics = subprocess.Popen([sys.executable, "physics_engine.py"])
        processes.append(physics)
        time.sleep(2) 
        
        # 2. Start the WebSocket Streamer (The Nervous System)
        print("Starting WebSocket Streamer...")
        streamer = subprocess.Popen([sys.executable, "streamer.py"])
        processes.append(streamer)
        time.sleep(1)

        # 3. Start the Consensus Engine (Swarm Intel)
        print("Starting Consensus Engine...")
        consensus = subprocess.Popen([sys.executable, "consensus_engine.py"])
        processes.append(consensus)
        time.sleep(1)
        
        # 4. Start the Streamlit Dashboard (The Face)
        print("Starting Command Center...")
        dashboard = subprocess.Popen(["streamlit", "run", "cloud_dashboard.py"]) 
        processes.append(dashboard)

        # Keep the master script running
        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down OrbitalNet OS...")
        for p in processes:
            p.terminate()
        print("All systems offline.")

if __name__ == "__main__":
    boot_system()

