"""One-time download of HISTORICAL TLEs from Space-Track.org for the Phase 3 replay.

The fleet is the same FLEET_POOL_SIZE satellites the earlier phases use (the
first entries of satellites.txt), identified by NORAD catalog number, so every
phase talks about the same physical spacecraft. For each ISO week that contains
a selected event we fetch the TLEs those satellites had in a 1-day window at the
start of that week; the replay then propagates from the nearest-epoch TLE
(at most a few days, well within SGP4's useful range for LEO).

Events dated before the fleet was in orbit simply get no TLEs and are excluded
by the replay loader; that exclusion is recorded, not hidden.

Credentials come from the environment, never from files in the repo:
    SPACETRACK_USER, SPACETRACK_PASS
Space-Track's limits are 30 requests/min and 300/hour; we stay under both.

Run once (after fetch_bts):  python -m research.data.fetch_tles
"""

from __future__ import annotations

import datetime
import hashlib
import http.cookiejar
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from research.data.fetch_bts import RAW_DIR

LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
QUERY_URL = ("https://www.space-track.org/basicspacedata/query/class/gp_history/"
             "NORAD_CAT_ID/{ids}/EPOCH/{start}--{end}/orderby/EPOCH%20asc/format/3le")
REPO_ROOT = Path(__file__).resolve().parents[2]
TLE_PATH = REPO_ROOT / "satellites.txt"
FLEET_POOL_SIZE = 20  # same value as experiments/phase2_single_planner.py
MIN_INTERVAL_S = 15.0  # safe margin under Space-Track's 300 requests/hour and 30/min limit


def fleet_norad_ids(path: Path = TLE_PATH, n: int = FLEET_POOL_SIZE) -> dict[str, str]:
    """name -> 5-digit NORAD id, taken from line 1 columns 3-7 of each TLE."""
    lines = path.read_text(encoding="utf-8").splitlines()
    out: dict[str, str] = {}
    for i in range(0, len(lines) - 2, 3):
        out[lines[i].strip()] = lines[i + 1][2:7].strip()
        if len(out) >= n:
            break
    return out


def mjd_to_datetime(mjd: float) -> datetime.datetime:
    return datetime.datetime(1858, 11, 17, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=mjd)


def week_starts(peak_jds: list[float]) -> list[datetime.date]:
    """BTS `peakt` is JD - 2458000. Return the Monday of each distinct event week."""
    weeks = set()
    for pt in peak_jds:
        d = mjd_to_datetime(pt + 2458000.0 - 2400000.5).date()
        weeks.add(d - datetime.timedelta(days=d.weekday()))
    return sorted(weeks)


def main() -> None:
    user, password = os.environ.get("SPACETRACK_USER"), os.environ.get("SPACETRACK_PASS")
    if not user or not password:
        raise SystemExit("Set SPACETRACK_USER and SPACETRACK_PASS in the environment first.")

    selection = json.loads((RAW_DIR / "selection.json").read_text())
    weeks = week_starts([o["peakt"] for o in selection["objects"]])
    fleet = fleet_norad_ids()
    ids = ",".join(sorted(fleet.values()))
    out_dir = RAW_DIR / "tles"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fleet.json").write_text(json.dumps(fleet, indent=1))

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    logged_in = False
    for attempt in range(5):
        try:
            opener.open(LOGIN_URL, data=urllib.parse.urlencode({"identity": user, "password": password}).encode(),
                        timeout=60).read()
            logged_in = True
            break
        except Exception as e:
            print(f"Login failed (attempt {attempt + 1}/5): {e}. Retrying in 10s...", flush=True)
            time.sleep(10)
    if not logged_in:
        raise RuntimeError("Failed to login to Space-Track after 5 attempts.")

    manifest_path = RAW_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}
    last = 0.0
    for n, week in enumerate(weeks):
        path = out_dir / f"{week.isoformat()}.tle"
        if path.exists():
            continue
        wait = MIN_INTERVAL_S - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        url = QUERY_URL.format(ids=ids, start=week.isoformat(), end=(week + datetime.timedelta(days=1)).isoformat())
        data = None
        for attempt in range(15):
            try:
                data = opener.open(url, timeout=120).read()
                last = time.monotonic()
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_s = 120 + attempt * 30
                    print(f"Rate limited (429) on {week} (attempt {attempt + 1}/15). Cooling down for {wait_s}s and renewing session...", flush=True)
                    time.sleep(wait_s)
                    try:
                        opener.open(LOGIN_URL, data=urllib.parse.urlencode({"identity": user, "password": password}).encode(), timeout=60).read()
                    except Exception as login_err:
                        print(f"Re-login error: {login_err}", flush=True)
                else:
                    print(f"HTTP error {e.code} on {week} (attempt {attempt + 1}/15): {e}. Retrying in 25s...", flush=True)
                    time.sleep(25)
            except Exception as e:
                print(f"Network error on {week} (attempt {attempt + 1}/15): {e}. Retrying in 25s...", flush=True)
                time.sleep(25)
        if data is None:
            raise RuntimeError(f"Failed to fetch TLEs for {week} after 15 attempts.")

        path.write_bytes(data)  # may be empty for weeks before launch; that is informative
        manifest["files"][path.relative_to(RAW_DIR).as_posix()] = {
            "url": url, "sha256": hashlib.sha256(data).hexdigest(),
            "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        if n % 10 == 0:
            n_tles = data.count(b"\n") // 3
            print(f"[{n + 1}/{len(weeks)}] {week} ({n_tles} TLEs)", flush=True)
            manifest_path.write_text(json.dumps(manifest, indent=1))
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"done: {len(weeks)} weeks")


if __name__ == "__main__":
    main()
