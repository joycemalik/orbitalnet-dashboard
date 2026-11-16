"""Scorecard — every preregistered hypothesis verdict, read straight from research/results/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RES = ROOT / "research" / "results"
st.set_page_config(page_title="Scorecard", layout="wide", page_icon="📊")
st.title("📊 Research scorecard")
st.caption("Every value below is read from JSON files in research/results/. Nothing is typed by hand.")

PHASES = [
    ("Phase 2 — planner vs baselines (synthetic)", "phase2/analysis_test.json", "verdict"),
    ("Phase 3 — real ZTF transients vs real Starlink fleet", "phase3/analysis_test.json", "overall_pass_all_seeds"),
    ("Phase 5 — two-band (g+r) real replay, prereg v2", "phase5/analysis_test_v2.json", "overall_pass_all_seeds"),
    ("Phase 6 — frozen v3 configuration, real replay", "phase6/analysis_test_v3.json", "overall_pass_all_seeds"),
]

rows = []
for name, rel, key in PHASES:
    f = RES / rel
    if not f.exists():
        rows.append({"phase": name, "status": "🔬 not run"})
        continue
    d = json.loads(f.read_text())
    row = {"phase": name, "status": "✅ test run complete"}
    for h, ok in d.get(key, {}).items():
        row[h] = "✅ pass" if ok else "❌ fail"
    rows.append(row)
st.subheader("Preregistered hypotheses (held-out test seeds)")
st.dataframe(pd.DataFrame(rows).fillna("—"), use_container_width=True, hide_index=True)

st.subheader("Effect sizes with 95% confidence intervals")
choice = st.selectbox("Phase", [p for p in PHASES if (RES / p[1]).exists() and p[2] == "overall_pass_all_seeds"],
                      format_func=lambda p: p[0])
d = json.loads((RES / choice[1]).read_text())
fig = go.Figure()
for run in d["runs"]:
    rn = Path(run.get("run_dir", "?")).name
    for k, v in run.items():
        if isinstance(v, dict) and "estimate" in v and "ci95" in v:
            lo, hi = v["ci95"]
            fig.add_trace(go.Scatter(x=[v["estimate"]], y=[f"{k}  [{rn}]"], mode="markers",
                                     error_x=dict(type="data", symmetric=False, array=[hi - v["estimate"]],
                                                  arrayminus=[v["estimate"] - lo]),
                                     marker=dict(size=11, color="#51cf66" if v.get("pass") else "#ff6b6b"),
                                     showlegend=False))
fig.add_vline(x=0, line_dash="dot")
fig.update_layout(height=120 + 40 * len(fig.data), margin=dict(l=0, r=0, t=10, b=0),
                  xaxis_title="estimate (green = hypothesis passed)")
st.plotly_chart(fig, use_container_width=True)
st.caption("H1: P makes fewer confident-wrong calls on unknown events than closed-world B3 (negative is good). "
           "H2: AUROC of P(h0) for spotting unknowns (>0.5 is good). H3: no extra confident-wrong on known events. "
           "H4/H5 (Phases 5–6): two-band AUROC gain over Phase 3 config; accuracy non-inferior to B3.")

with st.expander("Raw JSON"):
    st.json(d)
