# JOAA submission (Springer Nature template)

Build: `latexmk -pdf main.tex` (or pdflatex → bibtex → pdflatex ×2). Overleaf also works: upload this folder.

Upload to Editorial Manager (https://www.editorialmanager.com/joaa/): `main.tex`, `refs.bib`, `main.bbl`,
`sn-jnl.cls`, `sn-basic.bst`, `figures/*.png`, plus the compiled `main.pdf`.

Before submitting: fill the TODOs in Declarations, add the author list for the NMMA-Astro-COLIBRI reference in `refs.bib`,
and add in-text `\cite{}` calls (none existed in the source docx; all references are currently listed via `\nocite{*}`).
