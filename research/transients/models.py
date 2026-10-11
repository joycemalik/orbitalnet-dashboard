"""Parametric light-curve models for Phase 1.

Two *modeled* classes ("fast", "slow") are pure single-exponential decays from
t=0 — these are the only two hypotheses the closed-world planner knows about.
One *withheld* class ("bump") is a rise-then-decay shape never exposed to any
planner's hypothesis space; it exists only to generate test events and check
whether a planner (dis)honestly recognizes that neither modeled class fits.

All flux values are in arbitrary linear units; Phase 1 does not model
instrument limiting magnitude (that is introduced in Phase 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

# Decay timescales (days) for the two modeled classes.
TAU_FAST = 1.0
TAU_SLOW = 4.0

# Withheld "bump" class: Gaussian rise followed by an exponential decay.
BUMP_T_PEAK = 1.5
BUMP_SIGMA_RISE = 0.6
BUMP_TAU_DECAY = 2.5

MODELED_CLASSES = ("fast", "slow")
WITHHELD_CLASS = "bump"
ALL_CLASSES = MODELED_CLASSES + (WITHHELD_CLASS,)

AMPLITUDE_RANGE = (5.0, 20.0)  # log-uniform draw range for per-event amplitude


@dataclass(frozen=True)
class SimulatedEvent:
    true_class: str
    amplitude: float

    def flux(self, t: np.ndarray) -> np.ndarray:
        return flux_for_class(self.true_class, t, self.amplitude)


def flux_exp_decay(t: np.ndarray, amplitude: float, tau: float) -> np.ndarray:
    """f(t) = A * exp(-t/tau) for t >= 0. Equation: Phase 1 modeled-class light curve."""
    t = np.asarray(t, dtype=float)
    return amplitude * np.exp(-np.clip(t, 0.0, None) / tau)


def flux_bump(t: np.ndarray, amplitude: float) -> np.ndarray:
    """Gaussian rise to BUMP_T_PEAK, then exponential decay. Withheld class only."""
    t = np.asarray(t, dtype=float)
    rise = amplitude * np.exp(-0.5 * ((t - BUMP_T_PEAK) / BUMP_SIGMA_RISE) ** 2)
    decay = amplitude * np.exp(-(t - BUMP_T_PEAK) / BUMP_TAU_DECAY)
    return np.where(t < BUMP_T_PEAK, rise, decay)


def flux_for_class(cls: str, t: np.ndarray, amplitude: float) -> np.ndarray:
    if cls == "fast":
        return flux_exp_decay(t, amplitude, TAU_FAST)
    if cls == "slow":
        return flux_exp_decay(t, amplitude, TAU_SLOW)
    if cls == WITHHELD_CLASS:
        return flux_bump(t, amplitude)
    raise ValueError(f"unknown class {cls!r}")


def modeled_flux_fn(cls: str) -> Callable[[np.ndarray, float], np.ndarray]:
    """Returns f(t, amplitude) -> flux for one of the two MODELED_CLASSES."""
    if cls not in MODELED_CLASSES:
        raise ValueError(f"{cls!r} is not a modeled class; modeled classes are {MODELED_CLASSES}")
    tau = TAU_FAST if cls == "fast" else TAU_SLOW
    return lambda t, amplitude: flux_exp_decay(t, amplitude, tau)


def sample_event(rng: np.random.Generator, class_prior: dict[str, float] | None = None) -> SimulatedEvent:
    """Draws a true class (from ALL_CLASSES, including the withheld one) and an amplitude."""
    classes = list(ALL_CLASSES)
    if class_prior is None:
        probs = np.full(len(classes), 1.0 / len(classes))
    else:
        probs = np.array([class_prior[c] for c in classes], dtype=float)
        probs = probs / probs.sum()
    true_class = rng.choice(classes, p=probs)
    log_amp = rng.uniform(np.log(AMPLITUDE_RANGE[0]), np.log(AMPLITUDE_RANGE[1]))
    amplitude = float(np.exp(log_amp))
    return SimulatedEvent(true_class=str(true_class), amplitude=amplitude)


# ---------------------------------------------------------------------------
# Phase 2: 4 modeled classes + 3 withheld classes, realigned to the classes
# named in Hypothesis-Discriminating Observation Campaigns....pdf
# ("the manuscript"): kilonova, shock-cooling/Type IIb early phase, GRB
# afterglow (broken power-law), M-dwarf flare (modeled); a fast blue optical
# transient (AT2018cow-like), a tidal disruption event, and a synthetic
# "nonsense" class with physically odd evolution (withheld).
#
# The manuscript asks for "published light-curve codes or templates... cited"
# (e.g. sncosmo). This branch has no network access beyond installing
# requirements-research.txt, so these are NOT those templates — they are
# this project's own physically-motivated analytic approximations of each
# class's qualitative shape (rise/decay timescale, power-law vs exponential
# family, single- vs double-peaked). Documented here and in research/LOG.md;
# replace with real forward models (e.g. sncosmo, a kilonova grid) before
# any claim of physical realism beyond "qualitatively distinct shapes".
# ---------------------------------------------------------------------------

# Kilonova: fast blue transient (AT2017gfo-like blue component).
KN_T_PEAK, KN_SIGMA_RISE, KN_TAU_DECAY = 0.7, 0.35, 1.3

# Shock-cooling / Type IIb early phase: early cooling peak, then a slow rise
# toward the main radioactively-powered peak (not reached within the window).
SC_T_PEAK, SC_SIGMA_RISE, SC_TAU_DECAY = 0.6, 0.3, 1.0
SC_MAIN_START, SC_MAIN_TAU_RISE, SC_MAIN_FRAC = 3.0, 6.0, 0.7

# GRB afterglow: broken power-law decline (shallow pre-break, steep post-break).
GRB_T_BREAK, GRB_ALPHA1, GRB_ALPHA2, GRB_T_FLOOR = 1.5, 0.5, 1.8, 0.05

# M-dwarf flare: fast rise and decay on a sub-hour timescale (days here).
FLARE_T_PEAK, FLARE_SIGMA_RISE, FLARE_TAU_DECAY = 0.02, 0.01, 0.03

# FBOT (withheld): fast rise/decay, distinct timescale from the kilonova.
FBOT_T_PEAK, FBOT_SIGMA_RISE, FBOT_TAU_DECAY = 1.0, 0.4, 1.8

# TDE (withheld): slow rise then classic t^-5/3 fallback-accretion decline.
TDE_T_PEAK, TDE_SIGMA_RISE, TDE_DECAY_INDEX = 5.0, 3.0, 5.0 / 3.0

# Synthetic "nonsense" class (withheld): secularly brightening oscillation —
# qualitatively impossible for a fading transient, by construction.
NONSENSE_PERIOD, NONSENSE_AMP_FRAC = 2.5, 0.5

MODELED_CLASSES_P2 = ("kilonova", "shock_cooling", "grb_afterglow", "flare")
WITHHELD_CLASSES_P2 = ("fbot", "tde", "nonsense")
ALL_CLASSES_P2 = MODELED_CLASSES_P2 + WITHHELD_CLASSES_P2


def _bump_component(t: np.ndarray, amplitude: float, t_peak: float, sigma_rise: float, tau_decay: float) -> np.ndarray:
    rise = amplitude * np.exp(-0.5 * ((t - t_peak) / sigma_rise) ** 2)
    decay = amplitude * np.exp(-(t - t_peak) / tau_decay)
    return np.where(t < t_peak, rise, decay)


def flux_kilonova(t: np.ndarray, amplitude: float) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    return _bump_component(t, amplitude, KN_T_PEAK, KN_SIGMA_RISE, KN_TAU_DECAY)


def flux_shock_cooling(t: np.ndarray, amplitude: float) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    early = _bump_component(t, amplitude, SC_T_PEAK, SC_SIGMA_RISE, SC_TAU_DECAY)
    main = np.where(
        t >= SC_MAIN_START,
        amplitude * SC_MAIN_FRAC * (1.0 - np.exp(-(t - SC_MAIN_START) / SC_MAIN_TAU_RISE)),
        0.0,
    )
    return early + main


def flux_grb_afterglow(t: np.ndarray, amplitude: float) -> np.ndarray:
    t = np.clip(np.asarray(t, dtype=float), GRB_T_FLOOR, None)
    pre = amplitude * (t / GRB_T_BREAK) ** (-GRB_ALPHA1)
    post = amplitude * (t / GRB_T_BREAK) ** (-GRB_ALPHA2)
    return np.where(t < GRB_T_BREAK, pre, post)


def flux_flare(t: np.ndarray, amplitude: float) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    return _bump_component(t, amplitude, FLARE_T_PEAK, FLARE_SIGMA_RISE, FLARE_TAU_DECAY)


def flux_fbot(t: np.ndarray, amplitude: float) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    return _bump_component(t, amplitude, FBOT_T_PEAK, FBOT_SIGMA_RISE, FBOT_TAU_DECAY)


def flux_tde(t: np.ndarray, amplitude: float) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    rise = amplitude * np.exp(-0.5 * ((t - TDE_T_PEAK) / TDE_SIGMA_RISE) ** 2)
    decay = amplitude * np.clip(t / TDE_T_PEAK, 1e-3, None) ** (-TDE_DECAY_INDEX)
    return np.where(t < TDE_T_PEAK, rise, decay)


def flux_nonsense(t: np.ndarray, amplitude: float) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    growth = np.clip(t, 0.0, None) / 10.0
    oscillation = 1.0 + NONSENSE_AMP_FRAC * np.sin(2 * np.pi * t / NONSENSE_PERIOD)
    return amplitude * growth * oscillation


def flux_for_class_p2(cls: str, t: np.ndarray, amplitude: float) -> np.ndarray:
    fns = {
        "kilonova": flux_kilonova,
        "shock_cooling": flux_shock_cooling,
        "grb_afterglow": flux_grb_afterglow,
        "flare": flux_flare,
        "fbot": flux_fbot,
        "tde": flux_tde,
        "nonsense": flux_nonsense,
    }
    if cls not in fns:
        raise ValueError(f"unknown Phase 2 class {cls!r}")
    return fns[cls](t, amplitude)


def modeled_flux_fn_p2(cls: str) -> Callable[[np.ndarray, float], np.ndarray]:
    if cls not in MODELED_CLASSES_P2:
        raise ValueError(f"{cls!r} is not a Phase 2 modeled class; modeled classes are {MODELED_CLASSES_P2}")
    return lambda t, amplitude: flux_for_class_p2(cls, t, amplitude)


def modeled_flux_fn_p2_perturbed(cls: str, factor: float) -> Callable[[np.ndarray, float], np.ndarray]:
    """Same shape as `modeled_flux_fn_p2`, but with every class's timescale
    dilated by `factor` (evaluates the true shape at t/factor) — a generic,
    class-agnostic way to misspecify "the decay timescale" for the S3_model_error
    scenario (manuscript Scenario 5), used only in the planner's own belief,
    never in the true event-generating function."""
    if cls not in MODELED_CLASSES_P2:
        raise ValueError(f"{cls!r} is not a Phase 2 modeled class; modeled classes are {MODELED_CLASSES_P2}")
    return lambda t, amplitude: flux_for_class_p2(cls, np.asarray(t, dtype=float) / factor, amplitude)


# Speed grouping for the "early-time parameter error, fast vs. slow classes"
# metric (H2 / decay-ablation): flare and kilonova fade fastest; shock-
# cooling's early peak also fades fast even though its main peak is slow;
# the GRB afterglow's pre-break decline is comparatively shallow/slow.
SPEED_GROUP_P2 = {
    "kilonova": "fast", "flare": "fast", "shock_cooling": "fast", "grb_afterglow": "slow",
}


def sample_event_p2(rng: np.random.Generator, class_prior: dict[str, float] | None = None) -> SimulatedEvent:
    classes = list(ALL_CLASSES_P2)
    if class_prior is None:
        probs = np.full(len(classes), 1.0 / len(classes))
    else:
        probs = np.array([class_prior[c] for c in classes], dtype=float)
        probs = probs / probs.sum()
    true_class = rng.choice(classes, p=probs)
    log_amp = rng.uniform(np.log(AMPLITUDE_RANGE[0]), np.log(AMPLITUDE_RANGE[1]))
    amplitude = float(np.exp(log_amp))
    return SimulatedEvent(true_class=str(true_class), amplitude=amplitude)
