"""Phase 3 - counterfactual replay of REAL transients against the REAL fleet.

"What if our constellation had chased these transients?" Every event is a
spectroscopically classified ZTF Bright Transient Survey object (real light
curve, real RA/Dec, real date); the fleet is the same Starlink satellites as
Phase 2, propagated from Space-Track element sets archived at the time. Only
the planners' *measurements* are simulated: truth at a chosen time is the GP
mean through the real ZTF points, plus noise from the instrument model.

Hypotheses: modeled = SN Ia / SN II / SN Ibc (empirical templates built from
the TEMPLATE split only); withheld (real h0) = TDE, SLSN, SN Ibn.

Chronological split of the usable events:
  template   -> first detected before 2020-01-01 (fleet not yet in orbit);
                builds the class templates; never scored
  validation -> older half of post-2020 events; tuning and development (--split validation)
  test       -> newer half; locked until research/PREREGISTRATION.md exists (--split test)

Usage:
  python -m research.experiments.phase3_real_replay --split validation --seed 1 --n-events 100
"""

from __future__ import annotations

import argparse
import datetime
import json
import time
from pathlib import Path

import numpy as np

from research.data.fetch_bts import FLEET_COVERAGE_START_MJD, RAW_DIR
from research.experiments.metrics import auroc, log_score, time_to_identification
from research.inference.bayes import ClosedWorldBelief
from research.inference.openworld import AmplitudeMarginalGP, open_world_posterior
from research.orbitsim.contacts import build_contact_schedule_historical
from research.orbitsim.geometry import radec_to_unit_eci
from research.orbitsim.tle import load_3le_latest
from research.planners.phase2 import MODE_SWITCH_TAU, STRATEGIES_P2, fixed_cadence_planner
from research.transients.noise import assign_instruments, noise_sigma_from_limiting_magnitude
from research.transients.real_events import (
    MODELED_CLASSES,
    RealEvent,
    build_class_templates,
    load_real_events,
    template_flux_fn_resolver,
)
from research.util import atomic_write_json, config_hash, git_commit_hash

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "research" / "results" / "phase3"
TLE_DIR = RAW_DIR / "tles"

# SN timescales are days-weeks, not the minutes-days of Phase 2's classes.
CANDIDATE_TIMES_DAYS = np.exp(np.linspace(np.log(0.5), np.log(60.0), 16))
N_OBS_BUDGET = 5
N_SATELLITES = 8                  # same as Phase 2's nominal scenario
LIMITING_MAGNITUDE_CHOICES = (19.0, 20.0, 21.0)
AMPLITUDE_GRID = np.exp(np.linspace(np.log(0.5), np.log(200.0), 25))  # covers 1st-99th pct peak flux
H0_GP_LENGTHSCALE_DAYS = 10.0     # tunable on validation only
MAX_TLE_AGE_DAYS = 7.0
CONFIDENT_THRESHOLD = 0.95
SPLITS = ("template", "validation", "test")


def split_events(events: list[RealEvent]) -> dict[str, list[RealEvent]]:
    """Chronological (events are sorted by first-detection MJD): everything
    before the fleet existed builds templates; the post-launch events are
    halved into validation (older) and test (newer)."""
    template = [e for e in events if e.t0_mjd < FLEET_COVERAGE_START_MJD]
    scored = [e for e in events if e.t0_mjd >= FLEET_COVERAGE_START_MJD]
    half = len(scored) // 2
    return {"template": template, "validation": scored[:half], "test": scored[half:]}


def load_fleet_archive() -> tuple[list[tuple[datetime.datetime, dict]], tuple[str, ...], list[str]]:
    names_all = tuple(json.loads((TLE_DIR / "fleet.json").read_text()).keys())
    archive, empty = [], []
    for path in sorted(TLE_DIR.glob("*.tle")):
        fleet = load_3le_latest(str(path))
        if not fleet:
            empty.append(path.stem)
            continue
        epoch = datetime.datetime.fromisoformat(path.stem).replace(tzinfo=datetime.timezone.utc)
        archive.append((epoch, fleet))
    return archive, names_all[:N_SATELLITES], empty


def mjd_to_datetime(mjd: float) -> datetime.datetime:
    return datetime.datetime(1858, 11, 17, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=mjd)


