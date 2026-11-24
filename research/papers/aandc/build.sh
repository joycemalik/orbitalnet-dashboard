#!/usr/bin/env bash
# Build the Astronomy and Computing manuscript and cover letter (run from anywhere).
set -e
cd "$(dirname "$0")"
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
bibtex main >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
pdflatex -interaction=nonstopmode cover_letter.tex >/dev/null || true
grep -E "^! |undefined" main.log cover_letter.log || echo "no errors or undefined refs"
