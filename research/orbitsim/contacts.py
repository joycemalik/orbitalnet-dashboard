"""Builds a per-seed visibility (contact) schedule: for a fixed fleet, a
fixed sky target direction, and a grid of candidate times, which satellites
can see the target at which times. This is the "contact graph" PLAN.md
promised to build headless, using real Earth-occlusion geometry instead of
the live stack's haversine hack.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import numpy as np
from sgp4.api import Satrec

from research.orbitsim.geometry import random_sky_direction, visibility_margin_deg
from research.orbitsim.tle import datetime_to_jd_fr, propagate_eci_km

REFERENCE_EPOCH = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


@dataclass
class ContactSchedule:
    satellite_names: tuple[str, ...]
    candidate_times_days: np.ndarray  # elapsed days since REFERENCE_EPOCH
    visibility: np.ndarray            # bool, shape (n_times, n_satellites)
    margin_deg: np.ndarray             # float, same shape; >=0 where visible (B1's continuous score)
    target_dir_eci: np.ndarray


def build_contact_schedule(
    fleet: dict[str, Satrec],
    candidate_times_days: np.ndarray,
    rng: np.random.Generator,
) -> ContactSchedule:
    names = tuple(fleet.keys())
    target_dir = random_sky_direction(rng)
    n_times, n_sats = len(candidate_times_days), len(names)
    margin = np.full((n_times, n_sats), -180.0)

    for i, t_days in enumerate(candidate_times_days):
        dt = REFERENCE_EPOCH + datetime.timedelta(days=float(t_days))
        jd, fr = datetime_to_jd_fr(dt)
        for j, name in enumerate(names):
            pos, _vel, err = propagate_eci_km(fleet[name], jd, fr)
            if err == 0:
                margin[i, j] = visibility_margin_deg(pos, target_dir)

    visibility = margin >= 0.0
    return ContactSchedule(
        satellite_names=names,
        candidate_times_days=np.asarray(candidate_times_days, dtype=float),
        visibility=visibility,
        margin_deg=margin,
        target_dir_eci=target_dir,
    )


def contact_fraction(schedule: ContactSchedule) -> float:
    """Fraction of (time, satellite) cells with visibility — used directly by
    the Phase 4 contact-fraction sweep."""
    return float(np.mean(schedule.visibility))


def build_contact_schedule_historical(
    fleets_by_epoch: list[tuple[datetime.datetime, dict[str, Satrec]]],
    satellite_names: tuple[str, ...],
    t0: datetime.datetime,
    candidate_times_days: np.ndarray,
    target_dir: np.ndarray,
    max_tle_age_days: float,
) -> tuple[ContactSchedule, np.ndarray]:
    """Phase 3: real date, real sky direction, archived TLEs. For each
    candidate time t0 + t, each satellite is propagated from the element set
    whose epoch is nearest in time (from `fleets_by_epoch`, sorted by epoch).
    Cells whose nearest TLE is older/newer than `max_tle_age_days`, or whose
    satellite is absent from that file, are marked NOT visible rather than
    propagated far outside SGP4's useful range. Returns (schedule, tle_age_days)."""
    epochs = np.array([e.timestamp() for e, _ in fleets_by_epoch])
    n_times, n_sats = len(candidate_times_days), len(satellite_names)
    margin = np.full((n_times, n_sats), -180.0)
    tle_age = np.full((n_times, n_sats), np.inf)

    for i, t_days in enumerate(candidate_times_days):
        dt = t0 + datetime.timedelta(days=float(t_days))
        jd, fr = datetime_to_jd_fr(dt)
        for j, name in enumerate(satellite_names):
            # nearest-epoch file that actually contains this satellite
            for k in np.argsort(np.abs(epochs - dt.timestamp())):
                satrec = fleets_by_epoch[k][1].get(name)
                if satrec is None:
                    continue
                age = abs(epochs[k] - dt.timestamp()) / 86400.0
                if age <= max_tle_age_days:
                    pos, _vel, err = propagate_eci_km(satrec, jd, fr)
                    if err == 0:
                        margin[i, j] = visibility_margin_deg(pos, target_dir)
                        tle_age[i, j] = age
                break

    schedule = ContactSchedule(
        satellite_names=satellite_names,
        candidate_times_days=np.asarray(candidate_times_days, dtype=float),
        visibility=margin >= 0.0,
        margin_deg=margin,
        target_dir_eci=target_dir,
    )
    return schedule, tle_age
