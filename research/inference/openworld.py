"""Open-world hypothesis h0: a flexible Gaussian Process stands in for "no
modeled class fits." Its model evidence (log marginal likelihood) is
compared against each modeled class's evidence (marginalized over the
amplitude nuisance parameter) in a single top-level Bayes-factor comparison
over {class_1, ..., class_K, h0}.

Phase 1 fixes the GP kernel hyperparameters rather than optimizing them
(notebook-sized existence proof); Phase 2+ may revisit this.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from research.inference.bayes import ClosedWorldBelief
from research.transients.noise import SIGMA0

GP_LENGTHSCALE = 1.2  # days
GP_VAR_F = 100.0      # prior variance of the latent function, flux^2 units


@dataclass
class SimpleGP:
    """Exact GP regression with a fixed RBF kernel and zero prior mean."""

    lengthscale: float = GP_LENGTHSCALE
    var_f: float = GP_VAR_F
    sigma_n: float = SIGMA0

    def kernel(self, x1: np.ndarray, x2: np.ndarray) -> np.ndarray:
        d2 = (x1[:, None] - x2[None, :]) ** 2
        return self.var_f * np.exp(-0.5 * d2 / self.lengthscale ** 2)

    def _sigma_n_arr(self, n: int, sigma_n_arr) -> np.ndarray:
        if sigma_n_arr is None:
            return np.full(n, self.sigma_n)
        return np.asarray(sigma_n_arr, dtype=float)

    def _cholesky(self, t: np.ndarray, sigma_n_arr=None) -> np.ndarray:
        n = len(t)
        K = self.kernel(t, t) + np.diag(self._sigma_n_arr(n, sigma_n_arr) ** 2)
        return np.linalg.cholesky(K)

    def log_marginal_likelihood(self, t: np.ndarray, y: np.ndarray, sigma_n_arr=None) -> float:
        """Equation: log p(y|X) = -1/2 y^T K^-1 y - 1/2 log|K| - n/2 log(2 pi).
        `sigma_n_arr`, if given, is a per-observation noise std (Phase 2+,
        heterogeneous instruments); defaults to `self.sigma_n` for every
        point (Phase 1 behavior)."""
        t = np.asarray(t, dtype=float)
        y = np.asarray(y, dtype=float)
        n = len(t)
        if n == 0:
            return 0.0
        L = self._cholesky(t, sigma_n_arr)
        alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))
        quad = float(y @ alpha)
        log_det = 2.0 * np.sum(np.log(np.diag(L)))
        return -0.5 * quad - 0.5 * log_det - 0.5 * n * np.log(2 * np.pi)

    def predict(self, t_obs: np.ndarray, y_obs: np.ndarray, t_star: float,
                sigma_n_arr=None, candidate_sigma_n: float | None = None) -> tuple[float, float]:
        """Posterior predictive mean and std (including observation noise) for
        one new candidate measurement time t_star. `candidate_sigma_n` is the
        noise of the instrument that WOULD take this candidate measurement
        (Phase 2+); defaults to `self.sigma_n` (Phase 1 behavior)."""
        t_obs = np.asarray(t_obs, dtype=float)
        y_obs = np.asarray(y_obs, dtype=float)
        cand_sigma = self.sigma_n if candidate_sigma_n is None else candidate_sigma_n
        if len(t_obs) == 0:
            return 0.0, float(np.sqrt(self.var_f + cand_sigma ** 2))
        L = self._cholesky(t_obs, sigma_n_arr)
        k_star = self.kernel(t_obs, np.array([t_star]))[:, 0]
        alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_obs))
        mean_star = float(k_star @ alpha)
        v = np.linalg.solve(L, k_star)
        var_star = self.var_f - float(v @ v)
        var_star = max(var_star, 1e-12) + cand_sigma ** 2
        return mean_star, float(np.sqrt(var_star))


def open_world_posterior(
    belief: ClosedWorldBelief,
    t_obs: np.ndarray,
    y_obs: np.ndarray,
    gp: SimpleGP,
    sigma_n_arr=None,
) -> dict[str, float]:
    """Top-level posterior over {modeled classes..., "h0"}, combining each
    modeled class's evidence (marginalized over amplitude) with the GP's
    evidence, under a uniform prior across the K+1 hypotheses. `sigma_n_arr`
    carries per-observation instrument noise for Phase 2+ (None -> Phase 1's
    single fixed `gp.sigma_n` for every point)."""
    n_classes = len(belief.classes)
    n_hyp = n_classes + 1
    log_prior = -np.log(n_hyp)

    class_log_evidence = belief.class_log_evidence()
    log_post = {cls: log_prior + ev for cls, ev in class_log_evidence.items()}
    log_post["h0"] = log_prior + gp.log_marginal_likelihood(t_obs, y_obs, sigma_n_arr)

    m = max(log_post.values())
    log_z = m + np.log(sum(np.exp(v - m) for v in log_post.values()))
    return {k: float(np.exp(v - log_z)) for k, v in log_post.items()}
