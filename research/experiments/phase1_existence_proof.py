"""Phase 1 — existence proof.

2 modeled classes ("fast", "slow") + 1 withheld class ("bump"), simple
parametric light-curve models, no orbits. Compares three strategies on
IDENTICAL events/noise (paired by seed):

  random               - B0-style: next measurement time chosen uniformly at random
  B3_closed_world_eig  - closed-world expected-information-gain planner (no h0)
  P_open_world_eig     - expected-information-gain planner that also models h0

Writes:
  <out-dir>/config.json          (committed)
  <out-dir>/summary.json         (committed)
  <out-dir>/worked_example.json  (committed - one illustrative event per class)
  <out-dir>/events_raw.jsonl     (gitignored - full per-event trajectories)
  research/results/progress.json (gitignored - live status for the viewer app)

Usage:
  python -m research.experiments.phase1_existence_proof --seed 0 --n-events 100 --tag demo
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import time

import numpy as np

from research.inference.bayes import ClosedWorldBelief, default_amplitude_grid
from research.inference.openworld import SimpleGP, open_world_posterior
from research.planners.baselines import random_planner
from research.planners.eig_planner import closed_world_eig_planner
from research.planners.openworld_planner import open_world_eig_planner
from research.transients.models import (
    ALL_CLASSES,
    MODELED_CLASSES,
    WITHHELD_CLASS,
    flux_for_class,
    sample_event,
)
from research.transients.noise import SIGMA0, draw_noise_grid
from research.util import atomic_write_json, config_hash, git_commit_hash, seed_for

CANDIDATE_TIMES = np.exp(np.linspace(np.log(0.2), np.log(10.0), 20))
N_OBS_BUDGET = 5
CONFIDENT_THRESHOLD = 0.9
AMPLITUDE_GRID_SIZE = 25

STRATEGIES = {
    "random": random_planner,
    "B3_closed_world_eig": closed_world_eig_planner,
    "P_open_world_eig": open_world_eig_planner,
}


def _run_one_strategy(planner_fn, planner_rng, event, candidate_times, observed_grid, amplitude_grid):
    belief = ClosedWorldBelief.with_uniform_prior(amplitude_grid=amplitude_grid)
    gp = SimpleGP()
    remaining_mask = np.ones(len(candidate_times), dtype=bool)
    t_obs: list[float] = []
    y_obs: list[float] = []
    history = []

    for _ in range(N_OBS_BUDGET):
        idx = planner_fn(planner_rng, candidate_times, remaining_mask, belief, np.array(t_obs), np.array(y_obs), gp)
        remaining_mask[idx] = False
        t = float(candidate_times[idx])
        y = float(observed_grid[idx])
        t_obs.append(t)
        y_obs.append(y)
        belief.update(t, y, SIGMA0)
        history.append({
            "t": t,
            "y": y,
            "class_posterior": belief.class_posterior(),
            "open_world_posterior": open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp),
        })

    has_h0 = planner_fn is open_world_eig_planner
    if has_h0:
        final_post = open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp)
    else:
        final_post = belief.class_posterior()

    decision = max(final_post, key=final_post.get)
    max_prob = final_post[decision]

    if event.true_class in MODELED_CLASSES:
        correct = decision == event.true_class
    else:
        correct = decision == "h0" if has_h0 else False

    confident = max_prob >= CONFIDENT_THRESHOLD
    return {
        "t_obs": t_obs,
        "y_obs": y_obs,
        "final_posterior": final_post,
        "decision": decision,
        "max_posterior": max_prob,
        "confident": bool(confident),
        "correct": bool(correct),
        "confident_wrong": bool(confident and not correct),
        "history": history,
    }


def run(seed: int, n_events: int, out_dir: str, tag: str, progress_file: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    amplitude_grid = default_amplitude_grid(AMPLITUDE_GRID_SIZE)
    ss = np.random.SeedSequence(seed)
    event_seeds = ss.spawn(n_events)

    config = {
        "phase": "phase1_existence_proof",
        "seed": seed,
        "n_events": n_events,
        "n_obs_budget": N_OBS_BUDGET,
        "confident_threshold": CONFIDENT_THRESHOLD,
        "sigma0": SIGMA0,
        "candidate_times": CANDIDATE_TIMES.tolist(),
        "amplitude_grid_size": AMPLITUDE_GRID_SIZE,
        "modeled_classes": list(MODELED_CLASSES),
        "withheld_class": WITHHELD_CLASS,
        "strategies": list(STRATEGIES.keys()),
        "tag": tag,
    }
    cfg_hash = config_hash(config)
    commit = git_commit_hash()

    raw_path = os.path.join(out_dir, "events_raw.jsonl")
    worked_example: dict[str, dict] = {}

    per_strategy_records = {name: [] for name in STRATEGIES}

    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(raw_path, "w", encoding="utf-8") as raw_f:
        for i in range(n_events):
            event_rng = np.random.default_rng(event_seeds[i])
            event = sample_event(event_rng)
            noise = draw_noise_grid(event_rng, len(CANDIDATE_TIMES), SIGMA0)
            true_flux = flux_for_class(event.true_class, CANDIDATE_TIMES, event.amplitude)
            observed_grid = true_flux + noise

            event_record = {
                "event_index": i,
                "true_class": event.true_class,
                "amplitude": event.amplitude,
                "strategies": {},
            }

            for name, planner_fn in STRATEGIES.items():
                planner_rng = np.random.default_rng(seed_for(seed, i, name))
                result = _run_one_strategy(
                    planner_fn, planner_rng, event, CANDIDATE_TIMES, observed_grid, amplitude_grid
                )
                event_record["strategies"][name] = result
                per_strategy_records[name].append(result | {
                    "true_class": event.true_class, "amplitude": event.amplitude,
                })

                if event.true_class not in worked_example and name == "P_open_world_eig":
                    worked_example[event.true_class] = {
                        "event_index": i,
                        "true_class": event.true_class,
                        "amplitude": event.amplitude,
                        "history": result["history"],
                        "final_posterior": result["final_posterior"],
                        "decision": result["decision"],
                    }

            raw_f.write(json.dumps(event_record) + "\n")

            if (i + 1) % max(1, n_events // 20) == 0 or (i + 1) == n_events:
                atomic_write_json(progress_file, {
                    "phase": "phase1_existence_proof",
                    "mode": tag,
                    "seed": seed,
                    "events_done": i + 1,
                    "n_events": n_events,
                    "status": "running" if (i + 1) < n_events else "done",
                    "started_at": started_at,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })

    summary = {
        "config": config,
        "config_hash": cfg_hash,
        "git_commit": commit,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "strategies": {},
    }

    for name, records in per_strategy_records.items():
        n = len(records)
        modeled = [r for r in records if r["true_class"] in MODELED_CLASSES]
        withheld = [r for r in records if r["true_class"] == WITHHELD_CLASS]

        def rate(rs, key):
            return float(np.mean([r[key] for r in rs])) if rs else float("nan")

        summary["strategies"][name] = {
            "n_events": n,
            "confident_wrong_rate_overall": rate(records, "confident_wrong"),
            "confident_wrong_rate_modeled": rate(modeled, "confident_wrong"),
            "confident_wrong_rate_withheld": rate(withheld, "confident_wrong"),
            "accuracy_modeled": rate(modeled, "correct"),
            "accuracy_withheld": rate(withheld, "correct"),
            "mean_max_posterior": float(np.mean([r["max_posterior"] for r in records])),
            "mean_confident_rate": rate(records, "confident"),
        }

    atomic_write_json(os.path.join(out_dir, "config.json"), config)
    atomic_write_json(os.path.join(out_dir, "summary.json"), summary)
    atomic_write_json(os.path.join(out_dir, "worked_example.json"), {
        "config_hash": cfg_hash, "git_commit": commit, "examples": worked_example,
    })

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--n-events", type=int, required=True)
    parser.add_argument("--out-dir", type=str, default="research/results/phase1")
    parser.add_argument("--tag", type=str, default="full", choices=["demo", "full"])
    parser.add_argument("--progress-file", type=str, default="research/results/progress.json")
    args = parser.parse_args()

    t0 = time.time()
    summary = run(args.seed, args.n_events, args.out_dir, args.tag, args.progress_file)
    elapsed = time.time() - t0
    print(f"Phase 1 ({args.tag}) done in {elapsed:.1f}s. Summary written to {args.out_dir}/summary.json")
    for name, stats in summary["strategies"].items():
        print(f"  {name}: confident_wrong_rate_withheld={stats['confident_wrong_rate_withheld']:.3f} "
              f"confident_wrong_rate_modeled={stats['confident_wrong_rate_modeled']:.3f} "
              f"accuracy_withheld={stats['accuracy_withheld']:.3f}")


if __name__ == "__main__":
    main()
