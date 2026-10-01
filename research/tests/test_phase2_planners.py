import numpy as np
import pytest

from research.inference.bayes import ClosedWorldBelief
from research.inference.openworld import SimpleGP
from research.orbitsim.contacts import ContactSchedule
from research.planners.phase2 import (
    STRATEGIES_P2,
    classifier_entropy_planner,
    cnp_reimplementation_planner,
    fixed_cadence_planner,
    _per_class_posterior_mean_amplitude,
)
from research.transients.models import MODELED_CLASSES_P2, modeled_flux_fn_p2


def _toy_schedule() -> ContactSchedule:
    # 3 times x 2 satellites; satellite 1 always has a bigger visibility margin.
    margin = np.array([
        [10.0, 1.0],
        [20.0, 2.0],
        [-5.0, 3.0],  # sat 0 occluded at t=2
    ])
    visibility = margin >= 0.0
    return ContactSchedule(
        satellite_names=("SAT-A", "SAT-B"),
        candidate_times_days=np.array([1.0, 2.0, 4.0]),
        visibility=visibility,
        margin_deg=margin,
        target_dir_eci=np.array([1.0, 0.0, 0.0]),
    )


def _toy_belief() -> ClosedWorldBelief:
    amplitude_grid = np.array([10.0])
    return ClosedWorldBelief.with_uniform_prior(
        classes=MODELED_CLASSES_P2, amplitude_grid=amplitude_grid, flux_fn_resolver=modeled_flux_fn_p2
    )


def test_cnp_reimplementation_prefers_higher_margin_when_instruments_equal():
    schedule = _toy_schedule()
    remaining_mask = schedule.visibility.copy()
    instrument_sigma = np.array([1.0, 1.0])  # identical instruments -> margin decides
    belief = _toy_belief()
    rng = np.random.default_rng(0)

    t_idx, sat_idx = cnp_reimplementation_planner(rng, schedule, remaining_mask, instrument_sigma, belief, [], [], [])
    assert (t_idx, sat_idx) == (1, 0)  # t=2.0, SAT-A: margin=20, the global max


def test_fixed_cadence_picks_earliest_time_lowest_satellite_index():
    schedule = _toy_schedule()
    remaining_mask = schedule.visibility.copy()
    instrument_sigma = np.array([1.0, 1.0])
    belief = _toy_belief()
    rng = np.random.default_rng(0)

    t_idx, sat_idx = fixed_cadence_planner(rng, schedule, remaining_mask, instrument_sigma, belief, [], [], [])
    assert (t_idx, sat_idx) == (0, 0)


def test_classifier_entropy_matches_its_own_disagreement_formula():
    schedule = _toy_schedule()
    remaining_mask = schedule.visibility.copy()
    instrument_sigma = np.array([1.0, 2.0])
    belief = _toy_belief()
    rng = np.random.default_rng(0)

    t_idx, sat_idx = classifier_entropy_planner(rng, schedule, remaining_mask, instrument_sigma, belief, [], [], [])

    amp_est = _per_class_posterior_mean_amplitude(belief)
    cells = np.argwhere(remaining_mask)
    best_score, best_cell = -np.inf, None
    for i, j in cells:
        t, sigma = schedule.candidate_times_days[i], instrument_sigma[j]
        means = np.array([
            belief.flux_fn_resolver(cls)(np.array([t]), np.array([amp_est[k]]))[0]
            for k, cls in enumerate(belief.classes)
        ])
        score = np.var(means) / sigma ** 2
        if score > best_score:
            best_score, best_cell = score, (int(i), int(j))
    assert (t_idx, sat_idx) == best_cell


@pytest.mark.parametrize("name", list(STRATEGIES_P2.keys()))
def test_all_strategies_return_a_feasible_cell(name):
    schedule = _toy_schedule()
    remaining_mask = schedule.visibility.copy()
    instrument_sigma = np.array([1.0, 2.0])
    belief = _toy_belief()
    gp = SimpleGP()
    rng = np.random.default_rng(0)

    t_idx, sat_idx = STRATEGIES_P2[name](rng, schedule, remaining_mask, instrument_sigma, belief, [], [], [], gp)
    assert remaining_mask[t_idx, sat_idx]
