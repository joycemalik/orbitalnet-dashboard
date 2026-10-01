"""Expected information gain (EIG) between a candidate measurement and a
discrete hypothesis-of-interest variable, computed by exact 1D quadrature
over the (scalar, Gaussian-mixture-distributed) observation y.

For a candidate measurement with per-cell predictive means `means` (one
per hypothesis cell, e.g. one per (class, amplitude) grid point) under
current posterior weights `log_weights`, and a grouping of cells into a
coarser "hypothesis of interest" (e.g. class, ignoring the amplitude
nuisance parameter):

    EIG = H[p(group)] - E_y[ H[p(group | y)] ]

where the outer expectation is over the marginal predictive
p(y) = sum_cells weight(cell) * Normal(y; means[cell], sigma^2), evaluated
by trapezoidal quadrature on a fine grid wide enough to hold all of the
mixture's mass (no sampling noise, so the estimator is deterministic given
its inputs).
"""

from __future__ import annotations

import numpy as np
from scipy.special import logsumexp


def _log_normal_pdf(y: np.ndarray, mean: np.ndarray, sigma) -> np.ndarray:
    """sigma may be a scalar (shared across cells) or an array broadcastable
    against `mean` (per-cell noise, e.g. a GP predictive std alongside fixed
    measurement-noise cells)."""
    return -0.5 * np.log(2 * np.pi * sigma ** 2) - 0.5 * ((y - mean) / sigma) ** 2


def _group_logsumexp(log_values: np.ndarray, group_idx: np.ndarray, n_groups: int) -> np.ndarray:
    """Vectorized logsumexp-by-group. `log_values` has shape (..., n_cells);
    returns shape (..., n_groups). Loops only over n_groups (a handful of
    classes/h0), never over the (possibly large) leading batch dimension —
    that loop was the Phase-1 performance bug: calling this once per
    quadrature point in a Python for-loop made EIG evaluation scale
    unusably past a few dozen events."""
    out = np.empty(log_values.shape[:-1] + (n_groups,))
    for g in range(n_groups):
        out[..., g] = logsumexp(log_values[..., group_idx == g], axis=-1)
    return out


def _entropy_from_log_probs(log_probs: np.ndarray) -> np.ndarray:
    """Shannon entropy (nats) along the last axis of (assumed normalized)
    log-probabilities. Vectorized over any leading batch shape."""
    probs = np.exp(log_probs)
    safe = probs > 0
    terms = np.where(safe, probs * np.log(np.where(safe, probs, 1.0)), 0.0)
    return -np.sum(terms, axis=-1)


def group_entropy(log_weights: np.ndarray, group_idx: np.ndarray, n_groups: int) -> float:
    """Shannon entropy (nats) of the marginal distribution obtained by summing
    `log_weights` (assumed normalized, i.e. logsumexp(log_weights) == 0) over
    cells sharing the same `group_idx`."""
    group_log_probs = _group_logsumexp(log_weights, group_idx, n_groups)
    return float(_entropy_from_log_probs(group_log_probs))


def expected_information_gain(
    log_weights: np.ndarray,
    means: np.ndarray,
    sigma,
    group_idx: np.ndarray,
    n_groups: int,
    n_y: int = 2001,
    pad_sigmas: float = 8.0,
) -> float:
    """EIG for one candidate measurement time, given its predictive `means`
    per hypothesis cell (and, optionally, a per-cell `sigma`). `log_weights`
    must already be normalized (logsumexp(log_weights) == 0)."""
    h_prior = group_entropy(log_weights, group_idx, n_groups)

    sigma_arr = np.broadcast_to(np.asarray(sigma, dtype=float), means.shape)
    lo = np.min(means - pad_sigmas * sigma_arr)
    hi = np.max(means + pad_sigmas * sigma_arr)
    y_grid = np.linspace(lo, hi, n_y)

    # log_joint[y_idx, cell] = log_weights[cell] + log N(y; means[cell], sigma)
    log_normal = _log_normal_pdf(y_grid[:, None], means[None, :], sigma_arr[None, :])
    log_joint = log_weights[None, :] + log_normal
    log_p_y = logsumexp(log_joint, axis=1)  # (n_y,)
    p_y = np.exp(log_p_y)

    log_post_given_y = log_joint - log_p_y[:, None]  # (n_y, n_cells)

    group_log_probs_given_y = _group_logsumexp(log_post_given_y, group_idx, n_groups)  # (n_y, n_groups)
    entropy_given_y = _entropy_from_log_probs(group_log_probs_given_y)  # (n_y,)

    total_mass = np.trapezoid(p_y, y_grid)
    expected_post_entropy = np.trapezoid(entropy_given_y * p_y, y_grid) / total_mass

    return float(h_prior - expected_post_entropy)
