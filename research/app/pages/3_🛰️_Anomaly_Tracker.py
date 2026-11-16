"""Satellite anomaly track (work in progress) — maneuver detection and fragmentation bursts from real catalog data."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "research" / "results" / "anomaly"
st.set_page_config(page_title="Anomaly Tracker", layout="wide", page_icon="🛰️")
st.title("🛰️ Satellite anomaly tracker — real Space-Track data")
st.info("🔬 In progress: thresholds are not frozen yet and the held-out window has not been run. "
        "Shown here is the validation window only.")

grid_f = RES / "validation_grid.json"
if grid_f.exists():
    g = json.loads(grid_f.read_text())
    st.subheader("Maneuver detector — known-event recall vs false alarms")
    c = st.columns(3)
    c[0].metric("Sourced known maneuvers", g["n_known"])
    c[1].metric("Derelict objects (negatives)", g["n_negative_objects"])
    c[2].metric("Object-years scanned", f"{g['negative_object_years']:.0f}")
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
    st.subheader(f"Fragmentation bursts found from catalog order ({len(b)})")
    fig = px.scatter(b, x="first_cataloged", y="pieces", size="pieces", hover_name="debris_name",
                     hover_data=["parents", "launch"], log_y=True, title="Debris bursts (bubble = pieces cataloged)")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(b, use_container_width=True, hide_index=True)
