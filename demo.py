"""One-click demo launcher for OrbitalNet OS (fully local, no AWS).

Starts:
  * physics_engine.py   -> satellite state into Redis (Memurai)
  * streamer.py         -> websocket :8765 for the 3D globe
  * consensus_engine.py -> leader election + CNP auctions
  * Streamlit app.py              on http://localhost:8501  (live mission control)
  * Streamlit research viewer     on http://localhost:8502  (Event Lab, scorecard, anomaly tracker)
then opens both in the browser. Ctrl+C (or closing the window) stops everything.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def redis_up() -> bool:
    try:
        import redis
        return bool(redis.Redis(host="127.0.0.1", port=6379, socket_timeout=2).ping())
    except Exception:
        return False


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    print("🚀 OrbitalNet OS — one-click demo\n")
    if not redis_up():
        print("🧠 Memurai not responding — trying to start the service…")
        subprocess.run(["net", "start", "Memurai"], capture_output=True)
        time.sleep(2)
    if not redis_up():
        print("❌ Memurai (Redis) is not running on 127.0.0.1:6379.\n"
              "   Start it from Windows Services (services.msc → Memurai → Start), then run DEMO.bat again.")
        input("Press Enter to exit…")
        return 1
    print("✅ Memurai online")

    for p in (8501, 8502, 8765):
        if port_open(p):
            print(f"⚠️  Port {p} is already in use — an old demo may still be running. Close it first.")

    st = [PY, "-m", "streamlit", "run"]
    headless = ["--server.headless", "true", "--browser.gatherUsageStats", "false"]
    specs = [
        ("Physics engine", [PY, "physics_engine.py"], 2),
        ("WebSocket streamer", [PY, "streamer.py"], 1),
        ("Consensus engine", [PY, "consensus_engine.py"], 1),
        ("Mission control (8501)", st + ["app.py", "--server.port", "8501"] + headless, 0),
        ("Research dashboard (8502)", st + ["research/app/viewer.py", "--server.port", "8502"] + headless, 0),
    ]
    procs = []
    try:
        for name, cmd, wait in specs:
            print(f"▶  {name}")
            procs.append((name, subprocess.Popen(cmd, cwd=ROOT)))
            time.sleep(wait)
        deadline = time.time() + 60
        while time.time() < deadline and not (port_open(8501) and port_open(8502)):
            time.sleep(1)
        webbrowser.open("http://localhost:8501")
        webbrowser.open("http://localhost:8502")
        print("\n✅ All systems online.\n"
              "   Mission control : http://localhost:8501\n"
              "   Research + Event Lab : http://localhost:8502\n"
              "   Press Ctrl+C here to shut everything down.\n")
        while True:
            for name, p in procs:
                if p.poll() is not None:
                    print(f"⚠️  {name} exited (code {p.returncode})")
                    procs.remove((name, p))
                    break
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down…")
    finally:
        for _name, p in procs:
            if p.poll() is None:
                p.terminate()
        for _name, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("All systems offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
