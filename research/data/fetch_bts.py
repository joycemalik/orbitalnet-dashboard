"""One-time download of real transients for the Phase 3 real-data replay.

Sources (both public, no credentials):
  - ZTF Bright Transient Survey catalog (spectroscopic classifications = ground truth)
    https://sites.astro.caltech.edu/ztf/bts/explorer.php
  - ALeRCE public API, per-object ZTF detections (the real light curves)
    https://api.alerce.online/ztf/v1/objects/<oid>/lightcurve

Everything is written to research/data/raw/ together with a manifest.json that
records the download time, source URL and sha256 of every file, so experiments
can run offline afterwards and prove which bytes they used. Re-running skips
files that already exist (use --refresh to re-download).

Run once:  python -m research.data.fetch_bts --per-class 300
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import time
import urllib.request
from pathlib import Path

BTS_URL = "https://sites.astro.caltech.edu/ztf/bts/explorer.php?f=s&format=csv"
ALERCE_LC_URL = "https://api.alerce.online/ztf/v1/objects/{oid}/lightcurve"

RAW_DIR = Path(__file__).resolve().parent / "raw"

# BTS "type" string -> replay class. Modeled = the planner's hypothesis set;
# withheld = real physics the planner has no model for (the real h0).
# Everything not listed (CVs, AGN, novae, unclassified "-", rare SN subtypes)
# is dropped rather than force-fitted into a class.
CLASS_MAP = {
    "SN Ia": "sn_ia", "SN Ia-91T": "sn_ia", "SN Ia-91bg": "sn_ia",
    "SN II": "sn_ii", "SN IIP": "sn_ii", "SN IIb": "sn_ii",
    "SN Ib": "sn_ibc", "SN Ic": "sn_ibc", "SN Ib/c": "sn_ibc", "SN Ic-BL": "sn_ibc",
    "TDE": "tde", "SLSN-I": "slsn", "SLSN-II": "slsn", "SN Ibn": "fast_interacting",
}
MODELED_CLASSES = ("sn_ia", "sn_ii", "sn_ibc")
WITHHELD_CLASSES = ("tde", "slsn", "fast_interacting")


def _get(url: str, retries: int = 3, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "orbitalnet-research/phase3"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("unreachable")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# The fleet (first Starlink v1.0 batch) launched 2019-11-11. Events peaking
# before this date can only build class templates (no orbit needed); events
# after it are the scored validation/test pool.
FLEET_COVERAGE_START_MJD = 58849.0  # 2020-01-01T00:00 UTC
FLEET_COVERAGE_START_PEAKT = FLEET_COVERAGE_START_MJD + 2400000.5 - 2458000.0  # BTS peakt = JD - 2458000


def _evenly_spaced(items: list[dict], k: int) -> list[dict]:
    """Deterministic, time-uniform subsample (items sorted by peak time)."""
    if len(items) <= k:
        return items
    idx = sorted({int(round(x)) for x in [i * (len(items) - 1) / (k - 1) for i in range(k)]})
    return [items[i] for i in idx]


def select_objects(catalog_csv: str, per_class: int) -> list[dict]:
    """Deterministic selection: map classes; for each MODELED class keep up to
    `per_class` events before fleet coverage (template pool) AND up to
    `per_class` after it (scored pool), each evenly spaced in time. Keep ALL
    withheld-class events (they are rare)."""
    # The BTS endpoint prefixes the CSV with a blank line; skip it.
    rows = list(csv.DictReader(io.StringIO(catalog_csv.lstrip())))
    by_class: dict[str, list[dict]] = {}
    for row in rows:
        cls = CLASS_MAP.get(row["type"].strip())
        if cls is None:
            continue
        try:
            peakt = float(row["peakt"])
        except ValueError:
            continue
        by_class.setdefault(cls, []).append({"oid": row["ZTFID"], "iau": row["IAUID"],
                                             "bts_type": row["type"], "cls": cls,
                                             "ra": row["RA"], "dec": row["Dec"],
                                             "peakt": peakt, "redshift": row["redshift"]})
    selected: list[dict] = []
    for cls, items in sorted(by_class.items()):
        items.sort(key=lambda r: (r["peakt"], r["oid"]))
        if cls in WITHHELD_CLASSES:
            selected.extend(items)
            continue
        pre = [r for r in items if r["peakt"] < FLEET_COVERAGE_START_PEAKT]
        post = [r for r in items if r["peakt"] >= FLEET_COVERAGE_START_PEAKT]
        selected.extend(_evenly_spaced(pre, per_class) + _evenly_spaced(post, per_class))
    return selected


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--per-class", type=int, default=300, help="cap per modeled class")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.2, help="politeness delay between API calls (s)")
    args = ap.parse_args()

    lc_dir = RAW_DIR / "lightcurves"
    lc_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = RAW_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}

    def record(path: Path, url: str, data: bytes) -> None:
        manifest["files"][path.relative_to(RAW_DIR).as_posix()] = {
            "url": url, "sha256": _sha256(data),
            "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}

    catalog_path = RAW_DIR / "bts_catalog.csv"
    if args.refresh or not catalog_path.exists():
        data = _get(BTS_URL)
        catalog_path.write_bytes(data)
        record(catalog_path, BTS_URL, data)
    selected = select_objects(catalog_path.read_text(encoding="utf-8"), args.per_class)
    (RAW_DIR / "selection.json").write_text(json.dumps(
        {"per_class": args.per_class, "class_map": CLASS_MAP,
         "modeled": MODELED_CLASSES, "withheld": WITHHELD_CLASSES, "objects": selected}, indent=1))

    failed: list[str] = []
    for i, obj in enumerate(selected):
        path = lc_dir / f"{obj['oid']}.json"
        if path.exists() and not args.refresh:
            continue
        url = ALERCE_LC_URL.format(oid=obj["oid"])
        try:
            data = _get(url)
            json.loads(data)  # refuse to cache non-JSON error pages
        except Exception as exc:
            failed.append(f"{obj['oid']}: {exc}")
            continue
        path.write_bytes(data)
        record(path, url, data)
        if i % 50 == 0:
            print(f"[{i + 1}/{len(selected)}] {obj['oid']} ({obj['cls']})", flush=True)
            manifest_path.write_text(json.dumps(manifest, indent=1))
        time.sleep(args.sleep)

    manifest["failed"] = failed
    manifest_path.write_text(json.dumps(manifest, indent=1))
    counts: dict[str, int] = {}
    for obj in selected:
        counts[obj["cls"]] = counts.get(obj["cls"], 0) + 1
    print(f"selected per class: {counts}; failed downloads: {len(failed)}")


if __name__ == "__main__":
    main()
