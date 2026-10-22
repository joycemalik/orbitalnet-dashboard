"""Known-answer tests for the Phase C conformal layer (research/inference/conformal.py)."""

import numpy as np
import pytest

from research.inference.conformal import (class_conditional_threshold, conformal_decision, conformal_pvalue,
                                          conformal_threshold, log_bf_score)


def test_threshold_is_the_correct_order_statistic():
    s = np.arange(1.0, 20.0)  # n = 19, alpha = 0.1 -> k = ceil(20 * 0.9) = 18
    assert conformal_threshold(s, 0.1) == 18.0
    assert conformal_threshold(s[:5], 0.1) == float("inf")  # n too small to certify 10%


@pytest.mark.parametrize("n,alpha", [(30, 0.1), (100, 0.05), (281, 0.1)])
def test_finite_sample_coverage_bounds(n, alpha):
    """Exact theory: alpha - 1/(n+1) <= P(flag) <= alpha for continuous scores,
    whatever the score distribution (heavy-tailed here)."""
    rng = np.random.default_rng(0)
    reps = 40000
    cal = rng.standard_cauchy((reps, n))
    new = rng.standard_cauchy(reps)
    taus = np.array([conformal_threshold(c, alpha) for c in cal])
    far = np.mean(new > taus)
    mc = 4 * np.sqrt(alpha * (1 - alpha) / reps)
    assert far <= alpha + mc
    assert far >= alpha - 1.0 / (n + 1) - mc


def test_max_rule_holds_for_every_class_under_label_shift():
    """Three classes with very different score distributions; calibration is
    balanced, deployment is 90% one class. Per-class FAR must be <= alpha."""
    rng = np.random.default_rng(1)
    alpha, reps, n_per = 0.1, 6000, 60
    locs = {"a": 0.0, "b": 2.0, "c": -1.0}
    flags = {k: [] for k in locs}
    for _ in range(reps):
        labels = np.repeat(list(locs), n_per)
        scores = np.concatenate([rng.normal(locs[k], 1.0, n_per) for k in locs])
        tau, _ = class_conditional_threshold(scores, labels, alpha)
        for k in locs:
            flags[k].append(rng.normal(locs[k], 1.0) > tau)
    for k in locs:
        assert np.mean(flags[k]) <= alpha + 4 * np.sqrt(alpha * (1 - alpha) / reps)


def test_pvalue_super_uniform():
    rng = np.random.default_rng(2)
    p = np.array([conformal_pvalue(rng.normal(size=50), rng.normal()) for _ in range(20000)])
    for a in (0.05, 0.1, 0.3):
        assert np.mean(p <= a) <= a + 0.01


def test_score_and_decision():
    assert log_bf_score({"x": -10.0, "y": -3.0}, -1.0) == pytest.approx(2.0)
    post = {"x": 0.97, "y": 0.03}
    assert conformal_decision(post, score=5.0, tau=1.0, confident_threshold=0.95) == ("h0", False)
    assert conformal_decision(post, score=0.0, tau=1.0, confident_threshold=0.95) == ("x", True)
