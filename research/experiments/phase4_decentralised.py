"""Phase 4 - decentralised follow-up by a fleet with inter-satellite links.

Each episode: N_EVENTS concurrent transients (Phase 2 classes, uniform over
modeled + withheld), alerted at t0 = REFERENCE_EPOCH + U[0, 1) d, 8 real-TLE
satellites, ISL ranges RANGES_KM. Every strategy sees the identical episode
(events, noise, instruments, geometry, links): paired comparison.

Sharding (several laptops): episodes are independent (one SeedSequence child
each), so `--shard i --n-shards N` runs the episodes with index % N == i and
the merged result is identical to a single-machine run.

Usage:
  python -m research.experiments.phase4_decentralised --split validation --seed 41 --n-episodes 100 --reserve 0.05
  python -m research.experiments.phase4_decentralised --split test --seed 4000 --n-episodes 250 --reserves-json research/results/phase4/reserves.json --shard 0 --n-shards 3
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from research.experiments.phase2_single_planner import (
    AMPLITUDE_GRID_SIZE, CANDIDATE_TIMES_DAYS, CONFIDENT_THRESHOLD, _belief_flux_fn_resolver, _fleet_subset,
)
from research.experiments.scenarios import SCENARIOS, class_prior_for_scenario
from research.inference.bayes import default_amplitude_grid
from research.orbitsim.contacts import REFERENCE_EPOCH, ContactSchedule
from research.orbitsim.geometry import random_sky_direction, visibility_margin_deg
from research.orbitsim.isl import epoch_link_plan
from research.planners.decentralised import SAT_BUDGET, default_strategies, run_strategy
from research.transients.models import MODELED_CLASSES_P2, WITHHELD_CLASSES_P2, flux_for_class_p2, sample_event_p2
from research.transients.noise import assign_instruments, noise_sigma_from_limiting_magnitude
from research.util import atomic_write_json, git_commit_hash

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "research" / "results" / "phase4"
PREREGISTRATION_PATH = REPO_ROOT / "research" / "PREREGISTRATION_H4.md"
TEST_SEED_MIN = 4000

N_EVENTS = 4
N_SATELLITES = 8
RANGES_KM = [1000.0, 2000.0, 3000.0, 5000.0]
BETA, GAMMA, GP_LENGTHSCALE = 1.0, 0.1, 1.2   # frozen by PREREGISTRATION_PHASE2.md
SCENARIO_FOR = {"nominal": "S1_nominal", "model_error": "S3_model_error"}


def build_episode(seed_seq: np.random.SeedSequence, fleet: dict, scenario_cfg: dict) -> tuple[dict, dict, list]:
    rng = np.random.default_rng(seed_seq)
    t0 = REFERENCE_EPOCH + datetime.timedelta(days=float(rng.uniform(0.0, 1.0)))
    prior = class_prior_for_scenario(scenario_cfg["withheld_weight"], MODELED_CLASSES_P2, WITHHELD_CLASSES_P2)
    events = [sample_event_p2(rng, prior) for _ in range(N_EVENTS)]
    dirs = [random_sky_direction(rng) for _ in range(N_EVENTS)]
    names = tuple(fleet.keys())
    inst = assign_instruments(rng, names, scenario_cfg["limiting_magnitude_choices"])
    sigma = np.array([noise_sigma_from_limiting_magnitude(inst[n]) for n in names])
    plan = epoch_link_plan(fleet, t0, CANDIDATE_TIMES_DAYS, RANGES_KM)
    pos = plan["epoch_positions"]  # (n_epochs, n_sats, 3)
    visible, schedules, observed = [], [], []
    for ev, d in zip(events, dirs):
        margin = np.array([[visibility_margin_deg(pos[k, j], d) if np.all(np.isfinite(pos[k, j])) else -180.0
                            for j in range(len(names))] for k in range(len(CANDIDATE_TIMES_DAYS))])
        vis = margin >= 0.0
        visible.append(vis)
        schedules.append(ContactSchedule(names, CANDIDATE_TIMES_DAYS, vis, margin, d))
        flux = flux_for_class_p2(ev.true_class, CANDIDATE_TIMES_DAYS, ev.amplitude)
        noise = rng.normal(size=vis.shape) * sigma[None, :]
        observed.append(flux[:, None] + noise)
    episode = {"epoch_times": CANDIDATE_TIMES_DAYS, "visible": visible, "schedules": schedules,
               "instrument_sigma": sigma, "observed": observed}
    return episode, plan, events


def _entropy(p: dict) -> float:
    v = np.array([x for x in p.values() if x > 0])
    return float(-np.sum(v * np.log(v)))


def run_episode(idx: int, seed_seq, scenario_name: str, reserves: dict) -> dict:
    scenario_cfg = SCENARIOS[scenario_name]
    fleet = _fleet_subset(N_SATELLITES)
    flux_res = _belief_flux_fn_resolver(scenario_cfg.get("model_error_factor", 1.0))
    grid = default_amplitude_grid(AMPLITUDE_GRID_SIZE)
    episode, plan, events = build_episode(seed_seq, fleet, scenario_cfg)
    out = {"episode_index": idx,
           "link_up_fraction": {str(int(r)): plan["by_range"][r]["link_up_fraction"] for r in RANGES_KM},
           "events": [{"true_class": ev.true_class, "amplitude": float(ev.amplitude),
                       "modeled": ev.true_class in MODELED_CLASSES_P2,
                       "n_visible_cells": int(episode["visible"][e].sum())} for e, ev in enumerate(events)],
           "strategies": {}}
    for spec in default_strategies(RANGES_KM, reserves):
        res = run_strategy(spec, episode, plan, MODELED_CLASSES_P2, grid, flux_res, GP_LENGTHSCALE, BETA, GAMMA)
        rows = []
        for e, ev in enumerate(events):
            pe = res["per_event"][e]
            ow = pe["ow_posterior"]
            decision = max(ow, key=ow.get)
            modeled = ev.true_class in MODELED_CLASSES_P2
            correct = decision == ev.true_class if modeled else decision == "h0"
            confident = ow[decision] >= CONFIDENT_THRESHOLD
            rows.append({"decision": decision, "correct": bool(correct),
                         "confident_wrong": bool(confident and not correct), "p_h0": ow["h0"],
                         "cw_entropy": _entropy(pe["cw_posterior"]), "n_obs": pe["n_obs"],
                         "duplicates": pe["duplicates"], "obs_epochs": pe["obs_epochs"],
                         "max_log_e_ground": pe["max_log_e_ground"], "max_log_e_union": pe["max_log_e_union"],
                         "max_log_e_mean": pe["max_log_e_mean"], "max_log_e_prod": pe["max_log_e_prod"]})
        out["strategies"][spec.name] = {"reserve": spec.reserve, "records_moved": res["records_moved"],
                                        "mean_stale_fraction": res["mean_stale_fraction"],
                                        "budget_used": res["budget_used"], "events": rows}
    return out


def _star(args):
    return run_episode(*args)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=("validation", "test"), required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-episodes", type=int, required=True)
    ap.add_argument("--scenario", choices=list(SCENARIO_FOR), default="nominal")
    ap.add_argument("--reserve", type=float, default=None, help="one reserve price for every strategy family")
    ap.add_argument("--reserves-json", type=str, default=None, help="per-family reserve prices {O,G,A,K: value}")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--tag", type=str, default="")
    args = ap.parse_args()

    if args.split == "validation" and args.seed >= TEST_SEED_MIN:
        sys.exit(f"validation seeds must be < {TEST_SEED_MIN}")
    if args.split == "test":
        if args.seed < TEST_SEED_MIN:
            sys.exit(f"test seeds must be >= {TEST_SEED_MIN}")
        if not PREREGISTRATION_PATH.exists():
            sys.exit(f"refusing test run: {PREREGISTRATION_PATH} does not exist (commit the preregistration first)")
        if args.reserves_json is None:
            sys.exit("test runs need --reserves-json (chosen on validation)")
    if args.reserves_json:
        reserves = json.loads(Path(args.reserves_json).read_text())["reserves"]
    else:
        r = args.reserve if args.reserve is not None else 0.0
        reserves = {f: r for f in ("O", "G", "A", "K")}
    if not 0 <= args.shard < args.n_shards:
        sys.exit("--shard must be in [0, n_shards)")

    scenario_name = SCENARIO_FOR[args.scenario]
    seeds = np.random.SeedSequence(args.seed).spawn(args.n_episodes)
    items = [(i, s, scenario_name, reserves) for i, s in enumerate(seeds) if i % args.n_shards == args.shard]
    t_start = time.time()
    if args.workers <= 1:
        records = [_star(it) for it in items]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            records = list(ex.map(_star, items, chunksize=1))
    records.sort(key=lambda r: r["episode_index"])

    run_name = args.tag or (f"{args.split}_{args.scenario}_seed{args.seed}_n{args.n_episodes}_"
                            + ("reservesjson" if args.reserves_json else f"r{reserves['O']:g}"))
    meta = {"git_commit": git_commit_hash(), "python": platform.python_version(), "numpy": np.__version__,
            "argv": sys.argv, "split": args.split, "seed": args.seed, "n_episodes": args.n_episodes,
            "scenario": scenario_name, "reserves": reserves, "shard": args.shard, "n_shards": args.n_shards,
            "n_events_per_episode": N_EVENTS, "ranges_km": RANGES_KM, "sat_budget": SAT_BUDGET,
            "beta": BETA, "gamma": GAMMA, "gp_lengthscale": GP_LENGTHSCALE,
            "seconds": round(time.time() - t_start, 1)}
    path = RESULTS_DIR / run_name / f"shard_{args.shard}of{args.n_shards}.json"
    atomic_write_json(str(path), {"meta": meta, "episodes": records})
    print(f"wrote {path} ({len(records)} episodes, {meta['seconds']} s)")


if __name__ == "__main__":
    main()
