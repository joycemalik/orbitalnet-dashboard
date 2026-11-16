"""Evidence — every preregistered hypothesis verdict, read straight from research/results/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import plotly.graph_objects as go
import streamlit as st

from ui.theme import GREEN, ROSSO, apply_theme, hero, kpis, label

apply_theme()
RES = ROOT / "research" / "results"

PHASES = [
    ("Phase 2", "Planner vs baselines · simulated", "phase2/analysis_test.json", "verdict"),
    ("Phase 3", "Real ZTF transients · real Starlink fleet", "phase3/analysis_test.json", "overall_pass_all_seeds"),
    ("Phase 5", "Two-band (g+r) real replay · prereg v2", "phase5/analysis_test_v2.json", "overall_pass_all_seeds"),
    ("Phase 6", "Frozen v3 configuration · real replay", "phase6/analysis_test_v3.json", "overall_pass_all_seeds"),
]
HYP = {"H1": "Fewer confident-wrong calls on unknowns", "H2": "P(h0) separates unknowns (AUROC)",
       "H3": "No extra errors on known events", "H4": "Two-band AUROC gain", "H5": "Accuracy non-inferior to B3"}

loaded = [(p, n, json.loads((RES / f).read_text()), k) for p, n, f, k in PHASES if (RES / f).exists()]
verdicts = {p: d.get(k, {}) for p, _n, d, k in loaded}
n_pass = sum(v for vs in verdicts.values() for v in vs.values())
n_all = sum(len(vs) for vs in verdicts.values())

hero("Discovery · Evidence", "What the research shows",
     "Preregistered hypotheses, evaluated once on held-out test seeds. Every value is read from research/results/ — "
     "nothing typed by hand. Failures are shown as failures.", status=f"{n_pass}/{n_all} hypotheses passed")

kpis([("Phases evaluated", len(loaded), "", "on held-out test data"),
      ("Hypotheses passed", n_pass, f"/ {n_all}", "preregistered before testing", GREEN),
      ("Hypotheses failed", n_all - n_pass, "", "reported, not hidden", ROSSO)])

label("01", "Hypothesis matrix")
hs = sorted({h for vs in verdicts.values() for h in vs})
cells = ['<div class="on-cell head"></div>'] + [f'<div class="on-cell head" title="{HYP.get(h, h)}">{h}</div>' for h in hs]
for p, n, _d, _k in loaded:
    cells.append(f'<div class="on-cell head"><b style="color:#fff">{p}</b><br><span style="font-weight:400">{n}</span></div>')
    for h in hs:
        v = verdicts[p].get(h)
        cells.append('<div class="on-cell na">—</div>' if v is None else
                     f'<div class="on-cell {"pass" if v else "fail"}">{"PASS" if v else "FAIL"}</div>')
st.markdown(f'<div class="on-matrix" style="grid-template-columns: 2.4fr repeat({len(hs)}, 1fr)">{"".join(cells)}</div>',
            unsafe_allow_html=True)
st.caption("  ·  ".join(f"**{h}** {HYP.get(h, '')}" for h in hs))

label("02", "Effect sizes · 95% confidence intervals")
opts = [x for x in loaded if x[3] == "overall_pass_all_seeds"]
pick = st.segmented_control("Phase", [x[0] for x in opts], default=opts[-1][0] if opts else None)
sel = next((x for x in opts if x[0] == pick), None)
if sel:
    d = sel[2]
    fig = go.Figure()
    for run in d["runs"]:
        rn = Path(run.get("run_dir", "?")).name
        for k, v in run.items():
            if isinstance(v, dict) and "estimate" in v and "ci95" in v:
                lo, hi = v["ci95"]
                fig.add_trace(go.Scatter(
                    x=[v["estimate"]], y=[f"{k.split('_')[0]} · {rn}"], mode="markers", showlegend=False,
                    error_x=dict(type="data", symmetric=False, array=[hi - v["estimate"]],
                                 arrayminus=[v["estimate"] - lo], thickness=1.5,
                                 color=GREEN if v.get("pass") else ROSSO),
                    marker=dict(size=10, symbol="diamond", color=GREEN if v.get("pass") else ROSSO),
                    hovertext=k))
    fig.add_vline(x=0, line=dict(dash="dot", color="#444"))
    fig.update_layout(height=140 + 30 * len(fig.data), xaxis_title="estimate  ·  green = passed, red = failed",
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with st.expander("Raw analysis file"):
        st.json(d)
