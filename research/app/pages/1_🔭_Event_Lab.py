"""Event Lab — inject your own transient and watch the open-world planner decide what it is."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from research.app.event_lab import (
    ALL_CLASSES_P2, CONFIDENT_THRESHOLD, MODELED_CLASSES_P2, PRETTY, custom_flux, preset_flux_fn, run_lab,
)

st.set_page_config(page_title="Event Lab", layout="wide", page_icon="🔭")
st.title("🔭 Event Lab — create a space event, let the constellation figure it out")
st.caption(
    "User-injected scenario (interactive demo, not a measured result). Uses the real Phase 2 machinery: "
    "real TLE fleet → visibility of your sky position → open-world planner (method P) picks each observation → "
    "posterior over 4 known physical models **plus h0 = 'none of them'**."
)

left, right = st.columns([1, 2])
with left:
    st.subheader("1 · Where in the sky?")
    ra = st.slider("Right ascension (°)", 0.0, 360.0, 120.0, 1.0)
    dec = st.slider("Declination (°)", -90.0, 90.0, 20.0, 1.0)

    st.subheader("2 · What happens there?")
    mode = st.radio("Event", ["🧪 Invent my own", "📚 Pick a known type"], horizontal=True)
    if mode.startswith("📚"):
        cls = st.selectbox("Type", ALL_CLASSES_P2, format_func=lambda c: PRETTY[c] +
                           ("" if c in MODELED_CLASSES_P2 else "  (not in the planner's models)"))
        amp = st.slider("Brightness", 5.0, 20.0, 10.0)
        flux_fn = preset_flux_fn(cls, amp)
        label = PRETTY[cls]
    else:
        amp = st.slider("Peak brightness", 5.0, 20.0, 10.0)
        t_peak = st.slider("Peak time (days)", 0.0, 10.0, 3.0, 0.1)
        rise = st.slider("Rise width (days)", 0.05, 5.0, 1.0, 0.05)
        decay = st.slider("Fade time (days)", 0.05, 15.0, 2.0, 0.05)
        reb = st.slider("Second flare strength", 0.0, 1.5, 0.8, 0.05)
        reb_t = st.slider("Second flare at (days)", 1.0, 19.0, 9.0, 0.5)
        flux_fn = lambda t: custom_flux(t, amp, t_peak, rise, decay, reb, reb_t)  # noqa: E731
        label = "Your invented event"

    n_obs = st.slider("Observation budget", 3, 8, 5)
    seed = st.number_input("Noise seed", 0, 9999, 0)
    go_btn = st.button("🚀 Launch observation campaign", type="primary", use_container_width=True)

with right:
    sky = go.Figure()
    sky.add_trace(go.Scattergeo(lon=[ra - 180], lat=[dec], mode="markers+text", text=["  your event"],
                                marker=dict(size=18, color="#ff4b4b", symbol="star")))
    sky.update_geos(projection_type="mollweide", showland=False, showcoastlines=False,
                    showframe=True, bgcolor="#0b1020", lataxis_showgrid=True, lonaxis_showgrid=True)
    sky.update_layout(height=260, margin=dict(l=0, r=0, t=30, b=0), title="Sky position (RA/Dec, Mollweide)",
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(sky, use_container_width=True)
    t_dense = np.exp(np.linspace(np.log(0.01), np.log(20.0), 200))
    prev = go.Figure(go.Scatter(x=t_dense, y=flux_fn(t_dense), line=dict(color="#ffa94d", width=3), name=label))
    prev.update_layout(height=230, margin=dict(l=0, r=0, t=30, b=0), title="True light curve (hidden from the planner)",
                       xaxis_type="log", xaxis_title="days since discovery", yaxis_title="flux")
    st.plotly_chart(prev, use_container_width=True)

if go_btn:
    with st.spinner("Propagating 20 real satellites (SGP4) and planning observations…"):
        st.session_state["lab"] = (run_lab(ra, dec, flux_fn, seed=int(seed), n_obs=n_obs), label)

if "lab" in st.session_state:
    res, label = st.session_state["lab"]
    st.divider()
    st.subheader(f"3 · Campaign: {label}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Satellites in fleet", res.n_satellites)
    c2.metric("Visible (time, satellite) slots", res.visible_cells)
    c3.metric("Observations taken", len(res.steps))
    if not res.steps:
        st.error("No satellite can see this sky position in the campaign window — try another RA/Dec.")
        st.stop()

    hyps = list(MODELED_CLASSES_P2) + ["h0"]
    colors = ["#4dabf7"] * len(MODELED_CLASSES_P2) + ["#ff4b4b"]
    lc_slot, post_slot = st.columns(2)
    lc_ph, post_ph = lc_slot.empty(), post_slot.empty()
    log_ph = st.empty()
    play = st.button("▶️ Replay step by step")

    def render(k: int):
        steps = res.steps[:k]
        lc = go.Figure()
        lc.add_trace(go.Scatter(x=res.true_flux_dense_t, y=res.true_flux_dense, name="truth (hidden)",
                                line=dict(color="rgba(255,169,77,0.35)", dash="dot")))
        if steps:
            lc.add_trace(go.Scatter(x=[s["t"] for s in steps], y=[s["y"] for s in steps], mode="markers",
                                    error_y=dict(array=[s["sigma"] for s in steps]),
                                    marker=dict(size=12, color="#51cf66"), name="satellite measurements",
                                    text=[s["sat"] for s in steps]))
        lc.update_layout(height=340, xaxis_type="log", title=f"Measurements after step {k}",
                         xaxis_title="days", yaxis_title="flux", margin=dict(t=40, b=0))
        lc_ph.plotly_chart(lc, use_container_width=True, key=f"lc{k}{time.time()}")
        post = steps[-1]["posterior"] if steps else {h: 1 / len(hyps) for h in hyps}
        pf = go.Figure(go.Bar(x=[post[h] for h in hyps], y=[PRETTY[h] for h in hyps], orientation="h",
                              marker_color=colors, text=[f"{post[h]:.0%}" for h in hyps], textposition="auto"))
        pf.update_layout(height=340, xaxis_range=[0, 1], title="Belief: which hypothesis explains it?",
                         margin=dict(t=40, b=0))
        post_ph.plotly_chart(pf, use_container_width=True, key=f"pf{k}{time.time()}")
        log_ph.table([{"step": i + 1, "satellite": s["sat"], "day": round(s["t"], 3),
                       "instrument depth (mag)": s["lim_mag"], "leading hypothesis":
                       PRETTY[max(s["posterior"], key=s["posterior"].get)]} for i, s in enumerate(steps)])

    if play:
        for k in range(len(res.steps) + 1):
            render(k)
            time.sleep(1.2)
    else:
        render(len(res.steps))

    v, p = res.verdict, res.verdict_prob
    if v == "h0" and p >= CONFIDENT_THRESHOLD:
        st.error(f"## 🚨 NULL HYPOTHESIS h0 WINS — UNMODELED PHENOMENON SPOTTED\n"
                 f"P(h0) = {p:.1%}. None of the known physical models explain these measurements. "
                 + (f"The planner switched to *preservation mode* at step {res.mode_switch_step} "
                    "to keep covering the anomaly for follow-up." if res.mode_switch_step else ""))
        st.balloons()
    elif p >= CONFIDENT_THRESHOLD:
        st.success(f"## ✅ Identified: {PRETTY[v]}  (posterior {p:.1%})")
    else:
        st.warning(f"## 🤔 Not confident yet — leading: {PRETTY[v]} at {p:.1%} "
                   f"(below the {CONFIDENT_THRESHOLD:.0%} bar). The system refuses to over-claim.")
