"""Event Lab — inject your own transient and watch the open-world planner decide what it is.

User-injected scenario for demonstration; never written to research/results/.
"""

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
from ui.theme import AMBER, BLUE, GREEN, LINE, MUTED, ROSSO, apply_theme, hero, kpis, label, verdict

apply_theme()  # idempotent; also makes the page work standalone

hero("Discovery · Event Lab", "Inject a space event",
     "Place a transient anywhere in the sky and shape its light curve. Twenty real satellites work out who can see it, "
     "the open-world planner chooses each measurement, and the belief engine decides: a known kind of explosion — "
     "or h0, something no model explains.",
     status="User-injected scenario")

PRESETS = {
    "Mystery signal": dict(mode="custom", t_peak=3.0, rise=1.0, decay=2.0, reb=0.8, reb_t=9.0),
    "Kilonova": dict(mode="preset", cls="kilonova"),
    "Stellar flare": dict(mode="preset", cls="flare"),
    "GRB afterglow": dict(mode="preset", cls="grb_afterglow"),
    "Tidal disruption": dict(mode="preset", cls="tde"),
    "Design your own": dict(mode="custom", t_peak=1.0, rise=0.4, decay=4.0, reb=0.0, reb_t=9.0),
}
choice = st.pills("Quick start", list(PRESETS), default="Mystery signal", key="preset")
P = PRESETS.get(choice or "Mystery signal")

ctrl, view = st.columns([0.9, 2.1], gap="large")
with ctrl:
    label("01", "Target")
    ra = st.slider("Right ascension", 0.0, 360.0, 120.0, 1.0, format="%.0f°")
    dec = st.slider("Declination", -90.0, 90.0, 20.0, 1.0, format="%.0f°")

    label("02", "Signal")
    amp = st.slider("Peak brightness", 5.0, 20.0, 10.0, 0.5)
    if P["mode"] == "preset":
        cls = st.selectbox("Physical model", ALL_CLASSES_P2, index=ALL_CLASSES_P2.index(P["cls"]),
                           format_func=lambda c: PRETTY[c] + ("" if c in MODELED_CLASSES_P2 else "  · unknown to planner"))
        flux_fn = preset_flux_fn(cls, amp)
        name = PRETTY[cls]
    else:
        t_peak = st.slider("Peak at", 0.0, 10.0, P["t_peak"], 0.1, format="%.1f d")
        rise = st.slider("Rise width", 0.05, 5.0, P["rise"], 0.05, format="%.2f d")
        decay = st.slider("Fade time", 0.05, 15.0, P["decay"], 0.05, format="%.2f d")
        reb = st.slider("Second flare strength", 0.0, 1.5, P["reb"], 0.05)
        reb_t = st.slider("Second flare at", 1.0, 19.0, P["reb_t"], 0.5, format="%.1f d")
        flux_fn = lambda t: custom_flux(t, amp, t_peak, rise, decay, reb, reb_t)  # noqa: E731
        name = "Custom transient"

    with st.expander("Campaign settings"):
        n_obs = st.slider("Observation budget", 3, 8, 5)
        seed = st.number_input("Noise seed", 0, 9999, 0)
    launch = st.button("Launch observation campaign", type="primary", use_container_width=True,
                       icon=":material/rocket_launch:")

with view:
    rng = np.random.default_rng(7)
    sx, sy = rng.uniform(-180, 180, 500), np.degrees(np.arcsin(rng.uniform(-1, 1, 500)))
    sky = go.Figure()
    sky.add_trace(go.Scattergeo(lon=sx, lat=sy, mode="markers", hoverinfo="skip",
                                marker=dict(size=rng.uniform(1, 3, 500), color="rgba(220,230,255,0.55)")))
    sky.add_trace(go.Scattergeo(lon=[ra - 180], lat=[dec], mode="markers", hovertext=f"RA {ra:.0f}°  Dec {dec:.0f}°",
                                marker=dict(size=34, color="rgba(225,6,0,0.18)", line=dict(color=ROSSO, width=1))))
    sky.add_trace(go.Scattergeo(lon=[ra - 180], lat=[dec], mode="markers+text", text=["   TARGET"],
                                textfont=dict(family="JetBrains Mono", color=ROSSO, size=11), textposition="middle right",
                                marker=dict(size=9, color=ROSSO, symbol="diamond")))
    sky.update_geos(projection_type="mollweide", showland=False, showcoastlines=False, showocean=False,
                    showframe=True, framecolor=LINE, bgcolor="#05060A",
                    lataxis=dict(showgrid=True, gridcolor="#151922", dtick=30),
                    lonaxis=dict(showgrid=True, gridcolor="#151922", dtick=30))
    sky.update_layout(height=330, showlegend=False, margin=dict(l=0, r=0, t=28, b=0), title="CELESTIAL SPHERE · MOLLWEIDE")
    st.plotly_chart(sky, use_container_width=True, config={"displayModeBar": False})

    t_dense = np.exp(np.linspace(np.log(0.01), np.log(20.0), 300))
    y = flux_fn(t_dense)
    prev = go.Figure(go.Scatter(x=t_dense, y=y, line=dict(color=AMBER, width=2.5), fill="tozeroy",
                                fillcolor="rgba(255,176,32,0.08)", name=name))
    prev.update_layout(height=250, title=f"TRUE LIGHT CURVE · {name.upper()} · HIDDEN FROM THE PLANNER",
                       xaxis=dict(type="log", title="days since discovery"), yaxis_title="flux", showlegend=False)
    st.plotly_chart(prev, use_container_width=True, config={"displayModeBar": False})

