"""Phase C analysis: apply the conformal open-set layer to phaseC_replay runs.

Every number comes from events.jsonl files written by phaseC_replay.py.
Thresholds are calibrated per strategy on KNOWN-class events of the
calibration run only, then applied unchanged to the evaluation run.

Decisions compared per strategy X:
  raw        X's native decision: closed-world argmax (baselines) or the
             open-world argmax including h0 (P, L)
  conformal  "h0" if s > tau (max rule), else closed-world argmax;
             confident iff not flagged and max closed posterior >= 0.95

Usage:
  python -m research.experiments.phaseC_analysis --cal DIR --eval DIR [--eval DIR ...] --out FILE
  python -m research.experiments.phaseC_analysis --crossfit DIR --out FILE     (validation development)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta as beta_dist

from research.experiments.metrics import auroc
from research.inference.conformal import class_conditional_threshold
from research.transients.real_events import MODELED_CLASSES
from research.util import atomic_write_json

CONFIDENT = 0.95
ALPHAS = (0.05, 0.1)
N_BOOT = 10000


def load(run_dir: str | Path) -> list[dict]:
    with open(Path(run_dir) / "events.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def strategy_names(records: list[dict]) -> list[str]:
    return list(records[0]["strategies"].keys())


def arrays(records: list[dict], name: str) -> dict:
    out = {"score": [], "closed_dec": [], "closed_max": [], "raw_dec": [], "raw_max": [], "n_obs": []}
    for r in records:
        s = r["strategies"][name]
        cp = s["closed_posterior"]
        raw = s["open_posterior"] if (name.startswith("P_") or name.startswith("L_")) else cp
        out["score"].append(s["score"])
        out["closed_dec"].append(max(cp, key=cp.get)); out["closed_max"].append(max(cp.values()))
        out["raw_dec"].append(max(raw, key=raw.get)); out["raw_max"].append(max(raw.values()))
        out["n_obs"].append(s["n_obs_used"])
    out = {k: np.array(v) for k, v in out.items()}
    out["true"] = np.array([r["true_class"] for r in records])
    out["withheld"] = np.array([r["withheld"] for r in records])
    return out


def outcomes(a: dict, tau: float | None) -> dict[str, np.ndarray]:
    """Per-event correct / confident-wrong / flagged for the raw (tau None)
    or conformal decision."""
    if tau is None:
        dec, conf = a["raw_dec"], a["raw_max"] >= CONFIDENT
    else:
        flagged = a["score"] > tau
        dec = np.where(flagged, "h0", a["closed_dec"])
        conf = ~flagged & (a["closed_max"] >= CONFIDENT)
    flagged = dec == "h0"
    correct = np.where(a["withheld"], flagged, dec == a["true"])
    return {"correct": correct, "confident_wrong": conf & ~correct, "flagged": flagged}


def clopper_pearson(k: int, n: int, level: float = 0.95) -> list[float | None]:
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else float(beta_dist.ppf((1 - level) / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta_dist.ppf(1 - (1 - level) / 2, k + 1, n - k))
    return [lo, hi]


def rate(x: np.ndarray, mask: np.ndarray) -> dict:
    k, n = int(np.sum(x[mask])), int(np.sum(mask))
    return {"rate": k / n if n else None, "k": k, "n": n, "ci95": clopper_pearson(k, n)}


def paired_bootstrap(diff_known: np.ndarray, diff_unknown: np.ndarray | None, which: str, seed: int = 0) -> dict:
    """Mean per-event difference on one stratum, 95% bootstrap CI."""
    d = diff_known if which == "known" else diff_unknown
    if d is None or len(d) == 0:
        return {"mean": None, "ci95": [None, None], "n": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(N_BOOT, len(d)))
    boots = d[idx].mean(axis=1)
    return {"mean": float(d.mean()), "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))],
            "n": int(len(d))}


def summarize(a: dict, tau: float | None) -> dict:
    o = outcomes(a, tau)
    known, unk = ~a["withheld"], a["withheld"]
    out = {
        "accuracy_known": rate(o["correct"], known),
        "confident_wrong_known": rate(o["confident_wrong"], known),
        "flag_rate_known": rate(o["flagged"], known),
        "flag_rate_per_class": {c: rate(o["flagged"], a["true"] == c) for c in MODELED_CLASSES},
        "mean_obs_used": float(np.mean(a["n_obs"])),
    }
    if unk.any():
        out["flag_rate_unknown"] = rate(o["flagged"], unk)
        out["confident_wrong_unknown"] = rate(o["confident_wrong"], unk)
    return out


def calibrate(cal_records: list[dict], name: str, alpha: float) -> tuple[float, dict]:
    a = arrays(cal_records, name)
    known = ~a["withheld"]
    tau, per = class_conditional_threshold(a["score"][known], a["true"][known], alpha, list(MODELED_CLASSES))
    return tau, {"tau": tau, "per_class_tau": per, "n_cal_per_class": {c: int(np.sum(a["true"][known] == c))
                                                                     for c in MODELED_CLASSES}}


def compare(a_x: dict, tau_x: float | None, a_ref: dict, tau_ref: float | None) -> dict:
    ox, orf = outcomes(a_x, tau_x), outcomes(a_ref, tau_ref)
    known, unk = ~a_x["withheld"], a_x["withheld"]
    out = {}
    for metric in ("correct", "confident_wrong"):
        d = ox[metric].astype(float) - orf[metric].astype(float)
        out[f"{metric}_known"] = paired_bootstrap(d[known], None, "known")
        if unk.any():
            out[f"{metric}_unknown"] = paired_bootstrap(None, d[unk], "unknown")
    return out


def evaluate(cal_records: list[dict], eval_records: list[dict]) -> dict:
    names = strategy_names(eval_records)
    res = {"n_eval": len(eval_records), "n_eval_unknown": int(sum(r["withheld"] for r in eval_records)),
           "auroc_score": {}, "raw": {}, "conformal": {}, "vs_B3_raw": {}}
    A = {n: arrays(eval_records, n) for n in names}
    for n in names:
        a = A[n]
        if a["withheld"].any():
            res["auroc_score"][n] = auroc(a["score"][a["withheld"]], a["score"][~a["withheld"]])
        res["raw"][n] = summarize(a, None)
    for alpha in ALPHAS:
        key = f"alpha_{alpha:g}"
        res["conformal"][key], res["vs_B3_raw"][key] = {}, {}
        for n in names:
            tau, cal_info = calibrate(cal_records, n, alpha)
            res["conformal"][key][n] = {**summarize(A[n], tau), "calibration": cal_info}
            res["vs_B3_raw"][key][n] = compare(A[n], tau, A["B3_closed_world_eig"], None)
    return res


def _fold(oid: str) -> int:
    return int(hashlib.sha256(oid.encode()).hexdigest(), 16) % 2


def crossfit(records: list[dict]) -> dict:
    """Development only: 2-fold hash split of KNOWN events; each fold is
    calibrated on the other; unknown events are evaluated under both
    calibrations (reported per fold, never pooled with each other)."""
    unknown = [r for r in records if r["withheld"]]
    out = {}
    for f in (0, 1):
        cal = [r for r in records if not r["withheld"] and _fold(r["oid"]) != f]
        ev = [r for r in records if not r["withheld"] and _fold(r["oid"]) == f] + unknown
        out[f"fold{f}"] = evaluate(cal, ev)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cal")
    ap.add_argument("--eval", nargs="*", default=[])
    ap.add_argument("--crossfit")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.crossfit:
        res = {"mode": "crossfit", "run": args.crossfit, **crossfit(load(args.crossfit))}
    else:
        cal = load(args.cal)
        res = {"mode": "calibrated", "cal": args.cal, "evals": {e: evaluate(cal, load(e)) for e in args.eval}}
    atomic_write_json(Path(args.out), res)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
