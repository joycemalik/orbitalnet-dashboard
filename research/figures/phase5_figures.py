"""Figures for Phases 3-5, generated ONLY from research/results/ files.

  fig_roc_{split}.png      ROC of P(h0) (unmodeled vs ordinary SNe) per arm
  fig_example_{split}.png  one real unmodeled event: its real ZTF light curve,
                           the measurements P chose, and P(h0) vs B3's max
                           posterior after each measurement

Usage:
  python -m research.figures.phase5_figures --split validation --seed 1
  python -m research.figures.phase5_figures --split test --seed 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
RES = REPO_ROOT / "research" / "results"
OUT = REPO_ROOT / "docs" / "figures"

ARMS = {  # label -> (validation dir, test dir template)
    "single band (Phase 3 config)": ("phase4/validation_seed1_r5_l5", "phase5/test_seed{S}_final_r5"),
    "single band, 2x pointings": ("phase4/validation_seed1_r10_l5", "phase5/test_seed{S}_final_r10"),
    "colour + discrepancy (v2)": ("phase5/validation_seed1_gr5_k0.5", "phase5/test_seed{S}_final_gr5_k0.5"),
}
COLORS = ["#8a8f98", "#c9a227", "#2f7fd8"]


def _load(d: Path) -> list[dict]:
    return [json.loads(l) for l in open(d / "events.jsonl", encoding="utf-8")]


def roc(pos: np.ndarray, neg: np.ndarray):
    thr = np.unique(np.concatenate([pos, neg, [np.inf, -np.inf]]))[::-1]
    return np.array([(neg >= t).mean() for t in thr]), np.array([(pos >= t).mean() for t in thr])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("validation", "test"), required=True)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    runs = {lab: _load(RES / (v if args.split == "validation" else t.format(S=args.seed)))
            for lab, (v, t) in ARMS.items()}

    fig, ax = plt.subplots(figsize=(4.6, 4.2), dpi=150)
    for (lab, recs), c in zip(runs.items(), COLORS):
        p = np.array([r["strategies"]["P_open_world_eig"]["p_h0_final"] for r in recs])
        w = np.array([r["withheld"] for r in recs])
        fpr, tpr = roc(p[w], p[~w])
        auc = float(np.trapezoid(tpr, fpr))
        ax.plot(fpr, tpr, color=c, lw=2, label=f"{lab}  AUROC {auc:.2f}")
    ax.plot([0, 1], [0, 1], ls=":", color="#bbb", lw=1)
    ax.set(xlabel="ordinary SNe called unknown (false-alarm rate)", ylabel="real unmodeled events flagged",
           xlim=(0, 1), ylim=(0, 1), title=f"P(unknown) on real ZTF transients ({args.split}, seed {args.seed})")
    ax.title.set_fontsize(9)
    ax.legend(fontsize=7, loc="lower right", frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / f"fig_roc_{args.split}.png")
    plt.close(fig)

    # Worked example: the first (chronological) TDE where v2-P ends with
    # P(h0) >= 0.5 while B3 ends confidently wrong. Chosen by that rule, not by eye.
    v2 = runs["colour + discrepancy (v2)"]
    ex = next((r for r in v2 if r["true_class"] == "tde"
               and r["strategies"]["P_open_world_eig"]["p_h0_final"] >= 0.5
               and r["strategies"]["B3_closed_world_eig"]["confident_wrong"]), None)
    if ex is None:
        print("no event matches the worked-example rule; example figure skipped")
        return
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 3.4), dpi=150)
    a1.errorbar(ex["real_t_days"], ex["real_flux"], yerr=ex["real_flux_err"], fmt="o", ms=3, color="#999",
                label="real ZTF r-band detections")
    hP = ex["strategies"]["P_open_world_eig"]["history"]
    a1.plot([h["t"] for h in hP], [h["y"] for h in hP], "D", color=COLORS[2], ms=6,
            label="open-world planner's r measurements")
    a1.set(xlabel="days since first detection", ylabel="flux (ZP 20)", title=f"{ex['oid']} ({ex['bts_type']})",
           xlim=(-3, 90))  # planning window is 0.5-60 d; later ZTF points are off-axis
    a1.legend(fontsize=7, frameon=False)
    steps = np.arange(1, len(hP) + 1)
    a2.plot(steps, [h["posterior"]["h0"] for h in hP], "-o", color=COLORS[2], label="open-world: P(unknown)")
    hB = ex["strategies"]["B3_closed_world_eig"]["history"]
    a2.plot(np.arange(1, len(hB) + 1), [max(h["posterior"].values()) for h in hB], "-s", color="#c0392b",
            label=f"closed-world B3: confidence in '{ex['strategies']['B3_closed_world_eig']['decision']}'")
    a2.axhline(0.95, ls=":", color="#bbb")
    a2.set(xlabel="measurement #", ylabel="probability", ylim=(0, 1.02), title="belief after each measurement")
    a2.legend(fontsize=7, frameon=False, loc="lower right")
    for a in (a1, a2):
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        a.title.set_fontsize(9)
    fig.tight_layout()
    fig.savefig(OUT / f"fig_example_{args.split}.png")
    plt.close(fig)
    print("wrote", OUT / f"fig_roc_{args.split}.png", OUT / f"fig_example_{args.split}.png", "example:", ex["oid"])


if __name__ == "__main__":
    main()
