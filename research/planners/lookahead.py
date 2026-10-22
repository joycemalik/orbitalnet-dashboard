"""Phase C strategy L: P's utility plus the value of the options a causal
measurement closes.

Under the strictly-forward protocol (Phase 2c/6), measuring at epoch i
closes every epoch <= i. Greedy P ignores that: on the causal validation
replay it jumps to informative late epochs and ends with ~2.3 of its 5
measurements (fixed cadence uses all 5). L scores a cell (i, j) as

    S(i, j) = U(i, j) + lam * V_i,
    V_i     = sum of the (b_left - 1) largest u_e over epochs e > i,
    u_e     = max_j' U(e, j') among still-feasible cells at epoch e,

with U = P's own utility under the CURRENT belief (one batch evaluation,
no extra cost). V_i is a non-adaptive, additive estimate of what the rest
of the budget can still buy after choosing epoch i (it ignores redundancy,
so it overestimates; lam scales it). lam = 0 is exactly P.
"""

from __future__ import annotations

import numpy as np

from research.planners.phase2 import open_world_utility_batch
from research.transients.real_events import G_TIME_OFFSET_DAYS


def lookahead_values(cells: np.ndarray, utility: np.ndarray, n_times: int, n_left: int) -> np.ndarray:
    """V_i for each cell's epoch (see module docstring)."""
    best = np.full(n_times, -np.inf)
    np.maximum.at(best, cells[:, 0], utility)
    k = max(n_left - 1, 0)
    v_epoch = np.zeros(n_times)
    for i in range(n_times):
        later = best[i + 1:]
        later = np.sort(later[np.isfinite(later)])[::-1][:k]
        v_epoch[i] = float(np.sum(np.clip(later, 0.0, None)))
    return v_epoch[cells[:, 0]]


def make_lookahead_planner(lam: float, budget: int):
    def lookahead_planner(rng, schedule, remaining_mask, instrument_sigma, belief, t_obs, y_obs, sigma_obs, gp):
        n_done = int(np.sum(np.asarray(t_obs, dtype=float) < G_TIME_OFFSET_DAYS / 2))  # pointings, not g fluxes
        cells, utility = open_world_utility_batch(schedule, remaining_mask, instrument_sigma, belief,
                                                  t_obs, y_obs, sigma_obs, gp)
        score = utility + lam * lookahead_values(cells, utility, remaining_mask.shape[0], budget - n_done)
        best_k = int(np.argmax(score))
        return int(cells[best_k, 0]), int(cells[best_k, 1])
    return lookahead_planner


__all__ = ["lookahead_values", "make_lookahead_planner"]
