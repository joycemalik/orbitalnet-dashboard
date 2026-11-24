"""Copy freshly generated paper numbers/tables/figures into the journal manuscripts.

research/figures/paper_main.py and research/figures/phase4_numbers.py write to
research/papers/main/generated/. The JAA manuscript (research/papers/jaa/) and the
Astronomy and Computing manuscript (research/papers/aandc/) keep their own generated/
folders, so after regenerating run:

    python research/papers/sync_generated.py

Only files each paper already uses are copied; nothing is edited by hand.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "main" / "generated"
DSTS = [HERE / "jaa" / "generated", HERE / "aandc" / "generated"]


def main() -> None:
    for dst_root in DSTS:
        copied = 0
        for dst in sorted(dst_root.rglob("*")):
            if not dst.is_file():
                continue
            src = SRC / dst.relative_to(dst_root)
            if src.exists() and src.read_bytes() != dst.read_bytes():
                shutil.copy2(src, dst)
                print(f"updated {dst.relative_to(HERE)}")
                copied += 1
        print(f"{copied} file(s) updated in {dst_root.relative_to(HERE.parent.parent)}")

if __name__ == "__main__":
    main()
