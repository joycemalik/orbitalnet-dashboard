# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

**OrbitalNet OS** (also called USOS) simulates a constellation of satellites (loaded from real-world TLE data) that autonomously bid on ground-station tasking missions via a Contract Net Protocol (CNP) auction, with a live 3D WebGL globe visualization.

Repo layout (unified on `main`, Nov 2026):

- `app.py` — the single Streamlit console (:8501). Routes mission-control pages (`mission_control/pages/`) and research pages (`research/app/`) via `st.navigation`. It stays at the repo root because `st.Page` paths resolve from the main script's folder.
- `ui/` — shared theme (`ui/theme.py`, imported by both sides) and the overview page (`ui/overview.py`).
- `mission_control/` — the active, local-first live stack (a package; see `mission_control/README.md`).
- `research/` — studies, preregistrations, results, papers (see `research/README.md`).
- `docs/` — the GitHub Pages site (deployed from `main:/docs`). Only website files go here. `story/` is the Vercel site.
- `materials/` — handouts, deck, college report and their builder scripts (not served).
- `legacy/aws/` — the old Lambda + SNS + DynamoDB design (`lambda_function.py`, `cloud_dashboard.py`, `TECHNICAL_SPEC.md`, its own `config.py`). The devcontainer still boots it. Don't assume `TECHNICAL_SPEC.md` describes the current system.

## How to run

1. Ensure Memurai (Redis for Windows) is running on `127.0.0.1:6379`.
2. `pip install -r requirements.txt -r requirements-research.txt` (research versions are pinned; Python 3.13).
3. `python -m mission_control.demo` (or double-click `DEMO.bat`) — boots physics engine → streamer (ws :8765) → consensus engine → `streamlit run app.py` (:8501), all from the repo root. `python -m mission_control.boot_os` does the same with plain output. Ctrl+C stops everything.
4. Research viewer: `python -m research.launch` (or `launch_research.bat`), port 8502.

Always run modules from the repo root with `-m`. Mission-control code uses package imports (`from mission_control.config import get_redis_client`).

## Architecture / key files

- `mission_control/physics_engine.py` — propagates orbits from `mission_control/data/satellites.txt` (TLEs) via `sgp4`, generates telemetry, writes satellite state into Redis.
- `mission_control/consensus_engine.py` — elects plane leaders, runs CNP auctions for missions in `MISSIONS_LEDGER`, forms/rolls enclaves, logs forensics to `AUCTION_LOGS`.
- `mission_control/streamer.py` — websocket server (`ws://localhost:8765`) broadcasting Redis state to the globe.
- `mission_control/scoring_engine.py`, `hal_simulator.py`, `scenario_engine.py`, `config.py` — scoring maths, mock hardware telemetry, scenario definitions, shared constants + Redis client factory.
- `mission_control/globe/index.html` — Three.js globe, connects to `ws://localhost:8765`.
- `mission_control/pages/1_visualization.py`, `2_ground_station.py`, `3_under_the_hood.py` — Operations pages.

**Redis is the integration bus.** Components don't call each other directly. They communicate only through Redis keys (`STARLINK-<id>`, `MISSIONS_LEDGER`, `AUCTION_LOGS`, `TIME_MULTIPLIER`/`CHRONOS_MULTIPLIER`, `TRIGGER_CHAOS`, `CURRENT_MISSION`, `CURRENT_SUN_LON`, `SCORING_WEIGHTS`). This lets each process crash/restart independently. Preserve this decoupling: don't introduce direct imports/calls between the engines and the Streamlit pages.

## Known pitfalls

- **Streamlit rerun ordering**: in `mission_control/pages/3_under_the_hood.py`, the auto-refresh `time.sleep(4); st.rerun()` call must stay at the very bottom of the script, after all `st.tabs(...)` blocks render. Calling `st.rerun()` earlier silently breaks rendering of later tabs. If you touch this file, keep the refresh logic at the bottom.
- **Encoding fragility on Windows**: PowerShell's `Set-Content` has repeatedly corrupted UTF-8 emoji characters in `mission_control/pages/3_under_the_hood.py` and the emoji-named `research/app/pages/*`. Prefer the Edit tool (or Python with `encoding="utf-8"`) over `Set-Content`.
- `mission_control/pages/1_visualization.py` re-reads `globe/index.html` from disk on every page load and injects a cache-busting timestamp comment to defeat Streamlit's iframe caching. Don't remove this without replacing the cache-busting mechanism.
- `docs/` is public (GitHub Pages) and the repo is public. Don't put private documents there.
- Paper numbers: `research/figures/paper_main.py` and `phase4_numbers.py` write to `research/papers/main/generated/`; run `python research/papers/sync_generated.py` to copy them into `research/papers/jaa/generated/`.

## Testing

`pytest research/` (97 tests). Mission control has the `assert`-based self-test `python -m mission_control.scoring_engine`.

## Security

`.env` holds AWS credentials and is gitignored. Never commit it, and don't echo its contents into chat or commits.

## Research rules (research/)

- All new work lives in `research/`. It must NOT import redis, streamlit, websockets, or any live-stack module. Exception: the read-only viewer pages in `research/app/` use streamlit and the shared `ui.theme`; experiment and analysis code must stay free of them.
- Every experiment is a script in `research/experiments/` that takes `--seed` and `--n-events`, and writes JSON/CSV to `research/results/`. Nothing is hand-edited.
  Exception (branch `research/sat-anomaly`, `research/anomaly/`): detectors run over real
  catalog data, so they take `--start/--end/--tiers` instead (plus `--seed` wherever they sample).
  Source data must be original (Space-Track gp_history, CelesTrak/GCAT, GFZ), never synthetic,
  except in tests.
- NEVER fabricate, estimate, or hardcode result numbers. Tables and figures are generated only from files in `research/results/`.
- Strategies B0, B1, B2, B3, P, O must receive identical events, orbits, budgets and contact schedules for a given seed.
- Tune hyperparameters on the validation seeds only. Test seeds are untouched until `research/PREREGISTRATION.md` is committed.
- Each phase ends with passing tests (`pytest research/`) and a commit.
- If something in the design is ambiguous or physically questionable, stop and ask rather than guessing.