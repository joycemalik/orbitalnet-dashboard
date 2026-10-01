"""Phase 2 strategies, realigned to Hypothesis-Discriminating
Observation Campaigns....pdf ("the manuscript"). Each strategy chooses
(time_idx, satellite_idx) among currently visible, not-yet-used cells of a
ContactSchedule, with per-satellite instrument noise (`instrument_sigma`,
indexed to match `schedule.satellite_names`).

Utility (manuscript eq. 3-4), strategy P only:

    U(a|b_t) = [ I_class(a) + beta * I_Z(a) + gamma * D(a, b_t) ] / cost(a)

I_class and I_Z are exact (reuse the batched EIG estimator from
research.inference.mutual_information — no new quadrature machinery). D is a
Fisher-information-style SNR^2 proxy for the per-class mutual information
I_k(Y_a) the manuscript's eq. 4 calls for, NOT that exact quantity — computing
I_k(Y_a) exactly would need one more quadrature per class per candidate per
step, which this branch's compute budget does not support at 1000-event
scale. Documented in research/LOG.md. cost(a) is fixed at 1 (uniform);
the manuscript's exposure/slew cost model is future work.
"""

from __future__ import annotations

import numpy as np

from research.inference.bayes import ClosedWorldBelief
from research.inference.mutual_information import expected_information_gain_batch
from research.inference.openworld import SimpleGP, open_world_posterior
from research.orbitsim.contacts import ContactSchedule
from research.planners.openworld_planner import _amplitude_conditional_posterior

DEFAULT_BETA = 1.0     # weight on the adequacy term I(Z; Y_a)
DEFAULT_GAMMA = 0.01   # weight on the decay term D(a, b_t) (SNR^2 units, not nats -- see module docstring)
MODE_SWITCH_TAU = 0.9  # P(h0) threshold; two consecutive steps above this trips preservation mode


def _feasible_cells(remaining_mask: np.ndarray) -> np.ndarray:
    return np.argwhere(remaining_mask)  # (n_feasible, 2) rows of (time_idx, sat_idx)


def fixed_cadence_planner(rng: np.random.Generator, schedule: ContactSchedule, remaining_mask, instrument_sigma,
                           belief: ClosedWorldBelief, t_obs, y_obs, sigma_obs, gp=None) -> tuple[int, int]:
    """B0: fixed recipe. Deterministically takes the earliest still-feasible
    time, breaking ties by lowest satellite index -- a regular cadence that
    never reacts to what the data say, standing in for the manuscript's
    "two bands every N hours" human-style practice."""
    cells = _feasible_cells(remaining_mask)
    order = np.lexsort((cells[:, 1], cells[:, 0]))
    best = order[0]
    return int(cells[best, 0]), int(cells[best, 1])


def cnp_reimplementation_planner(rng: np.random.Generator, schedule: ContactSchedule, remaining_mask,
                                  instrument_sigma, belief: ClosedWorldBelief, t_obs, y_obs, sigma_obs, gp=None,
                                  w_margin: float = 0.7, w_instrument: float = 0.3) -> tuple[int, int]:
    """B1: static-score dispatch, the same shape as consensus_engine.py's
    auction (gatekeeper -> weighted proximity+battery score -> argmax), with
    the visibility margin standing in for "proximity" and instrument
    sensitivity (1/sigma) standing in for "battery". No EIG, no belief, no
    hypothesis tracking — it never asks what a measurement would teach it.
    See research/PLAN.md section 1."""
    cells = _feasible_cells(remaining_mask)
    margins = schedule.margin_deg[cells[:, 0], cells[:, 1]]
    max_margin = float(np.max(schedule.margin_deg[schedule.visibility])) + 1e-9
    norm_margin = margins / max_margin

    sens = 1.0 / instrument_sigma[cells[:, 1]]
    max_sens = float(np.max(1.0 / instrument_sigma))
    norm_sens = sens / max_sens

    score = w_margin * norm_margin + w_instrument * norm_sens
    best = int(np.argmax(score))
    return int(cells[best, 0]), int(cells[best, 1])


def _modeled_means_for_times(belief: ClosedWorldBelief, t_cands: np.ndarray) -> np.ndarray:
    """Returns shape (n_cands, n_classes * n_amp): flattened (class, amplitude)
    predictive means for each candidate time, vectorized across candidates."""
    per_class = []
    for cls in belief.classes:
        f = belief.flux_fn_resolver(cls)
        # (n_cands, 1) and (1, n_amp) broadcast to (n_cands, n_amp) inside f,
        # which is pure elementwise arithmetic for every modeled class.
        means = f(t_cands[:, None], belief.amplitude_grid[None, :])
        per_class.append(means)  # (n_cands, n_amp)
    return np.concatenate(per_class, axis=1)  # (n_cands, n_classes * n_amp)


