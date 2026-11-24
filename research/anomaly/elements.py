"""Orbital-element time series from GP/TLE history.

Mean elements only (SGP4 Brouwer mean motion), which is what TLE-based
anomaly work uses: absolute SMA is offset from osculating by up to a few km,
but steps and trends -- what the detectors look at -- are preserved.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MU_EARTH = 398600.4418  # km^3/s^2
R_EARTH = 6378.137  # km, WGS-84 equatorial
SIDEREAL_REV_PER_DAY = 1.00273790935  # Earth rotation rate, rev/day


def sma_km(mean_motion_rev_day: np.ndarray | float) -> np.ndarray:
    n = np.asarray(mean_motion_rev_day, dtype=float) * 2.0 * np.pi / 86400.0
    return np.cbrt(MU_EARTH / n ** 2)


def geo_drift_deg_day(mean_motion_rev_day: np.ndarray | float) -> np.ndarray:
    """Eastward-negative longitude drift for near-GEO objects: positive = drifting west."""
    return (np.asarray(mean_motion_rev_day, dtype=float) - SIDEREAL_REV_PER_DAY) * 360.0


def build_series(gp: pd.DataFrame) -> pd.DataFrame:
    """GP rows (NORAD_CAT_ID, EPOCH, MEAN_MOTION, ECCENTRICITY, INCLINATION,
    RA_OF_ASC_NODE, BSTAR) -> per-object, epoch-sorted series with derived
    columns. Duplicate epochs keep the last-issued element set; obviously
    corrupt sets (non-physical mean motion or eccentricity) are dropped and
    counted in df.attrs['dropped']."""
    df = gp.copy()
    df["EPOCH"] = pd.to_datetime(df["EPOCH"], utc=True)
    bad = (df.MEAN_MOTION <= 0.5) | (df.MEAN_MOTION > 17.5) | (df.ECCENTRICITY < 0) | (df.ECCENTRICITY >= 1)
    n_bad = int(bad.sum())
    df = df[~bad]
    sort_cols = ["NORAD_CAT_ID", "EPOCH"] + (["GP_ID"] if "GP_ID" in df else [])
    df = df.sort_values(sort_cols).drop_duplicates(["NORAD_CAT_ID", "EPOCH"], keep="last")
    df["SMA_KM"] = sma_km(df.MEAN_MOTION.to_numpy())
    df["ALT_KM"] = df.SMA_KM - R_EARTH
    df["PERIGEE_KM"] = df.SMA_KM * (1 - df.ECCENTRICITY) - R_EARTH
    df = df.reset_index(drop=True)
    df.attrs["dropped"] = n_bad
    return df
