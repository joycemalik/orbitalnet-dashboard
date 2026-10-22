"""Phase C: split-conformal open-set decisions with a distribution-free bound
on the false-"unknown" rate for KNOWN classes.

Setting. Any planner (B0-B3, P, L) runs on an event and ends with
measurements D. A nonconformity score s(D) is computed (here: the log Bayes
factor of the h0 GP against the best modeled class, `log_bf_score`). The
event is flagged "unknown" iff s(D) > tau, where tau is computed from the
scores of n CALIBRATION events whose class is known.

Guarantee (standard split conformal, e.g. Vovk et al. 2005; Angelopoulos &
Bates 2021). If the calibration scores of class c and the score of a new
class-c event are exchangeable (true when events are i.i.d. draws of the
whole pipeline -- light curve, orbit geometry, noise, planner), then with
tau_c = the ceil((n_c + 1)(1 - alpha))-th smallest calibration score,

    alpha - 1/(n_c + 1)  <=  P(s_new > tau_c)  <=  alpha        (no ties)

The upper bound needs no model of the score's distribution, no assumption
that the templates are right, and holds for any planner.

Label-shift robustness ("max rule"). Using tau = max_c tau_c gives
P(flag | class c) <= alpha for EVERY known class c simultaneously, so the
bound survives any change in the class mix between calibration and
deployment (the fresh set is ~half SN Ia; validation is balanced).

Consequence for accuracy. Flagging only removes decisions: if the
underlying closed-world decision is correct with probability a on known
events, the conformal decision is correct with probability >= a - alpha,
and its confident-wrong rate on known events can only go down.
"""

from __future__ import annotations

import math

import numpy as np


def conformal_threshold(cal_scores: np.ndarray, alpha: float) -> float:
    """tau such that P(s_new > tau) <= alpha for an exchangeable new score.
    Returns +inf when n is too small to certify alpha (never flag)."""
    s = np.sort(np.asarray(cal_scores, dtype=float))
    n = len(s)
    k = math.ceil((n + 1) * (1.0 - alpha))
    if k > n:
        return float("inf")
    return float(s[k - 1])


def class_conditional_threshold(cal_scores: np.ndarray, cal_labels, alpha: float,
                                classes=None) -> tuple[float, dict[str, float]]:
    """Max-rule threshold: max over classes of each class's own conformal
    threshold. Returns (tau, per-class taus)."""
    cal_scores = np.asarray(cal_scores, dtype=float)
    cal_labels = np.asarray(cal_labels)
    classes = sorted(set(cal_labels.tolist())) if classes is None else classes
    per = {c: conformal_threshold(cal_scores[cal_labels == c], alpha) for c in classes}
    return max(per.values()), per


def conformal_pvalue(cal_scores: np.ndarray, s: float) -> float:
    """(1 + #{cal >= s}) / (n + 1): super-uniform under exchangeability."""
    cal_scores = np.asarray(cal_scores, dtype=float)
    return float((1 + np.sum(cal_scores >= s)) / (len(cal_scores) + 1))


def log_bf_score(class_log_evidence: dict[str, float], h0_log_evidence: float) -> float:
    """log p(D | h0) - max_c log p(D | c). Prior-free (unlike P's posterior)."""
    return float(h0_log_evidence - max(class_log_evidence.values()))


def conformal_decision(closed_posterior: dict[str, float], score: float, tau: float,
                       confident_threshold: float) -> tuple[str, bool]:
    """('h0', False) if flagged, else (closed-world argmax, confident?)."""
    if score > tau:
        return "h0", False
    dec = max(closed_posterior, key=closed_posterior.get)
    return dec, bool(closed_posterior[dec] >= confident_threshold)


__all__ = ["conformal_threshold", "class_conditional_threshold", "conformal_pvalue", "log_bf_score",
           "conformal_decision"]
