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
    OUT.mkdir(exist_ok=True)
    for old in OUT.iterdir():  # clear contents (the folder itself may be open in Explorer)
        shutil.rmtree(old) if old.is_dir() else old.unlink()
    tex = inline(HERE / "main.tex")
    # Elsevier asks for one file per figure, named Figure_1, Figure_2, ... in order of appearance.
    figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)
    for n, path in enumerate(figs, start=1):
        new = f"Figure_{n}{Path(path).suffix}"
        tex = tex.replace("{" + path + "}", "{" + new + "}", 1)
        shutil.copy2(HERE / path, OUT / new)
    (OUT / "main.tex").write_text(tex, encoding="utf-8")
    for name in ["refs.bib", "main.bbl", "main.pdf", "highlights.txt", "cover_letter.pdf"]:
        shutil.copy2(HERE / name, OUT / name)
    print("\n".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
