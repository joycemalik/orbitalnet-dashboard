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


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "select":
        print(json.dumps(select_reserves(), indent=2))
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
