"""Download one day of near-circular LEO GP history per query from Space-Track.

Resumable (existing day files are skipped). Reuses the rate-limited client from the
anomaly track; spacing is MIN_INTERVAL_S (15 s). The Space-Track limit is per account,
so do not run this while another fetcher is active.

Run:  python -m research.atlas.fetch_leo_days --start 2024-04-20 --end 2024-06-10
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import os

import pandas as pd
from dotenv import load_dotenv

from research.anomaly.fetch_history import FIELDS, SpaceTrack
from research.atlas.common import ATLAS_RAW, DAYS_DIR, MAIN

URL = ("https://www.space-track.org/basicspacedata/query/class/gp_history/"
       "EPOCH/{a}--{b}/MEAN_MOTION/%3E11.25/ECCENTRICITY/%3C0.02/"
       "orderby/NORAD_CAT_ID%20asc,EPOCH%20asc/predicates/" + ",".join(FIELDS) + "/format/csv")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True, help="inclusive last day")
    args = ap.parse_args()

    load_dotenv(MAIN / ".env")
    user, password = os.environ.get("SPACETRACK_USER"), os.environ.get("SPACETRACK_PASS")
    if not user or not password:
        raise SystemExit("SPACETRACK_USER / SPACETRACK_PASS missing from the repo .env")

    DAYS_DIR.mkdir(parents=True, exist_ok=True)
    day, last = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    todo = []
    while day <= last:
        if not (DAYS_DIR / f"{day}.parquet").exists():
            todo.append(day)
        day += dt.timedelta(days=1)
    print(f"{len(todo)} days to fetch", flush=True)
    if not todo:
        return
    st = SpaceTrack(user, password)
    for n, day in enumerate(todo):
        url = URL.format(a=day, b=day + dt.timedelta(days=1))
        data = st.get(url)
        df = pd.read_csv(io.BytesIO(data)) if data.strip() else pd.DataFrame(columns=FIELDS)
        df.to_parquet(DAYS_DIR / f"{day}.parquet", index=False)
        print(f"[{n + 1}/{len(todo)}] {day}: {len(df):,} sets, {df.NORAD_CAT_ID.nunique():,} objects", flush=True)


if __name__ == "__main__":
    main()
