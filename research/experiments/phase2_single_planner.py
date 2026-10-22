"""Phase 2 - single-planner experiment with real orbits (causal rebuild).

Realigned to Hypothesis-Discriminating Observation Campaigns....pdf
("the manuscript"): 4 modeled classes (kilonova, shock-cooling, GRB
afterglow, M-dwarf flare) + 3 withheld classes (FBOT, TDE, synthetic
nonsense), instrument noise from limiting magnitudes, feasibility from real
SGP4-based visibility (research.orbitsim), strategies B0 fixed-cadence, B1 CNP
reimplementation, B2 classifier-entropy, B3 closed-world EIG, P open-world EIG
with the manuscript's beta/gamma utility and mode switch, plus two ablations of
P (no decay term; no adequacy term, h0 kept in the belief), across 3 scenarios
(research.experiments.scenarios: Nominal, Crowding, Model error).

Causality (2026-10-22): measurements are strictly forward in time. After a
measurement at candidate epoch i, epochs <= i are closed for that strategy.
The first build let planners pick any unused (epoch, satellite) cell, so ~95%
of adaptive sequences went backwards in time (research/LOG.md, Phase 2c).

Usage:
  python -m research.experiments.phase2_single_planner --split validation --seed 1 --n-events 300
  python -m research.experiments.phase2_single_planner --split test --seed 1000 --n-events 1000  (needs PREREGISTRATION_PHASE2.md)
"""

from __future__ import annotations

import argparse
import datetime
import functools
import json
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from research.experiments.metrics import auroc, log_score, posterior_mean_amplitude
from research.experiments.scenarios import SCENARIOS, class_prior_for_scenario
from research.inference.bayes import ClosedWorldBelief, default_amplitude_grid
from research.inference.openworld import GP_LENGTHSCALE, SimpleGP, open_world_posterior
from research.orbitsim.contacts import build_contact_schedule
from research.orbitsim.tle import load_tle_subset
from research.planners.phase2 import (
    DEFAULT_BETA,
    DEFAULT_GAMMA,
    MODE_SWITCH_TAU,
    STRATEGIES_P2,
    fixed_cadence_planner,
    open_world_eig_planner_p2,
)
from research.transients.models import (
    AMPLITUDE_RANGE,
    MODELED_CLASSES_P2,
    SPEED_GROUP_P2,
    WITHHELD_CLASSES_P2,
    flux_for_class_p2,
    modeled_flux_fn_p2,
    modeled_flux_fn_p2_perturbed,
    sample_event_p2,
)
from research.transients.noise import assign_instruments, noise_sigma_from_limiting_magnitude
from research.util import atomic_write_json, config_hash, git_commit_hash

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TLE_PATH = REPO_ROOT / "satellites.txt"
RESULTS_DIR = REPO_ROOT / "research" / "results" / "phase2"
PREREGISTRATION_PATH = REPO_ROOT / "research" / "PREREGISTRATION_PHASE2.md"
FLEET_POOL_SIZE = 20  # covers the largest scenario's n_satellites with margin

# The manuscript's modeled classes span minutes (M-dwarf flare) to weeks (TDE,
# withheld), which a 0.2-10 day grid cannot represent.
CANDIDATE_TIMES_DAYS = np.exp(np.linspace(np.log(0.01), np.log(20.0), 16))
N_OBS_BUDGET = 5
AMPLITUDE_GRID_SIZE = 15
CONFIDENT_THRESHOLD = 0.95  # manuscript H1: 95% posterior
# Prior variance of ln(amplitude): log-uniform draw on AMPLITUDE_RANGE.
LN_AMP_PRIOR_VAR = float(np.log(AMPLITUDE_RANGE[1] / AMPLITUDE_RANGE[0]) ** 2 / 12.0)

# Seed discipline: validation seeds < 1000, test seeds >= 1000. Test seeds are
# refused until PREREGISTRATION_PHASE2.md exists.
TEST_SEED_MIN = 1000

OPEN_WORLD_PREFIX = "P_"


