"""Export atlas results for the static site page docs/atlas.html.

Reads research/results/atlas/**/atlas_summary.json ONLY and writes docs/atlas/results.js
(sets window.RESULTS_ATLAS) plus copies the generated figures into docs/atlas/. The page
fills every number from that object, so nothing is typed into the HTML by hand.

Run:  python -m research.atlas.export_site
Pure json/shutil; no live-stack imports.
"""

from __future__ import annotations

import json
import shutil

from research.atlas.common import RESULTS, WT_ROOT

OUT = WT_ROOT / "docs" / "atlas"
EVENTS = {"may2024": RESULTS, "oct2024": RESULTS / "oct2024"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = {}
    for name, d in EVENTS.items():
        f = d / "atlas_summary.json"
        data[name] = json.loads(f.read_text()) if f.exists() else None
        if f.exists():
            shutil.copyfile(d / "atlas_primary.png", OUT / f"{name}.png")
    (OUT / "results.js").write_text("window.RESULTS_ATLAS = " + json.dumps(data) + ";\n")
    print("wrote", OUT / "results.js", [k for k, v in data.items() if v])


if __name__ == "__main__":
    main()
