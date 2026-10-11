"""Phase 2 - single-planner experiment with real orbits.

Realigned to Hypothesis-Discriminating Observation Campaigns....pdf
("the manuscript"): 4 modeled classes (kilonova, shock-cooling, GRB
afterglow, M-dwarf flare) + 3 withheld classes (FBOT, TDE, synthetic
nonsense), instrument noise from limiting magnitudes, feasibility from real
SGP4-based visibility (research.orbitsim), 5 strategies (B0 fixed-cadence,
B1 CNP reimplementation, B2 classifier-entropy, B3 closed-world EIG, P
open-world EIG with the manuscript's beta/gamma utility and mode switch)
across 3 scenarios (research.experiments.scenarios: Nominal, Crowding,
Model error — Communication sweep and Node loss are Phase 4's, see that
module's docstring). See research/LOG.md for the simplifications made
relative to the manuscript (no exact per-class decay quadrature, no
exposure/slew cost model, no wavelength bands).

Usage:
  python -m research.experiments.phase2_single_planner --mode validation
  python -m research.experiments.phase2_single_planner --mode test
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import time
from pathlib import Path

import numpy as np

from research.experiments.metrics import auroc, log_score, posterior_mean_amplitude, time_to_identification
from research.experiments.scenarios import SCENARIOS, class_prior_for_scenario
from research.inference.bayes import ClosedWorldBelief, default_amplitude_grid
from research.inference.openworld import SimpleGP, open_world_posterior
from research.orbitsim.contacts import build_contact_schedule
from research.orbitsim.tle import load_tle_subset
from research.planners.phase2 import DEFAULT_BETA, DEFAULT_GAMMA, MODE_SWITCH_TAU, STRATEGIES_P2, fixed_cadence_planner
from research.transients.models import (
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
FLEET_POOL_SIZE = 20  # covers the largest scenario's n_satellites with margin

# Widened relative to the first (pre-manuscript) draft of this file: the
# manuscript's modeled classes span minutes (M-dwarf flare) to weeks (TDE,
# withheld), which a 0.2-10 day grid cannot represent.
CANDIDATE_TIMES_DAYS = np.exp(np.linspace(np.log(0.01), np.log(20.0), 16))
N_OBS_BUDGET = 5
AMPLITUDE_GRID_SIZE = 15
CONFIDENT_THRESHOLD = 0.95  # manuscript H1: 95% posterior
EARLY_STEP_INDEX = 2
TARGET_H0_FALSE_ALARM_RATE = 0.05

# Seed discipline (validity check 4): validation and test seeds are disjoint
# and fixed here; test seeds are not to be used until PREREGISTRATION.md is
# committed. See research/PREREGISTRATION.md once written.
SCENARIO_ORDER = list(SCENARIOS.keys())
VALIDATION_SEED = {name: 1 + i for i, name in enumerate(SCENARIO_ORDER)}
TEST_SEED = {name: 1000 + 1000 * i for i, name in enumerate(SCENARIO_ORDER)}
VALIDATION_N_EVENTS = 200
TEST_N_EVENTS = 1000


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


def run_one_event(event_seed_seq: np.random.SeedSequence, fleet: dict, scenario_cfg: dict,
                   amplitude_grid: np.ndarray) -> dict:
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
    time_span = float(CANDIDATE_TIMES_DAYS[-1] - CANDIDATE_TIMES_DAYS[0])

    # Each strategy's planner gets its own independently-spawned sub-stream
    # (not reused across events -- see research/LOG.md Phase 2 entry for the
    # seeding bug this replaced) while every strategy still sees IDENTICAL
    # events/noise/visibility/crowding above (paired-by-seed comparison).
    strategy_items = list(STRATEGIES_P2.items())
    strategy_child_seeds = event_seed_seq.spawn(len(strategy_items))

    per_strategy = {}
    for (name, planner_fn), child_seed in zip(strategy_items, strategy_child_seeds):
        belief = ClosedWorldBelief.with_uniform_prior(
            classes=MODELED_CLASSES_P2, amplitude_grid=amplitude_grid, flux_fn_resolver=belief_flux_fn_resolver
        )
        gp = SimpleGP()
        remaining_mask = base_visibility.copy()
        t_obs, y_obs, sigma_obs = [], [], []
        history = []
        planner_rng = np.random.default_rng(child_seed)

        is_open_world = name == "P_open_world_eig"
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
            history.append({
                "t": t, "sat": schedule.satellite_names[j], "sigma": sigma,
                "posterior": posterior_now,
                "amplitude_estimate": posterior_mean_amplitude(belief),
            })

            if is_open_world and mode_switch_step is None:
                if posterior_now.get("h0", 0.0) > MODE_SWITCH_TAU:
                    consecutive_h0_above_tau += 1
                    if consecutive_h0_above_tau >= 2:
                        mode_switch_step = step + 1  # 1-based
                else:
                    consecutive_h0_above_tau = 0

        posterior_key = "posterior"
        final_post = history[-1]["posterior"] if history else {c: 1.0 / len(belief.classes) for c in belief.classes}

        decision = max(final_post, key=final_post.get)
        max_prob = final_post[decision]
        if event.true_class in MODELED_CLASSES_P2:
            correct = decision == event.true_class
        else:
            correct = (decision == "h0") if is_open_world else False
        confident = max_prob >= CONFIDENT_THRESHOLD

        early_amp_error = None
        if event.true_class in MODELED_CLASSES_P2 and len(history) >= EARLY_STEP_INDEX:
            est = history[EARLY_STEP_INDEX - 1]["amplitude_estimate"]
            early_amp_error = abs(est - event.amplitude) / event.amplitude

        time_coverage_fraction = None
        if is_open_world and len(t_obs) >= 2 and time_span > 0:
            time_coverage_fraction = (max(t_obs) - min(t_obs)) / time_span

        per_strategy[name] = {
            "true_class": event.true_class,
            "amplitude": event.amplitude,
            "n_obs_used": len(t_obs),
            "decision": decision,
            "max_posterior": max_prob,
            "confident": bool(confident),
            "correct": bool(correct),
            "confident_wrong": bool(confident and not correct),
            "log_score": log_score(final_post, event.true_class, MODELED_CLASSES_P2),
            "time_to_identification": time_to_identification(history, posterior_key, CONFIDENT_THRESHOLD),
            "early_amplitude_rel_error": early_amp_error,
            "speed_group": SPEED_GROUP_P2.get(event.true_class),
            "p_h0_final": final_post.get("h0") if is_open_world else None,
            "mode_switch_step": mode_switch_step,
            "mode_switch_triggered": mode_switch_step is not None,
            "time_coverage_fraction": time_coverage_fraction,
        }

    return {"true_class": event.true_class, "amplitude": event.amplitude, "strategies": per_strategy}


def run_scenario(scenario_name: str, seed: int, n_events: int) -> dict:
    scenario_cfg = SCENARIOS[scenario_name]
    fleet = _fleet_subset(scenario_cfg["n_satellites"])
    amplitude_grid = default_amplitude_grid(AMPLITUDE_GRID_SIZE)

    ss = np.random.SeedSequence(seed)
    event_seeds = ss.spawn(n_events)

    records = []
    for i in range(n_events):
        record = run_one_event(event_seeds[i], fleet, scenario_cfg, amplitude_grid)
        records.append(record)

    return {"scenario": scenario_name, "scenario_cfg": scenario_cfg, "seed": seed, "n_events": n_events, "records": records}


def summarize(run_result: dict) -> dict:
    records = run_result["records"]
    strategy_names = list(STRATEGIES_P2.keys())
    summary = {"strategies": {}}

    for name in strategy_names:
        rows = [r["strategies"][name] for r in records]
        modeled_rows = [r for r in rows if r["true_class"] in MODELED_CLASSES_P2]
        withheld_rows = [r for r in rows if r["true_class"] not in MODELED_CLASSES_P2]

        def rate(rs, key):
            return float(np.mean([r[key] for r in rs])) if rs else None

        def mean_of(rs, key):
            vals = [r[key] for r in rs if r[key] is not None]
            return float(np.mean(vals)) if vals else None

        ttid = [r["time_to_identification"] for r in rows if r["time_to_identification"] is not None]

        entry = {
            "n_events": len(rows),
            "confident_wrong_rate_modeled": rate(modeled_rows, "confident_wrong"),
            "confident_wrong_rate_withheld": rate(withheld_rows, "confident_wrong"),
            "accuracy_modeled": rate(modeled_rows, "correct"),
            "accuracy_withheld": rate(withheld_rows, "correct"),
            "mean_log_score": mean_of(rows, "log_score"),
            "mean_log_score_modeled": mean_of(modeled_rows, "log_score"),
            "mean_log_score_withheld": mean_of(withheld_rows, "log_score"),
            "mean_time_to_identification": float(np.mean(ttid)) if ttid else None,
            "fraction_never_identified": float(np.mean([r["time_to_identification"] is None for r in rows])),
            "mean_instrument_time": mean_of(rows, "n_obs_used"),
            "early_amp_error_fast": mean_of(
                [r for r in modeled_rows if r["speed_group"] == "fast"], "early_amplitude_rel_error"
            ),
            "early_amp_error_slow": mean_of(
                [r for r in modeled_rows if r["speed_group"] == "slow"], "early_amplitude_rel_error"
            ),
        }

        if name == "P_open_world_eig":
            p_h0_modeled = np.array([r["p_h0_final"] for r in modeled_rows if r["p_h0_final"] is not None])
            p_h0_withheld = np.array([r["p_h0_final"] for r in withheld_rows if r["p_h0_final"] is not None])
            entry["auroc_p_h0_withheld_vs_modeled"] = auroc(p_h0_withheld, p_h0_modeled)
            entry["mode_switch_rate_withheld"] = rate(withheld_rows, "mode_switch_triggered")
            # Simplified "preservation" proxy (manuscript 6.4): fraction of
            # the candidate-time RANGE spanned by chosen measurements, for
            # withheld events where the mode switch fired. No wavelength
            # bands are modeled, so this is coverage-in-time only.
            preserved = [
                r["time_coverage_fraction"] for r in withheld_rows
                if r["mode_switch_step"] is not None and r["time_coverage_fraction"] is not None
            ]
            entry["mean_preservation_time_coverage"] = float(np.mean(preserved)) if preserved else None

        summary["strategies"][name] = entry

    return summary


def null_control_check(scenario_name: str, seed: int, n_events: int, tolerance: float = 0.15) -> dict:
    """Validity check 1: on MODELED-ONLY events with unperturbed models, P
    must perform about the same as B3 (both have the correct closed-world
    model; h0 should essentially never fire). Compares mean log score."""
    scenario_cfg = dict(SCENARIOS[scenario_name])
    scenario_cfg["withheld_weight"] = 0.0  # modeled classes only
    fleet = _fleet_subset(scenario_cfg["n_satellites"])
    amplitude_grid = default_amplitude_grid(AMPLITUDE_GRID_SIZE)

    ss = np.random.SeedSequence(seed)
    event_seeds = ss.spawn(n_events)
    b3_scores, p_scores = [], []
    for i in range(n_events):
        record = run_one_event(event_seeds[i], fleet, scenario_cfg, amplitude_grid)
        b3_scores.append(record["strategies"]["B3_closed_world_eig"]["log_score"])
        p_scores.append(record["strategies"]["P_open_world_eig"]["log_score"])

    mean_diff = float(np.mean(p_scores) - np.mean(b3_scores))
    passed = abs(mean_diff) <= tolerance
    return {
        "scenario": scenario_name, "n_events": n_events, "seed": seed,
        "mean_log_score_b3": float(np.mean(b3_scores)), "mean_log_score_p": float(np.mean(p_scores)),
        "mean_diff": mean_diff, "tolerance": tolerance, "passed": passed,
    }


def calibrate_h0_threshold(scenario_name: str, seed: int, n_events: int,
                            target_fpr: float = TARGET_H0_FALSE_ALARM_RATE) -> dict:
    """Validity check 3 (calibration half): choose a P(h0) threshold on
    VALIDATION-seed modeled-truth events so that the false-alarm rate equals
    `target_fpr`, to later be checked (not re-tuned) on test seeds."""
    scenario_cfg = SCENARIOS[scenario_name]
    fleet = _fleet_subset(scenario_cfg["n_satellites"])
    amplitude_grid = default_amplitude_grid(AMPLITUDE_GRID_SIZE)

    ss = np.random.SeedSequence(seed)
    event_seeds = ss.spawn(n_events)
    p_h0_modeled = []
    for i in range(n_events):
        record = run_one_event(event_seeds[i], fleet, scenario_cfg, amplitude_grid)
        if record["true_class"] in MODELED_CLASSES_P2:
            p_h0_modeled.append(record["strategies"]["P_open_world_eig"]["p_h0_final"])

    threshold = float(np.quantile(p_h0_modeled, 1.0 - target_fpr))
    return {
        "scenario": scenario_name, "n_events": n_events, "seed": seed,
        "target_fpr": target_fpr, "calibrated_threshold": threshold,
    }


def negative_control_check(scenario_name: str, test_records: list[dict], threshold: float, target_fpr: float) -> dict:
    """Validity check 3 (verification half): on TEST-seed modeled-truth
    events, the false-alarm rate at the FROZEN calibrated threshold must be
    close to the target. Reported honestly even if it drifts."""
    modeled = [r for r in test_records if r["true_class"] in MODELED_CLASSES_P2]
    p_h0 = [r["strategies"]["P_open_world_eig"]["p_h0_final"] for r in modeled]
    observed_fpr = float(np.mean([p >= threshold for p in p_h0])) if p_h0 else None
    return {
        "scenario": scenario_name, "threshold": threshold, "target_fpr": target_fpr,
        "observed_fpr": observed_fpr, "n_modeled_events": len(modeled),
    }


RESULTS_DIR = REPO_ROOT / "research" / "results" / "phase2"
PREREGISTRATION_PATH = REPO_ROOT / "research" / "PREREGISTRATION.md"


def _config() -> dict:
    return {
        "phase": "phase2_single_planner",
        "candidate_times_days": CANDIDATE_TIMES_DAYS.tolist(),
        "n_obs_budget": N_OBS_BUDGET,
        "amplitude_grid_size": AMPLITUDE_GRID_SIZE,
        "confident_threshold": CONFIDENT_THRESHOLD,
        "early_step_index": EARLY_STEP_INDEX,
        "target_h0_false_alarm_rate": TARGET_H0_FALSE_ALARM_RATE,
        "fleet_pool_size": FLEET_POOL_SIZE,
        "utility_beta": DEFAULT_BETA,
        "utility_gamma": DEFAULT_GAMMA,
        "mode_switch_tau": MODE_SWITCH_TAU,
        "scenarios": SCENARIOS,
        "strategies": list(STRATEGIES_P2.keys()),
        "validation_seeds": VALIDATION_SEED,
        "test_seeds": TEST_SEED,
        "validation_n_events": VALIDATION_N_EVENTS,
        "test_n_events": TEST_N_EVENTS,
    }


def run_validation_phase(scenarios=SCENARIO_ORDER) -> dict:
    """Runs the null control and h0-calibration checks on validation seeds
    for each scenario. Must be run, and PREREGISTRATION.md committed, before
    any test-seed run (seed discipline, validity check 4)."""
    results = {}
    for name in scenarios:
        seed = VALIDATION_SEED[name]
        null = null_control_check(name, seed, VALIDATION_N_EVENTS)
        calib = calibrate_h0_threshold(name, seed, VALIDATION_N_EVENTS)
        results[name] = {"null_control": null, "calibration": calib}
        print(f"[validation] {name}: null_control passed={null['passed']} (diff={null['mean_diff']:.4f}), "
              f"calibrated h0 threshold={calib['calibrated_threshold']:.4f}")
    return results


def run_test_phase(scenarios, validation_results: dict) -> None:
    """Runs the full test-seed experiment for each scenario. Refuses to run
    unless PREREGISTRATION.md exists (seed discipline, validity check 4)."""
    if not PREREGISTRATION_PATH.exists():
        raise RuntimeError(
            f"{PREREGISTRATION_PATH} does not exist. Run --mode validation, review the results, "
            "write and commit PREREGISTRATION.md, THEN run --mode test. Refusing to touch test seeds."
        )

    commit = git_commit_hash()
    cfg = _config()
    cfg_hash = config_hash(cfg)

    for name in scenarios:
        seed = TEST_SEED[name]
        t0 = time.time()
        run_result = run_scenario(name, seed, TEST_N_EVENTS)
        elapsed = time.time() - t0
        summary = summarize(run_result)

        threshold = validation_results[name]["calibration"]["calibrated_threshold"]
        target_fpr = TARGET_H0_FALSE_ALARM_RATE
        all_records_flat = [
            {"true_class": r["true_class"], "strategies": r["strategies"]} for r in run_result["records"]
        ]
        neg_control = negative_control_check(name, all_records_flat, threshold, target_fpr)

        out_dir = RESULTS_DIR / name
        os.makedirs(out_dir, exist_ok=True)
        atomic_write_json(out_dir / "config.json", cfg)
        atomic_write_json(out_dir / "summary.json", {
            "config": cfg, "config_hash": cfg_hash, "git_commit": commit,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scenario": name, "seed": seed, "tag": "test", "elapsed_seconds": elapsed,
            "summary": summary,
            "null_control": validation_results[name]["null_control"],
            "h0_calibration": validation_results[name]["calibration"],
            "negative_control": neg_control,
        })
        with open(out_dir / "events_raw.jsonl", "w", encoding="utf-8") as f:
            for r in run_result["records"]:
                f.write(json.dumps(r) + "\n")

        print(f"[test] {name} done in {elapsed:.1f}s. "
              f"P confident_wrong_withheld={summary['strategies']['P_open_world_eig']['confident_wrong_rate_withheld']} "
              f"B3 confident_wrong_withheld={summary['strategies']['B3_closed_world_eig']['confident_wrong_rate_withheld']} "
              f"neg_control_observed_fpr={neg_control['observed_fpr']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["validation", "test"], required=True)
    parser.add_argument("--scenario", choices=SCENARIO_ORDER, default=None,
                         help="Run a single scenario instead of all of them.")
    args = parser.parse_args()
    scenarios = [args.scenario] if args.scenario else SCENARIO_ORDER

    if args.mode == "validation":
        results = run_validation_phase(scenarios)
        out_path = RESULTS_DIR / "validation_results.json"
        os.makedirs(RESULTS_DIR, exist_ok=True)
        # Merge with any existing validation_results.json so --scenario runs
        # don't clobber other scenarios' already-computed validation results.
        existing = {}
        if out_path.exists():
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.update(results)
        atomic_write_json(out_path, existing)
        print(f"Validation results written to {out_path}")
    else:
        val_path = RESULTS_DIR / "validation_results.json"
        if not val_path.exists():
            raise RuntimeError(f"{val_path} not found. Run --mode validation first.")
        with open(val_path, "r", encoding="utf-8") as f:
            validation_results = json.load(f)
        missing = [s for s in scenarios if s not in validation_results]
        if missing:
            raise RuntimeError(f"Missing validation results for {missing}; run --mode validation for them first.")
        run_test_phase(scenarios, validation_results)


if __name__ == "__main__":
    main()