def build_strategies(beta: float = DEFAULT_BETA, gamma: float = DEFAULT_GAMMA) -> dict:
    """The five manuscript strategies plus two ablations of P (manuscript
    "Ablations": no decay term; no inadequacy term but h0 kept in the belief).
    Every name starting with P_ keeps h0 in its posterior and its mode switch."""
    strategies = {k: v for k, v in STRATEGIES_P2.items() if k != "P_open_world_eig"}
    strategies["P_open_world_eig"] = functools.partial(open_world_eig_planner_p2, beta=beta, gamma=gamma)
    strategies["P_no_decay"] = functools.partial(open_world_eig_planner_p2, beta=beta, gamma=0.0)
    strategies["P_no_adequacy"] = functools.partial(open_world_eig_planner_p2, beta=0.0, gamma=gamma)
    return strategies


_FLEET_POOL = None


def _fleet_pool() -> dict:
    global _FLEET_POOL
    if _FLEET_POOL is None:
        _FLEET_POOL = load_tle_subset(str(TLE_PATH), max_satellites=FLEET_POOL_SIZE)
    return _FLEET_POOL


def _fleet_subset(n_satellites: int) -> dict:
    pool = _fleet_pool()
    names = list(pool.keys())[:n_satellites]
    return {name: pool[name] for name in names}


def _belief_flux_fn_resolver(model_error_factor: float):
    if model_error_factor == 1.0:
        return modeled_flux_fn_p2
    return lambda cls: modeled_flux_fn_p2_perturbed(cls, model_error_factor)


def _entropy(posterior: dict) -> float:
    p = np.array([v for v in posterior.values() if v > 0], dtype=float)
    return float(-np.sum(p * np.log(p)))


def amplitude_information_fisher(true_class: str, amplitude: float, t_obs, sigma_obs) -> float:
    """Information recovered about ln(amplitude) under the TRUE class, in nats:
    0.5 * ln(1 + Var_prior(ln A) * sum_i SNR_i^2), SNR_i = f_true(t_i)/sigma_i.
    This is the Gaussian-channel (Fisher) information about ln A, evaluated on
    the noise-free true signal, so it depends only on WHEN and WITH WHICH
    instrument a strategy measured -- the quantity the decay term targets."""
    if len(t_obs) == 0:
        return 0.0
    f = flux_for_class_p2(true_class, np.asarray(t_obs, dtype=float), amplitude)
    snr2 = float(np.sum((f / np.asarray(sigma_obs, dtype=float)) ** 2))
    return 0.5 * float(np.log1p(LN_AMP_PRIOR_VAR * snr2))


def amplitude_information_grid(belief: ClosedWorldBelief, true_class: str) -> float:
    """Entropy reduction (nats) of the amplitude-grid posterior conditional on
    the true class. Saturates at ln(grid size) once one grid point dominates."""
    row = belief.log_joint[belief.classes.index(true_class)]
    p = np.exp(row - np.max(row))
    p = p / p.sum()
    nz = p[p > 0]
    return float(np.log(len(row)) + np.sum(nz * np.log(nz)))


