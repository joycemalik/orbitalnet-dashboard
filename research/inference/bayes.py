"""Closed-world Bayesian update over a discrete (class, amplitude) joint grid.

Each modeled class h has one unknown nuisance parameter, the amplitude A,
with a shared log-uniform prior discretized onto a grid. The joint hypothesis
space is the Cartesian product {classes} x {amplitude grid}; because both are
discrete and the noise is Gaussian, the posterior update is exact (no
sampling), which is what makes it testable against known answers.

Equation implemented (per measurement y_k at time t_k):
    p(y_k | h, A) = Normal(y_k; f_h(t_k, A), sigma^2)
    posterior(h, A) ∝ prior(h, A) * prod_k p(y_k | h, A)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from research.transients.models import MODELED_CLASSES, AMPLITUDE_RANGE, modeled_flux_fn


def default_amplitude_grid(n_points: int = 25) -> np.ndarray:
    lo, hi = AMPLITUDE_RANGE
    return np.exp(np.linspace(np.log(lo), np.log(hi), n_points))


@dataclass
class ClosedWorldBelief:
    """Joint log-posterior over (class, amplitude), stored as log-probabilities
    for numerical stability. Rows = classes (in `classes` order), columns =
    `amplitude_grid`.

    `flux_fn_resolver` maps a class name to its f(t, amplitude) flux function;
    it defaults to Phase 1's two-class resolver, but Phase 2+ passes
    `transients.models.modeled_flux_fn_p2` to use the 4-class hypothesis
    space without duplicating this class.
    """

    classes: tuple[str, ...]
    amplitude_grid: np.ndarray
    log_joint: np.ndarray  # shape (n_classes, n_amplitudes), not yet guaranteed normalized
    flux_fn_resolver: Callable[[str], Callable] = field(default=modeled_flux_fn, repr=False, compare=False)

    @classmethod
    def with_uniform_prior(cls, classes: tuple[str, ...] = MODELED_CLASSES,
                            amplitude_grid: np.ndarray | None = None,
                            flux_fn_resolver: Callable[[str], Callable] = modeled_flux_fn) -> "ClosedWorldBelief":
        if amplitude_grid is None:
            amplitude_grid = default_amplitude_grid()
        n_classes, n_amp = len(classes), len(amplitude_grid)
        log_prior = np.full((n_classes, n_amp), -np.log(n_classes * n_amp))
        return cls(classes=classes, amplitude_grid=amplitude_grid, log_joint=log_prior,
                    flux_fn_resolver=flux_fn_resolver)

    def copy(self) -> "ClosedWorldBelief":
        return ClosedWorldBelief(self.classes, self.amplitude_grid, self.log_joint.copy(), self.flux_fn_resolver)

    def log_likelihood_grid(self, t: float, y: float, sigma: float) -> np.ndarray:
        """log p(y | h, A) for every (h, A) cell, at measurement time t."""
        out = np.empty_like(self.log_joint)
        for i, cls in enumerate(self.classes):
            f = self.flux_fn_resolver(cls)
            means = f(np.full_like(self.amplitude_grid, t), self.amplitude_grid)
            out[i, :] = -0.5 * np.log(2 * np.pi * sigma ** 2) - 0.5 * ((y - means) / sigma) ** 2
        return out

    def update(self, t: float, y: float, sigma: float) -> None:
        """In-place Bayesian update given one new measurement (t, y)."""
        self.log_joint = self.log_joint + self.log_likelihood_grid(t, y, sigma)

    def normalized_log_joint(self) -> np.ndarray:
        m = np.max(self.log_joint)
        log_z = m + np.log(np.sum(np.exp(self.log_joint - m)))
        return self.log_joint - log_z

    def log_evidence(self) -> float:
        """log p(data so far) = log sum_{h,A} joint(h, A), under the CURRENT
        (unnormalized-since-prior) log_joint. Valid because log_joint started
        as a normalized prior and each update multiplies in a likelihood."""
        m = np.max(self.log_joint)
        return float(m + np.log(np.sum(np.exp(self.log_joint - m))))

    def class_log_evidence(self) -> dict[str, float]:
        """log p(data | class=h), marginalized over the amplitude grid under
        its own uniform 1/n_amp prior (independent of n_classes). Valid
        because log_joint started as a uniform prior over (class, amplitude)
        and each update only ever adds log-likelihood terms."""
        n_classes = len(self.classes)
        row_logsumexp = np.logaddexp.reduce(self.log_joint, axis=1)
        return {cls: float(row_logsumexp[i] + np.log(n_classes)) for i, cls in enumerate(self.classes)}

    def class_posterior(self) -> dict[str, float]:
        log_norm = self.normalized_log_joint()
        class_log_probs = np.logaddexp.reduce(log_norm, axis=1)
        probs = np.exp(class_log_probs)
        probs = probs / probs.sum()
        return {cls: float(p) for cls, p in zip(self.classes, probs)}

    def entropy(self) -> float:
        """Shannon entropy (nats) of the marginal posterior over classes."""
        probs = np.array(list(self.class_posterior().values()))
        probs = probs[probs > 0]
        return float(-np.sum(probs * np.log(probs)))
