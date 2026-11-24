"""Download GP (TLE) history from Space-Track for the target tiers.

Original source data: Space-Track.org `gp_history`, the 18th SDS public
catalog. Only the numeric fields the detectors need are requested
(predicates), as CSV, then stored as one parquet file per (tier, chunk,
year) under research/data/raw/anomaly/gp/. Existing files are skipped, so
the run is resumable and can be stopped at any time. Each file's URL and
sha256 go into the shared manifest.

Credentials: SPACETRACK_USER / SPACETRACK_PASS from the environment, or from
the gitignored repo .env (loaded with python-dotenv; never printed).
Rate limits (30/min, 300/hour) are respected with MIN_INTERVAL_S spacing.

Run:  python -m research.anomaly.fetch_history --tiers A_stations,B_geo_inspectors,D_derelicts,E_science
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd
from dotenv import load_dotenv

from research.anomaly.fetch_reference import ANOMALY_RAW, MANIFEST, SSL_CTX, record
from research.anomaly.targets import RESULTS_DIR
from research.data.fetch_tles import LOGIN_URL, MIN_INTERVAL_S, REPO_ROOT

FIELDS = ["NORAD_CAT_ID", "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION",
          "RA_OF_ASC_NODE", "ARG_OF_PERICENTER", "BSTAR", "MEAN_MOTION_DOT", "GP_ID"]
QUERY_URL = ("https://www.space-track.org/basicspacedata/query/class/gp_history/"
             "NORAD_CAT_ID/{ids}/EPOCH/{start}--{end}/orderby/EPOCH%20asc/"
             "predicates/" + ",".join(FIELDS) + "/format/csv")
GP_DIR = ANOMALY_RAW / "gp"
# Big constellations: fewer ids per query keeps each response well under Space-Track's size cap.
CHUNK = {"C_megaconstellations": 40}
DEFAULT_CHUNK = 150


class SpaceTrack:
    def __init__(self, user: str, password: str):
        self._auth = urllib.parse.urlencode({"identity": user, "password": password}).encode()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPSHandler(context=SSL_CTX))
        self._last = 0.0
        self.login()

    def login(self) -> None:
        for attempt in range(5):
            try:
                body = self._opener.open(LOGIN_URL, data=self._auth, timeout=60).read()
                if b"Failed" in body:
                    raise SystemExit("Space-Track rejected the credentials.")
                return
            except urllib.error.URLError as e:
                print(f"login failed ({attempt + 1}/5): {e}; retrying in 10s", flush=True)
                time.sleep(10)
        raise RuntimeError("could not log in to Space-Track")

    def get(self, url: str) -> bytes:
        for attempt in range(15):
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                data = self._opener.open(url, timeout=300).read()
                self._last = time.monotonic()
                return data
            except urllib.error.HTTPError as e:
                self._last = time.monotonic()
                cool = 120 + 30 * attempt if e.code == 429 else 25
                print(f"HTTP {e.code} ({attempt + 1}/15); waiting {cool}s", flush=True)
                time.sleep(cool)
                if e.code in (401, 429):
                    self.login()
            except Exception as e:  # network blips
                print(f"network error ({attempt + 1}/15): {e}; waiting 25s", flush=True)
                time.sleep(25)
        raise RuntimeError(f"giving up on {url}")


def chunks(ids: list[int], n: int) -> list[list[int]]:
    return [ids[i:i + n] for i in range(0, len(ids), n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", required=True, help="comma list of tier names from targets.json")
    ap.add_argument("--start-year", type=int, default=2021)
    ap.add_argument("--end-year", type=int, default=2026)
    args = ap.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    user, password = os.environ.get("SPACETRACK_USER"), os.environ.get("SPACETRACK_PASS")
    if not user or not password:
        raise SystemExit("Add SPACETRACK_USER and SPACETRACK_PASS to the repo .env first.")

    targets = json.loads((RESULTS_DIR / "targets.json").read_text())["tiers"]
    st = SpaceTrack(user, password)
    for tier in args.tiers.split(","):
        ids = sorted({i for group in targets[tier].values() for i in group})
        out_dir = GP_DIR / tier
        out_dir.mkdir(parents=True, exist_ok=True)
        jobs = [(k, c, y) for k, c in enumerate(chunks(ids, CHUNK.get(tier, DEFAULT_CHUNK)))
                for y in range(args.start_year, args.end_year + 1)]
        print(f"{tier}: {len(ids)} objects, {len(jobs)} queries", flush=True)
        for n, (k, chunk, year) in enumerate(jobs):
            path = out_dir / f"chunk{k:04d}_{year}.parquet"
            if path.exists():
                continue
            url = QUERY_URL.format(ids=",".join(map(str, chunk)), start=f"{year}-01-01", end=f"{year + 1}-01-01")
            data = st.get(url)
            df = pd.read_csv(io.BytesIO(data)) if data.strip() else pd.DataFrame(columns=FIELDS)
            df.to_parquet(path, index=False)
            record(MANIFEST, path.relative_to(ANOMALY_RAW).as_posix(), url, data)
            print(f"  [{n + 1}/{len(jobs)}] chunk {k} {year}: {len(df):,} sets", flush=True)


if __name__ == "__main__":
    main()
