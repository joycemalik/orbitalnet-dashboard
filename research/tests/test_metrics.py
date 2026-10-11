import numpy as np
import pytest

from research.experiments.metrics import auroc, log_score


def test_auroc_perfect_separation_is_one():
    pos = np.array([0.9, 0.95, 0.99])
    neg = np.array([0.1, 0.2, 0.3])
    assert auroc(pos, neg) == pytest.approx(1.0)


def test_auroc_reversed_separation_is_zero():
    pos = np.array([0.1, 0.2, 0.3])
    neg = np.array([0.9, 0.95, 0.99])
    assert auroc(pos, neg) == pytest.approx(0.0)


def test_auroc_identical_distributions_is_half():
    rng = np.random.default_rng(0)
    values = rng.normal(size=20)
    assert auroc(values, values) == pytest.approx(0.5)


def test_auroc_empty_class_is_none():
    assert auroc(np.array([]), np.array([0.5])) is None


def test_log_score_uses_h0_fallback_for_withheld_truth():
    posterior = {"fast": 0.1, "slow": 0.1, "h0": 0.8}
    score = log_score(posterior, "bump", modeled_classes=("fast", "slow"))
    assert score == pytest.approx(np.log(0.8))


def test_log_score_epsilon_floor_when_outcome_unrepresentable():
    posterior = {"fast": 0.5, "slow": 0.5}  # no h0 key at all
    score = log_score(posterior, "bump", modeled_classes=("fast", "slow"), epsilon=1e-6)
    assert score == pytest.approx(np.log(1e-6))
