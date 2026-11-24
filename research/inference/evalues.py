"""Phase 4: anytime-valid "unknown" detection with e-values.

Null H_known: the data come from SOME modeled class c with SOME amplitude A
in AMPLITUDE_RANGE, with Gaussian noise of the stated sigma.

Universal-inference e-process (Wasserman, Ramdas & Balakrishnan 2020, PNAS,
sec. 7): with a fixed alternative q (here the h0 Gaussian process, whose
marginal likelihood is a product of predictive densities, so it is
predictable),

    E_t = q(D_t) / sup_{c, A} L(c, A; D_t).

For the true (c*, A*), E_t <= q(D_t)/L(c*, A*; D_t), a nonnegative
martingale with mean 1 under the null, even when each measurement's time and
instrument were chosen adaptively from earlier data. Ville's inequality then
gives P(sup_t E_t >= 1/alpha) <= alpha: the false-"unknown" rate is
controlled at EVERY step and under any stopping rule, with no calibration
set. Every modeled flux is linear in A, so the sup over A is exact
(weighted least squares, clipped to the prior range).

Fusion across spacecraft (Vovk & Wang 2021, "E-values: calibration,
combination and applications"): the arithmetic mean of e-values is an
e-value under ARBITRARY dependence, so spacecraft that share overlapping
observations can still average their scalars. The product is valid only for
independent e-values; it is computed here as a foil to show the failure.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from research.inference.openworld import SimpleGP
from research.transients.models import AMPLITUDE_RANGE


def max_null_log_likelihood(t: np.ndarray, y: np.ndarray, sigma: np.ndarray, classes: tuple[str, ...],
                            flux_fn_resolver: Callable[[str], Callable],
                            amp_range: tuple[float, float] = AMPLITUDE_RANGE) -> float:
    """sup over modeled classes and A in amp_range of the Gaussian log-likelihood."""
    t, y, sigma = (np.asarray(a, dtype=float) for a in (t, y, sigma))
    w = 1.0 / sigma ** 2
    const = float(np.sum(-0.5 * np.log(2 * np.pi * sigma ** 2)))
    best = -np.inf
    for cls in classes:
        f = np.asarray(flux_fn_resolver(cls)(t, 1.0), dtype=float)  # unit-amplitude template
        ff = float(np.sum(w * f * f))
        a_hat = float(np.sum(w * y * f)) / ff if ff > 0 else amp_range[0]
        a_hat = float(np.clip(a_hat, amp_range[0], amp_range[1]))
        ll = const - 0.5 * float(np.sum(w * (y - a_hat * f) ** 2))
        best = max(best, ll)
    return best


def log_e_value(t, y, sigma, classes, flux_fn_resolver, gp: SimpleGP) -> float:
    """log E for the data (t, y, sigma); 0 (E = 1) for no data."""
    if len(t) == 0:
        return 0.0
    t, y, sigma = (np.asarray(a, dtype=float) for a in (t, y, sigma))
    return float(gp.log_marginal_likelihood(t, y, sigma) - max_null_log_likelihood(t, y, sigma, classes,
                                                                                    flux_fn_resolver))


def log_mean_exp(log_es) -> float:
    """log of the arithmetic mean of e-values (valid under any dependence)."""
    a = np.asarray(list(log_es), dtype=float)
    if a.size == 0:
        return 0.0
    m = float(np.max(a))
    return m + float(np.log(np.mean(np.exp(a - m))))


def alarm(log_e: float, alpha: float) -> bool:
    return log_e >= np.log(1.0 / alpha)
