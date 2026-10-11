"""Phase 1 instrument noise: fixed-sigma additive Gaussian noise.

Phase 2 replaces this with a noise model derived from instrument limiting
magnitudes; Phase 1 deliberately keeps it this simple so the Bayesian update
and mutual-information estimator have exact Gaussian likelihoods to be
tested against known answers.
"""

from __future__ import annotations

import numpy as np

SIGMA0 = 1.0  # fixed measurement noise std, same units as flux


def draw_noise_grid(rng: np.random.Generator, n_candidate_times: int, sigma: float = SIGMA0) -> np.ndarray:
    """Pre-draws one noise value per candidate time so every strategy sees an
    identical noise realization at a given time for a given event (required
    for a fair, paired-by-seed strategy comparison)."""
    return rng.normal(loc=0.0, scale=sigma, size=n_candidate_times)


# --- Phase 2: instrument noise from limiting magnitude ---------------------
#
# Standard flux-magnitude relation: flux ∝ 10^(-0.4 * mag). ZEROPOINT_MAG is
# an arbitrary reference magnitude at which the noise floor equals 1.0 flux
# unit (matching Phase 1's SIGMA0), so a satellite with a deeper (numerically
# larger) limiting magnitude has a smaller, more sensitive noise floor.
ZEROPOINT_MAG = 20.0
LIMITING_MAGNITUDE_CHOICES = (19.0, 20.0, 21.0)  # shallow, reference, deep


def noise_sigma_from_limiting_magnitude(limiting_magnitude: float) -> float:
    return float(10 ** (-0.4 * (limiting_magnitude - ZEROPOINT_MAG)))


def assign_instruments(rng: np.random.Generator, satellite_names: tuple[str, ...],
                        choices=LIMITING_MAGNITUDE_CHOICES) -> dict[str, float]:
    """Deterministically (given rng) assigns each satellite a limiting
    magnitude from `choices` — NOT via a name hash (that pattern, see
    physics_engine.classify_satellite, has no physical meaning and must not
    leak into the noise model; see research/PLAN.md section 2)."""
    drawn = rng.choice(choices, size=len(satellite_names))
    return {name: float(mag) for name, mag in zip(satellite_names, drawn)}