def run_one_event(event_seed_seq: np.random.SeedSequence, fleet: dict, scenario_cfg: dict,
                  amplitude_grid: np.ndarray, strategies: dict | None = None,
                  gp_lengthscale: float = GP_LENGTHSCALE, causal: bool = True) -> dict:
    strategies = strategies if strategies is not None else build_strategies()
    event_rng = np.random.default_rng(event_seed_seq)
    class_prior = class_prior_for_scenario(scenario_cfg["withheld_weight"], MODELED_CLASSES_P2, WITHHELD_CLASSES_P2)
    event = sample_event_p2(event_rng, class_prior)

    schedule = build_contact_schedule(fleet, CANDIDATE_TIMES_DAYS, event_rng)
    instruments = assign_instruments(event_rng, schedule.satellite_names, scenario_cfg["limiting_magnitude_choices"])
    instrument_sigma = np.array([noise_sigma_from_limiting_magnitude(instruments[n]) for n in schedule.satellite_names])

    # Crowding (S2): a fixed random fraction of (time, satellite) cells are
    # made infeasible, standing in for other events competing for the same
    # instruments. Applied once per event, shared by every strategy below,
    # so the comparison stays paired.
    crowding_fraction = scenario_cfg.get("crowding_fraction", 0.0)
    base_visibility = schedule.visibility.copy()
    if crowding_fraction > 0:
        keep = event_rng.uniform(size=base_visibility.shape) >= crowding_fraction
        base_visibility = base_visibility & keep

    true_flux = flux_for_class_p2(event.true_class, CANDIDATE_TIMES_DAYS, event.amplitude)
    noise_matrix = event_rng.normal(size=schedule.visibility.shape) * instrument_sigma[None, :]
    observed_matrix = true_flux[:, None] + noise_matrix

    belief_flux_fn_resolver = _belief_flux_fn_resolver(scenario_cfg.get("model_error_factor", 1.0))
    is_modeled_truth = event.true_class in MODELED_CLASSES_P2

    # Each strategy's planner gets its own independently-spawned sub-stream
    # while every strategy still sees IDENTICAL events/noise/visibility/crowding
    # above (paired-by-seed comparison).
    strategy_items = list(strategies.items())
    strategy_child_seeds = event_seed_seq.spawn(len(strategy_items))

    per_strategy = {}
    for (name, planner_fn), child_seed in zip(strategy_items, strategy_child_seeds):
        belief = ClosedWorldBelief.with_uniform_prior(
            classes=MODELED_CLASSES_P2, amplitude_grid=amplitude_grid, flux_fn_resolver=belief_flux_fn_resolver
        )
        gp = SimpleGP(lengthscale=gp_lengthscale)
        remaining_mask = base_visibility.copy()
        t_obs, y_obs, sigma_obs = [], [], []
        history = []
        planner_rng = np.random.default_rng(child_seed)

        is_open_world = name.startswith(OPEN_WORLD_PREFIX)
        consecutive_h0_above_tau = 0
        mode_switch_step = None

        for step in range(N_OBS_BUDGET):
            if not remaining_mask.any():
                break
            active_planner = planner_fn
            if is_open_world and mode_switch_step is not None:
                # Manuscript 5.5: preservation mode drops discrimination
                # terms and instead maximizes coverage -- approximated here
                # by falling back to B0's fixed-cadence selection among
                # whatever cells remain feasible.
                active_planner = fixed_cadence_planner
            i, j = active_planner(planner_rng, schedule, remaining_mask, instrument_sigma, belief, t_obs, y_obs, sigma_obs, gp)
            remaining_mask[i, j] = False
            if causal:
                remaining_mask[: i + 1, :] = False  # strictly forward in time
            t, y, sigma = float(CANDIDATE_TIMES_DAYS[i]), float(observed_matrix[i, j]), float(instrument_sigma[j])
            t_obs.append(t)
            y_obs.append(y)
            sigma_obs.append(sigma)
            belief.update(t, y, sigma)

            posterior_now = (
                open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp, np.array(sigma_obs))
                if is_open_world
                else belief.class_posterior()
            )
            history.append({"t": t, "posterior": posterior_now})

            if is_open_world and mode_switch_step is None:
                if posterior_now.get("h0", 0.0) > MODE_SWITCH_TAU:
                    consecutive_h0_above_tau += 1
                    if consecutive_h0_above_tau >= 2:
                        mode_switch_step = step + 1  # 1-based
                else:
                    consecutive_h0_above_tau = 0

        final_post = history[-1]["posterior"] if history else {c: 1.0 / len(belief.classes) for c in belief.classes}
        closed_world_final = belief.class_posterior()

        decision = max(final_post, key=final_post.get)
        max_prob = final_post[decision]
        if is_modeled_truth:
            correct = decision == event.true_class
        else:
            correct = (decision == "h0") if is_open_world else False
        confident = max_prob >= CONFIDENT_THRESHOLD

        # H1: first measurement time at which the posterior on the TRUE class
        # reaches the threshold (modeled truth only); None = censored.
        tti_days, tti_step = None, None
        if is_modeled_truth:
            for k, h in enumerate(history, start=1):
                if h["posterior"].get(event.true_class, 0.0) >= CONFIDENT_THRESHOLD:
                    tti_days, tti_step = h["t"], k
                    break

        per_strategy[name] = {
            "n_obs_used": len(t_obs),
            "t_obs": t_obs,
            "sigma_obs": sigma_obs,
            "decision": decision,
            "max_posterior": max_prob,
            "confident": bool(confident),
            "correct": bool(correct),
            "confident_wrong": bool(confident and not correct),
            "log_score": log_score(final_post, event.true_class, MODELED_CLASSES_P2),
            "time_to_id_days": tti_days,
            "time_to_id_step": tti_step,
            "p_true_final": final_post.get(event.true_class) if is_modeled_truth else final_post.get("h0"),
            "amp_info_fisher": (amplitude_information_fisher(event.true_class, event.amplitude, t_obs, sigma_obs)
                                if is_modeled_truth else None),
            "amp_info_grid": amplitude_information_grid(belief, event.true_class) if is_modeled_truth else None,
            "amp_estimate": posterior_mean_amplitude(belief),
            "cw_entropy_final": _entropy(closed_world_final),
            "p_h0_final": final_post.get("h0") if is_open_world else None,
            "mode_switch_step": mode_switch_step,
        }

    return {"true_class": event.true_class, "amplitude": event.amplitude,
            "modeled": is_modeled_truth, "speed_group": SPEED_GROUP_P2.get(event.true_class),
            "n_visible_cells": int(base_visibility.sum()), "strategies": per_strategy}


