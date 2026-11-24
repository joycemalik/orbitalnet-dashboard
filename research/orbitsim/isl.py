"""Phase 4: inter-satellite links (ISL) from real TLE geometry.

Two satellites can exchange messages at an instant iff (i) their separation is
at most the link range R, and (ii) the straight line between them clears the
Earth plus a grazing altitude (atmosphere / terrain margin). Links are
evaluated on a fixed sub-sampling grid, and information spreads by
store-and-forward flooding: at each instant every connected component of the
link graph pools what its members know (multi-hop, light-time ignored).

Decision (user, 2026-11-24): ISL line-of-sight with a range sweep, rather than
ground-relay passes or an abstract link probability.
"""

from __future__ import annotations

import datetime

import numpy as np
from sgp4.api import Satrec, jday

from research.orbitsim.geometry import EARTH_RADIUS_KM

GRAZING_ALTITUDE_KM = 80.0       # a link must clear Earth radius + this
SUBSAMPLE_STEP_DAYS = 2.0 / 1440  # 2-minute link-evaluation grid


def positions_eci_km(fleet: dict[str, Satrec], t0: datetime.datetime, t_days: np.ndarray) -> np.ndarray:
    """Vectorised SGP4: (n_times, n_sats, 3) ECI positions at t0 + t_days.
    Cells where SGP4 reports an error are NaN (treated as no link / not visible)."""
    jd0, fr0 = jday(t0.year, t0.month, t0.day, t0.hour, t0.minute, t0.second + t0.microsecond / 1e6)
    t_days = np.asarray(t_days, dtype=float)
    jd = np.full_like(t_days, jd0)
    fr = fr0 + t_days
    out = np.empty((len(t_days), len(fleet), 3))
    for j, sat in enumerate(fleet.values()):
        err, r, _v = sat.sgp4_array(jd, fr)
        r = np.asarray(r, dtype=float)
        r[np.asarray(err) != 0] = np.nan
        out[:, j, :] = r
    return out


def line_of_sight(p1: np.ndarray, p2: np.ndarray, min_radius_km: float) -> np.ndarray:
    """Vectorised: True where the segment p1-p2 stays above `min_radius_km`
    from Earth's centre. p1, p2: (..., 3)."""
    d = p2 - p1
    dd = np.sum(d * d, axis=-1)
    s = np.clip(-np.sum(p1 * d, axis=-1) / np.where(dd > 0, dd, 1.0), 0.0, 1.0)
    closest = p1 + s[..., None] * d
    return np.linalg.norm(closest, axis=-1) >= min_radius_km


def link_adjacency(pos: np.ndarray, range_km: float) -> np.ndarray:
    """pos: (n_times, n_sats, 3) -> bool (n_times, n_sats, n_sats) link graph
    (symmetric, no self-loops). range_km <= 0 gives no links; np.inf gives
    pure line-of-sight."""
    n_t, n_s, _ = pos.shape
    adj = np.zeros((n_t, n_s, n_s), dtype=bool)
    if range_km <= 0:
        return adj
    p1 = pos[:, :, None, :]
    p2 = pos[:, None, :, :]
    dist = np.linalg.norm(p1 - p2, axis=-1)
    los = line_of_sight(np.broadcast_to(p1, dist.shape + (3,)), np.broadcast_to(p2, dist.shape + (3,)),
                        EARTH_RADIUS_KM + GRAZING_ALTITUDE_KM)
    adj = (dist <= range_km) & los
    adj &= np.isfinite(dist)
    idx = np.arange(n_s)
    adj[:, idx, idx] = False
    return adj


def component_closure(adj_t: np.ndarray) -> np.ndarray:
    """Bool (n, n): C[i, j] = i and j are in the same connected component
    (reflexive). Instantaneous multi-hop relay."""
    n = adj_t.shape[0]
    c = adj_t | np.eye(n, dtype=bool)
    for _ in range(n):
        nxt = (c.astype(np.uint8) @ c.astype(np.uint8)) > 0
        if np.array_equal(nxt, c):
            break
        c = nxt
    return c


def components(adj_t: np.ndarray) -> list[list[int]]:
    """Connected components at one instant, each as a sorted list of indices,
    ordered by smallest member (deterministic)."""
    closure = component_closure(adj_t)
    seen, out = set(), []
    for i in range(adj_t.shape[0]):
        if i in seen:
            continue
        members = [int(j) for j in np.flatnonzero(closure[i])]
        seen.update(members)
        out.append(members)
    return out


def interval_reach(adj_seq: np.ndarray) -> np.ndarray:
    """Store-and-forward reachability over a time-ordered sequence of link
    graphs. M[i, j] = information j held at the start of the interval has
    reached i by its end. Reflexive."""
    n = adj_seq.shape[1]
    reach = np.eye(n, dtype=bool)
    prev = None
    for adj_t in adj_seq:
        # Re-applying the same component closure is idempotent (reach is
        # already closed under it), so only act when the graph changes.
        if not adj_t.any() or (prev is not None and np.array_equal(adj_t, prev)):
            prev = adj_t
            continue
        prev = adj_t
        c = component_closure(adj_t)
        reach = (c.astype(np.uint8) @ reach.astype(np.uint8)) > 0
    return reach


def subsample_grid(epochs_days: np.ndarray, step_days: float = SUBSAMPLE_STEP_DAYS) -> tuple[np.ndarray, list[slice]]:
    """Link-evaluation times: for each epoch k, the half-open interval
    (t_{k-1}, t_k] sampled every `step_days` and always including t_k
    (interval 0 is just {t_0}). Returns (times, slices) with slices[k]
    indexing interval k inside `times`."""
    times, slices, start = [], [], 0
    prev = None
    for t in epochs_days:
        if prev is None:
            pts = [float(t)]
        else:
            n = max(1, int(np.ceil((t - prev) / step_days)))
            pts = list(np.linspace(prev, t, n + 1)[1:])
        times.extend(pts)
        slices.append(slice(start, start + len(pts)))
        start += len(pts)
        prev = t
    return np.asarray(times), slices


def epoch_link_plan(fleet: dict[str, Satrec], t0: datetime.datetime, epochs_days: np.ndarray,
                    ranges_km: list[float]) -> dict:
    """For every link range R: per epoch k, the store-and-forward reach over
    (t_{k-1}, t_k] and the instantaneous components at t_k, plus link-up
    fraction. Positions at the epochs are returned too (for visibility)."""
    times, slices = subsample_grid(epochs_days)
    pos = positions_eci_km(fleet, t0, times)
    epoch_pos = np.stack([pos[s][-1] for s in slices])
    plan = {"epoch_positions": epoch_pos, "by_range": {}}
    n = len(fleet)
    for r in ranges_km:
        adj = link_adjacency(pos, r)
        reach = np.stack([interval_reach(adj[s]) for s in slices])
        comps = [components(adj[s][-1]) for s in slices]
        pair_up = adj[:, np.triu_indices(n, 1)[0], np.triu_indices(n, 1)[1]]
        plan["by_range"][r] = {"reach": reach, "components": comps,
                               "link_up_fraction": float(pair_up.mean())}
    return plan
