"""Phase C - causal two-band real replay with a conformal open-set layer and
the lookahead planner L. Same pipeline and frozen v3 configuration as
Phase 6 (gr bands, discrepancy 0.5, h0 GP lengthscale 5 d, strictly
forward measurements); per-event noise is drawn exactly as in
phase3_real_replay.run_one_event, so B0-B3 and P reproduce Phase 6 on the
same split and seed.

New per strategy: the prior-free nonconformity score
s = log p(D|h0) - max_c log p(D|c), computed post hoc for EVERY strategy
(baselines included) from its own measurements, plus the closed-world
posterior. Conformal thresholds are applied in phaseC_analysis.py, never
here (this script never sees a threshold).

Event sets: validation / test (Phase 3 chronological split), fresh_cal /
fresh_test (research/data/fetch_fresh.py, never used before Phase C).
test and fresh_test are locked until research/PREREGISTRATION_C.md exists.

Usage:
  python -m research.experiments.phaseC_replay --events validation --seed 1 --n-events 100000 --lambdas 0.25 0.5 1
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import subprocess
import time
from pathlib import Path

import numpy as np

from research.data.fetch_fresh import FRESH_LC_DIR, FRESH_SELECTION
from research.experiments.phase3_real_replay import (CANDIDATE_TIMES_DAYS, CONFIDENT_THRESHOLD, LIMITING_MAGNITUDE_CHOICES,
                                                     MAX_TLE_AGE_DAYS, AMPLITUDE_GRID, load_fleet_archive,
                                                     mjd_to_datetime, split_events)
from research.inference.bayes import ClosedWorldBelief
from research.inference.conformal import log_bf_score
from research.inference.openworld import AmplitudeMarginalGP, open_world_posterior
from research.orbitsim.contacts import build_contact_schedule_historical
from research.orbitsim.geometry import radec_to_unit_eci
from research.planners.lookahead import make_lookahead_planner
from research.planners.phase2 import MODE_SWITCH_TAU, STRATEGIES_P2, fixed_cadence_planner
from research.transients.noise import assign_instruments, noise_sigma_from_limiting_magnitude
from research.transients.real_events import (G_TIME_OFFSET_DAYS, MODELED_CLASSES, RealEvent, build_class_scatter,
                                             build_class_templates, build_class_templates_g, discrepancy_resolver,
                                             load_real_events, parse_g_band, parse_lightcurve, sexagesimal_to_deg,
                                             two_band_flux_fn_resolver)
from research.util import atomic_write_json, config_hash, git_commit_hash

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "research" / "results" / "phaseC"
PREREG = REPO_ROOT / "research" / "PREREGISTRATION_C.md"
LOCKED_SETS = ("test", "fresh_test")
# Frozen v3 configuration (research/PREREGISTRATION_V3.md), not re-tuned here.
GP_LENGTHSCALE = 5.0
DISCREPANCY_SCALE = 0.5
BUDGET = 5
OPEN_WORLD = ("P_open_world_eig",)


def load_fresh_events(role: str) -> tuple[list[RealEvent], dict]:
    sel = json.loads(FRESH_SELECTION.read_text())["objects"]
    events, excluded = [], {"missing_download": 0, "too_few_r_detections": 0, "too_few_g_detections": 0}
    for obj in sel:
        if obj["role"] != role:
            continue
        path = FRESH_LC_DIR / f"{obj['oid']}.json"
        if not path.exists():
            excluded["missing_download"] += 1
            continue
        raw = json.loads(path.read_text())
        parsed = parse_lightcurve(raw)
        if parsed is None:
            excluded["too_few_r_detections"] += 1
            continue
        t0, t, f, e = parsed
        g = parse_g_band(raw, t0)
        if g is None:
            excluded["too_few_g_detections"] += 1
            continue
        ra, dec = sexagesimal_to_deg(obj["ra"], obj["dec"])
        events.append(RealEvent(obj["oid"], obj["cls"], obj["bts_type"], ra, dec, t0, t, f, e, *g))
    events.sort(key=lambda ev: (ev.t0_mjd, ev.oid))
    return events, excluded


_STATE: dict = {}


def _init_worker(lambdas: list[float]) -> None:
    events, _ = load_real_events(require_g=True)
    splits = split_events(events)
    templates = build_class_templates(splits["template"])
    _STATE["resolver"] = two_band_flux_fn_resolver(templates, build_class_templates_g(splits["template"]))
    _STATE["disc"] = discrepancy_resolver(build_class_scatter(splits["template"], "r"), DISCREPANCY_SCALE,
                                          build_class_scatter(splits["template"], "g"))
    _STATE["archive"], _STATE["sat_names"], _ = load_fleet_archive()
    strategies = dict(STRATEGIES_P2)
    for lam in lambdas:
        strategies[f"L_lookahead_{lam:g}"] = make_lookahead_planner(lam, BUDGET)
    _STATE["strategies"] = strategies


def run_one_event_c(ev: RealEvent, seed_seq: np.random.SeedSequence) -> dict | None:
    """Mirrors phase3_real_replay.run_one_event (bands="gr", causal=True)
    draw for draw; adds L strategies and the post-hoc score for everyone."""
    resolver, disc, archive, sat_names = _STATE["resolver"], _STATE["disc"], _STATE["archive"], _STATE["sat_names"]
    strategies = _STATE["strategies"]
    rng = np.random.default_rng(seed_seq)
    schedule, tle_age = build_contact_schedule_historical(
        archive, sat_names, mjd_to_datetime(ev.t0_mjd), CANDIDATE_TIMES_DAYS,
        radec_to_unit_eci(ev.ra_deg, ev.dec_deg), MAX_TLE_AGE_DAYS, 0.0)
    schedule.visibility &= (CANDIDATE_TIMES_DAYS <= ev.last_time_with_truth)[:, None]
    if not schedule.visibility.any():
        return None
    instruments = assign_instruments(rng, schedule.satellite_names, LIMITING_MAGNITUDE_CHOICES)
    instrument_sigma = np.array([noise_sigma_from_limiting_magnitude(instruments[n]) for n in schedule.satellite_names])
    true_flux = ev.truth_flux(CANDIDATE_TIMES_DAYS)
    observed = true_flux[:, None] + rng.normal(size=schedule.visibility.shape) * instrument_sigma[None, :]
    true_flux_g = ev.truth_flux_g(CANDIDATE_TIMES_DAYS)
    observed_g = true_flux_g[:, None] + rng.normal(size=schedule.visibility.shape) * instrument_sigma[None, :]

    per = {}
    for (name, planner_fn), child in zip(strategies.items(), seed_seq.spawn(len(strategies))):
        belief = ClosedWorldBelief.with_uniform_prior(MODELED_CLASSES, AMPLITUDE_GRID, resolver)
        belief.discrepancy_resolver = disc
        gp = AmplitudeMarginalGP(AMPLITUDE_GRID, lengthscale=GP_LENGTHSCALE)
        remaining = schedule.visibility.copy()
        t_obs, y_obs, s_obs, cells = [], [], [], []
        planner_rng = np.random.default_rng(child)
        is_ow = name in OPEN_WORLD or name.startswith("L_")
        streak, switch_step = 0, None
        for step in range(BUDGET):
            if not remaining.any():
                break
            fn = fixed_cadence_planner if (is_ow and switch_step is not None) else planner_fn
            i, j = fn(planner_rng, schedule, remaining, instrument_sigma, belief, t_obs, y_obs, s_obs, gp)
            remaining[: i + 1, :] = False
            t, s = float(CANDIDATE_TIMES_DAYS[i]), float(instrument_sigma[j])
            for tt, yy in ((t, float(observed[i, j])), (t + G_TIME_OFFSET_DAYS, float(observed_g[i, j]))):
                t_obs.append(tt); y_obs.append(yy); s_obs.append(s)
                belief.update(tt, yy, s)
            cells.append([int(i), int(j)])
            if is_ow and switch_step is None:
                post = open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp, np.array(s_obs))
                streak = streak + 1 if post["h0"] > MODE_SWITCH_TAU else 0
                if streak >= 2:
                    switch_step = step + 1
        closed = belief.class_posterior()
        h0_lml = gp.log_marginal_likelihood(np.array(t_obs), np.array(y_obs), np.array(s_obs))
        ow = open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp, np.array(s_obs))
        per[name] = {"n_obs_used": len(cells), "cells": cells, "closed_posterior": closed, "open_posterior": ow,
                     "score": log_bf_score(belief.class_log_evidence(), h0_lml), "mode_switch_step": switch_step}
    return {"oid": ev.oid, "true_class": ev.true_class, "withheld": ev.is_withheld, "t0_mjd": ev.t0_mjd,
            "n_visible_cells": int(schedule.visibility.sum()), "strategies": per}


def _work(args):
    ev, ss = args
    return run_one_event_c(ev, ss)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", choices=("validation", "test", "fresh_cal", "fresh_test"), required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-events", type=int, required=True)
    ap.add_argument("--lambdas", type=float, nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tag", default="")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    args = ap.parse_args()
    if args.events in LOCKED_SETS and not PREREG.exists():
        raise SystemExit(f"{args.events} is locked until {PREREG.name} is committed.")

    t_start = time.time()
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout
    commit = git_commit_hash()
    if args.events.startswith("fresh"):
        events, excluded = load_fresh_events(args.events)
    else:
        all_events, excluded = load_real_events(require_g=True)
        events = split_events(all_events)[args.events]
    chosen = events[: args.n_events]
    seeds = np.random.SeedSequence(args.seed).spawn(len(chosen))
    with mp.Pool(args.workers, initializer=_init_worker, initargs=(args.lambdas,)) as pool:
        out = []
        for k, rec in enumerate(pool.imap(_work, list(zip(chosen, seeds)), chunksize=2)):
            out.append(rec)
            if k % 50 == 0:
                print(f"[{k + 1}/{len(chosen)}]", flush=True)
    records = [r for r in out if r is not None]
    no_contact = [ev.oid for ev, r in zip(chosen, out) if r is None]

    config = {"events": args.events, "seed": args.seed, "n_events_requested": args.n_events, "lambdas": args.lambdas,
              "bands": "gr", "causal": True, "gp_lengthscale": GP_LENGTHSCALE, "discrepancy_scale": DISCREPANCY_SCALE,
              "budget": BUDGET, "confident_threshold": CONFIDENT_THRESHOLD, "tag": args.tag,
              "n_loaded": len(events), "exclusions": excluded, "no_feasible_contact": no_contact}
    out_dir = Path(args.results_dir) / f"{args.events}_seed{args.seed}{'_' + args.tag if args.tag else ''}"
    out_dir.mkdir(parents=True, exist_ok=True)
    prov = {"git_commit": commit, "config_hash": config_hash(config), "runtime_s": round(time.time() - t_start, 1)}
    if diff:
        prov["git_dirty"] = True
        (out_dir / "git_diff.patch").write_text(diff, encoding="utf-8")
    atomic_write_json(out_dir / "config.json", {**config, **prov})
    with open(out_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(records)} events to {out_dir} in {prov['runtime_s']} s")


if __name__ == "__main__":
    main()
