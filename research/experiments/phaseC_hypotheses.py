"""Phase C preregistered hypotheses HC1-HC6 (research/PREREGISTRATION_C.md).

For one noise seed S:
  calibration  = fresh_cal_seed{S}        (known classes only)
  sealed known = fresh_test_seed{S}       (HC1-HC3)
  real unknown = test_seed{S}             (HC4-HC6; declared extra look at the Phase 3 test split)

  python -m research.experiments.phaseC_hypotheses --cal DIR --fresh DIR --test DIR --out FILE
Dry run on validation: --cal/--fresh/--test may point at cross-fit halves via --dryrun DIR.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

from research.experiments.metrics import auroc
from research.experiments.phaseC_analysis import (arrays, calibrate, clopper_pearson, load, outcomes,
                                                  paired_bootstrap, summarize)
from research.transients.real_events import MODELED_CLASSES
from research.util import atomic_write_json

ALPHA = 0.1
PRIMARY = "L_lookahead_0.25"
P_NAME = "P_open_world_eig"
B3 = "B3_closed_world_eig"
N_BOOT = 10000


def auroc_diff_bootstrap(a1: dict, a2: dict, seed: int = 0) -> dict:
    """AUROC(a1.score) - AUROC(a2.score), paired, stratified bootstrap."""
    w = a1["withheld"]
    pos, neg = np.flatnonzero(w), np.flatnonzero(~w)
    d0 = auroc(a1["score"][pos], a1["score"][neg]) - auroc(a2["score"][pos], a2["score"][neg])
    rng = np.random.default_rng(seed)
    boots = np.empty(N_BOOT)
    for b in range(N_BOOT):
        p, n = rng.choice(pos, len(pos)), rng.choice(neg, len(neg))
        boots[b] = auroc(a1["score"][p], a1["score"][n]) - auroc(a2["score"][p], a2["score"][n])
    return {"mean": float(d0), "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))]}


def diff_known(eval_recs, x_name, tau_x, metric, ref=B3, stratum="known"):
    ax, ar = arrays(eval_recs, x_name), arrays(eval_recs, ref)
    d = outcomes(ax, tau_x)[metric].astype(float) - outcomes(ar, None)[metric].astype(float)
    mask = ~ax["withheld"] if stratum == "known" else ax["withheld"]
    return paired_bootstrap(d[mask], d[mask], stratum)


def evaluate(cal, fresh, test, primary: str = PRIMARY, alpha: float = ALPHA) -> dict:
    tau, cal_info = calibrate(cal, primary, alpha)
    af = arrays(fresh, primary)
    of = outcomes(af, tau)
    known = ~af["withheld"]
    hc1 = {"pooled": {"k": int(of["flagged"][known].sum()), "n": int(known.sum())}}
    hc1["pooled"]["rate"] = hc1["pooled"]["k"] / hc1["pooled"]["n"]
    hc1["pooled"]["ci95"] = clopper_pearson(hc1["pooled"]["k"], hc1["pooled"]["n"])
    for c in MODELED_CLASSES:
        m = af["true"] == c
        k, n = int(of["flagged"][m].sum()), int(m.sum())
        hc1[c] = {"k": k, "n": n, "rate": k / n if n else None, "ci95": clopper_pearson(k, n)}
    hc1["pass"] = all(v["ci95"][0] is not None and v["ci95"][0] <= alpha for v in hc1.values() if isinstance(v, dict))
    hc2 = diff_known(fresh, primary, tau, "correct")
    hc2["pass"] = hc2["ci95"][0] > -0.05
    hc3 = diff_known(fresh, primary, tau, "confident_wrong")
    hc3["pass"] = hc3["ci95"][1] < 0.05

    at = arrays(test, primary)
    ot = outcomes(at, tau)
    unk = at["withheld"]
    hc4 = diff_known(test, primary, tau, "confident_wrong", stratum="unknown")
    hc4["pass"] = hc4["ci95"][1] < 0
    k, n = int(ot["flagged"][unk].sum()), int(unk.sum())
    hc5 = {"k": k, "n": n, "rate": k / n, "ci95": clopper_pearson(k, n)}
    hc5["pass"] = hc5["ci95"][0] > alpha
    hc6 = auroc_diff_bootstrap(at, arrays(test, P_NAME))
    hc6["pass"] = hc6["ci95"][0] > 0

    reported = {
        "test_split_known_flag_rate": summarize(at, tau)["flag_rate_per_class"],
        "test_split_acc_known_vs_B3": diff_known(test, primary, tau, "correct"),
        "test_split_cw_known_vs_B3": diff_known(test, primary, tau, "confident_wrong"),
        "P_raw_false_unknown_fresh": summarize(arrays(fresh, P_NAME), None)["flag_rate_known"],
        "P_raw_false_unknown_test": summarize(arrays(test, P_NAME), None)["flag_rate_known"],
        "fresh_summary_conformal": summarize(af, tau),
        "test_summary_conformal": summarize(at, tau),
        "auroc_score_test": {n: auroc(arrays(test, n)["score"][unk], arrays(test, n)["score"][~unk])
                             for n in test[0]["strategies"]},
        "all_strategies_conformal_fresh_flag_known": {},
    }
    for n in fresh[0]["strategies"]:
        t_n, _ = calibrate(cal, n, alpha)
        reported["all_strategies_conformal_fresh_flag_known"][n] = summarize(arrays(fresh, n), t_n)["flag_rate_per_class"]
    return {"primary": primary, "alpha": alpha, "calibration": cal_info,
            "HC1": hc1, "HC2": hc2, "HC3": hc3, "HC4": hc4, "HC5": hc5, "HC6": hc6, "reported": reported}


def _fold(oid: str) -> int:
    return int(hashlib.sha256(oid.encode()).hexdigest(), 16) % 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cal"); ap.add_argument("--fresh"); ap.add_argument("--test")
    ap.add_argument("--dryrun", help="validation run dir: cal = known fold 0, fresh = known fold 1, test = all")
    ap.add_argument("--primary", default=PRIMARY)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.dryrun:
        recs = load(args.dryrun)
        cal = [r for r in recs if not r["withheld"] and _fold(r["oid"]) == 0]
        fresh = [r for r in recs if not r["withheld"] and _fold(r["oid"]) == 1]
        test = recs
        src = {"dryrun": args.dryrun}
    else:
        cal, fresh, test = load(args.cal), load(args.fresh), load(args.test)
        src = {"cal": args.cal, "fresh": args.fresh, "test": args.test}
    res = {**src, **evaluate(cal, fresh, test, args.primary)}
    atomic_write_json(Path(args.out), res)
    for h in ("HC1", "HC2", "HC3", "HC4", "HC5", "HC6"):
        v = res[h]
        print(h, "PASS" if v["pass"] else "FAIL", {k: v[k] for k in v if k in ("mean", "ci95", "rate")} or
              {c: (round(v[c]["rate"], 3), [round(x, 3) for x in v[c]["ci95"]]) for c in v if isinstance(v[c], dict)})


if __name__ == "__main__":
    main()
