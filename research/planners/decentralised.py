"""Phase 4: a fleet of spacecraft plans follow-up of several concurrent
transients with only what each spacecraft currently knows.

Episode: N_EVENTS transients alerted at t0, each with its own sky direction,
class and amplitude; 8 real-TLE satellites, each with one instrument, at most
one measurement per epoch, and a budget of SAT_BUDGET measurements.

Knowledge is a grow-only set (a G-Set CRDT) of observation records
(event, epoch, satellite) -> (t, y, sigma). Merging is set union, so it is
commutative, associative and idempotent: a record can arrive twice, via any
path, in any order, and is never counted twice. Every belief is a
deterministic function of a set, so two spacecraft holding the same set hold
the same belief.

Strategies (all use P's frozen open-world utility, research.planners.phase2):
  O        oracle: ideal communication, one fleet-wide greedy auction
  A_R      auction: store-and-forward over ISLs of range R; at each epoch the
           members of each connected component pool knowledge and run a
           sequential greedy auction (the outcome a consensus auction such as
           CBBA converges to for a single round, Choi et al. 2009)
  K_R      knowledge only: same ISL knowledge sharing, but every spacecraft
           plans alone (no plan coordination)
  G        independent: no links (A_0 == K_0)
Within one auction, after spacecraft s wins event e, e's belief receives a
"believer" pseudo-observation at its predictive mean (as in batch Bayesian
optimisation) so the next bid on e sees diminishing returns.

A spacecraft spends a measurement only if the utility reaches its reserve
price (tuned per strategy on validation seeds).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from research.inference.bayes import ClosedWorldBelief
from research.inference.evalues import log_e_value
from research.inference.openworld import SimpleGP, open_world_posterior
from research.orbitsim.contacts import ContactSchedule
from research.planners.phase2 import open_world_utility_batch

SAT_BUDGET = 3
IDEAL = "ideal"


@dataclass(frozen=True)
class StrategySpec:
    name: str
    range_km: float | str   # km, 0 for none, or IDEAL
    coordinate: bool         # run an auction inside each connected component
    reserve: float = 0.0


def default_strategies(ranges_km: list[float], reserves: dict[str, float] | None = None) -> list[StrategySpec]:
    reserves = reserves or {}
    specs = [StrategySpec("O", IDEAL, True), StrategySpec("G", 0.0, True)]
    for r in ranges_km:
        specs.append(StrategySpec(f"A_{int(r)}", float(r), True))
        specs.append(StrategySpec(f"K_{int(r)}", float(r), False))
    return [StrategySpec(s.name, s.range_km, s.coordinate, reserves.get(family(s.name), 0.0)) for s in specs]


def family(name: str) -> str:
    return name.split("_")[0]


class BeliefCache:
    """Belief for (event, set of records), memoised; records are folded in
    sorted order so the result does not depend on arrival order."""

    def __init__(self, classes, amplitude_grid, flux_fn_resolver, store):
        self.classes, self.grid, self.flux = classes, amplitude_grid, flux_fn_resolver
        self.store = store
        self._cache: dict = {}

    def get(self, event: int, keys: frozenset):
        ck = (event, keys)
        if ck not in self._cache:
            b = ClosedWorldBelief.with_uniform_prior(classes=self.classes, amplitude_grid=self.grid,
                                                     flux_fn_resolver=self.flux)
            t, y, s = [], [], []
            for k in sorted(keys):
                tk, yk, sk = self.store[k]
                b.update(tk, yk, sk)
                t.append(tk); y.append(yk); s.append(sk)
            self._cache[ck] = (b, t, y, s)
        b, t, y, s = self._cache[ck]
        return b.copy(), list(t), list(y), list(s)


def predictive_mean(belief: ClosedWorldBelief, t: float) -> float:
    p = np.exp(belief.normalized_log_joint())
    means = np.stack([belief.flux_fn_resolver(c)(np.full_like(belief.amplitude_grid, t), belief.amplitude_grid)
                      for c in belief.classes])
    return float(np.sum(p * means))


def cell_utility(schedule_e: ContactSchedule, k: int, s: int, instrument_sigma, belief, t, y, sig, gp,
                 beta: float, gamma: float) -> float:
    mask = np.zeros_like(schedule_e.visibility)
    mask[k, s] = True
    _cells, u = open_world_utility_batch(schedule_e, mask, instrument_sigma, belief, t, y, sig, gp, beta, gamma)
    return float(u[0])


def greedy_auction(members, k, visible, budgets, known_keys_by_event, cache, schedules, instrument_sigma,
                   epoch_times, gp, beta, gamma, reserve):
    """Sequential greedy auction among `members` at epoch k. Returns list of
    (sat, event)."""
    n_events = len(schedules)
    state = {}
    for e in range(n_events):
        state[e] = cache.get(e, known_keys_by_event[e])
    bids = {}
    for s in members:
        if budgets[s] <= 0:
            continue
        for e in range(n_events):
            if visible[e][k, s]:
                b, t, y, sg = state[e]
                bids[(s, e)] = cell_utility(schedules[e], k, s, instrument_sigma, b, t, y, sg, gp, beta, gamma)
    out = []
    while bids:
        (s, e), u = max(bids.items(), key=lambda kv: (kv[1], -kv[0][0], -kv[0][1]))
        if u < reserve:
            break
        out.append((s, e))
        bids = {key: v for key, v in bids.items() if key[0] != s}
        b, t, y, sg = state[e]
        tk = float(epoch_times[k])
        y_hat = predictive_mean(b, tk)
        b.update(tk, y_hat, float(instrument_sigma[s]))  # believer pseudo-observation
        state[e] = (b, t + [tk], y + [y_hat], sg + [float(instrument_sigma[s])])
        for key in list(bids):
            if key[1] == e:
                bb, tt, yy, ss = state[e]
                bids[key] = cell_utility(schedules[e], k, key[0], instrument_sigma, bb, tt, yy, ss, gp, beta, gamma)
    return out


def run_strategy(spec: StrategySpec, episode: dict, link_plan: dict, classes, amplitude_grid, flux_fn_resolver,
                 gp_lengthscale: float, beta: float, gamma: float) -> dict:
    """Simulate one strategy on one episode. `episode` holds: epoch_times,
    visible (list per event of (n_epochs, n_sats) bool), schedules (per-event
    ContactSchedule), instrument_sigma, observed (list per event of
    (n_epochs, n_sats) noisy flux)."""
    epoch_times = episode["epoch_times"]
    visible, schedules = episode["visible"], episode["schedules"]
    sigma, observed = episode["instrument_sigma"], episode["observed"]
    n_epochs, n_sats = visible[0].shape
    n_events = len(visible)
    gp = SimpleGP(lengthscale=gp_lengthscale)
    store: dict = {}
    cache = BeliefCache(classes, amplitude_grid, flux_fn_resolver, store)

    known = [set() for _ in range(n_sats)]
    budgets = [SAT_BUDGET] * n_sats
    records_moved = 0
    duplicates = np.zeros(n_events, dtype=int)
    stale_frac = []
    # e-value traces: per event, per sat, running max of log E
    max_le_union = np.full((n_events, n_sats), 0.0)      # E on the spacecraft's CRDT set
    max_le_mean = np.full((n_events, n_sats), 0.0)       # mean of last-known own-data scalars
    max_le_prod = np.full((n_events, n_sats), 0.0)       # product of last-known CRDT-set scalars (foil)
    max_le_ground = np.zeros(n_events)                   # E on everything taken so far
    last_own = np.zeros((n_sats, n_sats, n_events))      # last_own[i, j, e] = log E_j(own data) known to i
    last_set = np.zeros((n_sats, n_sats, n_events))

    for k in range(n_epochs):
        # 1. store-and-forward sync over (t_{k-1}, t_k]
        if spec.range_km == IDEAL:
            reach = np.ones((n_sats, n_sats), dtype=bool)
            comps = [list(range(n_sats))]
        else:
            r = spec.range_km
            reach = link_plan["by_range"][r]["reach"][k] if r > 0 else np.eye(n_sats, dtype=bool)
            comps = link_plan["by_range"][r]["components"][k] if r > 0 else [[i] for i in range(n_sats)]
        new_known = [set().union(*[known[j] for j in np.flatnonzero(reach[i])]) for i in range(n_sats)]
        records_moved += sum(len(new_known[i] - known[i]) for i in range(n_sats))
        known = new_known
        if k > 0:
            for i in range(n_sats):
                js = np.flatnonzero(reach[i])
                last_own[i, js] = own_le_prev[js]
                last_set[i, js] = set_le_prev[js]
        if store:  # share of records already taken that each spacecraft does not yet know
            stale_frac.append(float(np.mean([1 - len(known[i]) / len(store) for i in range(n_sats)])))

        # 2. allocation
        groups = comps if spec.coordinate else [[i] for i in range(n_sats)]
        assignments = []
        for g in groups:
            g_keys = set().union(*[known[i] for i in g])
            by_event = [frozenset(x for x in g_keys if x[0] == e) for e in range(n_events)]
            assignments += greedy_auction(g, k, visible, budgets, by_event, cache, schedules, sigma, epoch_times,
                                          gp, beta, gamma, spec.reserve)

        # 3. measure
        per_event_count = np.zeros(n_events, dtype=int)
        for s, e in assignments:
            key = (e, k, s)
            store[key] = (float(epoch_times[k]), float(observed[e][k, s]), float(sigma[s]))
            known[s].add(key)
            budgets[s] -= 1
            per_event_count[e] += 1
        duplicates += np.clip(per_event_count - 1, 0, None)

        # 4. e-values at the end of epoch k
        own_le_prev = np.zeros((n_sats, n_events))
        set_le_prev = np.zeros((n_sats, n_events))
        for e in range(n_events):
            for i in range(n_sats):
                own = sorted(x for x in store if x[0] == e and x[2] == i)
                kn = sorted(x for x in known[i] if x[0] == e)
                own_le_prev[i, e] = _le(own, store, classes, flux_fn_resolver, gp)
                set_le_prev[i, e] = _le(kn, store, classes, flux_fn_resolver, gp)
            ground = sorted(x for x in store if x[0] == e)
            max_le_ground[e] = max(max_le_ground[e], _le(ground, store, classes, flux_fn_resolver, gp))
        for i in range(n_sats):
            last_own[i, i] = own_le_prev[i]
            last_set[i, i] = set_le_prev[i]
            for e in range(n_events):
                max_le_union[e, i] = max(max_le_union[e, i], set_le_prev[i, e])
                lo = last_own[i, :, e]
                m = float(np.max(lo))
                max_le_mean[e, i] = max(max_le_mean[e, i], m + float(np.log(np.mean(np.exp(lo - m)))))
                max_le_prod[e, i] = max(max_le_prod[e, i], float(np.sum(last_set[i, :, e])))

    # final ground decision per event, from every record taken
    per_event = []
    for e in range(n_events):
        keys = frozenset(x for x in store if x[0] == e)
        b, t, y, s = cache.get(e, keys)
        ow = open_world_posterior(b, np.array(t), np.array(y), gp, np.array(s) if s else None)
        per_event.append({"n_obs": len(keys), "ow_posterior": ow, "cw_posterior": b.class_posterior(),
                          "duplicates": int(duplicates[e]), "max_log_e_ground": float(max_le_ground[e]),
                          "max_log_e_union": max_le_union[e].tolist(), "max_log_e_mean": max_le_mean[e].tolist(),
                          "max_log_e_prod": max_le_prod[e].tolist(),
                          "obs_epochs": sorted(int(x[1]) for x in keys)})
    return {"per_event": per_event, "records_moved": int(records_moved),
            "mean_stale_fraction": float(np.mean(stale_frac)) if stale_frac else 0.0,
            "budget_used": int(n_sats * SAT_BUDGET - sum(budgets))}


def _le(keys, store, classes, flux_fn_resolver, gp) -> float:
    if not keys:
        return 0.0
    t = [store[x][0] for x in keys]
    y = [store[x][1] for x in keys]
    s = [store[x][2] for x in keys]
    return log_e_value(t, y, s, classes, flux_fn_resolver, gp)
