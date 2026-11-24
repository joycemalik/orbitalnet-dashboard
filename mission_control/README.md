# mission_control/: the live constellation simulator

Real satellites, real orbits, and a market for tasks. Every satellite in `data/satellites.txt` is
propagated with SGP4, and when a mission comes in, the satellites bid for it in a Contract Net
auction. The browser globe shows all of it live.

## Run
From the repo root, with Memurai (Redis) running on `127.0.0.1:6379`:
```
python -m mission_control.demo      # everything + console on :8501, opens the browser (same as DEMO.bat)
python -m mission_control.boot_os   # same stack, plain console output
```
Each process can also run on its own, e.g. `python -m mission_control.physics_engine`.

## Processes
| Module | Job |
|---|---|
| `physics_engine.py` | propagates the fleet with SGP4, adds mock hardware telemetry (`hal_simulator.py`), and writes each satellite's state to Redis every tick |
| `consensus_engine.py` | elects a leader per orbital plane, runs CNP auctions for missions in the ledger, forms and rolls enclaves, and logs every auction |
| `streamer.py` | websocket server on `ws://localhost:8765` that pushes Redis state to the globe |
| `scoring_engine.py` | the bid scoring maths (`python -m mission_control.scoring_engine` runs its self-test) |
| `scenario_engine.py` | ready-made mission scenarios for the dispatch page |
| `config.py` | shared constants and the Redis client factory |
| `pages/` | the three Operations pages shown in the console (Orbital View, Mission Dispatch, Auction Internals) |
| `globe/index.html` | the Three.js globe, re-read on every page load with a cache-busting stamp |
| `fix_encoding.py` | one-off repair for emoji mojibake in `pages/3_under_the_hood.py` |

## Redis is the bus
The processes never call each other. They only read and write these keys, so any one of them can
restart on its own:

| Key | Written by | Meaning |
|---|---|---|
| `STARLINK-<id>` | physics engine | one satellite's position, battery, hardware and status |
| `MISSIONS_LEDGER` | dispatch page, consensus engine | missions and their auction state |
| `AUCTION_LOGS` | consensus engine | auction history used by Auction Internals |
| `TIME_MULTIPLIER` / `CHRONOS_MULTIPLIER` | dispatch page / physics engine | simulation speed |
| `TRIGGER_CHAOS` | dispatch page | injects failures to test re-auctioning |
| `CURRENT_MISSION`, `CURRENT_SUN_LON` | streamer | what the globe highlights, and the day/night line |
| `SCORING_WEIGHTS` | Auction Internals page | live weights for the bid score |

Keep this decoupling. Don't add direct imports between the engines and the pages, and don't import
any of this from `research/`.
