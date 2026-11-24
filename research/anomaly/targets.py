"""Target tiers for the anomaly hunt, resolved against the real CelesTrak SATCAT.

Each tier is a set of OBJECT_NAME regexes. Every pattern was checked against the
downloaded catalog (fetch_reference.py) before being committed. The resolved
NORAD id lists are written to research/results/anomaly/targets.json with the
SATCAT sha256 they came from, so a later catalog refresh is visible.

Run:  python -m research.anomaly.targets
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from research.anomaly.fetch_reference import REF_DIR

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results" / "anomaly"
SATCAT_PATH = REF_DIR / "celestrak_satcat.csv"

# (?:...) groups only; capture groups make pandas warn.
TIERS: dict[str, dict[str, str]] = {
    "A_stations": {
        "stations": r"^(?:ISS \(ZARYA\)|CSS \(TIANHE\))$",
        "visiting": r"^(?:PROGRESS-MS|SOYUZ-MS|TIANZHOU|SHENZHOU|CREW DRAGON|DRAGON|CYGNUS|STARLINER)",
    },
    "B_geo_inspectors": {
        "luch_olymp": r"^(?:LUCH|OLYMP)",
        "cosmos_recent": r"^COSMOS 25(?:[5-9]\d)$",
        "shijian": r"^SHIJIAN-(?:17|21|23|25)|^SJ-(?:21|23) AKM",
        "tjs": r"^TJS-",
        "gssap": r"^USA (?:253|254|270|271|324|325)$",
    },
    "C_megaconstellations": {
        "starlink": r"^STARLINK",
        "oneweb": r"^ONEWEB",
        "qianfan": r"^QIANFAN",
        "guowang": r"^HULIANWANG DIGUI",
        "kuiper": r"^KUIPER",
    },
    "D_derelicts": {
        "envisat": r"^ENVISAT$",
        "big_rocket_bodies": r"^(?:CZ-5B|SL-16|ZENIT)",
    },
    "E_science": {
        "flagships": r"^(?:HST|SWIFT|FGRST \(GLAST\)|NUSTAR|TESS)$",
    },
}


def resolve(satcat: pd.DataFrame, since: str) -> dict[str, dict[str, list[int]]]:
    """Tier -> group -> sorted NORAD ids, keeping objects on orbit at any time >= `since`."""
    alive = satcat.DECAY_DATE.isna() | (satcat.DECAY_DATE >= since)
    out: dict[str, dict[str, list[int]]] = {}
    for tier, groups in TIERS.items():
        out[tier] = {}
        for group, pattern in groups.items():
            hit = satcat[alive & satcat.OBJECT_NAME.str.contains(pattern, regex=True, na=False)]
            out[tier][group] = sorted(int(n) for n in hit.NORAD_CAT_ID)
    return out


def load_satcat(path: Path = SATCAT_PATH) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2021-01-01", help="drop objects decayed before this date")
    args = ap.parse_args()
    resolved = resolve(load_satcat(), args.since)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"since": args.since,
               "satcat_sha256": hashlib.sha256(SATCAT_PATH.read_bytes()).hexdigest(),
               "patterns": TIERS, "tiers": resolved}
    (RESULTS_DIR / "targets.json").write_text(json.dumps(payload, indent=1))
    for tier, groups in resolved.items():
        print(tier, {g: len(ids) for g, ids in groups.items()})


if __name__ == "__main__":
    main()
