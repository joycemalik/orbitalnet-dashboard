"""One-click launcher for the research viewer: `python -m research.launch`.

- Checks research dependencies are importable.
- Starts Phase 1 (existence proof) as a background subprocess, writing live
  progress to research/results/progress.json.
- Starts the read-only Streamlit viewer on its own port (default 8502, never
  8501 — that's the live OrbitalNet OS app).
- Opens the browser.
- On Ctrl+C, terminates both subprocesses cleanly.

Modes:
  --mode quick  ~100 events, finishes in a couple of minutes, labeled DEMO.
  --mode full   1000 events, runs in the background while you watch progress.
If --mode is omitted and the console is interactive, you're asked to choose.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser

VIEWER_PORT = 8502
QUICK_N_EVENTS = 100
FULL_N_EVENTS = 1000


def check_dependencies() -> bool:
    missing = []
    for mod in ("numpy", "scipy", "matplotlib", "streamlit"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Install with:  pip install -r requirements-research.txt")
        return False
    return True


def choose_mode_interactively() -> str:
    print("Choose a mode:")
    print("  1) Quick demo  (~100 events, a couple of minutes, labeled DEMO)")
    print("  2) Full run    (1000 events, runs in the background)")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
            return "quick"
        if choice == "2":
            return "full"
        print("Please enter 1 or 2.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["quick", "full"], default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--port", type=int, default=VIEWER_PORT)
    args = parser.parse_args()

    if not check_dependencies():
        return 1

    mode = args.mode
    if mode is None:
        if sys.stdin.isatty():
            mode = choose_mode_interactively()
        else:
            print("No --mode given and input is not interactive; defaulting to --mode quick.")
            mode = "quick"

    n_events = QUICK_N_EVENTS if mode == "quick" else FULL_N_EVENTS
    tag = "demo" if mode == "quick" else "full"

    print(f"Starting Phase 1 ({tag}, n_events={n_events}, seed={args.seed})...")
    experiment_proc = subprocess.Popen([
        sys.executable, "-m", "research.experiments.phase1_existence_proof",
        "--seed", str(args.seed),
        "--n-events", str(n_events),
        "--tag", tag,
    ])

    print(f"Starting viewer app on http://localhost:{args.port} ...")
    app_path = "research/app/viewer.py"
    app_proc = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", app_path,
        "--server.port", str(args.port),
        "--server.headless", "true",
    ])

    time.sleep(2)
    webbrowser.open(f"http://localhost:{args.port}")

    print("Press Ctrl+C to shut down both the experiment and the viewer.")
    try:
        while True:
            time.sleep(1)
            if experiment_proc.poll() is not None and app_proc.poll() is not None:
                break
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for proc, name in ((experiment_proc, "experiment"), (app_proc, "viewer")):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"{name} did not exit in time, killing it.")
                    proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
