"""Explainable anomaly detectors over one object's element series.

All thresholds are function arguments with defaults that are placeholders
only: they get tuned on the 2021-2023 validation window (Phase 3) and frozen
in PREREGISTRATION_SA.md before the held-out window is touched.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from research.anomaly.elements import geo_drift_deg_day


@dataclass
class Event:
    norad: int
    kind: str  # "maneuver_raise" | "maneuver_lower" | "plane_change" | "sk_stopped" | "geo_drift_change"
    epoch_start: pd.Timestamp
    epoch_end: pd.Timestamp
    magnitude: float  # km for SMA steps, deg for inclination, deg/day for drift
    score: float  # robust z-score of the step against the object's own noise
    storm: bool = False  # set by spaceweather.tag_storm: overlaps a geomagnetic storm day

    def to_dict(self) -> dict:
        d = asdict(self)
        d["epoch_start"] = self.epoch_start.isoformat()
        d["epoch_end"] = self.epoch_end.isoformat()
        return d


def _mad_sigma(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) < 5:
        return np.nan
    return 1.4826 * float(np.median(np.abs(x - np.median(x))))


def _step_residuals(t_days: np.ndarray, y: np.ndarray, window: int) -> np.ndarray:
    """Step between consecutive sets, minus what the local (rolling-median)
    trend predicts for that gap. Drag decay is the trend; maneuvers are
    departures from it."""
    dy = np.diff(y)
    dt = np.diff(t_days)
    rate = np.where(dt > 0, dy / np.where(dt > 0, dt, 1), np.nan)
    trend = pd.Series(rate).rolling(window, center=True, min_periods=3).median().to_numpy()
    return dy - trend * dt


def despike(series: pd.DataFrame, column: str, *, z: float = 8.0, window: int = 15,
            cancel_frac: float = 0.2) -> pd.DataFrame:
    """Drop isolated bad element sets: a point whose step in and step out are both
    large, opposite in sign, and nearly cancel (|in + out| < cancel_frac * min).
    A real burn leaves the orbit changed; a bad TLE jumps out and straight back."""
    if len(series) < 10:
        return series
    t = (series.EPOCH - series.EPOCH.iloc[0]).dt.total_seconds().to_numpy() / 86400.0
    r = _step_residuals(t, series[column].to_numpy(dtype=float), window)
    sigma = max(_mad_sigma(r), 1e-6)
    a, b = r[:-1], r[1:]  # step into point i+1, step out of point i+1
    big = (np.abs(a) > z * sigma) & (np.abs(b) > z * sigma)
    cancels = (np.sign(a) != np.sign(b)) & (np.abs(a + b) < cancel_frac * np.minimum(np.abs(a), np.abs(b)))
    drop = np.flatnonzero(big & cancels) + 1
    out = series.drop(series.index[drop])
    out.attrs = {**series.attrs, "despiked": series.attrs.get("despiked", 0) + len(drop)}
    return out


def detect_steps(series: pd.DataFrame, column: str = "SMA_KM", *, z: float = 8.0,
                 min_step: float = 0.5, window: int = 15, merge_days: float = 2.0,
                 max_gap_days: float = 3.0, kinds: tuple[str, str] = ("maneuver_raise", "maneuver_lower")) -> list[Event]:
    """Flag step changes in `column` larger than `z` robust sigmas of the object's
    own residual noise. Consecutive flagged steps within `merge_days` merge into
    one burn sequence, and a sequence is kept only if its total reaches the
    absolute floor `min_step` (element-set fits lag a burn, so one maneuver is
    often spread over two or three sets).
    Across a tracking gap the sigma threshold grows by gap / `max_gap_days`:
    the trend error accumulates with the gap, but gaps are NOT skipped, because
    Space-Track often stops publishing right after a burn (e.g. ISS, 16-19 Jun 2022)."""
    series = despike(series, column, z=z, window=window)
    if len(series) < 10:
        return []
    t = (series.EPOCH - series.EPOCH.iloc[0]).dt.total_seconds().to_numpy() / 86400.0
    y = series[column].to_numpy(dtype=float)
    r = _step_residuals(t, y, window)
    sigma = _mad_sigma(r)
    if not np.isfinite(sigma):
        return []
    sigma = max(sigma, 1e-6)
    gap_scale = np.maximum(1.0, np.diff(t) / max_gap_days)
    hits = np.flatnonzero(np.abs(r) > z * sigma * gap_scale)
    events: list[Event] = []
    norad = int(series.NORAD_CAT_ID.iloc[0])
    group: list[int] = []
    for i in list(hits) + [None]:
        if group and (i is None or t[i] - t[group[-1] + 1] > merge_days or np.sign(r[i]) != np.sign(r[group[0]])):
            total = float(r[group].sum())
            if abs(total) >= min_step:
                events.append(Event(norad, kinds[0] if total > 0 else kinds[1],
                                    series.EPOCH.iloc[group[0]], series.EPOCH.iloc[group[-1] + 1],
                                    total, float(np.max(np.abs(r[group] / gap_scale[group])) / sigma)))
            group = []
        if i is not None:
            group.append(i)
    return events


def detect_plane_changes(series: pd.DataFrame, **kw) -> list[Event]:
    kw.setdefault("min_step", 0.01)
    return detect_steps(series, "INCLINATION", kinds=("plane_change", "plane_change"), **kw)


def detect_sk_stopped(series: pd.DataFrame, maneuvers: list[Event], *, quiet_days: float = 60.0,
                      min_prior_burns: int = 3, min_decay_km: float = 5.0) -> list[Event]:
    """Object that used to station-keep (>= min_prior_burns raises) has had no
    burn for `quiet_days` and has lost >= min_decay_km since its last one.
    This is the 'silent death / end of mission' signature."""
    raises = [e for e in maneuvers if e.kind == "maneuver_raise"]
    if len(raises) < min_prior_burns or series.empty:
        return []
    last = max(e.epoch_end for e in raises)
    after = series[series.EPOCH > last]
    if after.empty:
        return []
    quiet = (after.EPOCH.iloc[-1] - last).total_seconds() / 86400.0
    lost = float(after.SMA_KM.iloc[0] - after.SMA_KM.iloc[-1])
    if quiet < quiet_days or lost < min_decay_km:
        return []
    return [Event(int(series.NORAD_CAT_ID.iloc[0]), "sk_stopped", last, after.EPOCH.iloc[-1], lost, quiet)]


def detect_geo_drift_changes(series: pd.DataFrame, *, min_change: float = 0.05, **kw) -> list[Event]:
    """Near-GEO only: steps in longitude drift rate = start/stop of a relocation."""
    s = series[(series.MEAN_MOTION > 0.9) & (series.MEAN_MOTION < 1.1)].copy()
    if len(s) < 10:
        return []
    s["DRIFT"] = geo_drift_deg_day(s.MEAN_MOTION.to_numpy())
    kw.setdefault("min_step", min_change)
    return detect_steps(s, "DRIFT", kinds=("geo_drift_change", "geo_drift_change"), **kw)
