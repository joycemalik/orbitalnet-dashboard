"""GFZ Potsdam Kp (Kp_ap_Ap_SN_F107_since_1932.txt) -> daily max Kp, and storm
tagging of detections. Storm-time SMA lowerings are drag, not thrust; they
belong to the atlas track and are excluded from maneuver candidates here."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from research.anomaly.detectors import Event
from research.anomaly.fetch_reference import REF_DIR

KP_PATH = REF_DIR / "gfz_kp_ap_f107.txt"


def daily_max_kp(path=KP_PATH) -> pd.Series:
    """Index: UTC date (Timestamp, normalized). Missing values (-1) become NaN."""
    rows = [ln.split() for ln in path.read_text().splitlines() if ln and not ln.startswith("#")]
    df = pd.DataFrame(rows).iloc[:, :15]
    date = pd.to_datetime(df[0] + "-" + df[1] + "-" + df[2], utc=True)
    kp = df.iloc[:, 7:15].astype(float).replace(-1.0, np.nan)
    return pd.Series(kp.max(axis=1).to_numpy(), index=date, name="kp_max")


def storm_days(kp_max: pd.Series, kp_min: float = 6.0) -> set[pd.Timestamp]:
    return set(kp_max.index[kp_max >= kp_min])


def tag_storm(events: list[Event], storms: set[pd.Timestamp], pad_days: int = 1) -> list[Event]:
    """Mark events whose span [start - pad, end + pad] touches a storm day."""
    out = []
    for e in events:
        days = pd.date_range(e.epoch_start.normalize() - pd.Timedelta(days=pad_days),
                             e.epoch_end.normalize() + pd.Timedelta(days=pad_days), freq="D")
        out.append(dataclasses.replace(e, storm=any(d in storms for d in days)))
    return out
