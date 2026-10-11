"""Phase 3 analysis exactly as specified in research/PREREGISTRATION.md:
paired event-level bootstrap CIs for H1-H3 per run directory, plus the
reported-only metrics. Reads only files written by phase3_real_replay.py.

Usage:
  python -m research.experiments.phase3_analysis --runs research/results/phase3/test_seed1_final ... \
      --out research/results/phase3/analysis_test.json
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np

from research.experiments.metrics import auroc
from research.util import atomic_write_json

N_BOOT = 10_000
BOOT_SEED = 20261012
NONINFERIORITY_MARGIN = 0.05
STRATS = ("B0_fixed_cadence", "B1_cnp_reimplementation", "B2_classifier_entropy", "B3_closed_world_eig", "P_open_world_eig")


def _ci(x: np.ndarray) -> list[float]:
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def analyze_run(run_dir: Path) -> dict:
    recs = [json.loads(line) for line in open(run_dir / "events.jsonl", encoding="utf-8")]
    withheld = np.array([r["withheld"] for r in recs])
    cw = {s: np.array([r["strategies"][s]["confident_wrong"] for r in recs], dtype=float) for s in STRATS}
    correct = {s: np.array([r["strategies"][s]["correct"] for r in recs], dtype=float) for s in STRATS}
    p_h0 = np.array([r["strategies"]["P_open_world_eig"]["p_h0_final"] for r in recs], dtype=float)
    h0_decision = np.array([r["strategies"]["P_open_world_eig"]["decision"] == "h0" for r in recs], dtype=float)

    wi, mi = np.flatnonzero(withheld), np.flatnonzero(~withheld)
    rng = np.random.default_rng(BOOT_SEED)
    boot = {"h1_P_minus_B3": [], "h1_P_minus_B1": [], "h3_P_minus_B3": [], "auroc": []}
    for _ in range(N_BOOT):
        bw, bm = rng.choice(wi, len(wi)), rng.choice(mi, len(mi))  # stratified: keeps class balance
        boot["h1_P_minus_B3"].append(cw["P_open_world_eig"][bw].mean() - cw["B3_closed_world_eig"][bw].mean())
        boot["h1_P_minus_B1"].append(cw["P_open_world_eig"][bw].mean() - cw["B1_cnp_reimplementation"][bw].mean())
        boot["h3_P_minus_B3"].append(cw["P_open_world_eig"][bm].mean() - cw["B3_closed_world_eig"][bm].mean())
        boot["auroc"].append(auroc(p_h0[bw], p_h0[bm]))
    boot = {k: np.array(v) for k, v in boot.items()}

    h1 = {"estimate": float(cw["P_open_world_eig"][wi].mean() - cw["B3_closed_world_eig"][wi].mean()),
          "ci95": _ci(boot["h1_P_minus_B3"])}
    h1["pass"] = h1["ci95"][1] < 0
    h2 = {"estimate": auroc(p_h0[wi], p_h0[mi]), "ci95": _ci(boot["auroc"])}
    h2["pass"] = h2["ci95"][0] > 0.5
    h3 = {"estimate": float(cw["P_open_world_eig"][mi].mean() - cw["B3_closed_world_eig"][mi].mean()),
          "ci95": _ci(boot["h3_P_minus_B3"]), "margin": NONINFERIORITY_MARGIN}
    h3["pass"] = h3["ci95"][1] < NONINFERIORITY_MARGIN

    confusion = {s: {cls: dict(collections.Counter(r["strategies"][s]["decision"] for r in recs if r["true_class"] == cls))
                     for cls in sorted({r["true_class"] for r in recs})} for s in ("B1_cnp_reimplementation",
                                                                                     "B3_closed_world_eig", "P_open_world_eig")}
    return {
        "run_dir": run_dir.as_posix(), "n_events": len(recs), "n_withheld": int(len(wi)), "n_modeled": int(len(mi)),
        "H1_P_vs_B3_confident_wrong_withheld": h1,
        "H2_auroc_p_h0": h2,
        "H3_P_vs_B3_confident_wrong_modeled": h3,
        "reported": {
            "P_vs_B1_confident_wrong_withheld": {
                "estimate": float(cw["P_open_world_eig"][wi].mean() - cw["B1_cnp_reimplementation"][wi].mean()),
                "ci95": _ci(boot["h1_P_minus_B1"])},
            "confident_wrong_withheld": {s: float(cw[s][wi].mean()) for s in STRATS},
            "confident_wrong_modeled": {s: float(cw[s][mi].mean()) for s in STRATS},
            "accuracy_modeled": {s: float(correct[s][mi].mean()) for s in STRATS},
            "accuracy_withheld": {s: float(correct[s][wi].mean()) for s in STRATS},
            "P_h0_false_alarm_modeled": float(h0_decision[mi].mean()),
            "mean_log_score": {s: float(np.mean([r["strategies"][s]["log_score"] for r in recs])) for s in STRATS},
            "confusion": confusion,
            "exclusions": json.loads((run_dir / "exclusions.json").read_text())["loader"],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    per_run = [analyze_run(Path(d)) for d in args.runs]
    overall = {h: all(r[k]["pass"] for r in per_run) for h, k in (
        ("H1", "H1_P_vs_B3_confident_wrong_withheld"), ("H2", "H2_auroc_p_h0"), ("H3", "H3_P_vs_B3_confident_wrong_modeled"))}
    atomic_write_json(args.out, {"overall_pass_all_seeds": overall, "runs": per_run,
                                 "n_boot": N_BOOT, "boot_seed": BOOT_SEED})
    for r in per_run:
        print(r["run_dir"])
        for k in ("H1_P_vs_B3_confident_wrong_withheld", "H2_auroc_p_h0", "H3_P_vs_B3_confident_wrong_modeled"):
            print(f"  {k}: {r[k]['estimate']:.3f} CI {np.round(r[k]['ci95'], 3).tolist()} pass={r[k]['pass']}")
    print("overall:", overall)


if __name__ == "__main__":
    main()