def run_one_event(ev: RealEvent, seed_seq: np.random.SeedSequence, archive, sat_names, flux_resolver) -> dict | None:
    rng = np.random.default_rng(seed_seq)
    schedule, tle_age = build_contact_schedule_historical(
        archive, sat_names, mjd_to_datetime(ev.t0_mjd), CANDIDATE_TIMES_DAYS,
        radec_to_unit_eci(ev.ra_deg, ev.dec_deg), MAX_TLE_AGE_DAYS)
    # No extrapolation of the real light curve: times after the last real
    # detection have no ground truth, so they are not offered to any strategy.
    schedule.visibility &= (CANDIDATE_TIMES_DAYS <= ev.t_days[-1])[:, None]
    if not schedule.visibility.any():
        return None

    instruments = assign_instruments(rng, schedule.satellite_names, LIMITING_MAGNITUDE_CHOICES)
    instrument_sigma = np.array([noise_sigma_from_limiting_magnitude(instruments[n]) for n in schedule.satellite_names])
    true_flux = ev.truth_flux(CANDIDATE_TIMES_DAYS)
    observed = true_flux[:, None] + rng.normal(size=schedule.visibility.shape) * instrument_sigma[None, :]

    per_strategy = {}
    for (name, planner_fn), child in zip(STRATEGIES_P2.items(), seed_seq.spawn(len(STRATEGIES_P2))):
        belief = ClosedWorldBelief.with_uniform_prior(MODELED_CLASSES, AMPLITUDE_GRID, flux_resolver)
        gp = AmplitudeMarginalGP(AMPLITUDE_GRID, lengthscale=H0_GP_LENGTHSCALE_DAYS)
        remaining = schedule.visibility.copy()
        t_obs, y_obs, s_obs, history = [], [], [], []
        planner_rng = np.random.default_rng(child)
        is_ow = name == "P_open_world_eig"
        streak, switch_step = 0, None

        for step in range(N_OBS_BUDGET):
            if not remaining.any():
                break
            fn = fixed_cadence_planner if (is_ow and switch_step is not None) else planner_fn
            i, j = fn(planner_rng, schedule, remaining, instrument_sigma, belief, t_obs, y_obs, s_obs, gp)
            remaining[i, j] = False
            t, y, s = float(CANDIDATE_TIMES_DAYS[i]), float(observed[i, j]), float(instrument_sigma[j])
            t_obs.append(t); y_obs.append(y); s_obs.append(s)
            belief.update(t, y, s)
            post = (open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp, np.array(s_obs))
                    if is_ow else belief.class_posterior())
            history.append({"t": t, "sat": schedule.satellite_names[j], "sigma": s, "y": y,
                            "tle_age_days": float(tle_age[i, j]), "posterior": post})
            if is_ow and switch_step is None:
                streak = streak + 1 if post.get("h0", 0.0) > MODE_SWITCH_TAU else 0
                if streak >= 2:
                    switch_step = step + 1

        final = history[-1]["posterior"] if history else {c: 1.0 / len(MODELED_CLASSES) for c in MODELED_CLASSES}
        decision = max(final, key=final.get)
        correct = (decision == ev.true_class) if not ev.is_withheld else (is_ow and decision == "h0")
        confident = final[decision] >= CONFIDENT_THRESHOLD
        per_strategy[name] = {
            "n_obs_used": len(t_obs), "decision": decision, "max_posterior": final[decision],
            "confident": bool(confident), "correct": bool(correct),
            "confident_wrong": bool(confident and not correct),
            "log_score": log_score(final, ev.true_class, MODELED_CLASSES),
            "time_to_identification": time_to_identification(history, "posterior", CONFIDENT_THRESHOLD),
            "p_h0_final": final.get("h0") if is_ow else None,
            "mode_switch_step": switch_step,
            "history": history,
        }

    return {"oid": ev.oid, "true_class": ev.true_class, "bts_type": ev.bts_type, "withheld": ev.is_withheld,
            "t0_mjd": ev.t0_mjd, "ra_deg": ev.ra_deg, "dec_deg": ev.dec_deg,
            "n_visible_cells": int(schedule.visibility.sum()), "true_flux": true_flux.tolist(),
            "real_t_days": ev.t_days.tolist(), "real_flux": ev.flux.tolist(), "real_flux_err": ev.flux_err.tolist(),
            "strategies": per_strategy}


