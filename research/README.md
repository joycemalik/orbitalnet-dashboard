# research/: open-world follow-up planning and satellite-catalogue studies

This package has the science side of OrbitalNet. It is pure Python and never imports Redis,
Streamlit internals of mission control, or any live-stack module, so every result can be
reproduced without the simulator running. The only shared input is the TLE catalogue in
`mission_control/data/satellites.txt`.

## Layout
| Folder | What it holds |
|---|---|
| `transients/` | class models and light curves (modelled and withheld classes) |
| `inference/` | open-world posterior with $h_0$, conformal rule, anytime-valid e-values |
| `planners/` | P (open-world EIG), baselines B0–B3, lookahead L, decentralised fleet planner |
| `orbitsim/` | SGP4 visibility, fleets, inter-satellite links |
| `anomaly/`, `atlas/` | satellite-catalogue tracks: manoeuvre/fragmentation detectors, storm drag atlas |
| `experiments/` | one script per study. Each takes `--seed` (and `--n-events`/`--n-episodes`, or `--start/--end` for catalogue data) |
| `results/` | every output JSON/CSV. Nothing in it is hand-edited |
| `figures/` | scripts that turn results into paper numbers, tables and figures |
| `papers/` | `jaa/` (journal submission), `main/` (generated numbers + shared sections), `rnaas/` (research note) |
| `app/` | read-only research pages shown inside the Streamlit console |
| `tests/` | `pytest research/` |
| `data/` | fetch scripts. Raw downloads are gitignored, and `manifest.json` keeps their checksums |

## Studies at a glance
Every study commits its hypotheses before the test data are run. The verdicts below are copied from
`LOG.md`, which has the numbers and the reasoning.

| Study | Preregistration | Script(s) | Results | Verdict |
|---|---|---|---|---|
| Phase 1, existence proof | (exploratory) | `phase1_existence_proof.py` | `results/phase1*` | demo only |
| Phase 2c, causal simulation (H1–H3) | `PREREGISTRATION_PHASE2.md` | `phase2_single_planner.py`, `phase2_analysis.py` | `results/phase2` | H1 refuted, H2 and H3 supported |
| Phase 6, causal real ZTF replay (H1–H5) | `PREREGISTRATION_V3.md` (earlier: `PREREGISTRATION.md`, `_V2.md`) | `phase3_real_replay.py`, `phase3_analysis.py`, `phase5_analysis.py` | `results/phase3`, `phase5`, `phase6` | H1–H4 pass, H5 fails narrowly |
| Phase C, conformal open-set + lookahead (HC1–HC6) | `PREREGISTRATION_C.md` | `phaseC_replay.py`, `phaseC_hypotheses.py` | `results/phaseC` | 5 of 6 pass |
| Phase 4, decentralised fleet (H4.1–H4.4, HE1–HE2) | `PREREGISTRATION_H4.md` | `phase4_decentralised.py`, `phase4_analysis.py`, `merge_shards.py` | `results/phase4_fleet` | 5 of 6 pass (H4.2 fails) |
| Phase 4b, replication, spending, geometry (B1–B5) | `PREREGISTRATION_H4B.md` | same as Phase 4 (`--fleet dense`) | `results/phase4_fleet/b_*` | 5 of 5 pass |
| Phase E, e-process on real ZTF (HR1–HR2) | `PREREGISTRATION_E.md` | `phaseE_real_evalues.py`, `phaseE_analysis.py` | `results/phaseE` | 2 of 2 pass |
| Storm drag atlas, May 2024 (HA1–HA4) | `atlas/PREREGISTRATION_ATLAS.md` | `atlas/` | `results/atlas` | 3 of 4 pass (HA4 fails) |
| Storm drag atlas, Oct 2024 replication | `atlas/PREREGISTRATION_ATLAS_R1.md` | `atlas/` | `results/atlas` | 4 of 6 pass (R-HA1, R-HA4 fail) |
| Anomaly hunt (manoeuvres, fragmentation) | `anomaly/PLAN.md` (no preregistration yet) | `anomaly_validation.py`, `anomaly/` | `results/anomaly` | in progress, held-out window not run |

## Reproduce
```
pip install -r requirements-research.txt     # Python 3.13; versions are pinned on purpose
pytest research/                             # 97 tests
python -m research.experiments.phase4_decentralised --split validation --seed 41 --n-episodes 100 --reserve 1
python research/figures/paper_main.py        # regenerate paper numbers, tables, figures
python research/figures/phase4_numbers.py
python research/papers/sync_generated.py     # copy them into the JAA manuscript
```
Test seeds are only run after the matching preregistration is committed. The scripts refuse otherwise.

## Rules
The working rules for this package (no live-stack imports, identical inputs across strategies,
validation-only tuning, no hand-typed numbers) are in the repo's `CLAUDE.md`.
