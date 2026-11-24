"""Phase E - the anytime-valid e-process on REAL ZTF events.

Replays Phase C (research/experiments/phaseC_replay.py) draw for draw: same
events, same noise seeds, same full strategy set (lambdas 0.25), so every
planner takes exactly the measurements Phase C reported. Adds, after each
measurement step, the universal-inference e-value

    log E_t = log p_GP(D_t) - max_{c, A on grid} log L(c, A; D_t)

with the Phase C alternative (amplitude-marginal GP, length scale 5 d) and the
Phase C null likelihood (two-band templates + model discrepancy). The grid
maximum is <= the true supremum, so E is slightly larger than the exact
universal-inference statistic (anti-conservative); declared, not corrected.

Usage:
  python -m research.experiments.phaseE_real_evalues --events fresh_cal --seed 1
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from pathlib import Path

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402

from research.experiments import phaseC_replay as C  # noqa: E402
from research.experiments.phase3_real_replay import split_events  # noqa: E402
from research.inference.bayes import ClosedWorldBelief  # noqa: E402
from research.inference.openworld import AmplitudeMarginalGP, open_world_posterior  # noqa: E402
from research.orbitsim.contacts import build_contact_schedule_historical  # noqa: E402
from research.orbitsim.geometry import radec_to_unit_eci  # noqa: E402
from research.planners.phase2 import MODE_SWITCH_TAU, fixed_cadence_planner  # noqa: E402
from research.transients.noise import assign_instruments, noise_sigma_from_limiting_magnitude  # noqa: E402
from research.transients.real_events import G_TIME_OFFSET_DAYS, MODELED_CLASSES, load_real_events  # noqa: E402
from research.util import atomic_write_json, git_commit_hash  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "research" / "results" / "phaseE"
PREREG = REPO_ROOT / "research" / "PREREGISTRATION_E.md"
LOCKED_SETS = ("test", "fresh_test")
E_STRATEGIES = ("P_open_world_eig", "B3_closed_world_eig", "L_lookahead_0.25")
LAMBDAS = [0.25]


def run_one_event_e(ev, seed_seq):
    """Identical control flow and RNG use to phaseC_replay.run_one_event_c."""
    S = C._STATE
    resolver, disc, archive, sat_names, strategies = S["resolver"], S["disc"], S["archive"], S["sat_names"], S["strategies"]
    rng = np.random.default_rng(seed_seq)
    schedule, _age = build_contact_schedule_historical(
        archive, sat_names, C.mjd_to_datetime(ev.t0_mjd), C.CANDIDATE_TIMES_DAYS,
        radec_to_unit_eci(ev.ra_deg, ev.dec_deg), C.MAX_TLE_AGE_DAYS, 0.0)
    schedule.visibility &= (C.CANDIDATE_TIMES_DAYS <= ev.last_time_with_truth)[:, None]
    if not schedule.visibility.any():
        return None
    instruments = assign_instruments(rng, schedule.satellite_names, C.LIMITING_MAGNITUDE_CHOICES)
    sigma = np.array([noise_sigma_from_limiting_magnitude(instruments[n]) for n in schedule.satellite_names])
    observed = ev.truth_flux(C.CANDIDATE_TIMES_DAYS)[:, None] + rng.normal(size=schedule.visibility.shape) * sigma[None, :]
    observed_g = ev.truth_flux_g(C.CANDIDATE_TIMES_DAYS)[:, None] + rng.normal(size=schedule.visibility.shape) * sigma[None, :]
    per = {}
    for (name, planner_fn), child in zip(strategies.items(), seed_seq.spawn(len(strategies))):
        belief = ClosedWorldBelief.with_uniform_prior(MODELED_CLASSES, C.AMPLITUDE_GRID, resolver)
        belief.discrepancy_resolver = disc
        log_prior_cell = float(belief.log_joint.flat[0])
        gp = AmplitudeMarginalGP(C.AMPLITUDE_GRID, lengthscale=C.GP_LENGTHSCALE)
        remaining = schedule.visibility.copy()
        t_obs, y_obs, s_obs, cells, log_e = [], [], [], [], []
        planner_rng = np.random.default_rng(child)
        is_ow = name in C.OPEN_WORLD or name.startswith("L_")
        streak, switch_step = 0, None
        for step in range(C.BUDGET):
            if not remaining.any():
                break
            fn = fixed_cadence_planner if (is_ow and switch_step is not None) else planner_fn
            i, j = fn(planner_rng, schedule, remaining, sigma, belief, t_obs, y_obs, s_obs, gp)
            remaining[: i + 1, :] = False
            t, s = float(C.CANDIDATE_TIMES_DAYS[i]), float(sigma[j])
            for tt, yy in ((t, float(observed[i, j])), (t + G_TIME_OFFSET_DAYS, float(observed_g[i, j]))):
                t_obs.append(tt); y_obs.append(yy); s_obs.append(s)
                belief.update(tt, yy, s)
            cells.append([int(i), int(j)])
            if name in E_STRATEGIES:
                lml = gp.log_marginal_likelihood(np.array(t_obs), np.array(y_obs), np.array(s_obs))
                log_e.append(float(lml - (float(np.max(belief.log_joint)) - log_prior_cell)))
            if is_ow and switch_step is None:
                post = open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp, np.array(s_obs))
                streak = streak + 1 if post["h0"] > MODE_SWITCH_TAU else 0
                if streak >= 2:
                    switch_step = step + 1
        if name in E_STRATEGIES:
            per[name] = {"cells": cells, "log_e": log_e}
    return {"oid": ev.oid, "true_class": ev.true_class, "withheld": ev.is_withheld, "strategies": per}


def _work(args):
    return run_one_event_e(*args)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", choices=("validation", "test", "fresh_cal", "fresh_test"), required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()
    if args.events in LOCKED_SETS and not PREREG.exists():
        raise SystemExit(f"{args.events} is locked until {PREREG.name} is committed.")
    t0 = time.time()
    if args.events.startswith("fresh"):
        events, _ = C.load_fresh_events(args.events)
    else:
        events = split_events(load_real_events(require_g=True)[0])[args.events]
    if not events:
        raise SystemExit(f"no events loaded for {args.events}: is research/data/raw populated?")
    C._init_worker(LAMBDAS)  # fail loudly here; a crashing pool initializer just respawns forever
    seeds = np.random.SeedSequence(args.seed).spawn(len(events))
    with mp.Pool(args.workers, initializer=C._init_worker, initargs=(LAMBDAS,)) as pool:
        out = pool.map(_work, list(zip(events, seeds)), chunksize=2)
    records = [r for r in out if r is not None]
    path = RESULTS_DIR / f"{args.events}_seed{args.seed}.json"
    atomic_write_json(str(path), {"meta": {"git_commit": git_commit_hash(), "events": args.events, "seed": args.seed,
                                           "n_events": len(records), "seconds": round(time.time() - t0, 1)},
                                  "events": records})
    print(f"wrote {path} ({len(records)} events)")


if __name__ == "__main__":
    main()
