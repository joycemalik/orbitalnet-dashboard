"""B0-style baseline: picks the next measurement time uniformly at random
from whatever candidate times remain. Does not look at the belief at all.
"""

from __future__ import annotations

import numpy as np


def random_planner(rng: np.random.Generator, candidate_times, remaining_mask, belief, t_obs, y_obs, gp=None) -> int:
    idxs = np.flatnonzero(remaining_mask)
    return int(rng.choice(idxs))
