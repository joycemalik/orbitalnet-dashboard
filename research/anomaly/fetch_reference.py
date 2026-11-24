"""Download the public, no-login reference files the anomaly track depends on.

- CelesTrak SATCAT (CSV): names, owners, object types, launch/decay dates. Used
  to build the target tiers (targets.py) from the real catalog, not memory.
- GCAT satcat (TSV, J. McDowell, planet4589.org): independent catalog with
  status codes; one of the "already known" sources for novelty vetting.
- GFZ Potsdam Kp/ap/F10.7 since 1932: space-weather drivers for drag analysis.

Every file is written with its URL, sha256 and fetch time to manifest.json so
results can be traced back to the exact bytes used.

Run:  python -m research.anomaly.fetch_reference
"""

from __future__ import annotations

import datetime
import hashlib
import json
import ssl
import urllib.request
from pathlib import Path

import certifi

from research.data.fetch_bts import RAW_DIR

ANOMALY_RAW = RAW_DIR / "anomaly"
REF_DIR = ANOMALY_RAW / "reference"
MANIFEST = ANOMALY_RAW / "manifest.json"

SOURCES = {
    "celestrak_satcat.csv": "https://celestrak.org/pub/satcat.csv",
    "gcat_satcat.tsv": "https://planet4589.org/space/gcat/tsv/cat/satcat.tsv",
    "gfz_kp_ap_f107.txt": "https://kp.gfz-potsdam.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt",
}


def record(manifest_path: Path, rel: str, url: str, data: bytes) -> None:
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}
    manifest["files"][rel] = {
        "url": url, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
        "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    manifest_path.write_text(json.dumps(manifest, indent=1))


# certifi's bundle: the Windows Python store lacks the issuer GFZ's cert chains to.
SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def main() -> None:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        if (REF_DIR / name).exists():
            continue
        req = urllib.request.Request(url, headers={"User-Agent": "research-anomaly/0.1"})
        data = urllib.request.urlopen(req, timeout=300, context=SSL_CTX).read()
        (REF_DIR / name).write_bytes(data)
        record(MANIFEST, f"reference/{name}", url, data)
        print(f"{name}: {len(data):,} bytes")


if __name__ == "__main__":
    main()
