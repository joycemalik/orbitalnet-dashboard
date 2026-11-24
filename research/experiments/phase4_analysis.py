"""Phase 4 analysis: per-strategy summaries, reserve selection (rule declared
in research/LOG.md before validation), and paired episode-cluster bootstrap
intervals for strategy differences.

Usage:
  python -m research.experiments.phase4_analysis select   # validation runs -> results/phase4/reserves.json
  python -m research.experiments.phase4_analysis summary <run_dir_or_json> [--out file.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from research.experiments.metrics import auroc
from research.util import atomic_write_json

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "phase4_fleet"
ALPHA = 0.1
LOG_FLOOR = 1e-6
RESERVE_GRID = (0.1, 0.3, 1.0, 3.0, 10.0)
VALIDATION_SEED, VALIDATION_N = 41, 100
N_BOOT = 10_000


def load_run(path: Path) -> dict:
    path = Path(path)
    if path.is_dir():
        merged = path / "merged.json"
        if merged.exists():
            return json.loads(merged.read_text())
        shards = sorted(path.glob("shard_*of1.json"))
        if len(shards) == 1:
            return json.loads(shards[0].read_text())
        raise SystemExit(f"{path}: run merge_shards first")
    return json.loads(path.read_text())


def event_rows(run: dict, strategy: str):
    """Yield (episode_index, event_meta, strategy_row) for every event."""
    for ep in run["episodes"]:
        for meta, row in zip(ep["events"], ep["strategies"][strategy]["events"]):
            yield ep["episode_index"], meta, row


def log_score(meta: dict, row: dict) -> float:
    # p_h0 + per-class probabilities are not all stored; reconstruct p(true) from what is.
    if not meta["modeled"]:
        return float(np.log(max(row["p_h0"], LOG_FLOOR)))
    return float(np.log(max(row["p_true"], LOG_FLOOR)))


def summarize_strategy(run: dict, strategy: str) -> dict:
    rows = list(event_rows(run, strategy))
    mod = [r for _, m, r in rows if m["modeled"]]
    unk = [r for _, m, r in rows if not m["modeled"]]
    thr = np.log(1 / ALPHA)

    def rate(rs, f):
        return float(np.mean([f(r) for r in rs])) if rs else None

    eps = [ep["strategies"][strategy] for ep in run["episodes"]]
    out = {
        "n_modeled": len(mod), "n_unknown": len(unk),
        "acc_modeled": rate(mod, lambda r: r["correct"]),
        "cw_unknown": rate(unk, lambda r: r["confident_wrong"]),
        "cw_modeled": rate(mod, lambda r: r["confident_wrong"]),
        "flag_unknown": rate(unk, lambda r: r["decision"] == "h0"),
        "false_unknown_modeled": rate(mod, lambda r: r["decision"] == "h0"),
        "auroc_p_h0": auroc(np.array([r["p_h0"] for r in unk]), np.array([r["p_h0"] for r in mod])),
        "mean_log_score": float(np.mean([log_score(m, r) for _, m, r in rows])),
        "mean_obs_per_event": rate([r for _, _, r in rows], lambda r: r["n_obs"]),
        "duplicates_per_event": rate([r for _, _, r in rows], lambda r: r["duplicates"]),
        "records_moved_per_episode": float(np.mean([e["records_moved"] for e in eps])),
        "mean_stale_fraction": float(np.mean([e["mean_stale_fraction"] for e in eps])),
        "budget_used_per_episode": float(np.mean([e["budget_used"] for e in eps])),
        # HE1: anytime e-process on everything taken (ground)
        "e_ground_false_alarm_modeled": rate(mod, lambda r: r["max_log_e_ground"] >= thr),
        "e_ground_detect_unknown": rate(unk, lambda r: r["max_log_e_ground"] >= thr),
    }
    # HE2: per (event, spacecraft) onboard fused statistics
    for scheme in ("union", "mean", "prod"):
        key = f"max_log_e_{scheme}"
        out[f"e_{scheme}_false_alarm_modeled"] = float(np.mean([np.mean(np.array(r[key]) >= thr) for r in mod])) if mod else None
        out[f"e_{scheme}_detect_unknown"] = float(np.mean([np.mean(np.array(r[key]) >= thr) for r in unk])) if unk else None
    return out


def summarize(run: dict) -> dict:
    strategies = list(run["episodes"][0]["strategies"])
    return {s: summarize_strategy(run, s) for s in strategies}


def family(name: str) -> str:
    return name.split("_")[0]


def select_reserves() -> dict:
    """Apply the declared rule: per family, the reserve maximising the mean
    log score averaged over the family's members (ties -> smaller reserve)."""
    table = {}
    for r in RESERVE_GRID:
        run_dir = RESULTS_DIR / f"validation_nominal_seed{VALIDATION_SEED}_n{VALIDATION_N}_r{r:g}"
        summ = summarize(load_run(run_dir))
        table[r] = {s: v["mean_log_score"] for s, v in summ.items()}
    fams = sorted({family(s) for s in next(iter(table.values()))})
    chosen, scores = {}, {}
    for f in fams:
        per_r = {r: float(np.mean([v for s, v in table[r].items() if family(s) == f])) for r in RESERVE_GRID}
        best = max(per_r.values())
        chosen[f] = min(r for r, v in per_r.items() if v == best)
        scores[f] = per_r
    out = {"rule": "per family, argmax mean open-world log score over the family's members; ties -> smaller",
           "grid": list(RESERVE_GRID), "validation_seed": VALIDATION_SEED, "validation_n_episodes": VALIDATION_N,
           "family_mean_log_score": {f: {str(r): v for r, v in s.items()} for f, s in scores.items()},
           "reserves": chosen}
    atomic_write_json(str(RESULTS_DIR / "reserves.json"), out)
    return out


