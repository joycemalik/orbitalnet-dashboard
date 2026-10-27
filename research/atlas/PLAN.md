# Plan: Whole-Catalog Storm Drag Atlas (+ unsupervised scan)

Track branch: `research/sat-atlas` (git worktree, forked from `research/sat-anomaly`).
Runs in its own worktree so it never collides with the discovery-hunt session.

## Idea
Tracked LEO objects are free density probes. Every non-maneuvering object's
orbital decay rate, relative to its own quiet-time decay rate, is a
self-normalised measurement of the thermospheric density ratio
rho(t)/rho_quiet at that altitude (ballistic coefficient and area cancel).
Measured for the whole catalogue at once, per altitude shell, this gives a
time-resolved map of how the upper atmosphere responded to a geomagnetic storm.

Event: the May 2024 "Gannon" storm (Kp 9, Dst < -400 nT). Window
2024-04-20 .. 2024-06-10, one `gp_history` query per UTC day for near-circular
LEO objects.

## Phases
1. Preregistration (`PREREGISTRATION_ATLAS.md`) committed BEFORE any catalogue data is fetched.
2. Fetch: `fetch_leo_days.py` (Space-Track, shared account; run only when the other
   session's fetch is idle, because the 300/hour limit is per account).
3. Analysis: `density_ratio.py` -> `research/results/atlas/` (CSV/JSON + figure).
4. Tests with synthetic injected density factors (`research/tests/test_atlas.py`).
5. Unsupervised scan (only after 1-4): flag objects whose decay response differs from
   shell peers; explain each flag; keep unexplained ones as candidates. Separate prereg.

## Rules (inherited from CLAUDE.md research rules)
No redis/streamlit/websockets imports; all numbers from files in `research/results/atlas/`;
raw Space-Track data is never committed (gitignored, licence); failed hypotheses are results.
