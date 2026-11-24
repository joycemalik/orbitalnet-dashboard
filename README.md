# OrbitalNet OS

[![Website](https://img.shields.io/badge/Website-orbitalnet.joycemalik.com-8a1430?style=for-the-badge)](https://orbitalnet.joycemalik.com/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-console-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)

OrbitalNet is two things that grew together. The first is **mission control**: a live simulator where
10,000+ real satellites (propagated from real TLEs) bid for ground-station tasks in an auction and
show up on a 3D globe. The second is **the research** that came out of it: how a fleet of spacecraft
should decide what to measure next when a new transient appears, including the case where the
object is something nobody has a model for.

Both live in this repo, and both open in one console.

## Quick start
You need Python 3.13 and, for the live simulator, [Memurai](https://www.memurai.com/) (Redis for Windows) running on `127.0.0.1:6379`.

```
pip install -r requirements.txt -r requirements-research.txt
```

| What you want | How |
|---|---|
| Mission control + research pages, one console | double-click **`DEMO.bat`** (or `python -m mission_control.demo`), then open http://localhost:8501 |
| Research viewer with a live experiment run | double-click **`launch_research.bat`** (or `python -m research.launch`), port 8502 |
| Run the research tests | `pytest research/` |

The console has two sections. **Operations** has the Orbital View, Mission Dispatch and Auction Internals,
all fed live from the simulator. **Discovery** has the Event Lab, Evidence, Experiment Archive and
Anomaly Watch, which read the committed research results, so they work even when the simulator is off.

## What is where
```
app.py                 the console (Streamlit, :8501): routes mission control + research pages
ui/                    shared theme and the overview page
mission_control/       the live constellation simulator (see mission_control/README.md)
research/              studies, preregistrations, results, papers (see research/README.md)
docs/                  the public website (GitHub Pages)
story/                 the film / notebook site (Vercel)
materials/             handouts, deck, college report, figure builders
legacy/aws/            the original AWS Lambda + SNS + DynamoDB version, kept for reference
```

## How mission control works
Each part is its own process, and they talk only through Redis, so any one of them can crash or
restart without taking the others down.

```
satellites.txt (TLEs) → physics_engine ─┐
                                        ├─ Redis ─→ streamer (ws :8765) → 3D globe
              consensus_engine ─────────┤
   (leader election, CNP auctions)      └─→ console pages (:8501)
```
The physics engine propagates every satellite with SGP4 and writes its state. The consensus engine
elects a leader per orbital plane and runs Contract Net auctions for missions in the ledger. The
streamer pushes the state to the browser globe. Details and the Redis key list are in
[`mission_control/README.md`](mission_control/README.md).

## What the research found
The question is simple to state. When a new transient appears, which measurement should the
fleet take next, and how does it notice that the object fits none of its models? We gave the planner
an explicit "none of the above" hypothesis, so it can say "unknown" instead of growing more
confident in a wrong class. Every study had its hypotheses committed before the test data were run.

| Study | What it showed | Verdict |
|---|---|---|
| Simulation, 8 real-orbit satellites | the open-world planner recognised 96% of never-seen classes at 5% false alarm, against 21% for the usual approach | 2 of 3 hypotheses pass |
| Real ZTF transients | confidently wrong on 7–14% of real unknowns, against 50–56% | 4 of 5 pass |
| Conformal "unknown" rule | a certified false-alarm rate on sealed real supernovae (3–6%, bound 10%) | 5 of 6 pass |
| Fleet with inter-satellite links | perfect links add about 10 points of accuracy, but realistic links did not help with the tuned settings | 5 of 6 pass |
| Fleet follow-up (4b) | links do help at equal spending, and where satellites sit matters more than the links | 5 of 5 pass |
| Anytime-valid e-process on real data | 3.3–4.3% false "unknown" on sealed supernovae, 26–31% of real unknowns caught, no calibration data | 2 of 2 pass |
| Storm drag atlas (catalogue data) | geomagnetic storms measurably lower debris orbits, replicated in Oct 2024 | 3 of 4, then 4 of 6 |

The failures are reported with the same weight as the passes. Every number in the papers comes from
`research/results/`, so nothing is typed by hand. The full index (preregistration → script → results →
verdict) is in [`research/README.md`](research/README.md), and the reasoning is in [`research/LOG.md`](research/LOG.md).

## Papers
- **JAA submission:** `research/papers/jaa/` ("Knowing What You Do Not Know: Open-World Follow-Up Planning for Fading Transients, from One Spacecraft to a Fleet")
- **Research note:** `research/papers/rnaas/`
- **Original proposal:** `research/papers/Hypothesis-Discriminating Observation Campaigns for Distributed Space Observatories.pdf`
- **Website:** [orbitalnet.joycemalik.com](https://orbitalnet.joycemalik.com/)

## Authors and licence
Joyce Malik, Anup H, Moghitha B and Swathi Sathish, Department of Computer Science and Engineering,
Dr. Ambedkar Institute of Technology, Bengaluru. Released under the [MIT License](LICENSE).
