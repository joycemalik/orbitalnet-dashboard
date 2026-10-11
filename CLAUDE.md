# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

**OrbitalNet OS** (also called USOS) simulates a constellation of satellites (loaded from real-world TLE data) that autonomously bid on ground-station tasking missions via a Contract Net Protocol (CNP) auction, with a live 3D WebGL globe visualization.

Two architectures coexist in this repo:

- **Active/primary (local-first)** — Streamlit UI + Redis/Memurai + Python microservices + a Three.js globe. This is what recent commits target and what `boot_os.py` runs. Treat this as the current system.
- **Legacy (AWS-native)** — `lambda_function.py`, `cloud_dashboard.py`, and `TECHNICAL_SPEC.md` describe an older Lambda + SNS + DynamoDB design. It's still present and is what the devcontainer boots, but it is not where active development happens. Don't assume `TECHNICAL_SPEC.md` describes the current (Redis-based) system.

## How to run

1. Ensure Memurai (Redis for Windows) is running on `127.0.0.1:6379`.
2. `pip install -r requirements.txt`, then also `pip install websockets plotly` — both are imported by the code (`streamer.py`, `pages/3_under_the_hood.py`) but missing from `requirements.txt`.
3. `python boot_os.py` — boots, in order: physics engine (`physics_engine.py`) → websocket streamer (`streamer.py`, port 8765) → consensus engine (`consensus_engine.py`) → `streamlit run app.py` (port 8501). Ctrl+C shuts everything down gracefully.
4. Sidebar pages: Visualization (`pages/1_visualization.py`), Ground Station (`pages/2_ground_station.py`), Under the Hood (`pages/3_under_the_hood.py`).

Legacy path: the devcontainer auto-runs `streamlit run cloud_dashboard.py`, which talks directly to AWS (DynamoDB/SNS) instead of the local Redis stack — a separate entry point and stack from `boot_os.py`.

## Architecture / key files

- `app.py` — Streamlit landing page.
- `pages/1_visualization.py`, `2_ground_station.py`, `3_under_the_hood.py` — Streamlit's numeric-prefixed multipage convention; the prefix controls sidebar order.
- `physics_engine.py` — propagates orbits from `satellites.txt` (TLE data) via `sgp4`, generates telemetry, writes satellite state into Redis.
- `consensus_engine.py` — elects plane leaders, runs CNP auctions for missions in `MISSIONS_LEDGER`, forms/rolls enclaves, logs forensics to `AUCTION_LOGS`.
- `streamer.py` — websocket server (`ws://localhost:8765`) broadcasting Redis state to the front-end globe.
- `scoring_engine.py`, `hal_simulator.py`, `scenario_engine.py`, `config.py` — supporting libraries (scoring math, mock hardware telemetry, scenario definitions, shared constants + Redis client factory).
- `index.html` — Three.js globe, connects to `ws://localhost:8765`.

**Redis is the integration bus.** Components don't call each other directly — they communicate only through Redis keys (`STARLINK-<id>`, `MISSIONS_LEDGER`, `AUCTION_LOGS`, `TIME_MULTIPLIER`/`CHRONOS_MULTIPLIER`, `TRIGGER_CHAOS`, `CURRENT_MISSION`, `CURRENT_SUN_LON`, `SCORING_WEIGHTS`). This lets each process crash/restart independently. Preserve this decoupling — don't introduce direct imports/calls between the engines and the Streamlit pages.

## Known pitfalls

- **Streamlit rerun ordering**: in `pages/3_under_the_hood.py`, the auto-refresh `time.sleep(4); st.rerun()` call must stay at the very bottom of the script, after all `st.tabs(...)` blocks render. Calling `st.rerun()` earlier silently breaks rendering of later tabs — this exact bug was fixed in a recent commit. If you touch this file, keep the refresh logic at the bottom.
- **Encoding fragility on Windows**: PowerShell's `Set-Content` has repeatedly corrupted UTF-8 emoji characters in `pages/3_under_the_hood.py` (mojibake), requiring several follow-up fix commits. When editing files containing emoji on Windows, prefer the Edit tool (or `Out-File -Encoding utf8`) over `Set-Content`.
- `pages/1_visualization.py` re-reads `index.html` from disk on every page load and injects a cache-busting timestamp comment to defeat Streamlit's iframe caching — don't remove this without replacing the cache-busting mechanism.
- `requirements.txt` is incomplete (missing `websockets`, `plotly`) — update it if you add new dependencies, and don't assume it's authoritative for what's actually imported.

## Testing

No formal test suite. The closest thing is the `assert`-based self-test in `scoring_engine.py`, run via `python scoring_engine.py`.

## Security

`.env` holds AWS credentials and is gitignored. Never commit it, and don't echo its contents into chat or commits.

## Research branch rules (research/open-world-planner)

- All new work lives in `research/`. It must NOT import redis, streamlit, websockets, or any live-stack module.
- Every experiment is a script in `research/experiments/` that takes `--seed` and `--n-events`, and writes JSON/CSV to `research/results/`. Nothing is hand-edited.
- NEVER fabricate, estimate, or hardcode result numbers. Tables and figures are generated only from files in `research/results/`.
- Strategies B0, B1, B2, B3, P, O must receive identical events, orbits, budgets and contact schedules for a given seed.
- Tune hyperparameters on the validation seeds only. Test seeds are untouched until `research/PREREGISTRATION.md` is committed.
- Each phase ends with passing tests (`pytest research/`) and a commit.
- If something in the design is ambiguous or physically questionable, stop and ask rather than guessing.