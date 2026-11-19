#!/usr/bin/env bash
# Builds the Journal of Astrophysics and Astronomy submission PDF from the main paper's section files.
#   1. python -m research.figures.paper_main   (generated numbers, tables, figures)
#   2. bash research/papers/jaa/build.sh
# Output: research/papers/jaa/build/paper.pdf
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MAIN="$HERE/../main"
OUT="$HERE/build"
rm -rf "$OUT" && mkdir -p "$OUT"
cp "$MAIN"/*.tex "$OUT/"
cp -r "$MAIN/generated" "$OUT/generated"
cp "$MAIN/generated/numbers.tex" "$OUT/numbers.tex"
cd "$OUT"
# single-column layout: wide floats become normal floats, figures sized for one column
sed -i -e 's/table\*/table/g' -e 's/figure\*/figure/g' -e 's/width=\\columnwidth/width=0.72\\linewidth/g' \
  results_sim.tex results_real.tex results_conformal.tex discussion.tex
# body = everything between \input{abstract} and \section*{Reproducibility} of the main paper
awk '/\\input\{abstract\}/{f=1;next} /\\section\*\{Reproducibility\}/{f=0} f' paper.tex > body.tex
# bibliography = from \begin{thebibliography} to \end{document}
awk '/\\begin\{thebibliography\}/{f=1} f' paper.tex > biblio.tex
cat "$HERE/header.tex" body.tex "$HERE/footer.tex" biblio.tex > jaa_paper.tex
pdflatex -interaction=nonstopmode jaa_paper.tex >/dev/null || { tail -30 jaa_paper.log; exit 1; }
pdflatex -interaction=nonstopmode jaa_paper.tex >/dev/null || { tail -30 jaa_paper.log; exit 1; }
grep -E "undefined|Overfull" jaa_paper.log | head -20 || true
echo "built $OUT/jaa_paper.pdf"
