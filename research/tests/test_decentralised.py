"""Phase 4 tests: ISL geometry and store-and-forward, e-value validity,
CRDT order-invariance, strategy limiting cases, shard merge."""

import json

import numpy as np
import pytest

from research.inference.evalues import log_e_value, log_mean_exp, max_null_log_likelihood
from research.inference.openworld import SimpleGP
from research.orbitsim.isl import component_closure, components, interval_reach, line_of_sight, link_adjacency
from research.transients.models import AMPLITUDE_RANGE, MODELED_CLASSES_P2, flux_for_class_p2, modeled_flux_fn_p2


# --- ISL -------------------------------------------------------------------
def test_line_of_sight_blocked_through_earth():
    p1 = np.array([7000.0, 0, 0]); p2 = np.array([-7000.0, 0, 0])
    assert not line_of_sight(p1, p2, 6451.0)
    p3 = np.array([7000.0, 1000.0, 0])
    assert line_of_sight(p1, p3, 6451.0)


def test_link_adjacency_range_and_zero():
    pos = np.array([[[7000.0, 0, 0], [7000.0, 500.0, 0], [7000.0, 3000.0, 0]]])
    adj = link_adjacency(pos, 1000.0)[0]
    assert adj[0, 1] and adj[1, 0] and not adj[0, 2] and not adj[0, 0]
    assert not link_adjacency(pos, 0.0).any()


def test_store_and_forward_respects_time_order():
    n = 3
    ab = np.zeros((n, n), bool); ab[0, 1] = ab[1, 0] = True
    bc = np.zeros((n, n), bool); bc[1, 2] = bc[2, 1] = True
    forward = interval_reach(np.stack([ab, bc]))   # A->B, then B->C: C learns A
    backward = interval_reach(np.stack([bc, ab]))  # B->C first: C cannot learn A
    assert forward[2, 0] and not backward[2, 0]
    assert backward[0, 1] and backward[1, 2]


def test_components_multihop():
    adj = np.zeros((4, 4), bool); adj[0, 1] = adj[1, 0] = adj[1, 2] = adj[2, 1] = True
    assert components(adj) == [[0, 1, 2], [3]]
    assert component_closure(adj)[0, 2]


# --- e-values ----------------------------------------------------------------
def test_null_sup_is_exact_over_amplitude():
    t = np.array([0.3, 0.8, 1.5]); s = np.ones(3)
    y = flux_for_class_p2("kilonova", t, 9.0) + np.array([0.2, -0.1, 0.3])
    fine = np.linspace(*AMPLITUDE_RANGE, 20001)
    brute = max(
        np.max([np.sum(-0.5 * np.log(2 * np.pi) - 0.5 * (y - flux_for_class_p2(c, t, a)) ** 2) for a in fine])
        for c in MODELED_CLASSES_P2)
    assert max_null_log_likelihood(t, y, s, MODELED_CLASSES_P2, modeled_flux_fn_p2) == pytest.approx(brute, abs=1e-6)


def test_anytime_false_alarm_controlled_under_null():
    """Ville: P(sup_t E_t >= 1/alpha) <= alpha when the data come from a modeled class."""
    rng = np.random.default_rng(0)
    gp, alpha, n_rep, times = SimpleGP(lengthscale=1.2), 0.1, 400, np.exp(np.linspace(np.log(0.05), np.log(10), 8))
    alarms = 0
    for _ in range(n_rep):
        c = MODELED_CLASSES_P2[rng.integers(4)]
        a = float(np.exp(rng.uniform(*np.log(AMPLITUDE_RANGE))))
        y = flux_for_class_p2(c, times, a) + rng.normal(size=len(times))
        sup = max(log_e_value(times[:k], y[:k], np.ones(k), MODELED_CLASSES_P2, modeled_flux_fn_p2, gp)
                  for k in range(1, len(times) + 1))
        alarms += sup >= np.log(1 / alpha)
    # alpha = 0.1, n = 400: allow 3 binomial SDs of slack
    assert alarms / n_rep <= alpha + 3 * np.sqrt(alpha * (1 - alpha) / n_rep)


