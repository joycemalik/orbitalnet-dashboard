import subprocess
import time
import sys
import redis

def start_redis():
    print("🧠 Kickstarting Redis Database in WSL...")
    # Fire the boot command to WSL
    subprocess.run(["wsl", "-u", "root", "service", "redis-server", "start"], check=False)

def wait_for_redis(timeout=15):
    """Actively polls the Redis port until it wakes up."""
    print("⏳ Waiting for Redis to respond...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Attempt to connect and ping
            r = redis.Redis(host='localhost', port=6379, db=0)
            if r.ping():
                print("✅ Redis is online and ready!")
                return True
        except redis.exceptions.ConnectionError:
            # If it refuses, it's still booting. Wait 0.5s and try again.
            time.sleep(0.5)
            
    return False

def boot_system():
    print("🚀 Booting OrbitalNet OS Unified Platform...")
    
    # 1. Start the Brain
    start_redis()
    
    # 2. Wait for the Brain to actually wake up
    if not wait_for_redis():
        print("❌ FATAL: Redis failed to start within 15 seconds. Aborting boot sequence.")
        sys.exit(1)
        
    processes = []
    try:
        # 3. Safe to launch the rest of the OS
        print("Starting Physics Engine...")
        physics = subprocess.Popen([sys.executable, "physics_engine.py"])
        processes.append(physics)
        time.sleep(1)
        
        print("Starting WebSocket Streamer...")
        streamer = subprocess.Popen([sys.executable, "streamer.py"])
        processes.append(streamer)
        time.sleep(1)

        # 4. Start the Consensus Engine (Swarm Intel)
        print("Starting Consensus Engine...")
        consensus = subprocess.Popen([sys.executable, "consensus_engine.py"])
        processes.append(consensus)
        time.sleep(1)
        
        print("Starting Command Center...")
        # Make sure this points to your actual streamlit file
        dashboard = subprocess.Popen(["streamlit", "run", "cloud_dashboard.py"]) 
        processes.append(dashboard)

        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down OrbitalNet OS...")
        for p in processes:
            p.terminate()
        print("All systems offline.")

if __name__ == "__main__":
    boot_system()


