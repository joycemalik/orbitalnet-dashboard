"""research/app/viewer.py — read-only results viewer for the open-world
planner research track.

This app ONLY reads files under research/results/ and renders them. It never
computes, estimates, or hardcodes a result number. It does not import redis,
websockets, or any live-stack module, and it runs on its own Streamlit port
(separate from the live OrbitalNet OS app in app.py / pages/).
"""

from __future__ import annotations

import streamlit as st

from research.app.data import (
    list_scenarios_with_results,
    load_phase_summary,
    load_progress,
    load_scenario_summary,
    load_worked_example,
)
from research.app.plotting import (
    existence_proof_figure,
    strategy_comparison_figure,
    time_to_identification_figure,
    worked_example_figure,
)

st.set_page_config(page_title="Open-World Planner Research Viewer", layout="wide")

st.title("Open-World Sequential Measurement Planner — Results Viewer")
st.caption("Reads only from research/results/. Never computes a result number. "
           "👈 Try the 🔭 Event Lab in the sidebar to inject your own space event.")

progress = load_progress()
if progress:
    status = progress.get("status", "unknown")
    if status == "running":
        st.info(
            f"Running: {progress.get('phase')} ({progress.get('mode')}) — "
            f"{progress.get('events_done')}/{progress.get('n_events')} events "
            f"(seed {progress.get('seed')})"
        )
    else:
        st.success(
            f"Last run finished: {progress.get('phase')} ({progress.get('mode')}), "
            f"{progress.get('events_done')}/{progress.get('n_events')} events (seed {progress.get('seed')})"
        )
else:
    st.caption("No experiment has been run yet in this results directory.")


def provenance_line(summary: dict) -> None:
    cfg = summary["config"]
    st.caption(
        f"seed={cfg['seed']} | git_commit={summary['git_commit'][:12]} | "
        f"config_hash={summary['config_hash']} | tag={cfg.get('tag', '?')} | "
        f"n_events={cfg['n_events']} | generated_at={summary['generated_at']}"
    )
    if cfg.get("tag") == "demo":
        st.warning("DEMO run (small n_events) — not a statistically powered result.")


tabs = st.tabs([
    "Existence proof",
    "Worked example",
    "Strategy comparison",
    "Ablations",
    "Decentralization",
    "Hardware testbed",
])

with tabs[0]:
    st.header("Phase 1 — Existence proof")
    summary = load_phase_summary("phase1")
    if summary is None:
        st.info("Not run yet. Run Phase 1 (`python -m research.experiments.phase1_existence_proof ...`).")
    else:
        provenance_line(summary)
        st.pyplot(existence_proof_figure(summary))
        st.subheader("Confident-wrong rates by strategy")
        rows = []
        for name, stats in summary["strategies"].items():
            rows.append({
                "strategy": name,
                "confident_wrong (modeled truth)": stats["confident_wrong_rate_modeled"],
                "confident_wrong (withheld truth)": stats["confident_wrong_rate_withheld"],
                "accuracy (modeled truth)": stats["accuracy_modeled"],
                "accuracy (withheld truth, h0 credited)": stats["accuracy_withheld"],
                "n_events": stats["n_events"],
            })
        st.dataframe(rows, use_container_width=True)

with tabs[1]:
    st.header("Worked example")
    worked = load_worked_example("phase1")
    if worked is None or not worked.get("examples"):
        st.info("Not run yet.")
    else:
        st.caption(
            f"config_hash={worked['config_hash']} | git_commit={worked['git_commit'][:12]} | "
            "Phase 1 has no orbits yet, so no spacecraft/instrument is annotated here — "
            "that detail arrives with Phase 2."
        )
        true_class = st.selectbox("True class", sorted(worked["examples"].keys()))
        example = worked["examples"][true_class]
        st.pyplot(worked_example_figure(example))
        st.json(example["final_posterior"])

with tabs[2]:
    st.header("Strategy comparison")
    scenarios = list_scenarios_with_results("phase2")
    if not scenarios:
        st.info("Not run yet — this fills in after Phase 2 (single-planner experiment with orbits).")
    else:
        scenario = st.selectbox("Scenario", scenarios)
        scenario_result = load_scenario_summary("phase2", scenario)
        import json as _json, os as _os
        import pandas as _pd
        from research.app.data import RESULTS_DIR as _RD
        _cfg_path = _os.path.join(_RD, "phase2", scenario, "config.json")
        cfg = _json.load(open(_cfg_path)) if _os.path.exists(_cfg_path) else {}
        st.caption(
            f"split={cfg.get('split', '?')} | seed={cfg.get('seed', '?')} | n_events={scenario_result.get('n_events', '?')} | "
            f"git_commit={str(scenario_result.get('git_commit', '?'))[:12]} | config_hash={scenario_result.get('config_hash', '?')} | "
            f"generated_at={scenario_result.get('generated_at', '?')}"
        )
        if isinstance(cfg.get("scenario_cfg"), dict) and cfg["scenario_cfg"].get("description"):
            st.caption(cfg["scenario_cfg"]["description"])
        per_strategy = scenario_result.get("summary", {})
        per_strategy = per_strategy.get("strategies", per_strategy)
        st.subheader("Metrics by strategy (B0-B3 = baselines, P = open-world planner)")
        df = _pd.DataFrame(per_strategy).T
        df = df[[c for c in df.columns if df[c].map(lambda v: isinstance(v, (int, float))).all()]]
        st.dataframe(df, use_container_width=True)
        for col in ("accuracy_modeled", "confident_wrong_rate_withheld", "fraction_identified"):
            if col in df.columns:
                st.bar_chart(df[col].astype(float), horizontal=True, y_label=col)

with tabs[3]:
    st.header("Ablations")
    st.info("Ablation and later-phase results are on the 📊 Scorecard page (sidebar).")

with tabs[4]:
    st.header("Decentralization")
    st.info("Phase 4–6 results are on the 📊 Scorecard page (sidebar).")

with tabs[5]:
    st.header("Hardware testbed")
    st.info(
        "Phase 6 is design-only until Phases 1-4 pass their acceptance criteria. "
        "No firmware results will ever appear here automatically — this tab is a "
        "placeholder for design notes, not pending experiment output."
    )