def paired_bootstrap(run: dict, a: str, b: str, metric, population: str, seed: int = 0, n_boot: int = N_BOOT):
    """Difference metric(a) - metric(b) with a 95% percentile interval,
    resampling whole episodes (events in an episode share geometry and
    allocation). `metric(row) -> float`; population in {modeled, unknown, all}."""
    per_ep = []
    for ep in run["episodes"]:
        da, db = [], []
        for meta, ra, rb in zip(ep["events"], ep["strategies"][a]["events"], ep["strategies"][b]["events"]):
            if population == "all" or (population == "modeled") == meta["modeled"]:
                da.append(metric(ra)); db.append(metric(rb))
        per_ep.append((np.sum(da), np.sum(db), len(da)))
    arr = np.array(per_ep, dtype=float)
    est = (arr[:, 0].sum() - arr[:, 1].sum()) / arr[:, 2].sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    s = arr[idx]
    boots = (s[..., 0].sum(1) - s[..., 1].sum(1)) / np.clip(s[..., 2].sum(1), 1, None)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"estimate": float(est), "ci95": [float(lo), float(hi)]}


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided Clopper-Pearson upper bound."""
    from scipy.stats import beta
    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))


def evaluate_hypotheses(run: dict) -> dict:
    """PREREGISTRATION_H4.md, exactly as written."""
    acc = lambda r: float(r["correct"])
    thr = np.log(1 / ALPHA)
    out = {}
    for hid, a, b in (("H4.1", "O", "G"), ("H4.2", "A_5000", "G"), ("H4.3", "O", "A_5000")):
        d = paired_bootstrap(run, a, b, acc, "modeled")
        out[hid] = {"comparison": f"accuracy({a}) - accuracy({b})", **d, "pass": d["ci95"][0] > 0}
    d = paired_bootstrap(run, "A_5000", "K_5000", acc, "modeled")
    out["H4.4"] = {"comparison": "accuracy(A_5000) - accuracy(K_5000) within +-0.05", **d,
                   "pass": d["ci95"][0] > -0.05 and d["ci95"][1] < 0.05}
    he1 = {}
    for s in run["episodes"][0]["strategies"]:
        mod = [r for _, m, r in event_rows(run, s) if m["modeled"]]
        k = sum(r["max_log_e_ground"] >= thr for r in mod)
        he1[s] = {"false_unknown": k / len(mod), "k": int(k), "n": len(mod), "cp_upper95": cp_upper(int(k), len(mod))}
    out["HE1"] = {"per_strategy": he1, "pass": all(v["cp_upper95"] <= ALPHA for v in he1.values())}
    mod = [r for _, m, r in event_rows(run, "A_5000") if m["modeled"]]
    flags = [x >= thr for r in mod for x in r["max_log_e_mean"]]
    k, n = int(sum(flags)), len(flags)
    out["HE2"] = {"false_alarm": k / n, "k": k, "n": n, "cp_upper95": cp_upper(k, n), "pass": cp_upper(k, n) <= ALPHA}
    return out



def paired_cross(run_a: dict, sa: str, run_b: dict, sb: str, metric, population: str = "modeled",
                 seed: int = 0, n_boot: int = N_BOOT) -> dict:
    """metric(sa in run_a) - metric(sb in run_b) over identical episodes (same seed),
    episode-cluster bootstrap. Refuses if the runs' events differ."""
    per = []
    for ea, eb in zip(run_a["episodes"], run_b["episodes"]):
        assert ea["episode_index"] == eb["episode_index"]
        assert [e["true_class"] for e in ea["events"]] == [e["true_class"] for e in eb["events"]]
        xa, xb = [], []
        for meta, ra, rb in zip(ea["events"], ea["strategies"][sa]["events"], eb["strategies"][sb]["events"]):
            if population == "all" or (population == "modeled") == meta["modeled"]:
                xa.append(metric(ra)); xb.append(metric(rb))
        per.append((sum(xa), sum(xb), len(xa)))
    arr = np.array(per, dtype=float)
    est = (arr[:, 0].sum() - arr[:, 1].sum()) / arr[:, 2].sum()
    idx = np.random.default_rng(seed).integers(0, len(arr), size=(n_boot, len(arr)))
    s = arr[idx]
    boots = (s[..., 0].sum(1) - s[..., 1].sum(1)) / np.clip(s[..., 2].sum(1), 1, None)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"estimate": float(est), "ci95": [float(lo), float(hi)]}


