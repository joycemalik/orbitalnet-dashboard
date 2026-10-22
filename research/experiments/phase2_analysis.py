"""Phase 2c analysis: manuscript H1-H3 on the causal simulation runs.

Pre-declared in research/PREREGISTRATION_PHASE2.md (this file is committed
with it, before any test seed is run). Reads only research/results/phase2/.

  H1 (discrimination): modeled events; per baseline B in {B0,B1,B2,B3},
     one-sided paired Wilcoxon signed-rank on time to identification
     (P < B; censored = never identified, ranked last), Holm over the four.
     Pass: every Holm-adjusted p < 0.05 AND median(P) < median(B).
  H2 (irreversibility): modeled events; d = info(P) - info(P_no_decay);
     statistic mean(d | fast) - mean(d | slow); stratified bootstrap 95% CI.
     Pass: CI entirely above 0.
  H3 (open world): all events; TPR at FPR = 0.05 of P's P(h0) minus that of
     the closed-world posterior entropy of B3 (the classifier-entropy
     threshold); paired stratified bootstrap 95% CI. Pass: CI above 0.

Usage:
  python -m research.experiments.phase2_analysis --runs <S1 dir> [<S2 dir> <S3 dir>] --out <json> --seed 0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

from research.experiments.metrics import auroc
from research.util import atomic_write_json

BASELINES = ("B0_fixed_cadence", "B1_cnp_reimplementation", "B2_classifier_entropy", "B3_closed_world_eig")
P, P_NO_DECAY, P_NO_ADEQ = "P_open_world_eig", "P_no_decay", "P_no_adequacy"
CENSORED = 1e6  # stands in for "never identified" in rank tests (larger than any candidate time)
TARGET_FPR = 0.05
N_BOOT = 10_000
ALPHA = 0.05


def load_records(run_dir: Path) -> list[dict]:
    with open(run_dir / "events.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    m = len(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, k in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[k]))
        adj[k] = running
    return adj.tolist()


def roc_curve(pos: np.ndarray, neg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(FPR, TPR) over every distinct threshold, score >= threshold = flagged."""
    scores = np.concatenate([pos, neg])
    is_pos = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))])
    order = np.argsort(-scores, kind="mergesort")
    s, lab = scores[order], is_pos[order]
    last_of_tie = np.r_[np.nonzero(np.diff(s))[0], len(s) - 1]
    tpr = np.r_[0.0, np.cumsum(lab)[last_of_tie] / len(pos)]
    fpr = np.r_[0.0, np.cumsum(1.0 - lab)[last_of_tie] / len(neg)]
    return fpr, tpr


def tpr_at_fpr(pos: np.ndarray, neg: np.ndarray, target: float = TARGET_FPR) -> float:
    fpr, tpr = roc_curve(pos, neg)
    return float(np.interp(target, fpr, tpr))


def _median_with_censoring(x: np.ndarray) -> float:
    return float(np.median(x))  # inf survives np.median if more than half are censored


def h1(records: list[dict]) -> dict:
    mod = [r for r in records if r["modeled"]]

    def tti(name):
        return np.array([np.inf if r["strategies"][name]["time_to_id_days"] is None
                         else r["strategies"][name]["time_to_id_days"] for r in mod])

    p = tti(P)
    out, pvals = {"n_modeled": len(mod), "median_P_days": _median_with_censoring(p),
                  "fraction_identified_P": float(np.mean(np.isfinite(p))), "per_baseline": {}}, []
    for b in BASELINES:
        q = tti(b)
        d = np.where(np.isfinite(p), p, CENSORED) - np.where(np.isfinite(q), q, CENSORED)
        nz = d[d != 0]
        if len(nz) == 0:
            pval, rbc = 1.0, 0.0
        else:
            pval = float(wilcoxon(nz, alternative="less", zero_method="wilcox").pvalue)
            ranks = np.argsort(np.argsort(np.abs(nz))) + 1.0
            rbc = float((ranks[nz < 0].sum() - ranks[nz > 0].sum()) / ranks.sum())  # >0 favours P
        pvals.append(pval)
        out["per_baseline"][b] = {
            "median_days": _median_with_censoring(q), "fraction_identified": float(np.mean(np.isfinite(q))),
            "p_faster": float(np.mean(d < 0)), "p_slower": float(np.mean(d > 0)),
            "wilcoxon_p_one_sided": pval, "rank_biserial": rbc,
        }
    for b, adj in zip(BASELINES, holm(pvals)):
        e = out["per_baseline"][b]
        e["holm_p"] = adj
        e["pass"] = bool(adj < ALPHA and out["median_P_days"] < e["median_days"])
    out["pass"] = all(e["pass"] for e in out["per_baseline"].values())
    obs = {n: float(np.mean([r["strategies"][n]["n_obs_used"] for r in mod])) for n in (P, *BASELINES)}
    out["mean_obs_used_modeled"] = obs
    return out