def classifier_entropy_planner(rng: np.random.Generator, schedule: ContactSchedule, remaining_mask,
                                instrument_sigma, belief: ClosedWorldBelief, t_obs, y_obs, sigma_obs,
                                gp=None) -> tuple[int, int]:
    """B2: classifier-entropy sampling. Picks the candidate where the
    modeled classes' predicted fluxes disagree most relative to noise, using
    a POINT ESTIMATE (posterior-mean) amplitude per class rather than the
    full Bayesian marginal-likelihood machinery B3/P use -- "no physics
    likelihoods" per the manuscript, i.e. a disagreement heuristic standing
    in for a real classifier's predicted-class-entropy signal, which this
    project does not otherwise have a trained classifier to compute."""
    cells = _feasible_cells(remaining_mask)
    amp_est = _per_class_posterior_mean_amplitude(belief)
    t_cands = schedule.candidate_times_days[cells[:, 0]]
    sigma_cands = instrument_sigma[cells[:, 1]]

    means = np.stack([
        belief.flux_fn_resolver(cls)(t_cands, np.full_like(t_cands, amp_est[k]))
        for k, cls in enumerate(belief.classes)
    ], axis=1)  # (n_cells, n_classes)
    disagreement = np.var(means, axis=1) / (sigma_cands ** 2 + 1e-12)
    best = int(np.argmax(disagreement))
    return int(cells[best, 0]), int(cells[best, 1])


def _class_only_eig_batch(belief: ClosedWorldBelief, t_cands: np.ndarray, sigma_cands: np.ndarray) -> np.ndarray:
    """I(H_1:K; Y_a | b_t): EIG about the class label alone, ignoring h0
    entirely (closed-world, matches B3's own computation exactly)."""
    n_classes, n_amp = belief.log_joint.shape
    log_weights = belief.normalized_log_joint().ravel()
    group_idx = np.repeat(np.arange(n_classes), n_amp)
    means_batch = _modeled_means_for_times(belief, t_cands)
    sigma_batch = sigma_cands[:, None]
    return expected_information_gain_batch(log_weights, means_batch, sigma_batch, group_idx, n_classes)


def closed_world_eig_planner_p2(rng: np.random.Generator, schedule: ContactSchedule, remaining_mask,
                                 instrument_sigma, belief: ClosedWorldBelief, t_obs, y_obs, sigma_obs,
                                 gp=None) -> tuple[int, int]:
    """B3: closed-world expected information gain, centralized, no decay
    term, no h0 -- the manuscript's POIE-style key comparison."""
    cells = _feasible_cells(remaining_mask)
    t_cands = schedule.candidate_times_days[cells[:, 0]]
    sigma_cands = instrument_sigma[cells[:, 1]]
    eigs = _class_only_eig_batch(belief, t_cands, sigma_cands)
    best_k = int(np.argmax(eigs))
    return int(cells[best_k, 0]), int(cells[best_k, 1])


def _per_class_posterior_mean_amplitude(belief: ClosedWorldBelief) -> np.ndarray:
    """Posterior-mean amplitude estimate per class (each class's own row,
    renormalized), used only by the cheap decay-term proxy and B2."""
    n_classes = len(belief.classes)
    out = np.empty(n_classes)
    for i in range(n_classes):
        row = belief.log_joint[i]
        m = np.max(row)
        p = np.exp(row - m)
        p = p / p.sum()
        out[i] = float(np.sum(p * belief.amplitude_grid))
    return out


def _next_visible_index(visibility: np.ndarray) -> np.ndarray:
    """For each (time_idx, sat_idx) cell, the smallest LATER time_idx where
    that satellite is visible again, or -1 if there is none."""
    n_times, n_sats = visibility.shape
    next_idx = np.full((n_times, n_sats), -1, dtype=int)
    for j in range(n_sats):
        last = -1
        for i in range(n_times - 1, -1, -1):
            next_idx[i, j] = last
            if visibility[i, j]:
                last = i
    return next_idx


