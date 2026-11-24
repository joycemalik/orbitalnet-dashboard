"""Flat submission package for Astronomy and Computing (Elsevier Editorial Manager).

Inlines every \\input (generated numbers, result sections, tables) into one main.tex, moves figures
to the top level, and copies the bibliography, compiled PDF, highlights and cover letter.
Run after build.sh:  python research/papers/aandc/make_submission.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "submission"
INPUT = re.compile(r"\\input\{([^}]+)\}")


def inline(path: Path) -> str:
    text = path.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        name = m.group(1)
        sub = HERE / (name if name.endswith(".tex") else name + ".tex")
        return inline(sub).rstrip("\n")

    return INPUT.sub(repl, text)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    tex = inline(HERE / "main.tex").replace("generated/figures/", "")
    (OUT / "main.tex").write_text(tex, encoding="utf-8")
    for fig in sorted(set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex))):
        shutil.copy2(HERE / "generated" / "figures" / fig, OUT / fig)
    for name in ["refs.bib", "main.bbl", "main.pdf", "highlights.txt", "cover_letter.pdf"]:
        shutil.copy2(HERE / name, OUT / name)
    print("\n".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