def _boot_mean_diff(rng, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ia = rng.integers(0, len(a), size=(N_BOOT, len(a)))
    ib = rng.integers(0, len(b), size=(N_BOOT, len(b)))
    return a[ia].mean(axis=1) - b[ib].mean(axis=1)


def _ci(x: np.ndarray) -> list[float]:
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def h2(records: list[dict], rng) -> dict:
    mod = [r for r in records if r["modeled"]]

    def delta(group, ablation=P_NO_DECAY, key="amp_info_fisher"):
        return np.array([r["strategies"][P][key] - r["strategies"][ablation][key]
                         for r in mod if r["speed_group"] == group])

    fast, slow = delta("fast"), delta("slow")
    boot = _boot_mean_diff(rng, fast, slow)
    est = float(fast.mean() - slow.mean())
    per_class = {}
    for c in sorted({r["true_class"] for r in mod}):
        d = np.array([r["strategies"][P]["amp_info_fisher"] - r["strategies"][P_NO_DECAY]["amp_info_fisher"]
                      for r in mod if r["true_class"] == c])
        per_class[c] = {"n": len(d), "mean_delta": float(d.mean())}
    grid_fast, grid_slow = delta("fast", key="amp_info_grid"), delta("slow", key="amp_info_grid")
    return {
        "n_fast": len(fast), "n_slow": len(slow),
        "mean_delta_fast": float(fast.mean()), "mean_delta_slow": float(slow.mean()),
        "ci_delta_fast": _ci(rng.choice(fast, size=(N_BOOT, len(fast))).mean(axis=1)),
        "ci_delta_slow": _ci(rng.choice(slow, size=(N_BOOT, len(slow))).mean(axis=1)),
        "estimate": est, "ci95": _ci(boot), "pass": bool(np.percentile(boot, 2.5) > 0),
        "per_class": per_class,
        "reported_grid_entropy_version": {"mean_delta_fast": float(grid_fast.mean()),
                                          "mean_delta_slow": float(grid_slow.mean())},
    }


def _scores(records, name, key):
    pos = np.array([r["strategies"][name][key] for r in records if not r["modeled"]], dtype=float)
    neg = np.array([r["strategies"][name][key] for r in records if r["modeled"]], dtype=float)
    return pos, neg


def h3(records: list[dict], rng) -> dict:
    p_pos, p_neg = _scores(records, P, "p_h0_final")
    comparators = {
        "B3_entropy": _scores(records, "B3_closed_world_eig", "cw_entropy_final"),
        "B2_entropy": _scores(records, "B2_classifier_entropy", "cw_entropy_final"),
        "P_own_measurements_entropy": _scores(records, P, "cw_entropy_final"),
    }
    ip = rng.integers(0, len(p_pos), size=(N_BOOT, len(p_pos)))
    ineg = rng.integers(0, len(p_neg), size=(N_BOOT, len(p_neg)))
    tpr_p = np.array([tpr_at_fpr(p_pos[a], p_neg[b]) for a, b in zip(ip, ineg)])
    auc_p = np.array([auroc(p_pos[a], p_neg[b]) for a, b in zip(ip, ineg)])
    out = {"n_withheld": len(p_pos), "n_modeled": len(p_neg), "target_fpr": TARGET_FPR,
           "P_tpr_at_fpr": tpr_at_fpr(p_pos, p_neg), "P_auroc": auroc(p_pos, p_neg), "comparators": {}}
    fpr, tpr = roc_curve(p_pos, p_neg)
    out["roc"] = {"P_p_h0": {"fpr": fpr.tolist(), "tpr": tpr.tolist()}}
    for cname, (c_pos, c_neg) in comparators.items():
        tpr_c = np.array([tpr_at_fpr(c_pos[a], c_neg[b]) for a, b in zip(ip, ineg)])
        auc_c = np.array([auroc(c_pos[a], c_neg[b]) for a, b in zip(ip, ineg)])
        fpr, tpr = roc_curve(c_pos, c_neg)
        out["roc"][cname] = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}
        out["comparators"][cname] = {
            "tpr_at_fpr": tpr_at_fpr(c_pos, c_neg), "auroc": auroc(c_pos, c_neg),
            "delta_tpr": tpr_at_fpr(p_pos, p_neg) - tpr_at_fpr(c_pos, c_neg), "delta_tpr_ci95": _ci(tpr_p - tpr_c),
            "delta_auroc": auroc(p_pos, p_neg) - auroc(c_pos, c_neg), "delta_auroc_ci95": _ci(auc_p - auc_c),
        }
    primary = out["comparators"]["B3_entropy"]
    out["estimate"], out["ci95"] = primary["delta_tpr"], primary["delta_tpr_ci95"]
    out["pass"] = bool(primary["delta_tpr_ci95"][0] > 0)
    return out


