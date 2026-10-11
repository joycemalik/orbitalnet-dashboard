# OrbitalNet OS (USOS) & Open-World Autonomous Space Observatory Research

[![GitHub Pages](https://img.shields.io/badge/Research_Paper-Live_Page-8a1430?style=for-the-badge&logo=github)](https://orbitalnet.joycemalik.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Three.js](https://img.shields.io/badge/Three.js-WebGL_3D_Globe-000000?style=for-the-badge&logo=three.js&logoColor=white)](https://threejs.org)

An autonomous constellation management framework and open-world Bayesian decision system for distributed space observatories. 

This repository contains both the **OrbitalNet OS** real-time simulation platform and the formal research implementation for **open-world hypothesis-discriminating observation campaigns**.

---

## 🌟 Research Paper & Web Publication

- **Website (film, paper, roadmap, notebook):** [https://orbitalnet.joycemalik.com/](https://orbitalnet.joycemalik.com/)
- **The film:** [https://orbitalnet.joycemalik.com/film/](https://orbitalnet.joycemalik.com/film/)
- **Paper page:** [https://orbitalnet.joycemalik.com/](https://orbitalnet.joycemalik.com/)
- **Manuscript PDF:** [`Hypothesis-Discriminating Observation Campaigns for Distributed Space Observatories.pdf`](./Hypothesis-Discriminating%20Observation%20Campaigns%20for%20Distributed%20Space%20Observatories.pdf)

### Paper Summary: *"Differential Diagnosis for the Sky"*
When rapid fading astronomical transients (e.g., kilonovae, GRB afterglows, M-dwarf flares, TDEs) appear, distributed satellite constellations must decide which targets to observe under strict power, orbital visibility, and inter-satellite communication constraints. Standard closed-world Bayesian planners force unexpected phenomena into known taxonomy classes. 

This research introduces an **Open-World Expected Information Gain (EIG)** planner featuring an explicitly modeled null hypothesis ($h_0$) using Gaussian Process residual modeling and active mode switching.

---

## 🚀 System Architecture

OrbitalNet OS features a microservices architecture integrated via Redis as a real-time state bus.

```
                    +-----------------------------+
                    |  Real-World TLE Dataset     |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    |  physics_engine.py          | (SGP4 Orbit Propagation & Telemetry)
                    +--------------+--------------+
                                   | Writes satellite positions & state
                                   v
                    +-----------------------------+
                    |      Redis / Memurai        | (Decoupled Integration Bus)
                    +--------------+--------------+
                      /            |            \
                     /             |             \
  +-----------------+   +----------+----------+   +------------------------+
  | streamer.py     |   | consensus_engine.py |   | Streamlit Dashboard    |
  | (WebSocket Server)  | (CNP Bidding & Leader)  | (app.py & Multipage UI)|
  +--------+--------+   +---------------------+   +------------------------+
           |
           v
  +-----------------+
  | index.html      | (Live 3D WebGL Globe Visualization)
  +-----------------+
```

---

## 💡 Key System Components

### 1. Primary Local-First Platform (`boot_os.py`)
- **`physics_engine.py`**: Reads live/historical TLE orbit data (`satellites.txt`), propagates satellite positions using `sgp4`, generates thermal/power state telemetry, and writes positions into Redis.
- **`consensus_engine.py`**: Conducts decentralized Contract Net Protocol (CNP) auctions across orbital planes to assign mission taskings dynamically to candidate satellites.
- **`streamer.py`**: Broadcasts real-time satellite orbital vectors and auction states over WebSockets (`ws://localhost:8765`) to the Three.js front-end.
- **`index.html`**: Interactive Three.js WebGL globe visualizing real-time satellite trajectories and ground station visibility cones.
- **`app.py` & `pages/`**: Multi-page Streamlit analytical dashboard (`1_visualization.py`, `2_ground_station.py`, `3_under_the_hood.py`).

### 2. Research & Open-World Planning Engine (`research/`)
- **Open-World EIG formulation**: Evaluates Expected Information Gain across candidate model classes while maintaining a nonparametric $h_0$ residual model.
- **Baselines & Strategies**: Evaluates fixed-cadence dispatcher ($B_0$), SNR heuristic ($B_1$), classifier entropy ($B_2$), closed-world EIG ($B_3$), and open-world EIG ($P$).
- **Reproducibility pipeline**: Pure Python experiments with seed control, synthetic scenario generators, and pre-registered validation protocols.

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.10+
- [Memurai](https://www.memurai.com/) (Redis for Windows) or standard Redis server running on `127.0.0.1:6379`.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/joycemalik/orbitalnet-dashboard.git
   cd orbitalnet-dashboard
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🏃 Execution

### Running the Live OrbitalNet Simulation
Launch all microservices and the Streamlit dashboard in sequence using `boot_os.py`:

```bash
python boot_os.py
```

This boots:
1. `physics_engine.py` (Orbit propagation & state generation)
2. `streamer.py` (WebSocket server on `ws://localhost:8765`)
3. `consensus_engine.py` (CNP auction engine)
4. Streamlit UI (Opens automatically at `http://localhost:8501`)

*Press `Ctrl+C` in the terminal to gracefully shutdown all services.*

### Running Research Experiments
To execute or inspect the open-world planner experiments:

```bash
# Run pytest research test suite
pytest research/

# Run single experiment scenario
python -m research.experiments.phase2_single_planner --seed 42 --n-events 100
```

---

## 📂 Repository Structure

```
├── app.py                      # Main Streamlit entrance
├── boot_os.py                  # Process orchestrator & launcher
├── config.py                   # System-wide parameters & Redis client factory
├── physics_engine.py           # SGP4 orbit propagator & state generator
├── consensus_engine.py         # Contract Net Protocol auction engine
├── streamer.py                 # WebSocket telemetry broadcaster
├── index.html                  # Live Three.js WebGL globe
├── scoring_engine.py           # Multi-attribute auction utility scoring
├── hal_simulator.py            # Hardware Abstraction Layer mock telemetry
├── scenario_engine.py          # Scenario execution triggers
├── docs/                       # Web publication & hosted research paper page
│   └── index.html              # Hosted GitHub Pages manuscript site
├── research/                   # Open-world hypothesis-discrimination research codebase
│   ├── experiments/            # Controlled experiment benchmarks
│   ├── planners/               # Bayesian & Open-World EIG decision algorithms
│   ├── transients/             # Astrophysical lightcurve models
│   └── PREREGISTRATION.md      # Experimental pre-registration protocol
├── CLAUDE.md                   # System developer guide & architecture notes
├── requirements.txt            # Python dependencies
└── Hypothesis-Discriminating...pdf # Manuscript document
```

---

## 📜 Citation & License

If you build upon or reference this work in academic research, please cite:

```bibtex
@article{malik2026hypothesis,
  title={Hypothesis-Discriminating Observation Campaigns for Distributed Space Observatories},
  author={Malik, Joyce and Contributors},
  journal={OrbitalNet OS Research Publications},
  year={2026},
  url={https://orbitalnet.joycemalik.com/}
}
```

Licensed under the [MIT License](LICENSE).
