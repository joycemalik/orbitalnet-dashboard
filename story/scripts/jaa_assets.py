"""Build the JAA assets the website shows, straight from the repository.

  public/jaa/numbers.json     every macro in research/papers/jaa/generated/numbers*.tex
  public/jaa/fig*.png         the paper's figures, rendered from generated/figures/*.pdf
  public/jaa/jaa-manuscript.pdf
  public/code/index.html      the Colab notebook, rendered to static HTML

Nothing here is typed by hand. Run from anywhere: python story/scripts/jaa_assets.py
The outputs are committed, so a build machine without Python still serves them.
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
JAA = REPO / "research" / "papers" / "jaa"
OUT = HERE.parent / "public" / "jaa"
NOTEBOOK = REPO / "research" / "notebooks" / "jaa_walkthrough.ipynb"

SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def clean(v: str) -> str:
    v = re.sub(r"\\textbf\{([^}]*)\}", r"\1", v)
    v = re.sub(r"10\^\{([^}]*)\}", lambda m: "10" + m.group(1).translate(SUP), v)
    v = v.replace("$", "").replace("\\%", "%").replace("\\,", "\u2009").replace("~", " ")
    v = v.replace("--", "–")
    return v.strip()


def numbers() -> dict:
    out = {}
    for f in sorted((JAA / "generated").glob("numbers*.tex")):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", line)
            if m:
                out[m.group(1)] = clean(m.group(2))
    return out


def figures() -> list:
    import pymupdf
    names = []
    for pdf in sorted((JAA / "generated" / "figures").glob("*.pdf")):
        doc = pymupdf.open(pdf)
        doc[0].get_pixmap(dpi=200).save(OUT / (pdf.stem + ".png"))
        names.append(pdf.stem)
    return names


def roc_sim() -> None:
    """Simulation ROC curves (S1 nominal test run), thinned for the interactive chart."""
    a = json.loads((REPO / "research/results/phase2/analysis_test.json").read_text(encoding="utf-8"))
    s1 = {r["scenario"]: r for r in a["runs"]}["S1_nominal"]
    out = {}
    for k in ("P_p_h0", "B3_entropy", "B2_entropy"):
        fpr, tpr = s1["H3"]["roc"][k]["fpr"], s1["H3"]["roc"][k]["tpr"]
        pts, last = [], None
        for x, y in zip(fpr, tpr):
            p = (round(x, 4), round(y, 4))
            if p != last:
                pts.append(p)
                last = p
        out[k] = pts
    (OUT / "roc_sim.json").write_text(json.dumps(out), encoding="utf-8")


def notebook() -> None:
    if not NOTEBOOK.exists():
        return
    import nbformat
    from nbconvert import HTMLExporter
    nb = nbformat.read(NOTEBOOK, as_version=4)
    html, _ = HTMLExporter(template_name="lab", theme="dark").from_notebook_node(nb)
    bar = ('<a href="/" style="position:fixed;left:12px;bottom:12px;z-index:9999;font:500 11px/1 monospace;'
           'letter-spacing:.14em;text-transform:uppercase;color:#05060a;background:#7ff3ff;padding:9px 12px;'
           'border-radius:3px;text-decoration:none">← OrbitalNet</a>')
    html = re.sub(r"<body([^>]*)>", lambda m: m.group(0) + bar, html, count=1)
    code = HERE.parent / "public" / "code"
    code.mkdir(parents=True, exist_ok=True)
    (code / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    nums = numbers()
    (OUT / "numbers.json").write_text(json.dumps(nums, indent=1, ensure_ascii=False), encoding="utf-8")
    roc_sim()
    figs = figures()
    shutil.copy2(JAA / "main.pdf", OUT / "jaa-manuscript.pdf")
    notebook()
    print(f"jaa_assets: {len(nums)} numbers, figures {figs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
