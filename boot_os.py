import subprocess
import time
import sys
import redis
import threading

def start_redis():
    print("🧠 Kickstarting Redis Database in WSL...")
    subprocess.run(["wsl", "-u", "root", "service", "redis-server", "start"], check=False)

def wait_for_redis(timeout=15):
    """Actively polls the Redis port until it wakes up."""
    print("⏳ Waiting for Redis to respond...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            r = redis.Redis(host='localhost', port=6379, db=0)
            if r.ping():
                print("✅ Redis is online and ready!")
                r.close()
                return True
        except (redis.exceptions.ConnectionError, ConnectionRefusedError):
            time.sleep(0.5)
            
    return False

def redis_watchdog():
    """Background thread that monitors Redis and restarts it if it dies."""
    while True:
        time.sleep(10)  # Check every 10 seconds
        try:
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            r.close()
        except Exception:
            print("🔄 Redis watchdog detected failure. Restarting Redis in WSL...")
            start_redis()
            time.sleep(3)

def boot_system():
    print("🚀 Booting OrbitalNet OS Unified Platform...")
    
    # 1. Start the Brain
    start_redis()
    
    # 2. Wait for the Brain to actually wake up
    if not wait_for_redis():
        print("❌ FATAL: Redis failed to start within 15 seconds. Aborting boot sequence.")
        sys.exit(1)

    # 3. Start the Redis watchdog in the background
    watchdog = threading.Thread(target=redis_watchdog, daemon=True)
    watchdog.start()
    print("🐕 Redis watchdog started (will auto-restart if Redis dies).")
        
    processes = []
    try:
        # 4. Launch the OS components
        print("Starting Physics Engine...")
        physics = subprocess.Popen([sys.executable, "physics_engine.py"])
        processes.append(physics)
        time.sleep(2)
        
        print("Starting WebSocket Streamer...")
        streamer = subprocess.Popen([sys.executable, "streamer.py"])
        processes.append(streamer)
        time.sleep(1)

        print("Starting Consensus Engine...")
        consensus = subprocess.Popen([sys.executable, "consensus_engine.py"])
        processes.append(consensus)
        time.sleep(1)
        
        print("Starting Command Center...")
        dashboard = subprocess.Popen(["streamlit", "run", "app.py"]) 
        processes.append(dashboard)

        print("\n✅ OrbitalNet OS is fully online.\n")

        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down OrbitalNet OS...")
        for p in processes:
            p.terminate()
        print("All systems offline.")

if __name__ == "__main__":
    boot_system()