def summarize(records: list[dict]) -> dict:
    out = {}
    for name in STRATEGIES_P2:
        rows = [(r["withheld"], r["strategies"][name]) for r in records]
        mod = [s for w, s in rows if not w]
        wh = [s for w, s in rows if w]

        def rate(rs, k):
            return float(np.mean([s[k] for s in rs])) if rs else None

        entry = {
            "n_modeled": len(mod), "n_withheld": len(wh),
            "accuracy_modeled": rate(mod, "correct"), "accuracy_withheld": rate(wh, "correct"),
            "confident_wrong_rate_modeled": rate(mod, "confident_wrong"),
            "confident_wrong_rate_withheld": rate(wh, "confident_wrong"),
            "mean_log_score": float(np.mean([s["log_score"] for _, s in rows])) if rows else None,
            "mean_obs_used": rate([s for _, s in rows], "n_obs_used"),
        }
        if name == "P_open_world_eig":
            entry["auroc_p_h0_withheld_vs_modeled"] = auroc(
                np.array([s["p_h0_final"] for s in wh]), np.array([s["p_h0_final"] for s in mod]))
        out[name] = entry
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("validation", "test"), default="validation")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-events", type=int, required=True, help="first N events of the split (chronological)")
    args = ap.parse_args()
    if args.split == "test" and not (REPO_ROOT / "research" / "PREREGISTRATION.md").exists():
        raise SystemExit("Test split is locked until research/PREREGISTRATION.md is committed.")

    t_start = time.time()
    events, load_exclusions = load_real_events()
    splits = split_events(events)
    templates = build_class_templates(splits["template"])
    resolver = template_flux_fn_resolver(templates)
    archive, sat_names, empty_tle_weeks = load_fleet_archive()

    chosen = splits[args.split][: args.n_events]
    seeds = np.random.SeedSequence(args.seed).spawn(len(chosen))
    records, no_contact = [], []
    for k, (ev, ss) in enumerate(zip(chosen, seeds)):
        rec = run_one_event(ev, ss, archive, sat_names, resolver)
        if rec is None:
            no_contact.append(ev.oid)
        else:
            records.append(rec)
        if k % 25 == 0:
            print(f"[{k + 1}/{len(chosen)}] {ev.oid} ({ev.true_class})", flush=True)

    config = {
        "split": args.split, "seed": args.seed, "n_events_requested": args.n_events,
        "candidate_times_days": CANDIDATE_TIMES_DAYS.tolist(), "n_obs_budget": N_OBS_BUDGET,
        "satellites": list(sat_names), "limiting_magnitudes": LIMITING_MAGNITUDE_CHOICES,
        "amplitude_grid": AMPLITUDE_GRID.tolist(), "h0_gp_lengthscale_days": H0_GP_LENGTHSCALE_DAYS,
        "max_tle_age_days": MAX_TLE_AGE_DAYS, "confident_threshold": CONFIDENT_THRESHOLD,
        "split_sizes": {k: len(v) for k, v in splits.items()},
        "split_date_ranges_mjd": {k: [v[0].t0_mjd, v[-1].t0_mjd] for k, v in splits.items() if v},
    }
    out_dir = RESULTS_DIR / f"{args.split}_seed{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = {"git_commit": git_commit_hash(), "config_hash": config_hash(config),
                  "runtime_s": round(time.time() - t_start, 1)}
    atomic_write_json(out_dir / "config.json", {**config, **provenance})
    atomic_write_json(out_dir / "templates.json", {"grid_days": np.linspace(0.0, 90.0, 181).tolist(),
                                                   **{c: v.tolist() for c, v in templates.items()}})
    atomic_write_json(out_dir / "exclusions.json", {
        "loader": load_exclusions, "no_feasible_contact": no_contact, "empty_tle_weeks": empty_tle_weeks})
    with open(out_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    summary = summarize(records)
    atomic_write_json(out_dir / "summary.json", {**summary, **provenance, "n_scored": len(records),
                                                 "n_no_contact": len(no_contact)})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
