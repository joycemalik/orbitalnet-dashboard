#!/usr/bin/env bash
# Builds the storm-drag RNAAS note from generated numbers only.
#   1. python -m research.figures.rnaas_atlas        (numbers.tex from research/results/atlas/)
#   2. bash research/papers/rnaas_atlas/build.sh     (this script)
# Output: research/papers/rnaas_atlas/build/note.pdf
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
OUT="$HERE/build"
mkdir -p "$OUT"
cp "$HERE/note.tex" "$ROOT/research/results/rnaas_atlas/numbers.tex" "$ROOT/research/results/atlas/atlas_primary.png" "$OUT/"
[ -f "$OUT/aastex701.cls" ] || cp "$ROOT/research/papers/rnaas/build/aastex701.cls" "$OUT/"
cd "$OUT"
pdflatex -interaction=nonstopmode note.tex >/dev/null
pdflatex -interaction=nonstopmode note.tex >/dev/null
echo "built $OUT/note.pdf"
