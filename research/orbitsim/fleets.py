"""Phase 4b fleet selection rules (fixed before any Phase 4b outcome was seen).

sparse: the first 8 satellites of satellites.txt (Phase 2 / Phase 4 fleet).
dense:  8 satellites from ONE orbital plane. Operational shell = inclination
        within 0.2 deg of 53.05 and mean motion 15.0-15.1 rev/day. Plane = the
        5-degree RAAN bin with the most such satellites; inside it, the 8
        satellites whose RAAN is closest to the bin's median RAAN (ties by name).
"""

from __future__ import annotations

import collections

import numpy as np
from sgp4.api import Satrec

from research.orbitsim.tle import load_tle_subset

DEG = 180.0 / np.pi


def operational(sat: Satrec) -> bool:
    return abs(sat.inclo * DEG - 53.05) < 0.2 and 15.0 < sat.no_kozai * 1440 / (2 * np.pi) < 15.1


def dense_fleet(tle_path: str, n: int = 8) -> dict[str, Satrec]:
    allsats = load_tle_subset(tle_path)
    ops = {k: s for k, s in allsats.items() if operational(s)}
    bins = collections.Counter(int((s.nodeo * DEG) // 5) for s in ops.values())
    top_bin = sorted(bins.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    members = {k: s for k, s in ops.items() if int((s.nodeo * DEG) // 5) == top_bin}
    med = float(np.median([s.nodeo * DEG for s in members.values()]))
    chosen = sorted(members, key=lambda k: (abs(members[k].nodeo * DEG - med), k))[:n]
    return {k: members[k] for k in sorted(chosen)}
