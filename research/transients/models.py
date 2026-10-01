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
