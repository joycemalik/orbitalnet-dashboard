#!/usr/bin/env bash
# Builds the main paper PDF from generated numbers and figures only.
#   1. python -m research.figures.paper_main     (generated/numbers.tex, tables, figures)
#   2. bash research/papers/main/build.sh        (this script)
# Output: research/papers/main/build/paper.pdf, copied to docs/venues/paper.pdf
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
OUT="$HERE/build"
rm -rf "$OUT" && mkdir -p "$OUT"
cp "$HERE"/*.tex "$OUT/"
cp -r "$HERE/generated" "$OUT/generated"
cp "$HERE/generated/numbers.tex" "$OUT/numbers.tex"
cd "$OUT"
pdflatex -interaction=nonstopmode paper.tex >/dev/null || { tail -30 paper.log; exit 1; }
pdflatex -interaction=nonstopmode paper.tex >/dev/null || { tail -30 paper.log; exit 1; }
grep -E "undefined|Overfull" paper.log | head -20 || true
cp paper.pdf "$ROOT/docs/venues/paper.pdf"
echo "built $OUT/paper.pdf -> docs/venues/paper.pdf"
