"""Small shared helpers: git commit hash, config hashing, atomic JSON writes.
Used by every experiment script so every result file can show provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


def git_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def config_hash(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def seed_for(seed: int, *parts) -> int:
    """Deterministic (platform-independent) integer seed derived from a base
    seed plus arbitrary string/int parts, for per-event/per-strategy substreams."""
    blob = f"{seed}:" + ":".join(str(p) for p in parts)
    digest = hashlib.sha256(blob.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def atomic_write_json(path: str, obj) -> None:
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)
