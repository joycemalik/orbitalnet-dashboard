"""Builds materials/CIE_Writeup_OrbitalNet.pdf (Major Project Phase-II CIE write-up)."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

OUT = "materials/CIE_Writeup_OrbitalNet.pdf"
RED = colors.HexColor("#B00500")
INK = colors.HexColor("#1A1A1A")
GREY = colors.HexColor("#666666")
LIGHT = colors.HexColor("#F3F3F3")

ss = getSampleStyleSheet()
body = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14.2, textColor=INK,
                      alignment=TA_JUSTIFY, spaceAfter=5)
h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=13.5, leading=17, textColor=RED,
                    spaceBefore=12, spaceAfter=6, alignment=0)
h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=8, spaceAfter=4,
                    alignment=0)
small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11, textColor=GREY)
cell = ParagraphStyle("c", parent=body, fontSize=9, leading=12, alignment=0, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")


def P(t, s=body):
    return Paragraph(t, s)


def bullets(items, numbered=False):
    return ListFlowable([ListItem(P(i), leftIndent=12) for i in items],
                        bulletType="1" if numbered else "bullet", start="1" if numbered else None,
                        bulletFontSize=9, leftIndent=14, bulletColor=RED)


def table(rows, widths):
    data = [[P(c, cellb if r == 0 else cell) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LINEABOVE", (0, 0), (-1, 0), 1.2, RED)]))
    return t


from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String


def diagram():
    W, H = 170 * mm, 62 * mm
    d = Drawing(W, H)

    def box(x, y, w, h, t, sub="", hot=False):
        d.add(Rect(x, y, w, h, rx=3, ry=3, fillColor=RED if hot else LIGHT, strokeColor=RED, strokeWidth=0.8))
        d.add(String(x + w / 2, y + h / 2 + (2 if sub else -3), t, textAnchor="middle", fontName="Helvetica-Bold",
                     fontSize=9, fillColor=colors.white if hot else INK))
        if sub:
            d.add(String(x + w / 2, y + h / 2 - 9, sub, textAnchor="middle", fontName="Helvetica", fontSize=7.5,
                         fillColor=colors.white if hot else GREY))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=INK, strokeWidth=1))
        import math
        a = math.atan2(y2 - y1, x2 - x1); L = 5
        d.add(Polygon([x2, y2, x2 - L * math.cos(a - 0.4), y2 - L * math.sin(a - 0.4),
                       x2 - L * math.cos(a + 0.4), y2 - L * math.sin(a + 0.4)], fillColor=INK, strokeColor=INK))

    bw, bh = 120, 34
    cx = W / 2
    box(10, 120, bw, bh, "Physics engine", "SGP4 orbits, telemetry")
    box(cx - 70, 120, 140, bh, "REDIS BUS", "shared keys, no direct calls", hot=True)
    box(W - 10 - bw, 120, bw, bh, "Consensus engine", "leaders, CNP auctions")
    box(60, 55, bw, bh, "Streamer", "WebSocket :8765")
    box(W - 60 - bw, 55, bw, bh, "Streamlit console", "ops + Event Lab")
    box(60, 2, bw, bh, "3D WebGL globe", "Three.js")
    arrow(10 + bw, 137, cx - 70, 137)
    arrow(W - 10 - bw, 137, cx + 70, 137)
    arrow(cx - 40, 120, 60 + bw / 2, 55 + bh)
    arrow(cx + 40, 120, W - 60 - bw / 2, 55 + bh)
    arrow(60 + bw / 2, 55, 60 + bw / 2, 2 + bh)
    return d


S = []
S += [P("Dr. Ambedkar Institute of Technology", ParagraphStyle("i", parent=body, alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=12)),
      P("Department of Computer Science and Engineering · Major Project Phase-II CIE Write-up",
        ParagraphStyle("i2", parent=small, alignment=TA_CENTER)),
      Spacer(1, 10)]

S += [P("1. Project Title", h1),
      P("<b>OrbitalNet OS: An Autonomous Satellite Constellation for Task Allocation and Open-World Discovery of "
        "Space Transients</b>"),
      P("Note: verify the title with the project coordinator; if the registered title differs (e.g. "
        "“Hypothesis-Discriminating Observation Campaigns for Distributed Space Observatories”), use the "
        "registered one.", small)]

S += [P("2. Abstract", h1), P(
    "Satellite constellations are increasingly used for Earth observation and astronomy, but most still rely on "
    "centralized ground control, which is slow, a single point of failure, and blind to events its models do not "
    "describe. This project presents <b>OrbitalNet OS</b>, a fully local, fault-tolerant simulation platform in which a "
    "constellation built from <b>real satellite orbit data (TLEs)</b> organizes itself. In the <b>operations layer</b>, "
    "satellites are propagated with the <b>SGP4</b> model, elect orbital-plane leaders, and compete for ground-tasking "
    "missions through a <b>Contract Net Protocol (CNP) auction</b>; winners form “rolling enclaves” that hand "
    "a target over as they pass overhead. In the <b>discovery layer</b>, an <b>open-world sequential measurement "
    "planner</b> decides which satellite should observe a fading transient, and when, to learn the most about it. Its "
    "belief covers known physical classes plus an explicit <b>null hypothesis h0 (“none of the known "
    "models”)</b>, so the system can report that an event is new instead of forcing a wrong label. All components "
    "communicate only through a <b>Redis message bus</b>, so any process can crash and restart independently; a live "
    "<b>3D WebGL globe</b> and an interactive <b>Streamlit console</b> show the system working. Evaluated on <b>real "
    "ZTF Bright Transient Survey light curves</b> against the <b>real Starlink fleet</b>, with hypotheses preregistered "
    "before testing, <b>11 of 16 preregistered hypotheses passed</b>. In the final configuration P(h0) separated "
    "unknown from known events with an <b>AUROC of about 0.81</b> and made substantially fewer confident-but-wrong "
    "calls on unknown events than a closed-world planner.")]

S += [P("3. Objectives", h1), bullets([
    "Simulate a realistic constellation by propagating real TLE data with SGP4 and generating live telemetry "
    "(position, battery, payload, health).",
    "Design a <b>decentralized task-allocation mechanism</b>: plane-leader election, CNP auctions scored on proximity, "
    "battery and capability, and rolling enclaves that survive satellites moving out of view.",
    "Build a <b>fault-tolerant, loosely coupled architecture</b> in which components communicate only through Redis.",
    "Develop an <b>open-world measurement planner</b> that selects observations by expected information gain and keeps "
    "an explicit null hypothesis h0 to detect phenomena outside its models.",
    "<b>Validate scientifically</b> on real astronomical data (ZTF) and the real Starlink fleet, with preregistered "
    "hypotheses, held-out test seeds and baselines B0–B3.",
    "Extend the work to <b>satellite anomaly detection</b> (maneuvers and fragmentations) using real Space-Track history.",
    "Provide a <b>one-click interactive demonstration</b>: 3D globe, mission dispatch, auction forensics and an Event Lab "
    "where a user injects their own space event."], numbered=True)]

S += [P("4. Methodology and Implementation", h1), P("4.1 System architecture", h2),
      table([["Component", "Role"],
             ["physics_engine.py", "Propagates satellites from satellites.txt with SGP4; writes state to Redis every tick"],
             ["consensus_engine.py", "Elects plane leaders, runs CNP auctions, forms and rolls enclaves, logs every auction"],
             ["streamer.py", "WebSocket server (port 8765) streaming live state to the globe"],
             ["index.html", "Three.js 3D globe: satellites, enclave links, mission status"],
             ["Streamlit console (app.py)", "Overview, Mission Dispatch, Auction Internals, Event Lab, Evidence, Anomaly Watch"],
             ["demo.py / DEMO.bat", "One-click launcher that starts everything and shuts it down cleanly"]],
            [48 * mm, 122 * mm]),
      Spacer(1, 5),
      P("<b>Redis as the integration bus.</b> No component calls another directly; they share keys such as "
        "STARLINK-&lt;id&gt;, MISSIONS_LEDGER, AUCTION_LOGS and TIME_MULTIPLIER. Any process can fail and restart "
        "without bringing down the system. <b>Migration from cloud:</b> an earlier version ran on AWS (Lambda, SNS, "
        "DynamoDB); it was redesigned to run fully locally, removing cloud cost and latency and allowing thousands of "
        "satellites in real time."),
      diagram(),
      P("Figure 1: Block diagram of OrbitalNet OS.", ParagraphStyle("cap", parent=small, alignment=TA_CENTER)),

      P("4.2 Orbit simulation", h2), bullets([
          "Real two-line element sets are parsed with Satrec.twoline2rv and propagated with SGP4 to ECI coordinates, "
          "then converted to latitude and longitude.",
          "A time-warp (“Chronos”) multiplier from 1× to 7200× accelerates the simulation.",
          "hal_simulator.py generates battery, payload-type and health telemetry for each satellite."]),

      P("4.3 Decentralized task allocation (Contract Net Protocol)", h2), bullets([
          "<b>Gatekeeper filter:</b> a satellite may bid only if it is free, carries the required sensor (SAR, EO, ...) "
          "and is within range of the target zone (haversine distance).",
          "<b>Scoring:</b> score = w<sub>1</sub>·(normalized proximity) + w<sub>2</sub>·(battery state of "
          "charge); weights live in Redis (SCORING_WEIGHTS), with capability and risk-decay terms in scoring_engine.py.",
          "<b>Award:</b> the top-N bidders form an enclave.",
          "<b>Rolling enclave:</b> members are re-checked every tick; a satellite leaving range is dropped and the "
          "auction reopens to replace it.",
          "<b>Forensics:</b> every bid, score and decision is logged to AUCTION_LOGS and shown on the Auction Internals page.",
          "<b>Chaos engineering:</b> satellites can be deliberately failed (TRIGGER_CHAOS) to show recovery."],
          numbered=True),

      P("4.4 Open-world measurement planner (research core)", h2),
      P("<b>Problem.</b> A short-lived transient appears in the sky. Each satellite can observe it only when it has line "
        "of sight, and the budget is limited (5 measurements). The goal is to identify the event as fast as possible "
        "— or to recognize that it is unknown."),
      bullets([
          "<b>Hypotheses:</b> K known classes plus h0. Simulation: kilonova, shock cooling, GRB afterglow, stellar flare. "
          "Real data: SN Ia, SN II, SN Ibc.",
          "<b>Bayesian belief:</b> each known class is a light-curve template with amplitude marginalized over a grid; h0 "
          "is a Gaussian Process (a flexible “anything” model). The posterior spans all K+1 hypotheses.",
          "<b>Utility</b> for each candidate (time, satellite): U = I(class) + <i>beta</i> x I(adequacy) + <i>gamma</i> x D(decay). "
          "The planner picks the highest-utility feasible observation (visible, strictly forward in time).",
          "<b>Preservation mode:</b> if P(h0) &gt; 0.9 for two consecutive steps, the planner switches from identifying "
          "to covering the event, keeping the anomaly observed for follow-up.",
          "<b>Confidence rule:</b> a class is claimed only at posterior ≥ 95%; otherwise the system reports uncertainty.",
          "<b>Baselines:</b> B0 fixed cadence; B1 CNP nearest-capable dispatch; B2 classifier entropy; B3 closed-world "
          "information gain (no h0).",
          "<b>Discipline:</b> tuning on validation seeds only; hypotheses preregistered before test seeds were run; all "
          "strategies get identical events, orbits and noise per seed; every reported number is generated from result "
          "files, never hand-edited."]),

      P("4.5 Phases carried out", h2),
      table([["Phase", "Work done"],
             ["Phase 1", "Existence proof: an open-world planner can recognize a withheld class"],
             ["Phase 2", "Simulated transients, real Starlink orbits, 20 satellites; planner vs baselines B0–B3"],
             ["Phase 3", "Real ZTF transients replayed against the real fleet (historical TLEs); TDE, SLSN and SN Ibn "
                         "withheld as real unknowns"],
             ["Phases 4–5", "Two-band (g + r) observations, preregistration v2"],
             ["Phase 6", "Frozen final configuration (v3), re-evaluated on test seeds"],
             ["Phase C", "Conformal open-set calibration and a lookahead planner"],
             ["Anomaly track", "Maneuver and fragmentation detection from Space-Track history (in progress)"]],
            [32 * mm, 138 * mm]),

      P("4.6 Satellite anomaly detection (extension)", h2), bullets([
          "<b>Maneuver detector:</b> step detection in orbital elements with removal of isolated bad element sets, "
          "gap-scaled thresholds and geomagnetic-storm tagging (Kp ≥ 6); validated against sourced known maneuvers "
          "(e.g. ISS and Cygnus NG-17 reboosts) and 414 derelict objects as false-alarm negatives.",
          "<b>Fragmentation detector:</b> NORAD catalog order reveals bursts of debris from one launch; 49 bursts found in "
          "2021–2024, including NOAA-17, the Cosmos 1408 ASAT test and the CZ-6A breakup."]),

      P("4.7 Tools and technologies", h2),
      P("Python 3.13, sgp4, NumPy, SciPy, Redis/Memurai, Streamlit, Plotly, Three.js/WebGL, WebSockets, pytest (82 tests). "
        "Data: CelesTrak/Space-Track TLEs, ZTF Bright Transient Survey, GFZ Kp indices.")]

S += [P("5. Results and Conclusion", h1), P("5.1 Results (from research/results/)", h2), bullets([
    "<b>Phase 2 (simulated):</b> the open-world planner identified <b>98.8%</b> of known-class events with a median time "
    "of about <b>0.96 days</b>; the fixed-cadence baseline identified 48.4%.",
    "<b>Real-data replay (Phases 3, 5, 6):</b> AUROC of P(h0) for separating unknown from known events rose from "
    "<b>0.63</b> (Phase 3) to <b>0.81</b> (Phase 6, 95% CI 0.76–0.86). In Phase 6, confident-wrong calls on unknown "
    "events were about <b>49 percentage points lower</b> than the closed-world planner B3.",
    "<b>Overall: 11 of 16 preregistered hypotheses passed, 5 failed</b> — Phase 2 H1 (time to identification), "
    "Phase 3 and Phase 5 H3 (extra errors on known events), Phases 5–6 H5 (accuracy non-inferiority). Failures are "
    "reported openly.",
    "<b>Anomaly detector (validation window):</b> recalled <b>7 of 7</b> sourced known maneuvers at about <b>0.06 false "
    "alarms per object-year</b> outside storm days."]),
      table([["Phase", "H1", "H2", "H3", "H4", "H5"],
             ["Phase 2", "FAIL", "PASS", "PASS", "—", "—"],
             ["Phase 3", "PASS", "PASS", "FAIL", "—", "—"],
             ["Phase 5", "PASS", "PASS", "FAIL", "PASS", "FAIL"],
             ["Phase 6", "PASS", "PASS", "PASS", "PASS", "FAIL"]],
            [40 * mm] + [26 * mm] * 5),
      P("Table: Preregistered hypothesis outcomes on held-out test seeds (11/16 passed).",
        ParagraphStyle("cap2", parent=small, alignment=TA_CENTER)),
      P("5.2 Conclusion", h2),
      P("OrbitalNet OS shows that a satellite constellation built from real orbit data can <b>allocate tasks among its "
        "own satellites through auctions without central control</b>, and that it <b>tolerates failures</b> thanks to the "
        "Redis-based design. More importantly, it shows that <b>keeping an explicit null hypothesis</b> lets a "
        "constellation <b>recognize when an event matches none of its known physics</b>, where a closed-world system "
        "would confidently mislabel it. The results come from real astronomical data, real orbits and preregistered "
        "tests, and the honest reporting of failed hypotheses points directly to future work."),
      P("<b>Future work:</b> freeze the anomaly-detection thresholds and run the held-out window; improve accuracy on "
        "known classes; run the planner on-board, on real hardware.")]

S += [P("6. Outcome of the Project", h1), bullets([
    "A working <b>one-click system</b> (DEMO.bat): live 3D globe, mission dispatch, auction forensics, and an interactive "
    "<b>Event Lab</b> where any user can inject a space event and watch the system classify it or flag "
    "“unmodeled phenomenon spotted”.",
    "A <b>reproducible research framework</b>: preregistered hypotheses, 82 automated tests, results generated only from data.",
    "<b>Publication:</b> a short research note has been prepared from these results in the format of <i>Research Notes "
    "of the AAS</i> (status: ______________________). Poster / exhibition: ______________________."])]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                        bottomMargin=18 * mm, title="OrbitalNet OS — CIE Write-up", author="")


def footer(c, d):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawString(20 * mm, 10 * mm, "OrbitalNet OS · Major Project Phase-II CIE")
    c.drawRightString(190 * mm, 10 * mm, f"Page {d.page}")
    c.setStrokeColor(RED)
    c.setLineWidth(1.2)
    c.line(20 * mm, 287 * mm, 190 * mm, 287 * mm)
    c.restoreState()


doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("wrote", OUT)
