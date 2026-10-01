"""Real visibility geometry, replacing the live stack's flat-Earth haversine
gatekeeper (see research/PLAN.md section 2 for why that one doesn't carry
over). The transient is modeled as a fixed direction on the sky (effectively
at infinite distance, as real astronomical transients are) rather than a
ground point, which is the right model for a constellation of space-based
telescopes: visibility is governed by Earth occultation of that direction,
not by ground-track distance.

Sun-exclusion-angle constraints (a real space telescope cannot point too
close to the Sun) are NOT modeled here — documented simplification, see
research/LOG.md Phase 2 entry.
"""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0
GMST_DEG_AT_J2000 = 280.46061837
GMST_DEG_PER_DAY = 360.98564736629


def gmst_deg(jd_plus_fr: float) -> float:
    t = jd_plus_fr - 2451545.0
    return (GMST_DEG_AT_J2000 + GMST_DEG_PER_DAY * t) % 360.0


def eci_to_ecef(pos_eci_km: np.ndarray, jd_plus_fr: float) -> np.ndarray:
    theta = np.radians(gmst_deg(jd_plus_fr))
    x, y, z = pos_eci_km
    x_ecef = x * np.cos(theta) + y * np.sin(theta)
    y_ecef = -x * np.sin(theta) + y * np.cos(theta)
    return np.array([x_ecef, y_ecef, z])


def random_sky_direction(rng: np.random.Generator) -> np.ndarray:
    """A uniformly-random unit vector, used as a fixed (non-rotating, ECI
    frame) direction to an astronomically distant transient."""
    v = rng.normal(size=3)
    return v / np.linalg.norm(v)


def earth_angular_radius_deg(distance_from_earth_center_km: float) -> float:
    ratio = min(1.0, EARTH_RADIUS_KM / distance_from_earth_center_km)
    return np.degrees(np.arcsin(ratio))


def visibility_margin_deg(sat_pos_eci_km: np.ndarray, target_dir_eci: np.ndarray) -> float:
    """How far the target direction is from Earth's occulting disk, in
    degrees: >= 0 means visible (the CNP-style continuous "proximity" score
    for Phase 2's B1 reimplementation), < 0 means occluded."""
    r_norm = np.linalg.norm(sat_pos_eci_km)
    to_earth_center = -sat_pos_eci_km / r_norm
    cos_angle = np.clip(np.dot(target_dir_eci, to_earth_center), -1.0, 1.0)
    angle_to_earth_center_deg = np.degrees(np.arccos(cos_angle))
    return float(angle_to_earth_center_deg - earth_angular_radius_deg(r_norm))


def is_target_visible(sat_pos_eci_km: np.ndarray, target_dir_eci: np.ndarray) -> bool:
    """True iff Earth does not occult the fixed sky direction `target_dir_eci`
    as seen from the satellite at `sat_pos_eci_km`."""
    return visibility_margin_deg(sat_pos_eci_km, target_dir_eci) >= 0.0
