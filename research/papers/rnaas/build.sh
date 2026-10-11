#!/usr/bin/env bash
# Builds the RNAAS note PDF from generated numbers only.
#   1. python -m research.figures.rnaas_note        (numbers.tex, table.tex from results)
#   2. bash research/papers/rnaas/build.sh          (this script)
# Output: research/papers/rnaas/build/note.pdf, copied to docs/venues/rnaas-note.pdf
# Needs pdflatex and aastex701.cls (fetched from CTAN into build/ if absent).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
GEN="$ROOT/research/results/rnaas_note"
OUT="$HERE/build"
mkdir -p "$OUT"
cp "$HERE/note.tex" "$GEN/numbers.tex" "$GEN/table.tex" "$OUT/"
if [ ! -f "$OUT/aastex701.cls" ]; then
  tmp="$(mktemp -d)"
  curl -sL -o "$tmp/aastex.zip" https://mirrors.ctan.org/macros/latex/contrib/aastex.zip
  unzip -q -o "$tmp/aastex.zip" -d "$tmp"
  cp "$tmp/aastex/aastex701.cls" "$OUT/"
fi
cd "$OUT"
pdflatex -interaction=nonstopmode note.tex >/dev/null
pdflatex -interaction=nonstopmode note.tex >/dev/null
cp note.pdf "$ROOT/docs/venues/rnaas-note.pdf"
echo "built $OUT/note.pdf -> docs/venues/rnaas-note.pdf"
