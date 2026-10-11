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
st.caption("Reads only from research/results/. Never computes a result number.")

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
        cfg = scenario_result["config"]
        st.caption(
            f"seed={scenario_result['seed']} | git_commit={scenario_result['git_commit'][:12]} | "
            f"config_hash={scenario_result['config_hash']} | tag={scenario_result.get('tag', '?')} | "
            f"generated_at={scenario_result['generated_at']}"
        )
        scenario_cfg = cfg["scenarios"][scenario]
        st.caption(scenario_cfg["description"])

        summary = scenario_result["summary"]
        st.pyplot(strategy_comparison_figure(summary))
        st.pyplot(time_to_identification_figure(summary))

        st.subheader("Metrics by strategy")
        rows = []
        for name, stats in summary["strategies"].items():
            row = {
                "strategy": name,
                "accuracy (modeled)": stats["accuracy_modeled"],
                "accuracy (withheld)": stats["accuracy_withheld"],
                "mean log score": stats["mean_log_score"],
                "mean time to ID": stats["mean_time_to_identification"],
                "never identified": stats["fraction_never_identified"],
                "mean instrument time": stats["mean_instrument_time"],
                "early amp error (fast)": stats["early_amp_error_fast"],
                "early amp error (slow)": stats["early_amp_error_slow"],
            }
            if "auroc_p_h0_withheld_vs_modeled" in stats:
                row["AUROC P(h0)"] = stats["auroc_p_h0_withheld_vs_modeled"]
            rows.append(row)
        st.dataframe(rows, use_container_width=True)

        st.subheader("Validity checks")
        nc = scenario_result["null_control"]
        hc = scenario_result["h0_calibration"]
        ngc = scenario_result["negative_control"]
        st.write(
            f"Null control (P vs B3 on modeled-only events): "
            f"{'PASSED' if nc['passed'] else 'FAILED'} (mean log-score diff={nc['mean_diff']:.4f}, "
            f"tolerance={nc['tolerance']})"
        )
        st.write(
            f"h0 calibration: threshold={hc['calibrated_threshold']:.4f} calibrated for target FPR="
            f"{hc['target_fpr']} on validation seed {hc['seed']}"
        )
        st.write(
            f"Negative control (test seed): observed FPR={ngc['observed_fpr']} vs target={ngc['target_fpr']} "
            f"(n={ngc['n_modeled_events']} modeled events)"
        )

with tabs[3]:
    st.header("Ablations")
    st.info("Not run yet — this fills in after Phase 3 (remove h0 / adequacy term / decay).")

with tabs[4]:
    st.header("Decentralization")
    st.info("Not run yet — this fills in after Phase 4 (per-spacecraft beliefs, contact-fraction sweep).")

with tabs[5]:
    st.header("Hardware testbed")
    st.info(
        "Phase 6 is design-only until Phases 1-4 pass their acceptance criteria. "
        "No firmware results will ever appear here automatically — this tab is a "
        "placeholder for design notes, not pending experiment output."
    )