def reported(records: list[dict]) -> dict:
    names = list(records[0]["strategies"])
    mod = [r for r in records if r["modeled"]]
    wh = [r for r in records if not r["modeled"]]
    out = {}
    for n in names:
        def m(rs, k):
            return float(np.mean([r["strategies"][n][k] for r in rs])) if rs else None
        out[n] = {"accuracy_modeled": m(mod, "correct"), "accuracy_withheld": m(wh, "correct"),
                  "confident_wrong_modeled": m(mod, "confident_wrong"),
                  "confident_wrong_withheld": m(wh, "confident_wrong"),
                  "mean_log_score": m(records, "log_score"), "mean_obs_used": m(records, "n_obs_used")}
        if n.startswith("P_"):
            out[n]["h0_false_alarm_modeled"] = float(np.mean([r["strategies"][n]["decision"] == "h0" for r in mod]))
            out[n]["auroc_p_h0"] = auroc(*_scores(records, n, "p_h0_final"))
    return out


def tti_distributions(records: list[dict]) -> dict:
    """Per-strategy sorted time-to-identification (inf = censored), for Figure 1."""
    mod = [r for r in records if r["modeled"]]
    return {n: sorted(np.inf if r["strategies"][n]["time_to_id_days"] is None
                      else r["strategies"][n]["time_to_id_days"] for r in mod)
            for n in records[0]["strategies"]}


def analyse_run(run_dir: Path, seed: int) -> dict:
    records = load_records(run_dir)
    cfg = json.loads((run_dir / "config.json").read_text())
    rng = np.random.default_rng(seed)
    return {"run": run_dir.name, "scenario": cfg["scenario"], "split": cfg["split"], "seed": cfg["seed"],
            "git_commit": cfg["git_commit"], "n_events": len(records),
            "H1": h1(records), "H2": h2(records, rng), "H3": h3(records, rng),
            "reported": reported(records), "tti_days": tti_distributions(records)}


def _json_safe(o):
    if isinstance(o, float) and not np.isfinite(o):
        return "inf" if o > 0 else "-inf"
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_json_safe(v) for v in o]
    return o


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="run directories; the first is the primary (S1)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0, help="bootstrap seed")
    args = ap.parse_args()
    runs = [analyse_run(Path(d), args.seed) for d in args.runs]
    primary = runs[0]
    verdict = {h: primary[h]["pass"] for h in ("H1", "H2", "H3")}
    atomic_write_json(Path(args.out), _json_safe({"primary_run": primary["run"], "verdict": verdict,
                                                   "bootstrap_seed": args.seed, "runs": runs}))
    for r in runs:
        print(f"{r['run']}: H1 {r['H1']['pass']} (median P {r['H1']['median_P_days']:.3g} d vs "
              + ", ".join(f"{b[:2]} {e['median_days']:.3g} p={e['holm_p']:.2g}" for b, e in r['H1']['per_baseline'].items())
              + f") | H2 {r['H2']['pass']} {r['H2']['estimate']:+.3f} {np.round(r['H2']['ci95'], 3).tolist()}"
              f" | H3 {r['H3']['pass']} dTPR {r['H3']['estimate']:+.3f} {np.round(r['H3']['ci95'], 3).tolist()}"
              f" AUROC P {r['H3']['P_auroc']:.3f} vs B3-H {r['H3']['comparators']['B3_entropy']['auroc']:.3f}")
    print("verdict (primary):", verdict)


if __name__ == "__main__":
    main()
