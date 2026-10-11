"""Metric helpers shared by the Phase 2+ experiment scripts. Pure functions
over already-computed posteriors/records — no result numbers are invented
here, only combined/summarized."""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def log_score(posterior: dict, true_class: str, modeled_classes, epsilon: float = 1e-6) -> float:
    """log p(true outcome). A strategy whose decision space structurally
    cannot express the true outcome (e.g. a closed-world baseline when the
    truth is a withheld class) is scored as if it assigned it `epsilon`."""
    if true_class in modeled_classes:
        p = posterior.get(true_class, epsilon)
    else:
        p = posterior.get("h0", epsilon)
    return float(np.log(max(p, epsilon)))


def posterior_mean_amplitude(belief) -> float:
    probs = np.exp(belief.normalized_log_joint())  # (n_classes, n_amp)
    marginal_amp = probs.sum(axis=0)
    return float(np.sum(marginal_amp * belief.amplitude_grid))


def time_to_identification(history: list[dict], posterior_key: str, threshold: float) -> int | None:
    """1-based index of the first step whose posterior max exceeds
    `threshold`, or None if the budget ran out without reaching it."""
    for step, entry in enumerate(history, start=1):
        posterior = entry[posterior_key]
        if max(posterior.values()) >= threshold:
            return step
    return None


def auroc(scores_pos: np.ndarray, scores_neg: np.ndarray) -> float | None:
    """AUROC via the Mann-Whitney U / rank-sum identity — no sklearn
    dependency needed. Returns None if either class is empty (undefined)."""
    scores_pos = np.asarray(scores_pos, dtype=float)
    scores_neg = np.asarray(scores_neg, dtype=float)
    n_pos, n_neg = len(scores_pos), len(scores_neg)
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = rankdata(np.concatenate([scores_pos, scores_neg]))
    rank_sum_pos = float(np.sum(ranks[:n_pos]))
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))
