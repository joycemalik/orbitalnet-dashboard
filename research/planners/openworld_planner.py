"""Strategy P: expected-information-gain planner over the open-world
hypothesis set {modeled classes..., h0}. Unlike B3, the mixture it scores
candidate measurements against includes the GP's (h0) predictive, so a
measurement that would mainly help distinguish "fits no model" from "fits
some model" can win over one that only separates the two modeled classes.
"""

from __future__ import annotations

import numpy as np

from research.inference.bayes import ClosedWorldBelief
from research.inference.mutual_information import expected_information_gain
from research.inference.openworld import SimpleGP, open_world_posterior
from research.transients.noise import SIGMA0


def _amplitude_conditional_posterior(belief: ClosedWorldBelief) -> np.ndarray:
    """p(amplitude | class=h, data) per class row, independent of the
    class's overall posterior weight (see bayes.ClosedWorldBelief.class_log_evidence
    for why a row's shape alone gives this)."""
    n_classes, n_amp = belief.log_joint.shape
    out = np.empty((n_classes, n_amp))
    for i in range(n_classes):
        row = belief.log_joint[i]
        m = np.max(row)
        p = np.exp(row - m)
        out[i] = p / p.sum()
    return out


def open_world_eig_planner(
    rng: np.random.Generator,
    candidate_times: np.ndarray,
    remaining_mask: np.ndarray,
    belief: ClosedWorldBelief,
    t_obs,
    y_obs,
    gp: SimpleGP,
) -> int:
    idxs = np.flatnonzero(remaining_mask)
    n_classes, n_amp = belief.log_joint.shape

    ow_post = open_world_posterior(belief, t_obs, y_obs, gp)
    amp_cond = _amplitude_conditional_posterior(belief)
    class_weights = np.array([ow_post[cls] for cls in belief.classes])
    cell_weights = (class_weights[:, None] * amp_cond).ravel()
    weights = np.concatenate([cell_weights, [ow_post["h0"]]])
    weights = weights / weights.sum()
    log_weights = np.log(np.clip(weights, 1e-300, None))

    group_idx = np.concatenate([np.repeat(np.arange(n_classes), n_amp), [n_classes]])
    n_groups = n_classes + 1

    best_idx, best_eig = int(idxs[0]), -np.inf
    for idx in idxs:
        t_cand = float(candidate_times[idx])
        modeled_means = np.concatenate([
            belief.flux_fn_resolver(cls)(np.full(n_amp, t_cand), belief.amplitude_grid)
            for cls in belief.classes
        ])
        gp_mean, gp_std = gp.predict(np.asarray(t_obs), np.asarray(y_obs), t_cand)
        means = np.concatenate([modeled_means, [gp_mean]])
        sigmas = np.concatenate([np.full(n_classes * n_amp, SIGMA0), [gp_std]])
        eig = expected_information_gain(log_weights, means, sigmas, group_idx, n_groups)
        if eig > best_eig:
            best_eig, best_idx = eig, int(idx)
    return best_idx
