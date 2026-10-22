"""Phase 2c validation selection, by the rule declared in research/LOG.md
before the grid was run: maximize P's mean log score over all validation
events; ties within 0.02 -> smaller gamma, then GP lengthscale 1.2.

Usage:
  python -m research.experiments.phase2_select --glob "validation_S1_nominal_seed1_g*_l*" --out research/results/phase2/selection_validation.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.experiments.phase2_single_planner import RESULTS_DIR
from research.util import atomic_write_json

TIE = 0.02
DEFAULT_LENGTHSCALE = 1.2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rows = []
    for d in sorted(RESULTS_DIR.glob(args.glob)):
        cfg = json.loads((d / "config.json").read_text())
        s = json.loads((d / "summary.json").read_text())["summary"]
        p = s["P_open_world_eig"]
        rows.append({"run": d.name, "gamma": cfg["utility_gamma"], "gp_lengthscale": cfg["gp_lengthscale_days"],
                     "P_mean_log_score": p["mean_log_score"], "P_auroc_p_h0": p["auroc_p_h0"],
                     "P_accuracy_modeled": p["accuracy_modeled"],
                     "P_median_tti_days": p["median_time_to_id_days"],
                     "P_info_fast": p["mean_amp_info_fisher_fast"], "P_info_slow": p["mean_amp_info_fisher_slow"],
                     "P_no_decay_info_fast": s["P_no_decay"]["mean_amp_info_fisher_fast"],
                     "P_mean_obs_used": p["mean_obs_used"]})
    best = max(r["P_mean_log_score"] for r in rows)
    tied = [r for r in rows if r["P_mean_log_score"] >= best - TIE]
    chosen = min(tied, key=lambda r: (r["gamma"], abs(r["gp_lengthscale"] - DEFAULT_LENGTHSCALE)))
    atomic_write_json(Path(args.out), {"rule": "max P mean log score; ties within 0.02 -> smaller gamma, "
                                               "then lengthscale closest to 1.2", "rows": rows,
                                       "tied": [r["run"] for r in tied], "chosen": chosen})
    for r in sorted(rows, key=lambda r: -r["P_mean_log_score"]):
        print(f"{r['run']:45s} logS {r['P_mean_log_score']:.3f} auroc {r['P_auroc_p_h0']:.3f} "
              f"acc {r['P_accuracy_modeled']:.3f} tti {r['P_median_tti_days']} obs {r['P_mean_obs_used']:.2f} "
              f"info fast {r['P_info_fast']:.3f} (no-decay {r['P_no_decay_info_fast']:.3f})")
    print("chosen:", chosen["run"])


if __name__ == "__main__":
    main()
