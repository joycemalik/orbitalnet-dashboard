# Figures for the college report (orbitalnetos1.docx)

Insert each image under the caption of the same number already written in the report.

| File | Report caption | Source |
|---|---|---|
| `fig_4_1_system_architecture.png` | Fig 4.1 Overall system architecture of OrbitalNet OS | `make_diagrams.py` |
| `fig_4_2_use_case_diagram.png` | Fig 4.2 Use case diagram of OrbitalNet OS | `make_diagrams.py` |
| `fig_4_3_class_diagram_live_platform.png` | Fig 4.3 Class diagram (part 1): live platform | `make_diagrams.py` |
| `fig_4_4_class_diagram_research.png` | Fig 4.4 Class diagram (part 2): open-world planning and certification | `make_diagrams.py` |
| `fig_4_5_activity_diagram_auction_cycle.png` | Fig 4.5 Activity diagram of the auction cycle | `make_diagrams.py` |
| `fig_4_6_state_diagram_mission.png` | Fig 4.6 State diagram of a mission | `make_diagrams.py` |
| `fig_7_1_satellites_and_enclaves.png` | Fig 7.1 Satellites and enclaves after the four missions were awarded | `make_fig_7_1.py` (live Redis) |
| `fig_7_2_roc_unknown_verdict_ztf_test.png` | Fig 7.2 ROC for the "unknown" verdict on real ZTF transients (test, seed 1) | copy of `docs/figures/fig_roc_test.png` |
| `fig_7_3_openworld_planning_ZTF22abkfhua.png` | Fig 7.3 Open-world planning on one real transient | copy of `docs/figures/fig_example_test.png` |

## Screenshots (new, optional Figs 7.4-7.10)

Taken from the running system (`boot_os.py` + the four dispatched scenarios) by `take_screenshots.py`.

| File | Suggested caption |
|---|---|
| `screenshots/fig_7_4_overview_console.png` | Fig 7.4 Mission console overview with live telemetry |
| `screenshots/fig_7_5_orbital_view_globe.png` | Fig 7.5 Three.js globe showing the live fleet and mission status |
| `screenshots/fig_7_6_mission_dispatch.png` | Fig 7.6 Mission dispatch page of the ground station |
| `screenshots/fig_7_7_auction_internals.png` | Fig 7.7 Auction internals: executing missions and enclave members |
| `screenshots/fig_7_8_event_lab.png` | Fig 7.8 Event Lab: injecting a transient on the celestial sphere |
| `screenshots/fig_7_9_evidence.png` | Fig 7.9 Evidence page with the research results |
| `screenshots/fig_7_10_anomaly_watch.png` | Fig 7.10 Anomaly Watch page |

## Regenerate

```
python docs/report_figures/make_diagrams.py
python boot_os.py            # in another terminal; then dispatch the 4 scenarios
python docs/report_figures/make_fig_7_1.py
python docs/report_figures/take_screenshots.py
```
