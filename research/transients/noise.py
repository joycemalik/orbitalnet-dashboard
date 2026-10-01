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
