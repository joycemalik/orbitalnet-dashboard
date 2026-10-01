import numpy as np
import pytest

from research.inference.bayes import ClosedWorldBelief
from research.orbitsim.contacts import ContactSchedule
from research.planners.phase2 import _decay_term_batch, _next_visible_index
from research.transients.models import (
    MODELED_CLASSES_P2,
    modeled_flux_fn_p2,
    modeled_flux_fn_p2_perturbed,
)


def test_perturbed_model_is_true_model_with_dilated_time():
    t = np.array([0.5, 1.0, 2.0])
    amplitude = 10.0
    for cls in MODELED_CLASSES_P2:
        true_fn = modeled_flux_fn_p2(cls)
        perturbed_fn = modeled_flux_fn_p2_perturbed(cls, 1.3)
        expected = true_fn(t / 1.3, amplitude)
        actual = perturbed_fn(t, amplitude)
        np.testing.assert_allclose(actual, expected)


def test_perturbed_model_with_factor_one_matches_true_model():
    t = np.array([0.5, 1.0, 2.0])
    for cls in MODELED_CLASSES_P2:
        true_fn = modeled_flux_fn_p2(cls)
        perturbed_fn = modeled_flux_fn_p2_perturbed(cls, 1.0)
        np.testing.assert_allclose(perturbed_fn(t, 10.0), true_fn(t, 10.0))


def test_next_visible_index_finds_the_next_later_visible_slot():
    visibility = np.array([
        [True, False],
        [False, True],
        [True, True],
    ])
    next_idx = _next_visible_index(visibility)
    # satellite 0: visible at t=0, next visible t=2 -> next_idx[0,0]=2; at t=2, no later -> -1
    assert next_idx[0, 0] == 2
    assert next_idx[2, 0] == -1
    # satellite 1: visible at t=1, next visible t=2 -> next_idx[1,1]=2
    assert next_idx[1, 1] == 2
    assert next_idx[2, 1] == -1
    # satellite 0 at t=1 (not visible there, but function still reports the
    # next visible slot regardless of current-cell visibility): next is t=2
    assert next_idx[1, 0] == 2


def test_decay_term_is_zero_when_no_better_future_opportunity():
    """If the next feasible slot for a satellite is identical in SNR to now
    (e.g. the model is flat), D must be ~0 -- nothing is lost by waiting."""
    amplitude_grid = np.array([10.0])
    belief = ClosedWorldBelief.with_uniform_prior(classes=("kilonova",), amplitude_grid=amplitude_grid)
    # Monkeypatch-free: use a belief with a single class and give it a flat
    # resolver returning a constant flux so now/next SNR are identical.
    belief.flux_fn_resolver = lambda cls: (lambda t, a: np.full_like(np.asarray(t, dtype=float), 5.0) * 0 + a)

    schedule = ContactSchedule(
        satellite_names=("SAT-A",),
        candidate_times_days=np.array([1.0, 2.0]),
        visibility=np.array([[True], [True]]),
        margin_deg=np.array([[10.0], [10.0]]),
        target_dir_eci=np.array([1.0, 0.0, 0.0]),
    )
    instrument_sigma = np.array([1.0])
    cells = np.array([[0, 0]])
    t_cands = np.array([1.0])
    sigma_cands = np.array([1.0])

    d = _decay_term_batch(belief, schedule, instrument_sigma, cells, t_cands, sigma_cands)
    assert d[0] == pytest.approx(0.0, abs=1e-9)


def test_decay_term_is_positive_when_future_opportunity_is_worse():
    amplitude_grid = np.array([10.0])
    belief = ClosedWorldBelief.with_uniform_prior(classes=("kilonova",), amplitude_grid=amplitude_grid)
    # Flux decays with t, so the next slot (t=2) has lower SNR than now (t=1).
    belief.flux_fn_resolver = lambda cls: (lambda t, a: a * np.exp(-np.asarray(t, dtype=float)))

    schedule = ContactSchedule(
        satellite_names=("SAT-A",),
        candidate_times_days=np.array([1.0, 2.0]),
        visibility=np.array([[True], [True]]),
        margin_deg=np.array([[10.0], [10.0]]),
        target_dir_eci=np.array([1.0, 0.0, 0.0]),
    )
    instrument_sigma = np.array([1.0])
    cells = np.array([[0, 0]])
    t_cands = np.array([1.0])
    sigma_cands = np.array([1.0])

    d = _decay_term_batch(belief, schedule, instrument_sigma, cells, t_cands, sigma_cands)
    assert d[0] > 0.0
