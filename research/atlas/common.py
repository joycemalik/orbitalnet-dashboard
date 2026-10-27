"""Paths shared by the atlas scripts.

Raw data and the .env live in the main checkout (gitignored), not in this worktree.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

WT_ROOT = Path(__file__).resolve().parents[2]


def main_root() -> Path:
    if os.environ.get("ATLAS_MAIN_ROOT"):
        return Path(os.environ["ATLAS_MAIN_ROOT"])
    common = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=WT_ROOT, text=True).strip()
    return Path(common).parent


MAIN = main_root()
REF_DIR = MAIN / "research" / "data" / "raw" / "anomaly" / "reference"
ATLAS_RAW = MAIN / "research" / "data" / "raw" / "atlas"
DAYS_DIR = ATLAS_RAW / "leo_days"
RESULTS = WT_ROOT / "research" / "results" / "atlas"
