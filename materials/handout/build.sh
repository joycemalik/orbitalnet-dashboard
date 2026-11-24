#!/usr/bin/env bash
# Builds materials/OrbitalNet_Handout.pdf from materials/handout/handout.tex.
# Every metric comes from research/papers/main/generated/numbers.tex (generated from research/results/);
# vars.tex adds the satellite count (from satellites.txt) and numeric bar heights parsed from numbers.tex.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/../.."
OUT="$HERE/build"
mkdir -p "$OUT"
cp "$ROOT/research/papers/main/generated/numbers.tex" "$OUT/numbers.tex"
python - "$ROOT" "$OUT/vars.tex" <<'PY'
import re, sys, pathlib
root, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
lines = [l for l in (root / "satellites.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
nums = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (root / "research/papers/main/generated/numbers.tex").read_text(encoding="utf-8")))
def mid(k):  # midpoint of '0.79--0.81' / '96\%' -> float
    v = [float(x) for x in re.findall(r"\d*\.?\d+", nums[k])]
    return sum(v) / len(v)
o = [f"\\newcommand{{\\NSat}}{{{len(lines)//3:,}}}".replace(",", "{,}")]
for k in ["SimAucP", "SimAucBthree", "SimTprP", "SimTprBthree", "SimCwWhP", "SimCwWhBthree", "RealCCwWhP", "RealCCwWhBthree"]:
    o.append(f"\\newcommand{{\\v{k}}}{{{mid(k) / (100 if '%' in nums[k] else 1):.3f}}}")
out.write_text("\n".join(o) + "\n", encoding="utf-8")
PY
cp "$HERE/handout.tex" "$OUT/handout.tex"
cd "$OUT"
pdflatex -interaction=nonstopmode handout.tex >/dev/null || { grep -n "^!" -A4 handout.log | head -40; exit 1; }
pdflatex -interaction=nonstopmode handout.tex >/dev/null || { grep -n "^!" -A4 handout.log | head -40; exit 1; }
grep -E "Overfull" handout.log | head -10 || true
cp handout.pdf "$ROOT/materials/OrbitalNet_Handout.pdf"
echo "built materials/OrbitalNet_Handout.pdf"
