"""Strategy B3: closed-world expected-information-gain planner. Picks the
candidate time that maximizes EIG about the class label, considering only
the two modeled classes — it has no concept of h0 and so cannot express
"this doesn't fit any model."
"""

from __future__ import annotations

import numpy as np

from research.inference.bayes import ClosedWorldBelief
from research.inference.mutual_information import expected_information_gain
from research.transients.models import modeled_flux_fn
from research.transients.noise import SIGMA0


def closed_world_eig_planner(
    rng: np.random.Generator,
    candidate_times: np.ndarray,
    remaining_mask: np.ndarray,
    belief: ClosedWorldBelief,
    t_obs,
    y_obs,
    gp=None,
) -> int:
    idxs = np.flatnonzero(remaining_mask)
    n_classes, n_amp = belief.log_joint.shape
    log_weights = belief.normalized_log_joint().ravel()
    group_idx = np.repeat(np.arange(n_classes), n_amp)

    best_idx, best_eig = int(idxs[0]), -np.inf
    for idx in idxs:
        t_cand = candidate_times[idx]
        means = np.concatenate([
            modeled_flux_fn(cls)(np.full(n_amp, t_cand), belief.amplitude_grid)
            for cls in belief.classes
        ])
        eig = expected_information_gain(log_weights, means, SIGMA0, group_idx, n_classes)
        if eig > best_eig:
            best_eig, best_idx = eig, int(idx)
    return best_idx
