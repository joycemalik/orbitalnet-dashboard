import numpy as np
import pytest

from research.experiments.metrics import auroc
from research.experiments.phase2_analysis import holm, roc_curve, tpr_at_fpr


def test_holm_known_answer():
    # sorted p: 0.01, 0.02, 0.04 -> 0.03, 0.04, 0.04 (monotone step-down)
    assert holm([0.04, 0.01, 0.02]) == pytest.approx([0.04, 0.03, 0.04])


def test_roc_matches_brute_force_and_auroc():
    rng = np.random.default_rng(0)
    pos = np.round(rng.normal(1.0, 1.0, 60), 1)  # rounding creates ties
    neg = np.round(rng.normal(0.0, 1.0, 90), 1)
    fpr, tpr = roc_curve(pos, neg)
    thr = np.unique(np.concatenate([pos, neg]))[::-1]
    assert tpr[1:] == pytest.approx([np.mean(pos >= t) for t in thr])
    assert fpr[1:] == pytest.approx([np.mean(neg >= t) for t in thr])
    assert np.trapz(tpr, fpr) == pytest.approx(auroc(pos, neg))


def test_tpr_at_fpr_perfect_and_useless_scores():
    assert tpr_at_fpr(np.array([2.0, 3.0]), np.array([0.0, 1.0])) == pytest.approx(1.0)
    same = np.zeros(10)
    assert tpr_at_fpr(same, same, 0.05) == pytest.approx(0.05)