# --- parallel driver ---------------------------------------------------------
_WORKER = {}


def _init_worker(scenario_name: str, beta: float, gamma: float, gp_lengthscale: float, causal: bool) -> None:
    scenario_cfg = SCENARIOS[scenario_name]
    _WORKER.update(
        fleet=_fleet_subset(scenario_cfg["n_satellites"]), scenario_cfg=scenario_cfg,
        amplitude_grid=default_amplitude_grid(AMPLITUDE_GRID_SIZE), strategies=build_strategies(beta, gamma),
        gp_lengthscale=gp_lengthscale, causal=causal,
    )


def _run_indexed(item) -> dict:
    idx, seed_seq = item
    w = _WORKER
    rec = run_one_event(seed_seq, w["fleet"], w["scenario_cfg"], w["amplitude_grid"], w["strategies"],
                        w["gp_lengthscale"], w["causal"])
    rec["event_index"] = idx
    return rec


def run_scenario(scenario_name: str, seed: int, n_events: int, beta: float = DEFAULT_BETA,
                 gamma: float = DEFAULT_GAMMA, gp_lengthscale: float = GP_LENGTHSCALE, causal: bool = True,
                 workers: int = 1) -> list[dict]:
    event_seeds = np.random.SeedSequence(seed).spawn(n_events)
    init_args = (scenario_name, beta, gamma, gp_lengthscale, causal)
    items = list(enumerate(event_seeds))
    if workers <= 1:
        _init_worker(*init_args)
        return [_run_indexed(it) for it in items]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=init_args) as ex:
        records = list(ex.map(_run_indexed, items, chunksize=4))
    return sorted(records, key=lambda r: r["event_index"])