if launch:
    with st.status("Running campaign", expanded=True) as stat:
        st.write("Propagating 20 real satellites with SGP4…")
        st.write("Computing line-of-sight to target…")
        st.write("Planning each measurement by expected information gain…")
        st.session_state["lab"] = (run_lab(ra, dec, flux_fn, seed=int(seed), n_obs=n_obs), name)
        stat.update(label="Campaign complete", state="complete", expanded=False)

if "lab" not in st.session_state:
    st.stop()

res, name = st.session_state["lab"]
label("03", f"Campaign · {name}")
kpis([("Fleet", res.n_satellites, "sats", "real Starlink TLEs", BLUE),
      ("Visible slots", res.visible_cells, "", "(time, satellite) pairs with line of sight", GREEN),
      ("Measurements", len(res.steps), "", "chosen by the planner", ROSSO),
      ("Confidence bar", f"{CONFIDENT_THRESHOLD:.0%}", "", "required to claim an answer", AMBER)])
if not res.steps:
    verdict("warn", "No line of sight", "No satellite can see this point in the window",
            "Move the target and launch again.")
    st.stop()

hyps = list(MODELED_CLASSES_P2) + ["h0"]
step = st.slider("Replay", 0, len(res.steps), len(res.steps), format="after measurement %d",
                 help="Scrub through the campaign to watch the belief change.")
steps = res.steps[:step]
post = steps[-1]["posterior"] if steps else {h: 1 / len(hyps) for h in hyps}

a, b = st.columns([1.25, 1], gap="large")
with a:
    lc = go.Figure()
    lc.add_trace(go.Scatter(x=res.true_flux_dense_t, y=res.true_flux_dense, name="truth (hidden)",
                            line=dict(color="rgba(255,176,32,0.35)", dash="dot")))
    if steps:
        lc.add_trace(go.Scatter(x=[s["t"] for s in steps], y=[s["y"] for s in steps], mode="markers+text",
                                text=[str(i + 1) for i in range(len(steps))], textposition="top center",
                                textfont=dict(family="JetBrains Mono", color=MUTED, size=10),
                                error_y=dict(array=[s["sigma"] for s in steps], color=GREEN, thickness=1),
                                marker=dict(size=11, color=GREEN, line=dict(color="#000", width=1)),
                                hovertext=[s["sat"] for s in steps], name="measurements"))
    lc.update_layout(height=360, title="MEASUREMENTS VS HIDDEN TRUTH", xaxis=dict(type="log", title="days"),
                     yaxis_title="flux", legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(lc, use_container_width=True, config={"displayModeBar": False})
with b:
    order = sorted(hyps, key=lambda h: post[h])
    cols = [ROSSO if h == "h0" else (GREEN if post[h] >= CONFIDENT_THRESHOLD else BLUE) for h in order]
    pf = go.Figure(go.Bar(x=[post[h] for h in order], y=[PRETTY[h] for h in order], orientation="h",
                          marker=dict(color=cols), text=[f"{post[h]:.0%}" for h in order], textposition="outside",
                          textfont=dict(family="JetBrains Mono")))
    pf.add_vline(x=CONFIDENT_THRESHOLD, line=dict(color=AMBER, dash="dot", width=1))
    pf.update_layout(height=360, title="BELIEF · WHICH HYPOTHESIS EXPLAINS IT", xaxis=dict(range=[0, 1.12], tickformat=".0%"))
    st.plotly_chart(pf, use_container_width=True, config={"displayModeBar": False})

st.dataframe([{"#": i + 1, "Satellite": s["sat"], "Day": round(s["t"], 3), "Depth (mag)": s["lim_mag"],
               "Leading hypothesis": PRETTY[max(s["posterior"], key=s["posterior"].get)],
               "P(h0)": f"{s['posterior']['h0']:.1%}"} for i, s in enumerate(steps)],
             use_container_width=True, hide_index=True)

if step == len(res.steps):
    v, p = res.verdict, res.verdict_prob
    if v == "h0" and p >= CONFIDENT_THRESHOLD:
        verdict("alert", "Null hypothesis h0 · anomaly detected", "Unmodeled phenomenon spotted",
                f"P(h0) = {p:.1%}. None of the known physical models explain these measurements."
                + (f" Planner switched to preservation mode at measurement {res.mode_switch_step} to keep "
                   "covering it for follow-up." if res.mode_switch_step else ""))
    elif p >= CONFIDENT_THRESHOLD:
        verdict("ok", "Identified", PRETTY[v], f"Posterior {p:.1%} — above the {CONFIDENT_THRESHOLD:.0%} bar.")
    else:
        verdict("warn", "Not confident · refusing to over-claim", f"Leaning {PRETTY[v]} · {p:.0%}",
                f"Below the {CONFIDENT_THRESHOLD:.0%} bar. The system reports uncertainty instead of guessing.")
