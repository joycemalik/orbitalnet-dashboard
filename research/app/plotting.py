"""Matplotlib figure builders for the viewer app. These functions only
rearrange numbers that are already in the summary/worked-example JSON files
into a figure — they never compute a new result number.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def existence_proof_figure(summary: dict):
    strategies = list(summary["strategies"].keys())
    modeled = [summary["strategies"][s]["confident_wrong_rate_modeled"] for s in strategies]
    withheld = [summary["strategies"][s]["confident_wrong_rate_withheld"] for s in strategies]

    x = np.arange(len(strategies))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x - width / 2, modeled, width, label="true class modeled")
    ax.bar(x + width / 2, withheld, width, label="true class withheld (h0 should fire)")
    ax.set_xticks(x)
    ax.set_xticklabels(strategies, rotation=15, ha="right")
    ax.set_ylabel("confident-wrong rate")
    ax.set_title("Phase 1 existence proof: confident-wrong rate by strategy")
    ax.set_ylim(0, 1.0)
    ax.legend()
    fig.tight_layout()
    return fig


def worked_example_figure(example: dict):
    history = example["history"]
    steps = list(range(1, len(history) + 1))
    times = [h["t"] for h in history]

    hyp_names = sorted(history[0]["open_world_posterior"].keys())
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for hyp in hyp_names:
        probs = [h["open_world_posterior"][hyp] for h in history]
        ax.plot(steps, probs, marker="o", label=f"p({hyp})")

    ax.set_xticks(steps)
    ax.set_xticklabels([f"t={t:.2f}" for t in times], rotation=30, ha="right")
    ax.set_xlabel("measurement time (no spacecraft yet — Phase 1 has no orbits)")
    ax.set_ylabel("posterior probability")
    ax.set_title(f"Worked example — true class: {example['true_class']} (decision: {example['decision']})")
    ax.set_ylim(0, 1.0)
    ax.legend()
    fig.tight_layout()
    return fig
