"""Event Lab: run ONE user-defined transient through the Phase 2 open-world planner.

This is an interactive demo, not an experiment. Nothing it produces is written to
research/results/ or used in any table. It reuses the exact Phase 2 pieces:

- real TLE fleet (satellites.txt) -> visibility of the user's chosen sky position,
- instrument noise from limiting magnitude,
- open_world_eig_planner_p2 (method P) picking each (time, satellite),
- ClosedWorldBelief over the 4 modeled classes + GP evidence for h0 ("none of them").

Pure: no redis / streamlit / live-stack imports.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import numpy as np

from research.inference.bayes import ClosedWorldBelief, default_amplitude_grid
from research.inference.openworld import GP_LENGTHSCALE, SimpleGP, open_world_posterior
from research.orbitsim.contacts import REFERENCE_EPOCH, ContactSchedule
from research.orbitsim.geometry import radec_to_unit_eci, visibility_margin_deg
from research.orbitsim.tle import datetime_to_jd_fr, load_tle_subset, propagate_eci_km
from research.planners.phase2 import MODE_SWITCH_TAU, open_world_eig_planner_p2
from research.transients.models import (
    ALL_CLASSES_P2,
    MODELED_CLASSES_P2,
    flux_for_class_p2,
    modeled_flux_fn_p2,
)
from research.transients.noise import assign_instruments, noise_sigma_from_limiting_magnitude
from research.experiments.phase2_single_planner import (
    AMPLITUDE_GRID_SIZE,
    CANDIDATE_TIMES_DAYS,
    CONFIDENT_THRESHOLD,
    FLEET_POOL_SIZE,
    TLE_PATH,
)

PRETTY = {
    "kilonova": "Kilonova (neutron-star merger)",
    "shock_cooling": "Supernova shock cooling",
    "grb_afterglow": "Gamma-ray burst afterglow",
    "flare": "Stellar flare (M-dwarf)",
    "fbot": "Fast blue optical transient",
    "tde": "Tidal disruption event",
    "nonsense": "Unphysical oscillating signal",
    "h0": "h0: none of the known models",
}


def custom_flux(t: np.ndarray, amplitude: float, t_peak: float, rise: float, decay: float,
                rebright_frac: float = 0.0, rebright_t: float = 8.0) -> np.ndarray:
    """User-designed light curve: Gaussian rise to t_peak, exponential decay, optional second bump."""
    t = np.asarray(t, dtype=float)
    main = np.where(t < t_peak, np.exp(-0.5 * ((t - t_peak) / max(rise, 1e-3)) ** 2),
                    np.exp(-(t - t_peak) / max(decay, 1e-3)))
    second = rebright_frac * np.exp(-0.5 * ((t - rebright_t) / 1.5) ** 2)
    return amplitude * (main + second)


@dataclass
class LabResult:
    visible_cells: int
    n_satellites: int
    satellite_names: tuple
    times: np.ndarray
    true_flux_dense_t: np.ndarray
    true_flux_dense: np.ndarray
    steps: list = field(default_factory=list)   # each: t, y, sigma, sat, posterior
    verdict: str = ""
    verdict_prob: float = 0.0
    mode_switch_step: int | None = None


_FLEET = None


def _fleet():
    global _FLEET
    if _FLEET is None:
        _FLEET = load_tle_subset(str(TLE_PATH), max_satellites=FLEET_POOL_SIZE)
    return _FLEET


def schedule_for_target(ra_deg: float, dec_deg: float) -> ContactSchedule:
    fleet = _fleet()
    names = tuple(fleet.keys())
    target = radec_to_unit_eci(ra_deg, dec_deg)
    margin = np.full((len(CANDIDATE_TIMES_DAYS), len(names)), -180.0)
    for i, t_days in enumerate(CANDIDATE_TIMES_DAYS):
        jd, fr = datetime_to_jd_fr(REFERENCE_EPOCH + datetime.timedelta(days=float(t_days)))
        for j, name in enumerate(names):
            pos, _v, err = propagate_eci_km(fleet[name], jd, fr)
            if err == 0:
                margin[i, j] = visibility_margin_deg(pos, target)
    return ContactSchedule(names, np.asarray(CANDIDATE_TIMES_DAYS, float), margin >= 0.0, margin, target)


def run_lab(ra_deg: float, dec_deg: float, flux_fn, seed: int = 0, n_obs: int = 5) -> LabResult:
    """flux_fn(t_array) -> true flux. Returns the full step-by-step trace."""
    rng = np.random.default_rng(seed)
    schedule = schedule_for_target(ra_deg, dec_deg)
    instruments = assign_instruments(rng, schedule.satellite_names)
    sig = np.array([noise_sigma_from_limiting_magnitude(instruments[n]) for n in schedule.satellite_names])
    true_flux = flux_fn(CANDIDATE_TIMES_DAYS)
    observed = true_flux[:, None] + rng.normal(size=schedule.visibility.shape) * sig[None, :]

    dense_t = np.exp(np.linspace(np.log(0.01), np.log(20.0), 200))
    res = LabResult(int(schedule.visibility.sum()), len(schedule.satellite_names), schedule.satellite_names,
                    CANDIDATE_TIMES_DAYS, dense_t, flux_fn(dense_t))

    belief = ClosedWorldBelief.with_uniform_prior(
        classes=MODELED_CLASSES_P2, amplitude_grid=default_amplitude_grid(AMPLITUDE_GRID_SIZE),
        flux_fn_resolver=modeled_flux_fn_p2)
    gp = SimpleGP(lengthscale=GP_LENGTHSCALE)
    remaining = schedule.visibility.copy()
    t_obs, y_obs, s_obs = [], [], []
    above = 0
    for step in range(n_obs):
        if not remaining.any():
            break
        i, j = open_world_eig_planner_p2(rng, schedule, remaining, sig, belief, t_obs, y_obs, s_obs, gp)
        remaining[: i + 1, :] = False  # strictly forward in time
        t, y, s = float(CANDIDATE_TIMES_DAYS[i]), float(observed[i, j]), float(sig[j])
        t_obs.append(t); y_obs.append(y); s_obs.append(s)
        belief.update(t, y, s)
        post = open_world_posterior(belief, np.array(t_obs), np.array(y_obs), gp, np.array(s_obs))
        res.steps.append({"t": t, "y": y, "sigma": s, "sat": schedule.satellite_names[j],
                          "lim_mag": instruments[schedule.satellite_names[j]], "posterior": post})
        if res.mode_switch_step is None:
            above = above + 1 if post["h0"] > MODE_SWITCH_TAU else 0
            if above >= 2:
                res.mode_switch_step = step + 1
    if res.steps:
        post = res.steps[-1]["posterior"]
        res.verdict = max(post, key=post.get)
        res.verdict_prob = post[res.verdict]
    return res


def preset_flux_fn(cls: str, amplitude: float):
    assert cls in ALL_CLASSES_P2
    return lambda t: flux_for_class_p2(cls, t, amplitude)


__all__ = ["run_lab", "custom_flux", "preset_flux_fn", "PRETTY", "CONFIDENT_THRESHOLD",
           "MODELED_CLASSES_P2", "ALL_CLASSES_P2"]