def test_log_mean_exp():
    assert log_mean_exp([0.0, np.log(3.0)]) == pytest.approx(np.log(2.0))


# --- decentralised planner ---------------------------------------------------
@pytest.fixture(scope="module")
def small_episode():
    from research.experiments.phase2_single_planner import _fleet_subset
    from research.experiments.phase4_decentralised import build_episode
    from research.experiments.scenarios import SCENARIOS
    fleet = _fleet_subset(8)
    return build_episode(np.random.SeedSequence(123), fleet, SCENARIOS["S1_nominal"])


def _run(spec, ep):
    from research.experiments.phase4_decentralised import BETA, GAMMA, GP_LENGTHSCALE
    from research.inference.bayes import default_amplitude_grid
    from research.planners.decentralised import run_strategy
    episode, plan, _ = ep
    return run_strategy(spec, episode, plan, MODELED_CLASSES_P2, default_amplitude_grid(15), modeled_flux_fn_p2,
                        GP_LENGTHSCALE, BETA, GAMMA)


def test_belief_cache_order_invariant():
    from research.inference.bayes import default_amplitude_grid
    from research.planners.decentralised import BeliefCache
    store = {(0, 1, 0): (0.1, 5.0, 1.0), (0, 3, 2): (0.9, 3.0, 0.5), (0, 2, 1): (0.4, 4.0, 2.0)}
    c = BeliefCache(MODELED_CLASSES_P2, default_amplitude_grid(15), modeled_flux_fn_p2, store)
    b1 = c.get(0, frozenset(store))[0]
    c2 = BeliefCache(MODELED_CLASSES_P2, default_amplitude_grid(15), modeled_flux_fn_p2, dict(reversed(store.items())))
    b2 = c2.get(0, frozenset(reversed(list(store))))[0]
    np.testing.assert_allclose(b1.log_joint, b2.log_joint)


def test_no_links_auction_equals_knowledge_only(small_episode):
    from research.planners.decentralised import StrategySpec
    a = _run(StrategySpec("A_0", 0.0, True, 0.2), small_episode)
    k = _run(StrategySpec("K_0", 0.0, False, 0.2), small_episode)
    assert a["per_event"] == k["per_event"] and a["records_moved"] == 0


def test_oracle_has_no_staleness_and_respects_budget(small_episode):
    from research.planners.decentralised import IDEAL, SAT_BUDGET, StrategySpec
    o = _run(StrategySpec("O", IDEAL, True, 0.2), small_episode)
    assert o["mean_stale_fraction"] == 0.0
    assert o["budget_used"] <= 8 * SAT_BUDGET
    for pe in o["per_event"]:
        assert pe["obs_epochs"] == sorted(pe["obs_epochs"])


# --- sharding ----------------------------------------------------------------
def test_merge_rejects_mismatch_and_gaps(tmp_path):
    from research.experiments.merge_shards import merge
    meta = {"git_commit": "x", "python": "3", "numpy": "2", "split": "validation", "seed": 1, "n_episodes": 2,
            "scenario": "S1", "reserves": {}, "n_shards": 2, "n_events_per_episode": 4, "ranges_km": [1],
            "sat_budget": 3, "beta": 1, "gamma": 0.1, "gp_lengthscale": 1.2, "seconds": 1}
    for i in range(2):
        (tmp_path / f"shard_{i}of2.json").write_text(json.dumps({"meta": {**meta, "shard": i},
                                                                 "episodes": [{"episode_index": i}]}))
    assert [e["episode_index"] for e in merge(tmp_path)["episodes"]] == [0, 1]
    (tmp_path / "shard_1of2.json").write_text(json.dumps({"meta": {**meta, "shard": 1, "git_commit": "y"},
                                                          "episodes": [{"episode_index": 1}]}))
    with pytest.raises(SystemExit):
        merge(tmp_path)