def summarize(records: list[dict]) -> dict:
    out = {}
    for name in records[0]["strategies"]:
        rows = [(r, r["strategies"][name]) for r in records]
        mod = [s for r, s in rows if r["modeled"]]
        wh = [s for r, s in rows if not r["modeled"]]

        def rate(rs, key):
            return float(np.mean([s[key] for s in rs])) if rs else None

        def mean_of(rs, key):
            vals = [s[key] for s in rs if s[key] is not None]
            return float(np.mean(vals)) if vals else None

        tti = np.array([np.inf if s["time_to_id_days"] is None else s["time_to_id_days"] for s in mod])
        entry = {
            "n_modeled": len(mod), "n_withheld": len(wh),
            "accuracy_modeled": rate(mod, "correct"), "accuracy_withheld": rate(wh, "correct"),
            "confident_wrong_rate_modeled": rate(mod, "confident_wrong"),
            "confident_wrong_rate_withheld": rate(wh, "confident_wrong"),
            "mean_log_score": mean_of([s for _, s in rows], "log_score"),
            "mean_log_score_modeled": mean_of(mod, "log_score"),
            "mean_log_score_withheld": mean_of(wh, "log_score"),
            "median_time_to_id_days": float(np.median(tti)) if len(tti) else None,
            "fraction_identified": float(np.mean(np.isfinite(tti))) if len(tti) else None,
            "mean_obs_used": rate([s for _, s in rows], "n_obs_used"),
            "mean_amp_info_fisher_fast": mean_of([s for r, s in rows if r["speed_group"] == "fast"], "amp_info_fisher"),
            "mean_amp_info_fisher_slow": mean_of([s for r, s in rows if r["speed_group"] == "slow"], "amp_info_fisher"),
            "auroc_cw_entropy": auroc(np.array([s["cw_entropy_final"] for s in wh]),
                                      np.array([s["cw_entropy_final"] for s in mod])),
        }
        if name.startswith(OPEN_WORLD_PREFIX):
            entry["auroc_p_h0"] = auroc(np.array([s["p_h0_final"] for s in wh]),
                                        np.array([s["p_h0_final"] for s in mod]))
            entry["h0_false_alarm_modeled"] = float(np.mean([s["decision"] == "h0" for s in mod])) if mod else None
            entry["mode_switch_rate_withheld"] = float(np.mean([s["mode_switch_step"] is not None for s in wh])) if wh else None
        out[name] = entry
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=("validation", "test"), required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-events", type=int, required=True)
    ap.add_argument("--scenario", choices=list(SCENARIOS), default="S1_nominal")
    ap.add_argument("--beta", type=float, default=DEFAULT_BETA)
    ap.add_argument("--gamma", type=float, default=DEFAULT_GAMMA)
    ap.add_argument("--gp-lengthscale", type=float, default=GP_LENGTHSCALE)
    ap.add_argument("--non-causal", action="store_true", help="reproduce the first (time-unordered) build")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 4))
    ap.add_argument("--tag", default="")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    args = ap.parse_args()

    if (args.split == "test") != (args.seed >= TEST_SEED_MIN):
        raise SystemExit(f"Seed discipline: test seeds are >= {TEST_SEED_MIN}, validation seeds below it.")
    if args.split == "test" and not PREREGISTRATION_PATH.exists():
        raise SystemExit(f"Test seeds are locked until {PREREGISTRATION_PATH.name} is committed.")

    t_start = time.time()
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout
    commit_at_start = git_commit_hash()
    records = run_scenario(args.scenario, args.seed, args.n_events, args.beta, args.gamma, args.gp_lengthscale,
                           not args.non_causal, args.workers)

    config = {
        "phase": "phase2c_single_planner_causal", "split": args.split, "seed": args.seed,
        "n_events": args.n_events, "scenario": args.scenario, "scenario_cfg": SCENARIOS[args.scenario],
        "causal": not args.non_causal, "utility_beta": args.beta, "utility_gamma": args.gamma,
        "gp_lengthscale_days": args.gp_lengthscale, "candidate_times_days": CANDIDATE_TIMES_DAYS.tolist(),
        "n_obs_budget": N_OBS_BUDGET, "amplitude_grid_size": AMPLITUDE_GRID_SIZE,
        "confident_threshold": CONFIDENT_THRESHOLD, "mode_switch_tau": MODE_SWITCH_TAU,
        "fleet_pool_size": FLEET_POOL_SIZE, "strategies": list(records[0]["strategies"]), "tag": args.tag,
    }
    name = f"{args.split}_{args.scenario}_seed{args.seed}{'_' + args.tag if args.tag else ''}"
    out_dir = Path(args.results_dir) / name
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = {"git_commit": commit_at_start, "config_hash": config_hash(config),
                  "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "runtime_s": round(time.time() - t_start, 1)}
    if diff:
        provenance["git_dirty"] = True
        (out_dir / "git_diff.patch").write_text(diff, encoding="utf-8")
    atomic_write_json(out_dir / "config.json", {**config, **provenance})
    with open(out_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    summary = summarize(records)
    atomic_write_json(out_dir / "summary.json", {"summary": summary, **provenance, "n_events": len(records)})
    print(f"{name}: {provenance['runtime_s']}s")
    for k, v in summary.items():
        print(f"  {k:26s} acc_mod={v['accuracy_modeled']:.3f} cw_wh={v['confident_wrong_rate_withheld']:.3f} "
              f"med_tti={v['median_time_to_id_days']} info_fast={v['mean_amp_info_fisher_fast']:.3f} "
              f"info_slow={v['mean_amp_info_fisher_slow']:.3f} logS={v['mean_log_score']:.3f}"
              + (f" auroc_h0={v['auroc_p_h0']:.3f}" if 'auroc_p_h0' in v else f" auroc_H={v['auroc_cw_entropy']:.3f}"))


if __name__ == "__main__":
    main()
