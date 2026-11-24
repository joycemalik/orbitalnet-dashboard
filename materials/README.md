# materials/: documents about the project (not part of the website)

| File / folder | What it is | Built by |
|---|---|---|
| `OrbitalNet_Handout.pdf`, `handout/` | one-page project handout and its LaTeX source | `build_handout_pdf.py` or `handout/build.sh` |
| `OrbitalNet_Deck.pptx` / `.pdf`, `deck/` | 13-slide presentation and its figure sources | `deck/build_deck.py` |
| `OrbitalNet_Demo_Tutorial.pdf` | step-by-step demo tutorial | `build_tutorial_pdf.py` |
| `CIE_Writeup_OrbitalNet.pdf` | CIE write-up | `build_cie_pdf.py` |
| `handouts/` | final hand-exported handout | — |
| `report/` | college report (`orbitalnetos1.docx/.pdf`) and dataset parameters | Word |
| `report_figures/` | figures for the college report | scripts inside |
| `papers/` | illustrated Word copy of the research paper | `illustrate_paper_docx.py` |
| `presentations/` | other presentation exports | — |
| `notes/` | planning notes | — |

Every builder reads its numbers from `research/papers/main/generated/` or `research/results/`, so nothing
numeric is typed by hand. Run the builders from the repo root, e.g. `python materials/build_handout_pdf.py`.
The tutorial, CIE write-up and report describe the repo layout as it was when they were written, before
the `mission_control/` package existed.
