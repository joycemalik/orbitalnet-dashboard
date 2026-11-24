"""Fragmentation candidates from the catalog itself: bursts of new DEB entries
tied to a launch long after that launch.

NORAD numbers are assigned in cataloging order, so the running maximum of
LAUNCH_DATE over NORAD number is a lower bound on when each number was
assigned ("catalog date"). A burst of DEB pieces from one launch designator,
cataloged more than --min-age-days after launch, marks a breakup, an
anomalous shedding event, or a batch re-cataloging of old pieces. Which of
these it is gets decided at vetting, not here.

The catalog date lags the physical breakup (pieces take weeks to months to be
cataloged), so it is an upper bound on breakup time; the element history of
the pieces (fetched separately) is what pins the epoch.

Run: python -m research.anomaly.fragmentation --start 2021-01-01 --end 2024-07-01
"""

from __future__ import annotations

import argparse
import hashlib

import pandas as pd

from research.anomaly.targets import RESULTS_DIR, SATCAT_PATH, load_satcat


def catalog_dates(satcat: pd.DataFrame) -> pd.DataFrame:
    s = satcat.assign(norad=satcat.NORAD_CAT_ID.astype(int),
                      launch=pd.to_datetime(satcat.LAUNCH_DATE, errors="coerce"))
    s = s[s.norad < 80000].sort_values("norad")  # 8xxxx = analyst/temporary numbers
    return s.assign(catdate=s.launch.cummax(), launch_id=s.OBJECT_ID.str[:8])


def bursts(cat: pd.DataFrame, start: str, end: str, *, min_age_days: int = 30,
           min_pieces: int = 5, burst_days: int = 60) -> pd.DataFrame:
    """One row per (launch, burst): DEB pieces of a launch cataloged within
    `burst_days` of each other, at least `min_age_days` after launch, with the
    first piece in [start, end)."""
    deb = cat[(cat.OBJECT_TYPE == "DEB") & ((cat.catdate - cat.launch).dt.days >= min_age_days)]
    rows = []
    for lid, g in deb.groupby("launch_id"):
        g = g.sort_values("catdate")
        burst_id = (g.catdate.diff().dt.days > burst_days).cumsum()
        for _, b in g.groupby(burst_id):
            if len(b) < min_pieces or not (pd.Timestamp(start) <= b.catdate.min() < pd.Timestamp(end)):
                continue
            parent = cat[(cat.launch_id == lid) & (cat.OBJECT_TYPE != "DEB")]
            rows.append({"launch_id": lid, "debris_name": b.OBJECT_NAME.iloc[0],
                         "parents": ";".join(parent.OBJECT_NAME.head(3)),
                         "launch": b.launch.min().date().isoformat(),
                         "first_cataloged": b.catdate.min().date().isoformat(),
                         "last_cataloged": b.catdate.max().date().isoformat(),
                         "pieces": len(b), "on_orbit": int(b.DECAY_DATE.isna().sum()),
                         "norad_min": int(b.norad.min()), "norad_max": int(b.norad.max())})
    return pd.DataFrame(rows).sort_values("first_cataloged").reset_index(drop=True) if rows else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--end", default="2024-07-01")
    ap.add_argument("--min-age-days", type=int, default=30)
    ap.add_argument("--min-pieces", type=int, default=5)
    args = ap.parse_args()
    out = bursts(catalog_dates(load_satcat()), args.start, args.end,
                 min_age_days=args.min_age_days, min_pieces=args.min_pieces)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"fragmentation_bursts_{args.start}_{args.end}.csv"
    out.to_csv(path, index=False)
    (path.with_suffix(".sha")).write_text(hashlib.sha256(SATCAT_PATH.read_bytes()).hexdigest() + "  celestrak_satcat.csv\n")
    print(out.to_string())


if __name__ == "__main__":
    main()
