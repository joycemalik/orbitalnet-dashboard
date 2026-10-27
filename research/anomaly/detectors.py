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


def detect_steps(series: pd.DataFrame, column: str = "SMA_KM", *, z: float = 8.0,
                 min_step: float = 0.5, window: int = 15, merge_days: float = 2.0,
                 kinds: tuple[str, str] = ("maneuver_raise", "maneuver_lower")) -> list[Event]:
    """Flag step changes in `column` whose size exceeds both `z` robust sigmas of
    the object's own residual noise and an absolute floor `min_step`.
    Consecutive flagged steps within `merge_days` merge into one burn sequence."""
    if len(series) < 10:
        return []
    t = (series.EPOCH - series.EPOCH.iloc[0]).dt.total_seconds().to_numpy() / 86400.0
    y = series[column].to_numpy(dtype=float)
    r = _step_residuals(t, y, window)
    sigma = _mad_sigma(r)
    if not np.isfinite(sigma):
        return []
    sigma = max(sigma, 1e-6)
    hits = np.flatnonzero((np.abs(r) > z * sigma) & (np.abs(r) > min_step))
    events: list[Event] = []
    norad = int(series.NORAD_CAT_ID.iloc[0])
    group: list[int] = []
    for i in list(hits) + [None]:
        if group and (i is None or t[i] - t[group[-1] + 1] > merge_days or np.sign(r[i]) != np.sign(r[group[0]])):
            total = float(r[group].sum())
            events.append(Event(norad, kinds[0] if total > 0 else kinds[1],
                                series.EPOCH.iloc[group[0]], series.EPOCH.iloc[group[-1] + 1],
                                total, float(np.max(np.abs(r[group])) / sigma)))
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