def _decay_term_batch(belief: ClosedWorldBelief, schedule: ContactSchedule, instrument_sigma: np.ndarray,
                       cells: np.ndarray, t_cands: np.ndarray, sigma_cands: np.ndarray) -> np.ndarray:
    """D(a, b_t), approximated via SNR^2 loss between now and the next
    feasible slot for the same satellite (see module docstring)."""
    class_post = belief.class_posterior()
    b = np.array([class_post[c] for c in belief.classes])
    amp_est = _per_class_posterior_mean_amplitude(belief)

    next_idx = _next_visible_index(schedule.visibility)
    next_i = next_idx[cells[:, 0], cells[:, 1]]
    has_next = next_i >= 0
    t_next = np.where(has_next, schedule.candidate_times_days[np.clip(next_i, 0, None)], 0.0)

    means_now = np.stack([
        belief.flux_fn_resolver(cls)(t_cands, np.full_like(t_cands, amp_est[k]))
        for k, cls in enumerate(belief.classes)
    ], axis=1)  # (n_cells, n_classes)
    means_next = np.stack([
        belief.flux_fn_resolver(cls)(t_next, np.full_like(t_next, amp_est[k]))
        for k, cls in enumerate(belief.classes)
    ], axis=1)

    snr_now2 = (means_now / sigma_cands[:, None]) ** 2
    snr_next2 = np.where(has_next[:, None], (means_next / sigma_cands[:, None]) ** 2, 0.0)
    diff = np.clip(snr_now2 - snr_next2, 0.0, None)  # (n_cells, n_classes)
    return diff @ b  # (n_cells,)


def open_world_eig_planner_p2(rng: np.random.Generator, schedule: ContactSchedule, remaining_mask,
                               instrument_sigma, belief: ClosedWorldBelief, t_obs, y_obs, sigma_obs,
                               gp: SimpleGP, beta: float = DEFAULT_BETA, gamma: float = DEFAULT_GAMMA
                               ) -> tuple[int, int]:
    """P: full method. U = I_class + beta*I_Z + gamma*D, all per candidate
    (time, satellite); the GP's own predictive noise depends on which
    instrument is being asked about."""
    cells = _feasible_cells(remaining_mask)
    n_classes, n_amp = belief.log_joint.shape
    sigma_obs_arr = np.array(sigma_obs, dtype=float) if len(sigma_obs) else None
    t_obs_arr, y_obs_arr = np.asarray(t_obs, dtype=float), np.asarray(y_obs, dtype=float)
    t_cands = schedule.candidate_times_days[cells[:, 0]]
    sigma_cands = instrument_sigma[cells[:, 1]]

    i_class = _class_only_eig_batch(belief, t_cands, sigma_cands)

    ow_post = open_world_posterior(belief, t_obs_arr, y_obs_arr, gp, sigma_obs_arr)
    amp_cond = _amplitude_conditional_posterior(belief)
    class_weights = np.array([ow_post[cls] for cls in belief.classes])
    cell_weights = (class_weights[:, None] * amp_cond).ravel()
    weights = np.concatenate([cell_weights, [ow_post["h0"]]])
    weights = weights / weights.sum()
    log_weights = np.log(np.clip(weights, 1e-300, None))

    modeled_means_batch = _modeled_means_for_times(belief, t_cands)
    gp_means = np.empty(len(cells))
    gp_stds = np.empty(len(cells))
    for k in range(len(cells)):
        gp_means[k], gp_stds[k] = gp.predict(
            t_obs_arr, y_obs_arr, float(t_cands[k]),
            sigma_n_arr=sigma_obs_arr, candidate_sigma_n=float(sigma_cands[k]),
        )
    means_batch = np.concatenate([modeled_means_batch, gp_means[:, None]], axis=1)
    sigma_batch = np.concatenate(
        [np.broadcast_to(sigma_cands[:, None], (len(cells), n_classes * n_amp)), gp_stds[:, None]], axis=1
    )
    # I(Z; Y_a): group 0 = every modeled cell, group 1 = the single h0 cell.
    z_group_idx = np.concatenate([np.zeros(n_classes * n_amp, dtype=int), [1]])
    i_z = expected_information_gain_batch(log_weights, means_batch, sigma_batch, z_group_idx, 2)

    decay = _decay_term_batch(belief, schedule, instrument_sigma, cells, t_cands, sigma_cands)

    utility = i_class + beta * i_z + gamma * decay  # cost(a) == 1 (uniform; see module docstring)
    best_k = int(np.argmax(utility))
    return int(cells[best_k, 0]), int(cells[best_k, 1])


STRATEGIES_P2 = {
    "B0_fixed_cadence": fixed_cadence_planner,
    "B1_cnp_reimplementation": cnp_reimplementation_planner,
    "B2_classifier_entropy": classifier_entropy_planner,
    "B3_closed_world_eig": closed_world_eig_planner_p2,
    "P_open_world_eig": open_world_eig_planner_p2,
}
