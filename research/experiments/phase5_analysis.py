"""Analysis for research/PREREGISTRATION_V2.md (Phases 4+5 combined, second
look at the test split). Per seed:
  H1-H3: exactly as Phase 3 (phase3_analysis.analyze_run) on the primary arm.
  H4: AUROC(primary) - AUROC(r@5, Phase 3 config) > 0  (paired bootstrap).
  H5: P accuracy on modeled events non-inferior to B3: lower CI of (P - B3) > -0.05.
  Reported: the same AUROC difference vs r@10 (data-volume control).

Usage:
  python -m research.experiments.phase5_analysis --seeds 1 2 3 \
      --primary research/results/phase5/test_seed{S}_final_gr5_k0.5 \
      --ref research/results/phase5/test_seed{S}_final_r5 --r10 research/results/phase5/test_seed{S}_final_r10 \
      --out research/results/phase5/analysis_test_v2.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from research.experiments.metrics import auroc
from research.experiments.phase3_analysis import BOOT_SEED, N_BOOT, analyze_run
from research.util import atomic_write_json

ACC_MARGIN = 0.05


def _load(d: Path) -> dict:
    return {r["oid"]: r for r in (json.loads(l) for l in open(d / "events.jsonl", encoding="utf-8"))}


def paired(primary: Path, ref: Path) -> dict:
    a, b = _load(primary), _load(ref)
    common = sorted(set(a) & set(b))
    w = np.array([a[o]["withheld"] for o in common])
    wi, mi = np.flatnonzero(w), np.flatnonzero(~w)
    pa = np.array([a[o]["strategies"]["P_open_world_eig"]["p_h0_final"] for o in common])
    pb = np.array([b[o]["strategies"]["P_open_world_eig"]["p_h0_final"] for o in common])
    accP = np.array([a[o]["strategies"]["P_open_world_eig"]["correct"] for o in common], dtype=float)
    accB3 = np.array([a[o]["strategies"]["B3_closed_world_eig"]["correct"] for o in common], dtype=float)
    rng = np.random.default_rng(BOOT_SEED)
    d_auc, d_acc = [], []
    for _ in range(N_BOOT):
        bw, bm = rng.choice(wi, len(wi)), rng.choice(mi, len(mi))
        d_auc.append(auroc(pa[bw], pa[bm]) - auroc(pb[bw], pb[bm]))
        d_acc.append(accP[bm].mean() - accB3[bm].mean())
    ci = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]
    return {"n_common": len(common),
            "auroc_diff": {"estimate": auroc(pa[wi], pa[mi]) - auroc(pb[wi], pb[mi]), "ci95": ci(d_auc)},
            "acc_modeled_P_minus_B3": {"estimate": float(accP[mi].mean() - accB3[mi].mean()), "ci95": ci(d_acc)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    ap.add_argument("--primary", required=True, help="path template with {S}")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--r10", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    runs = []
    for s in args.seeds:
        prim = Path(args.primary.format(S=s))
        base = analyze_run(prim)
        vs_r5 = paired(prim, Path(args.ref.format(S=s)))
        vs_r10 = paired(prim, Path(args.r10.format(S=s)))
        h4 = {**vs_r5["auroc_diff"], "pass": vs_r5["auroc_diff"]["ci95"][0] > 0}
        h5 = {**vs_r5["acc_modeled_P_minus_B3"], "margin": ACC_MARGIN,
              "pass": vs_r5["acc_modeled_P_minus_B3"]["ci95"][0] > -ACC_MARGIN}
        runs.append({**base, "seed": s, "H4_auroc_vs_r5": h4, "H5_acc_modeled_P_vs_B3": h5,
                     "reported_auroc_vs_r10": vs_r10["auroc_diff"]})
    keys = {"H1": "H1_P_vs_B3_confident_wrong_withheld", "H2": "H2_auroc_p_h0",
            "H3": "H3_P_vs_B3_confident_wrong_modeled", "H4": "H4_auroc_vs_r5", "H5": "H5_acc_modeled_P_vs_B3"}
    overall = {h: all(r[k]["pass"] for r in runs) for h, k in keys.items()}
    atomic_write_json(args.out, {"overall_pass_all_seeds": overall, "runs": runs, "n_boot": N_BOOT, "boot_seed": BOOT_SEED})
    for r in runs:
        print(f"seed {r['seed']}:")
        for h, k in keys.items():
            print(f"  {h} {r[k]['estimate']:.3f} CI {np.round(r[k]['ci95'], 3).tolist()} pass={r[k]['pass']}")
        print(f"  (reported) AUROC diff vs r@10 {r['reported_auroc_vs_r10']['estimate']:.3f} "
              f"CI {np.round(r['reported_auroc_vs_r10']['ci95'], 3).tolist()}")
    print("overall:", overall)


if __name__ == "__main__":
    main()
