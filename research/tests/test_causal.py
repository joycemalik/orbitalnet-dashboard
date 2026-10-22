"""Causality (Phase 2c / Phase 6): measurements are strictly forward in time,
and turning the flag off reproduces the original time-unordered behaviour."""

import datetime

import numpy as np
import pytest

from research.experiments import phase2_single_planner as p2
from research.experiments import phase3_real_replay as p3
from research.experiments.scenarios import SCENARIOS
from research.inference.bayes import ClosedWorldBelief, default_amplitude_grid
from research.planners.phase2 import STRATEGIES_P2
from research.tests.test_phase3_real import _archive_from_repo_tles, _event
from research.transients.models import AMPLITUDE_RANGE, MODELED_CLASSES_P2, flux_for_class_p2, modeled_flux_fn_p2
from research.transients.real_events import build_class_templates, template_flux_fn_resolver


@pytest.fixture(scope="module")
def p2_records():
    fleet = p2._fleet_subset(8)
    grid = default_amplitude_grid(p2.AMPLITUDE_GRID_SIZE)
    seeds = np.random.SeedSequence(11).spawn(6)
    return [p2.run_one_event(s, fleet, SCENARIOS["S1_nominal"], grid) for s in seeds]


def test_phase2_measurements_strictly_forward(p2_records):
    for rec in p2_records:
        for name, s in rec["strategies"].items():
            assert all(b > a for a, b in zip(s["t_obs"], s["t_obs"][1:])), (name, s["t_obs"])


def test_phase2_strategies_share_event_and_include_ablations(p2_records):
    names = set(p2_records[0]["strategies"])
    assert set(STRATEGIES_P2) <= names and {"P_no_decay", "P_no_adequacy"} <= names
    for rec in p2_records:
        for s in rec["strategies"].values():
            assert s["n_obs_used"] <= p2.N_OBS_BUDGET


def test_phase2_time_to_id_refers_to_true_class(p2_records):
    for rec in p2_records:
        for s in rec["strategies"].values():
            if not rec["modeled"]:
                assert s["time_to_id_days"] is None
            elif s["time_to_id_days"] is not None:
                assert s["time_to_id_days"] == s["t_obs"][s["time_to_id_step"] - 1]
            # confident AND correct at the end implies the true class reached the threshold
            if rec["modeled"] and s["confident"] and s["correct"]:
                assert s["time_to_id_days"] is not None


def test_amplitude_information_fisher_known_answer():
    t, sigma, amp = 0.5, 0.4, 10.0
    f = float(flux_for_class_p2("kilonova", np.array([t]), amp)[0])
    var = np.log(AMPLITUDE_RANGE[1] / AMPLITUDE_RANGE[0]) ** 2 / 12.0
    expected = 0.5 * np.log(1.0 + var * (f / sigma) ** 2)
    assert p2.amplitude_information_fisher("kilonova", amp, [t], [sigma]) == pytest.approx(expected)
    assert p2.amplitude_information_fisher("kilonova", amp, [], []) == 0.0


def test_amplitude_information_grid_is_zero_at_prior_and_bounded():
    grid = default_amplitude_grid(p2.AMPLITUDE_GRID_SIZE)
    b = ClosedWorldBelief.with_uniform_prior(MODELED_CLASSES_P2, grid, modeled_flux_fn_p2)
    assert p2.amplitude_information_grid(b, "flare") == pytest.approx(0.0, abs=1e-12)
    b.update(0.5, float(flux_for_class_p2("kilonova", np.array([0.5]), 10.0)[0]), 0.05)
    info = p2.amplitude_information_grid(b, "kilonova")
    assert 0.0 < info <= np.log(len(grid)) + 1e-12


def test_phase2_non_causal_flag_allows_backward_steps():
    fleet = p2._fleet_subset(8)
    grid = default_amplitude_grid(p2.AMPLITUDE_GRID_SIZE)
    went_back = False
    for s in np.random.SeedSequence(7).spawn(5):
        rec = p2.run_one_event(s, fleet, SCENARIOS["S1_nominal"], grid, causal=False)
        went_back |= any(any(b < a for a, b in zip(v["t_obs"], v["t_obs"][1:])) for v in rec["strategies"].values())
    assert went_back


def _replay_fixture(monkeypatch):
    archive, names, epoch = _archive_from_repo_tles(n=8)
    mjd = (epoch - datetime.datetime(1858, 11, 17, tzinfo=datetime.timezone.utc)).total_seconds() / 86400.0
    monkeypatch.setattr(p3, "MAX_TLE_AGE_DAYS", 1e9)
    templates = build_class_templates([_event(f"{c}{i}", c, 58000.0, tau=t)
                                       for c, t in (("sn_ia", 8), ("sn_ii", 60), ("sn_ibc", 20)) for i in range(2)])
    return archive, names, template_flux_fn_resolver(templates), _event("z", "sn_ibc", mjd)


def test_replay_causal_is_forward_and_default_is_unchanged(monkeypatch):
    archive, names, resolver, ev = _replay_fixture(monkeypatch)
    causal = p3.run_one_event(ev, np.random.SeedSequence(7), archive, names, resolver, causal=True)
    for s in causal["strategies"].values():
        ts = [h["t"] for h in s["history"]]
        assert all(b > a for a, b in zip(ts, ts[1:]))
    default = p3.run_one_event(ev, np.random.SeedSequence(7), archive, names, resolver)
    explicit = p3.run_one_event(ev, np.random.SeedSequence(7), archive, names, resolver, causal=False)
    assert default == explicit
