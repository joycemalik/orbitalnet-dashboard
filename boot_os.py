import subprocess
import time
import sys
import redis
import threading

def check_memurai():
    print("🧠 Checking native Memurai (Redis) connection...")
    r = redis.Redis(host='127.0.0.1', port=6379)
    try:
        if r.ping():
            print("✅ Memurai is online and ready!")
            r.close()
            return True
    except redis.ConnectionError:
        print("❌ Memurai is dead. Start it in Windows Services.")
        sys.exit(1) # Kill the boot if the DB isn't there

def boot_system():
    print("🚀 Booting OrbitalNet OS Unified Platform...")
    
    # 1. Check Memurai
    check_memurai()
        
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
