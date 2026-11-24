"""Generates the Chapter 4 design diagrams (Fig 4.1-4.6) for the college report.

Run:  python docs/report_figures/make_diagrams.py
Output: PNGs (300 dpi) next to this script, named fig_4_X_<name>.png.
Content follows the Chapter 4 text of orbitalnetos1.docx and the function
names in the source files.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, Circle, FancyArrowPatch

OUT = Path(__file__).parent
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

C = dict(pres="#dbeafe", comm="#dcfce7", dec="#fef3c7", phys="#fce7f3",
         data="#e5e7eb", edge="#1f2937", act="#e0f2fe", note="#f3f4f6")


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fc="white", fs=9, bold=False, r=0.08, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={r}",
                                fc=fc, ec=C["edge"], lw=1.1, ls=ls))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            weight="bold" if bold else "normal", wrap=True)


def arrow(ax, p, q, dashed=False, text=None, both=False, rad=0.0, fs=7.5, color=None):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="<|-|>" if both else "-|>",
                                 mutation_scale=11, lw=1.0, color=color or C["edge"],
                                 ls="--" if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, text, fontsize=fs, ha="center",
                va="center", bbox=dict(fc="white", ec="none", pad=0.6))


def save(fig, name):
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


# ---------------------------------------------------------------- Fig 4.1
def fig_4_1():
    fig, ax = canvas(11, 8.2)
    layers = [
        (6.6, "Presentation layer", C["pres"],
         [("Three.js WebGL globe\nindex.html", 0), ("Streamlit console\napp.py + pages/ (1-3)", 1)]),
        (5.0, "Communication layer", C["comm"],
         [("WebSocket streamer\nstreamer.py  (ws://:8765)", 0), ("Mission & auction ledgers\nMISSIONS_LEDGER, AUCTION_LOGS", 1)]),
        (3.4, "Decision layer", C["dec"],
         [("Consensus engine\nCNP auction, plane leaders", 0), ("Scoring engine\ngatekeepers, risk decay", 1),
          ("Open-world planner\nresearch/ (h0, EIG, conformal)", 2)]),
        (1.8, "Physics layer", C["phys"],
         [("SGP4 physics engine\nphysics_engine.py (1 Hz)", 0), ("Hardware abstraction layer\nhal_simulator.py (telemetry)", 1)]),
    ]
    for y, name, fc, items in layers:
        ax.add_patch(FancyBboxPatch((0.3, y), 8.0, 1.3, boxstyle="round,pad=0.02,rounding_size=0.1",
                                    fc=fc, ec="#9ca3af", lw=0.8, alpha=0.55))
        ax.text(0.45, y + 1.12, name, fontsize=9.5, weight="bold", va="center")
        n = len(items); w = (7.6 - 0.25 * (n - 1)) / n
        for t, i in items:
            box(ax, 0.5 + i * (w + 0.25), y + 0.12, w, 0.82, t, fc="white", fs=8.5)
    # Redis bus
    box(ax, 8.8, 1.8, 1.9, 6.1, "Redis / Memurai\nshared state bus\n\nSTARLINK-<id>\nMISSIONS_LEDGER\nAUCTION_LOGS\nTIME_MULTIPLIER\nTRIGGER_CHAOS\nSCORING_WEIGHTS\nCURRENT_SUN_LON",
        fc=C["data"], fs=8.3)
    ax.text(9.75, 7.65, "Integration bus", ha="center", fontsize=9.5, weight="bold")
    for y in (6.6, 5.0, 3.4, 1.8):
        arrow(ax, (8.3, y + 0.65), (8.8, y + 0.65), both=True)
    # data source
    box(ax, 0.5, 0.25, 3.6, 0.9, "satellites.txt\nTLE file, 10,109 satellites", fc="white", fs=8.5)
    arrow(ax, (2.3, 1.15), (2.3, 1.92), text="parse TLE")
    box(ax, 4.6, 0.25, 3.5, 0.9, "boot_os.py\nstarts all services in order", fc="white", fs=8.5, ls="--")
    save(fig, "fig_4_1_system_architecture.png")


# ---------------------------------------------------------------- Fig 4.2
def actor(ax, x, y, label):
    ax.add_patch(Circle((x, y + 0.55), 0.13, fc="white", ec=C["edge"], lw=1.1))
    ax.plot([x, x], [y + 0.42, y + 0.05], color=C["edge"], lw=1.1)
    ax.plot([x - 0.22, x + 0.22], [y + 0.3, y + 0.3], color=C["edge"], lw=1.1)
    ax.plot([x, x - 0.18], [y + 0.05, y - 0.2], color=C["edge"], lw=1.1)
    ax.plot([x, x + 0.18], [y + 0.05, y - 0.2], color=C["edge"], lw=1.1)
    ax.text(x, y - 0.38, label, ha="center", va="top", fontsize=8.5)


def uc(ax, x, y, text, w=2.5, h=0.62):
    ax.add_patch(Ellipse((x, y), w, h, fc=C["act"], ec=C["edge"], lw=1.0))
    ax.text(x, y, text, ha="center", va="center", fontsize=8.2)
    return (x, y, w, h)


def fig_4_2():
    fig, ax = canvas(11, 8.6)
    ax.add_patch(FancyBboxPatch((2.2, 0.3), 6.6, 7.9, boxstyle="round,pad=0.02,rounding_size=0.1",
                                fc="#fafafa", ec=C["edge"], lw=1.2))
    ax.text(5.5, 7.95, "OrbitalNet OS", ha="center", fontsize=11, weight="bold")
    U = {}
    U["dispatch"] = uc(ax, 4.0, 7.2, "Dispatch mission")
    U["weights"] = uc(ax, 4.0, 6.35, "Set scoring weights")
    U["chaos"] = uc(ax, 4.0, 5.5, "Inject fault (chaos)")
    U["watch"] = uc(ax, 4.0, 4.65, "Watch fleet on globe")
    U["logs"] = uc(ax, 4.0, 3.8, "Inspect auction logs")
    U["time"] = uc(ax, 4.0, 2.95, "Accelerate time")
    U["plan"] = uc(ax, 4.0, 1.75, "Plan transient follow-up")
    U["unknown"] = uc(ax, 4.0, 0.7, "Flag unknown event")
    U["auction"] = uc(ax, 7.1, 7.2, "Run CNP auction")
    U["enclave"] = uc(ax, 7.1, 6.1, "Form enclave")
    U["bid"] = uc(ax, 7.1, 5.0, "Bid for mission")
    U["handoff"] = uc(ax, 7.1, 3.9, "Rolling hand-off")
    U["heal"] = uc(ax, 7.1, 2.9, "Self-heal (re-auction)")
    U["prop"] = uc(ax, 7.1, 1.6, "Propagate orbits")
    actor(ax, 0.9, 6.3, "Mission\ncommander")
    actor(ax, 0.9, 3.9, "Ground-station\noperator")
    actor(ax, 0.9, 1.0, "Astronomer")
    actor(ax, 10.1, 5.2, "Satellite node")
    actor(ax, 10.1, 1.9, "Physics engine")

    def link(a, key, right=False):
        x, y, w, h = U[key]
        ax.plot([a[0], x + (w / 2 if right else -w / 2)], [a[1], y], color=C["edge"], lw=0.8)
    for k in ("dispatch", "weights"): link((1.15, 6.6), k)
    for k in ("chaos", "watch", "logs", "time"): link((1.15, 4.2), k)
    for k in ("plan", "unknown"): link((1.15, 1.3), k)
    for k in ("bid", "enclave", "handoff"): link((9.85, 5.5), k, right=True)
    link((9.85, 2.2), "prop", right=True)

    def dep(a, b, label):
        xa, ya, wa, _ = U[a]; xb, yb, wb, hb = U[b]
        p = (xa + wa / 2, ya) if xb > xa else (xa, ya - 0.31)
        q = (xb - wb / 2, yb) if xb > xa else (xb, yb + hb / 2)
        arrow(ax, p, q, dashed=True, text=label, fs=7)
    dep("dispatch", "auction", "«include»")
    arrow(ax, (7.1, 6.89), (7.1, 6.41), dashed=True, text="«include»", fs=7)
    arrow(ax, (5.95, 3.95), (5.95, 5.95), dashed=True, rad=-0.22)
    ax.text(5.45, 4.95, "«extend»", fontsize=7, ha="center", bbox=dict(fc="white", ec="none", pad=0.5))
    arrow(ax, (7.75, 3.15), (8.0, 5.85), dashed=True, text="«extend»", fs=7, rad=-0.35)
    arrow(ax, (4.0, 1.44), (4.0, 1.01), dashed=True)
    ax.text(4.15, 1.22, "«include»", fontsize=7, va="center")
    arrow(ax, (5.25, 5.5), (5.85, 3.0), dashed=True, text="triggers", fs=7)
    save(fig, "fig_4_2_use_case_diagram.png")


# ---------------------------------------------------------------- Fig 4.3 / 4.4
def cls(ax, x, y, w, name, attrs, funcs, fc):
    lh = 0.26
    h = 0.42 + lh * (len(attrs) + len(funcs)) + (0.18 if funcs else 0.05)
    ax.add_patch(plt.Rectangle((x, y - h), w, h, fc="white", ec=C["edge"], lw=1.1))
    ax.add_patch(plt.Rectangle((x, y - 0.42), w, 0.42, fc=fc, ec=C["edge"], lw=1.1))
    ax.text(x + w / 2, y - 0.21, name, ha="center", va="center", weight="bold", fontsize=8 if len(name) > 34 else 9)
    yy = y - 0.42 - 0.2
    for a in attrs:
        ax.text(x + 0.08, yy, a, fontsize=7.6, va="center", family="DejaVu Sans Mono"); yy -= lh
    sep = yy + lh / 2 + 0.02
    if funcs:
        ax.plot([x, x + w], [sep, sep], color=C["edge"], lw=0.8)
    yy -= 0.08
    for f in funcs:
        ax.text(x + 0.08, yy, f, fontsize=7.6, va="center", family="DejaVu Sans Mono"); yy -= lh
    return dict(x=x, y=y, w=w, h=h, cx=x + w / 2, top=y, bot=y - h)


def fig_4_3():
    fig, ax = canvas(12, 8.4)
    pe = cls(ax, 0.3, 8.1, 3.6, "PhysicsEngine  (physics_engine.py)",
             ["satellites: list[Satrec]", "sim_time: datetime", "multiplier  (CHRONOS_MULTIPLIER)"],
             ["load_satellites(filepath)", "classify_satellite(name)", "eci_to_latlon(x, y, z, jd)", "start_engine()"], C["phys"])
    hal = cls(ax, 0.3, 4.6, 3.6, "MockHAL  (hal_simulator.py)",
              ["sat_id: str", "soc_raw: float", "thermal_raw: float", "memory_raw: float"],
              ["generate_telemetry(position_z)"], C["phys"])
    sc = cls(ax, 4.3, 8.1, 3.7, "ScoringEngine  (scoring_engine.py)",
             ["lambda_val = 0.5", "delta_floor = 0.2"],
             ["flatten_telemetry(t)", "evaluate_gatekeepers(state)", "calculate_aggregate_risk(state)",
              "calculate_base_capability(s, w)", "apply_risk_decay(c, R, λ)", "compute_final_score(t, w)",
              "calculate_swarm_utility(ci, div)"], C["dec"])
    ce = cls(ax, 8.4, 8.1, 3.4, "ConsensusEngine  (consensus_engine.py)",
             ["cycle = 5 s", "slew_margin = 1000 km"],
             ["haversine(lat1, lon1, lat2, lon2)", "elect_plane_leaders()",
              "  loop: CNP auction + award", "  loop: rolling hand-off", "  loop: chaos + self-heal"], C["dec"])
    sm = cls(ax, 8.4, 4.3, 3.4, "ScenarioManager  (scenario_engine.py)",
             ["SCENARIOS: dict (4 missions)"],
             ["dispatch_mission(name)", "inject_chaos()"], C["pres"])
    st = cls(ax, 4.3, 3.3, 3.7, "Streamer  (streamer.py)",
             ["url = ws://localhost:8765"],
             ["broadcast_telemetry(websocket)", "main()"], C["comm"])
    rd = cls(ax, 4.6, 1.2, 3.1, "Redis  (shared state)",
             ["STARLINK-<id>, MISSIONS_LEDGER", "AUCTION_LOGS, TRIGGER_CHAOS"], [], C["data"])
    arrow(ax, (pe["cx"], pe["bot"]), (hal["cx"], hal["top"]), text="uses")
    arrow(ax, (pe["x"] + pe["w"], 7.3), (sc["x"], 7.3), text="uses")
    arrow(ax, (ce["x"], 6.9), (sc["x"] + sc["w"], 6.9), text="uses")
    for p in [(pe["x"] + pe["w"] - 0.3, pe["bot"]), (ce["cx"], ce["bot"]), (sm["cx"], sm["bot"]),
              (st["cx"], st["bot"]), (hal["x"] + hal["w"], hal["bot"] + 0.3)]:
        arrow(ax, p, (rd["cx"], rd["top"]), dashed=True)
    ax.text(0.3, -0.15, "Solid arrow: module uses another.   Dashed arrow: reads/writes shared Redis state.",
            fontsize=8, style="italic")
    save(fig, "fig_4_3_class_diagram_live_platform.png")


def fig_4_4():
    fig, ax = canvas(12, 8.6)
    b = cls(ax, 0.3, 7.7, 3.7, "ClosedWorldBelief  (bayes.py)",
            ["classes: tuple[str]", "amp_grid: 25 log-spaced", "log_joint: ndarray"],
            ["update(t, y, sigma)", "class_posterior()", "class_log_evidence()", "entropy()"], C["dec"])
    gp = cls(ax, 4.3, 7.7, 3.5, "SimpleGP  (openworld.py)",
             ["kernel: squared-exponential", "sigma_n: float"],
             ["kernel(x1, x2)", "log_marginal_likelihood(t, y)", "predict(t_obs, y_obs, t*)"], C["comm"])
    agp = cls(ax, 4.3, 4.6, 3.5, "AmplitudeMarginalGP",
              ["amp_grid: ndarray"],
              ["log_marginal_likelihood(t, y)", "predict(t_obs, y_obs, t*)"], C["comm"])
    ow = cls(ax, 8.2, 7.7, 3.5, "open_world_posterior()",
             ["hypotheses: K classes + h0", "prior: uniform 1/(K+1)"], ["open_world_posterior(...)"], C["dec"])
    cf = cls(ax, 8.2, 5.4, 3.5, "Conformal  (conformal.py)",
             ["alpha: target false-alarm", "tau: threshold"],
             ["conformal_threshold(cal, α)", "log_bf_score(ev, h0_ev)", "conformal_pvalue(cal, s)",
              "conformal_decision(post, s, τ)"], C["pres"])
    pl = cls(ax, 0.3, 4.6, 3.7, "OpenWorldPlanner  (openworld_planner.py)",
             ["satellites, candidate times"], ["open_world_eig_planner(...)", "closed_world_eig_planner(...)"], C["dec"])
    mi = cls(ax, 0.3, 2.3, 3.7, "InformationGain  (mutual_information.py)",
             [], ["expected_information_gain(...)", "expected_information_gain_batch(...)"], C["comm"])
    geo = cls(ax, 4.3, 2.3, 3.5, "OrbitGeometry  (orbitsim/geometry.py)",
              [], ["is_target_visible(sat, dir)", "earth_angular_radius_deg(d)", "radec_to_unit_eci(ra, dec)"], C["phys"])
    arrow(ax, (agp["cx"], agp["top"]), (gp["cx"], gp["bot"]), text="extends / wraps")
    arrow(ax, (ow["x"], 7.2), (gp["x"] + gp["w"], 7.2), text="h0 evidence")
    arrow(ax, (ow["x"] + 0.4, ow["top"]), (b["x"] + b["w"] - 0.4, b["top"]), rad=0.18)
    ax.text(6.05, 8.42, "class evidence", fontsize=7.5, ha="center")
    arrow(ax, (cf["cx"], cf["top"]), (ow["cx"], ow["bot"]), text="posterior")
    arrow(ax, (pl["cx"], pl["top"]), (b["cx"], b["bot"]), text="belief")
    arrow(ax, (pl["x"] + pl["w"], 4.1), (agp["x"], 4.1), text="h0 predictive")
    arrow(ax, (pl["cx"], pl["bot"]), (mi["cx"], mi["top"]), text="EIG")
    arrow(ax, (pl["x"] + pl["w"] - 0.4, pl["bot"]), (geo["x"] + 0.4, geo["top"]), text="visibility")
    ax.text(0.3, 0.25, "Research package (research/): planning and certification. Arrows show which module uses which.",
            fontsize=8, style="italic")
    save(fig, "fig_4_4_class_diagram_research.png")


# ---------------------------------------------------------------- Fig 4.5
def diamond(ax, x, y, text, w=2.6, h=0.9):
    ax.add_patch(plt.Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)],
                             fc="#fef9c3", ec=C["edge"], lw=1.0))
    ax.text(x, y, text, ha="center", va="center", fontsize=8)


def fig_4_5():
    fig, ax = canvas(11.4, 12.5)
    X = 4.0
    ax.add_patch(Circle((X, 12.1), 0.17, fc=C["edge"]))
    steps = [(11.3, "Read fleet from Redis (STARLINK-*)"),
             (10.45, "Group satellites by orbital plane (RAAN)"),
             (9.6, "Elect plane leader = highest score in each plane"),
             (8.75, "Read every mission in MISSIONS_LEDGER")]
    prev = 11.93
    for y, t in steps:
        arrow(ax, (X, prev), (X, y + 0.3)); box(ax, X - 2.1, y - 0.3, 4.2, 0.6, t, fc=C["act"], fs=8.5); prev = y - 0.3
    arrow(ax, (X, prev), (X, 7.75)); diamond(ax, X, 7.3, "Mission status?", w=2.8)
    # OPEN branch (left)
    L = 1.9
    arrow(ax, (X - 1.4, 7.3), (L, 6.7), text="OPEN_AUCTION")
    box(ax, L - 1.6, 5.9, 3.2, 0.7, "Apply gatekeepers;\nscore every bidder (U)", fc=C["act"], fs=8)
    arrow(ax, (L, 5.9), (L, 5.35)); diamond(ax, L, 4.9, "≥ N eligible?", w=2.4)
    box(ax, L - 1.6, 3.4, 3.2, 0.75, "Lock best N; status\n= EXECUTING", fc=C["act"], fs=8)
    arrow(ax, (L, 4.45), (L, 4.15), text="yes")
    ax.plot([L - 1.2, 0.3], [4.9, 4.9], color=C["edge"], lw=1.0); ax.text(0.45, 5.0, "no", fontsize=7.5)
    box(ax, 0.05, 2.35, 1.6, 0.75, "Stay pending,\nretry next cycle", fc=C["note"], fs=7.6)
    ax.plot([0.3, 0.3], [4.9, 3.1], color=C["edge"], lw=1.0); arrow(ax, (0.3, 3.2), (0.3, 3.1))
    # EXECUTING branch (right)
    R = 7.4
    arrow(ax, (X + 1.4, 7.3), (R, 6.7), text="EXECUTING")
    box(ax, R - 1.8, 5.9, 3.6, 0.7, "Release members that left\nthe footprint (hand-off)", fc=C["act"], fs=8)
    arrow(ax, (R, 5.9), (R, 5.35)); diamond(ax, R, 4.9, "TRIGGER_CHAOS set?", w=2.9)
    box(ax, R + 1.6, 4.55, 1.7, 0.7, "Kill random\nnodes", fc=C["act"], fs=8)
    arrow(ax, (R + 1.45, 4.9), (R + 1.6, 4.9), text="")
    ax.text(R + 1.5, 5.12, "yes", fontsize=7.5)
    arrow(ax, (R, 4.45), (R, 3.95), text="no")
    arrow(ax, (R + 2.45, 4.55), (R + 0.9, 3.8), rad=-0.2)
    diamond(ax, R, 3.5, "members < N?", w=2.5)
    box(ax, R - 1.6, 1.9, 3.2, 0.7, "Re-open auction\n(status = OPEN_AUCTION)", fc=C["act"], fs=8)
    arrow(ax, (R, 3.05), (R, 2.6), text="yes")
    # merge
    box(ax, X - 2.1, 0.8, 4.2, 0.6, "Write results to ledger + AUCTION_LOGS", fc=C["act"], fs=8.5)
    arrow(ax, (L, 3.4), (X - 1.0, 1.4)); arrow(ax, (0.8, 2.35), (X - 1.8, 1.4))
    arrow(ax, (R, 1.9), (X + 1.0, 1.4))
    arrow(ax, (R + 1.25, 3.5), (X + 2.1, 1.1), rad=-0.3); ax.text(R + 1.35, 3.2, "no", fontsize=7.5)
    # loop back
    ax.plot([X + 2.1, 11.1, 11.1], [1.1, 1.1, 11.3], color=C["edge"], lw=1.0, ls="--")
    arrow(ax, (11.1, 11.3), (X + 2.1, 11.3), dashed=True)
    ax.text(11.25, 6.5, "wait 5 s,\nnext cycle", fontsize=8, ha="left", rotation=90, va="center")
    save(fig, "fig_4_5_activity_diagram_auction_cycle.png")


# ---------------------------------------------------------------- Fig 4.6
def fig_4_6():
    fig, ax = canvas(10, 5.2)
    ax.add_patch(Circle((0.35, 2.6), 0.17, fc=C["edge"]))
    box(ax, 2.0, 2.1, 2.4, 1.0, "OPEN_AUCTION", fc=C["dec"], fs=10, bold=True, r=0.25)
    box(ax, 6.2, 2.1, 2.4, 1.0, "EXECUTING", fc=C["comm"], fs=10, bold=True, r=0.25)
    ax.add_patch(Circle((9.5, 2.6), 0.2, fc="white", ec=C["edge"], lw=1.5))
    ax.add_patch(Circle((9.5, 2.6), 0.11, fc=C["edge"]))
    arrow(ax, (0.52, 2.6), (2.0, 2.6)); ax.text(1.25, 2.75, "dispatch_mission()", fontsize=7.5, ha="center")
    arrow(ax, (4.4, 2.95), (6.2, 2.95), text="≥ N eligible bidders\n/ lock best N", fs=7.5)
    arrow(ax, (6.2, 2.25), (4.4, 2.25), text="enclave < N\n(hand-off or chaos)", fs=7.5)
    arrow(ax, (2.6, 3.1), (3.6, 3.1), rad=-1.6)
    ax.text(3.1, 4.25, "< N bidders in range\n/ retry next cycle", ha="center", fontsize=7.5)
    arrow(ax, (7.0, 3.1), (7.9, 3.1), rad=-1.6)
    ax.text(7.45, 4.25, "member left footprint\n/ release, still ≥ N", ha="center", fontsize=7.5)
    arrow(ax, (8.6, 2.6), (9.3, 2.6))
    ax.text(8.95, 1.95, "mission ends\n/ release members", ha="center", fontsize=7.5)
    save(fig, "fig_4_6_state_diagram_mission.png")


if __name__ == "__main__":
    for f in (fig_4_1, fig_4_2, fig_4_3, fig_4_4, fig_4_5, fig_4_6):
        f()
