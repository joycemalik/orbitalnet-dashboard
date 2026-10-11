"""Phase 4: paired comparison of arms run on the SAME events (e.g. gr@5 vs
r@5 vs r@10). For each arm and strategy: AUROC of P(h0), confident-wrong
and accuracy on modeled/withheld, h0 false-alarm rate; and paired
event-level bootstrap CIs for (arm - reference) differences.

Usage:
  python -m research.experiments.phase4_compare --ref research/results/phase4/validation_seed1_r5_l5 \
      --arms research/results/phase4/validation_seed1_gr5_l5 research/results/phase4/validation_seed1_r10_l5 \
      --out research/results/phase4/compare_validation.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from research.experiments.metrics import auroc
from research.util import atomic_write_json

N_BOOT = 10_000
BOOT_SEED = 20261012
STRATS = ("B0_fixed_cadence", "B1_cnp_reimplementation", "B2_classifier_entropy", "B3_closed_world_eig", "P_open_world_eig")


def load(run_dir: Path) -> dict[str, dict]:
    return {r["oid"]: r for r in (json.loads(l) for l in open(run_dir / "events.jsonl", encoding="utf-8"))}


def metrics(recs: list[dict], strat: str, wi: np.ndarray, mi: np.ndarray) -> dict:
    s = [r["strategies"][strat] for r in recs]
    cw = np.array([x["confident_wrong"] for x in s], dtype=float)
    ok = np.array([x["correct"] for x in s], dtype=float)
    out = {"cw_withheld": cw[wi].mean(), "cw_modeled": cw[mi].mean(),
           "acc_withheld": ok[wi].mean(), "acc_modeled": ok[mi].mean()}
    if strat == "P_open_world_eig":
        p = np.array([x["p_h0_final"] for x in s], dtype=float)
        h0 = np.array([x["decision"] == "h0" for x in s], dtype=float)
        out["auroc"] = auroc(p[wi], p[mi])
        out["h0_false_alarm"] = h0[mi].mean()
    return {k: float(v) for k, v in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ref = load(Path(args.ref))
    arms = {a: load(Path(a)) for a in args.arms}
    common = sorted(set(ref).intersection(*[set(v) for v in arms.values()]))
    withheld = np.array([ref[o]["withheld"] for o in common])
    wi, mi = np.flatnonzero(withheld), np.flatnonzero(~withheld)
    ref_recs = [ref[o] for o in common]

    result = {"ref": args.ref, "n_common": len(common), "n_withheld": int(len(wi)), "n_modeled": int(len(mi)),
              "arms": {args.ref: {s: metrics(ref_recs, s, wi, mi) for s in STRATS}}, "diff_vs_ref_P": {}}
    rng = np.random.default_rng(BOOT_SEED)
    boots = [(rng.choice(wi, len(wi)), rng.choice(mi, len(mi))) for _ in range(N_BOOT)]
    for a, recs_by_oid in arms.items():
        recs = [recs_by_oid[o] for o in common]
        result["arms"][a] = {s: metrics(recs, s, wi, mi) for s in STRATS}
        point = {k: result["arms"][a]["P_open_world_eig"][k] - result["arms"][args.ref]["P_open_world_eig"][k]
                 for k in result["arms"][a]["P_open_world_eig"]}
        samples = {k: [] for k in point}
        for bw, bm in boots:
            ma = metrics(recs, "P_open_world_eig", bw, bm)
            mr = metrics(ref_recs, "P_open_world_eig", bw, bm)
            for k in samples:
                samples[k].append(ma[k] - mr[k])
        result["diff_vs_ref_P"][a] = {k: {"estimate": point[k],
                                          "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]}
                                      for k, v in samples.items()}

    atomic_write_json(args.out, result)
    print(f"common events: {len(common)} ({len(wi)} withheld)")
    for a, d in result["arms"].items():
        P = d["P_open_world_eig"]
        print(f"{Path(a).name:32} P: auroc {P['auroc']:.3f} cw_wh {P['cw_withheld']:.3f} cw_mod {P['cw_modeled']:.3f} "
              f"acc_mod {P['acc_modeled']:.3f} acc_wh {P['acc_withheld']:.3f} h0FA {P['h0_false_alarm']:.3f} | "
              f"B3 cw_wh {d['B3_closed_world_eig']['cw_withheld']:.3f} acc_mod {d['B3_closed_world_eig']['acc_modeled']:.3f}")
    for a, d in result["diff_vs_ref_P"].items():
        print(Path(a).name, "- ref:", {k: (round(v["estimate"], 3), [round(x, 3) for x in v["ci95"]]) for k, v in d.items()})


if __name__ == "__main__":
    main()
