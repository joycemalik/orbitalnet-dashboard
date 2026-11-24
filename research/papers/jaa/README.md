# Journal of Astrophysics and Astronomy submission

Uses the journal's own double-column class and reference style from its author kit
(`archive/JAA.zip`): `jaa.cls` and `apj.bst`.

Build: `pdflatex main && bibtex main && pdflatex main && pdflatex main` (or `latexmk -pdf main.tex`).

Every number, table and figure comes from `generated/`. Regenerate it with `research/figures/paper_main.py` and
`research/figures/phase4_numbers.py`, then run `python research/papers/sync_generated.py`.
Do not type numbers by hand. The writing voice is described in `STYLE.md`.

Checked against the journal's Information for Authors: double column, abstract of at most 200 words
with no citations, 3 to 6 keywords, British English, IAU-style author-year references, full postal address,
an email for every author, acknowledgements straight after the main text, and figure text of at least 8 pt
at printed size.

Upload to Editorial Manager (https://www.editorialmanager.com/joaa/): `main.tex`, `results_*.tex`, `refs.bib`,
`main.bbl`, `jaa.cls`, `apj.bst`, the `generated/` folder, and the compiled `main.pdf`.