def evaluate_h4b(r1: dict, r2: dict, r3: dict) -> dict:
    """PREREGISTRATION_H4B.md, exactly as written."""
    acc = lambda r: float(r["correct"])
    epochs = lambda r: float(len(set(r["obs_epochs"])))
    out = {}
    d = paired_cross(r1, "A_5000", r1, "G", acc); out["B1"] = {**d, "pass": d["ci95"][0] > 0}
    d = paired_cross(r1, "A_5000", r1, "K_5000", acc); out["B2"] = {**d, "pass": d["ci95"][0] > -0.05 and d["ci95"][1] < 0.05}
    d = paired_cross(r3, "O", r1, "O", acc); out["B3"] = {**d, "pass": d["ci95"][0] > 0}
    d = paired_cross(r1, "O", r2, "O", acc); out["B4"] = {**d, "pass": d["ci95"][0] > 0}
    d = paired_cross(r1, "O", r2, "O", epochs, "all"); out["B5"] = {**d, "pass": d["ci95"][0] > 0}
    out["reported_dense_A5000_minus_G"] = paired_cross(r2, "A_5000", r2, "G", acc)
    return out


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "select":
        print(json.dumps(select_reserves(), indent=2))
    elif cmd == "hypotheses":
        run = load_run(Path(sys.argv[2]))
        res = {"hypotheses": evaluate_hypotheses(run), "summary": summarize(run), "meta": run["meta"]}
        atomic_write_json(sys.argv[3], res)
        for h, v in res["hypotheses"].items():
            print(h, "PASS" if v["pass"] else "FAIL", {k: v[k] for k in v if k in ("estimate", "ci95", "false_alarm", "cp_upper95")})
    elif cmd == "h4b":
        runs = [load_run(RESULTS_DIR / t) for t in ("b_sparse_equal3", "b_dense_equal3", "b_sparse_selected")]
        res = {"hypotheses": evaluate_h4b(*runs),
               "summary": {t: summarize(r) for t, r in zip(("sparse_equal3", "dense_equal3", "sparse_selected"), runs)},
               "link_up": {t: {k: float(np.mean([ep["link_up_fraction"][k] for ep in r["episodes"]]))
                               for k in r["episodes"][0]["link_up_fraction"]}
                           for t, r in zip(("sparse", "dense"), runs[:2])}}
        atomic_write_json(str(RESULTS_DIR / "analysis_h4b.json"), res)
        for h, v in res["hypotheses"].items():
            print(h, ("PASS" if v.get("pass") else "FAIL") if "pass" in v else "reported", round(v["estimate"], 4), [round(x, 4) for x in v["ci95"]])
    elif cmd == "summary":
        run = load_run(Path(sys.argv[2]))
        out = summarize(run)
        if "--out" in sys.argv:
            atomic_write_json(sys.argv[sys.argv.index("--out") + 1], out)
        for s, v in out.items():
            print(f"{s:7s} acc={v['acc_modeled']:.2f} cwU={v['cw_unknown']:.2f} flag={v['flag_unknown']:.2f} "
                  f"falseU={v['false_unknown_modeled']:.2f} auc={v['auroc_p_h0']:.2f} ls={v['mean_log_score']:.2f} "
                  f"obs={v['mean_obs_per_event']:.1f} dup={v['duplicates_per_event']:.2f} "
                  f"stale={v['mean_stale_fraction']:.2f} eFA={v['e_ground_false_alarm_modeled']:.3f} "
                  f"eDet={v['e_ground_detect_unknown']:.2f} prodFA={v['e_prod_false_alarm_modeled']:.3f} "
                  f"meanFA={v['e_mean_false_alarm_modeled']:.3f}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
