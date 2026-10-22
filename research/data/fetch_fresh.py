"""Phase C: a FRESH, never-used set of real known-class transients.

The Phase 3 selection (research/data/raw/selection.json) took at most 300
post-2020 events per modeled class from the BTS catalog; the catalog holds
~8,600 post-2020 SNe of the modeled classes. Everything NOT in that
selection has never been loaded by any experiment on this branch, so it is
a genuinely sealed set. (All withheld-class events were already selected --
they are rare -- so this set contains modeled classes only. It tests the
claims about KNOWN classes: the false-"unknown" rate and accuracy cost.)

Selection is deterministic: unselected post-fleet events of each modeled
class, sorted by peak time, evenly spaced, capped per class. Each object is
assigned a role by sha256(oid): even -> "fresh_cal" (conformal calibration),
odd -> "fresh_test" (sealed until research/PREREGISTRATION_C.md exists).
A hash split makes the two halves exchangeable by construction.

Run once:  python -m research.data.fetch_fresh --per-class 700
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import io
import csv
import json
import time
from pathlib import Path

from research.data.fetch_bts import (ALERCE_LC_URL, CLASS_MAP, FLEET_COVERAGE_START_PEAKT, MODELED_CLASSES, RAW_DIR,
                                     _evenly_spaced, _get, _sha256)

DATA_DIR = Path(__file__).resolve().parent
FRESH_LC_DIR = RAW_DIR / "fresh_lightcurves"          # gitignored (raw/*)
FRESH_SELECTION = DATA_DIR / "fresh_selection.json"   # tracked
FRESH_MANIFEST = DATA_DIR / "fresh_manifest.json"     # tracked


def role_of(oid: str) -> str:
    return "fresh_cal" if int(hashlib.sha256(oid.encode()).hexdigest(), 16) % 2 == 0 else "fresh_test"


def select_fresh(catalog_csv: str, already: set[str], per_class: int) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(catalog_csv.lstrip())))
    by_class: dict[str, list[dict]] = {}
    for row in rows:
        cls = CLASS_MAP.get(row["type"].strip())
        if cls not in MODELED_CLASSES or row["ZTFID"] in already:
            continue
        try:
            peakt = float(row["peakt"])
        except ValueError:
            continue
        if peakt < FLEET_COVERAGE_START_PEAKT:
            continue
        by_class.setdefault(cls, []).append({"oid": row["ZTFID"], "iau": row["IAUID"], "bts_type": row["type"],
                                             "cls": cls, "ra": row["RA"], "dec": row["Dec"], "peakt": peakt,
                                             "redshift": row["redshift"], "role": role_of(row["ZTFID"])})
    out: list[dict] = []
    for cls, items in sorted(by_class.items()):
        items.sort(key=lambda r: (r["peakt"], r["oid"]))
        out.extend(_evenly_spaced(items, per_class))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--per-class", type=int, default=700)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    catalog = (RAW_DIR / "bts_catalog.csv").read_text(encoding="utf-8")
    already = {o["oid"] for o in json.loads((RAW_DIR / "selection.json").read_text())["objects"]}
    selected = select_fresh(catalog, already, args.per_class)
    assert not ({o["oid"] for o in selected} & already)
    FRESH_SELECTION.write_text(json.dumps({"per_class": args.per_class, "excluded_phase3_selection": len(already),
                                           "objects": selected}, indent=1))
    FRESH_LC_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(FRESH_MANIFEST.read_text()) if FRESH_MANIFEST.exists() else {"files": {}}

    def fetch(obj: dict):
        path = FRESH_LC_DIR / f"{obj['oid']}.json"
        if path.exists():
            return obj["oid"], None, None
        url = ALERCE_LC_URL.format(oid=obj["oid"])
        try:
            data = _get(url)
            json.loads(data)
        except Exception as exc:  # noqa: BLE001 -- recorded, never silent
            return obj["oid"], None, str(exc)
        path.write_bytes(data)
        time.sleep(0.1)
        return obj["oid"], {"url": url, "sha256": _sha256(data),
                            "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}, None

    failed = []
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        for k, (oid, rec, err) in enumerate(pool.map(fetch, selected)):
            if rec:
                manifest["files"][f"fresh_lightcurves/{oid}.json"] = rec
            if err:
                failed.append(f"{oid}: {err}")
            if k % 100 == 0:
                print(f"[{k + 1}/{len(selected)}]", flush=True)
                FRESH_MANIFEST.write_text(json.dumps(manifest, indent=1))
    manifest["failed"] = failed
    FRESH_MANIFEST.write_text(json.dumps(manifest, indent=1))
    counts: dict[str, int] = {}
    for o in selected:
        counts[f"{o['cls']}/{o['role']}"] = counts.get(f"{o['cls']}/{o['role']}", 0) + 1
    print(f"selected: {counts}; failed: {len(failed)}")


if __name__ == "__main__":
    main()
