"""Copy freshly generated paper numbers/tables/figures into the JAA manuscript.

research/figures/paper_main.py and research/figures/phase4_numbers.py write to
research/papers/main/generated/. The JAA manuscript (research/papers/jaa/) keeps
its own generated/ folder, so after regenerating run:

    python research/papers/sync_generated.py

Only files the JAA paper already uses are copied; nothing is edited by hand.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "main" / "generated"
DST = HERE / "jaa" / "generated"


def main() -> None:
    copied = 0
    for dst in sorted(DST.rglob("*")):
        if not dst.is_file():
            continue
        src = SRC / dst.relative_to(DST)
        if src.exists() and src.read_bytes() != dst.read_bytes():
            shutil.copy2(src, dst)
            print(f"updated {dst.relative_to(HERE)}")
            copied += 1
    print(f"{copied} file(s) updated in {DST.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
