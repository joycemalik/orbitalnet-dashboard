"""Satellite anomaly track (work in progress) — maneuver detection and fragmentation bursts from real catalog data."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import sys
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ui.theme import apply_theme, hero, kpis, label  # noqa: E402

apply_theme()
RES = ROOT / "research" / "results" / "anomaly"
hero("Discovery · Anomaly Watch", "Who moved, who broke up", "Maneuvers and fragmentations found in real Space-Track element history.", status="Work in progress", ok=False)
st.info("🔬 In progress: thresholds are not frozen yet and the held-out window has not been run. "
        "Shown here is the validation window only.")

grid_f = RES / "validation_grid.json"
if grid_f.exists():
    g = json.loads(grid_f.read_text())
    label("01", "Maneuver detector · recall vs false alarms")
    kpis([("Sourced known maneuvers", g["n_known"]), ("Derelict objects", g["n_negative_objects"], "", "negatives"),
          ("Object-years scanned", f"{g['negative_object_years']:.0f}")])
    df = pd.DataFrame([{k: r[k] for k in ("z", "min_km", "recall", "false_alarms",
                                          "false_alarms_per_object_year", "storm_lowerings")} for r in g["grid"]])
    fig = px.scatter(df, x="false_alarms_per_object_year", y="recall", color="z", size="min_km",
                     hover_data=df.columns, title="Each dot = one threshold setting")
    st.plotly_chart(fig, use_container_width=True)
    best = max(g["grid"], key=lambda r: (r["recall"], -r["false_alarms"]))
    st.markdown(f"**Known events at the best setting (z={best['z']}, min {best['min_km']} km):**")
    st.dataframe(pd.DataFrame(best["events"]), use_container_width=True, hide_index=True)

bursts = sorted(RES.glob("fragmentation_bursts_*.csv"))
if bursts:
    b = pd.read_csv(bursts[-1])
    label("02", f"Fragmentation bursts from catalog order · {len(b)}")
    fig = px.scatter(b, x="first_cataloged", y="pieces", size="pieces", hover_name="debris_name",
                     hover_data=["parents", "launch"], log_y=True, title="Debris bursts (bubble = pieces cataloged)")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(b, use_container_width=True, hide_index=True)
