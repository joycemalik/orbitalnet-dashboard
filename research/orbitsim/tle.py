"""Headless TLE loading + SGP4 propagation. Same approach as
physics_engine.load_satellites()/sat.sgp4(jd, fr) in the live stack, but as
plain functions over explicit arguments/returns (no Redis, no infinite loop)
so it is reproducible and testable. See research/PLAN.md section 2.
"""

from __future__ import annotations

import datetime

import numpy as np
from sgp4.api import Satrec, jday


def load_tle_subset(filepath: str, max_satellites: int | None = None) -> dict[str, Satrec]:
    satellites: dict[str, Satrec] = {}
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i in range(0, len(lines), 3):
        if i + 2 >= len(lines):
            break
        name = lines[i].strip()
        line1, line2 = lines[i + 1].strip(), lines[i + 2].strip()
        try:
            satellites[name] = Satrec.twoline2rv(line1, line2)
        except Exception:
            continue
        if max_satellites is not None and len(satellites) >= max_satellites:
            break
    return satellites


def datetime_to_jd_fr(dt: datetime.datetime) -> tuple[float, float]:
    return jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


def propagate_eci_km(satrec: Satrec, jd: float, fr: float) -> tuple[np.ndarray, np.ndarray, int]:
    """Returns (position_km, velocity_km_s, sgp4_error_code). error_code == 0 means OK."""
    e, position, velocity = satrec.sgp4(jd, fr)
    return np.array(position), np.array(velocity), e
