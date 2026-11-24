"""Builds materials/OrbitalNet_Demo_Tutorial.pdf — a plain-language guide to understanding, running and explaining
OrbitalNet OS. Result counts are read from research/results/ at build time (never typed by hand)."""
import json
import math
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "materials" / "OrbitalNet_Demo_Tutorial.pdf"
RES = ROOT / "research" / "results"
RED = colors.HexColor("#B00500")
INK = colors.HexColor("#1A1A1A")
GREY = colors.HexColor("#666666")
LIGHT = colors.HexColor("#F3F3F3")
TIP = colors.HexColor("#FFF6E5")
SAY = colors.HexColor("#EAF4EA")

ss = getSampleStyleSheet()
body = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14.2, textColor=INK,
                      spaceAfter=5)
h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=RED,
                    spaceBefore=6, spaceAfter=8)
h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=9,
                    spaceAfter=4)
small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11, textColor=GREY)
cell = ParagraphStyle("c", parent=body, fontSize=9, leading=12, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")
mono = ParagraphStyle("m", parent=cell, fontName="Courier", fontSize=8.8, leading=11.5)


def P(t, s=body):
    return Paragraph(t, s)


def bullets(items, numbered=False):
    return ListFlowable([ListItem(P(i), leftIndent=12) for i in items],
                        bulletType="1" if numbered else "bullet", start="1" if numbered else None,
                        bulletFontSize=9, leftIndent=14, bulletColor=RED)


def table(rows, widths, head=True):
    data = [[P(c, cellb if (r == 0 and head) else cell) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if head:
        style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("LINEABOVE", (0, 0), (-1, 0), 1.2, RED)]
    t.setStyle(TableStyle(style))
    return t


def box(title, text, bg):
    inner = [P(f"<b>{title}</b>", cell), P(text, cell)]
    t = Table([[inner]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LINEBEFORE", (0, 0), (0, -1), 2.5, RED)]))
    return KeepTogether([t, Spacer(1, 6)])


def say(text):
    return box("WHAT TO SAY", "&ldquo;" + text + "&rdquo;", SAY)


def tip(text, title="TIP"):
    return box(title, text, TIP)


def diagram():
    W, H = 170 * mm, 66 * mm
    d = Drawing(W, H)

    def b(x, y, w, h, t, sub="", hot=False):
        d.add(Rect(x, y, w, h, rx=3, ry=3, fillColor=RED if hot else LIGHT, strokeColor=RED, strokeWidth=0.8))
        d.add(String(x + w / 2, y + h / 2 + (2 if sub else -3), t, textAnchor="middle", fontName="Helvetica-Bold",
                     fontSize=9, fillColor=colors.white if hot else INK))
        if sub:
            d.add(String(x + w / 2, y + h / 2 - 9, sub, textAnchor="middle", fontName="Helvetica", fontSize=7.5,
                         fillColor=colors.white if hot else GREY))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=INK, strokeWidth=1))
        a = math.atan2(y2 - y1, x2 - x1)
        L = 5
        d.add(Polygon([x2, y2, x2 - L * math.cos(a - 0.4), y2 - L * math.sin(a - 0.4),
                       x2 - L * math.cos(a + 0.4), y2 - L * math.sin(a + 0.4)], fillColor=INK, strokeColor=INK))

    bw, bh = 120, 34
    cx = W / 2
    b(10, 140, bw, bh, "satellites.txt", "~10,000 real TLEs")
    b(10, 80, bw, bh, "physics_engine.py", "SGP4 orbits + telemetry")
    b(cx - 70, 80, 140, bh, "REDIS / MEMURAI", "shared keys = message bus", hot=True)
    b(W - 10 - bw, 80, bw, bh, "consensus_engine.py", "leaders, CNP auctions")
    b(60, 18, bw, bh, "streamer.py", "WebSocket :8765")
    b(W - 60 - bw, 18, bw, bh, "Streamlit console", "app.py :8501")
    arrow(70, 140, 70, 80 + bh)
    arrow(10 + bw, 97, cx - 70, 97)
    d.add(Line(W - 10 - bw, 103, cx + 70, 103, strokeColor=INK, strokeWidth=1))
    arrow(W - 10 - bw, 91, cx + 70, 91)
    arrow(cx + 70, 103, W - 10 - bw, 103)
    arrow(cx - 30, 80, 60 + bw / 2, 18 + bh)
    arrow(cx + 30, 80, W - 60 - bw / 2, 18 + bh)
    d.add(String(60 + bw / 2, 4, "-> index.html 3D globe (shown inside the console)", textAnchor="middle",
                 fontName="Helvetica", fontSize=7.5, fillColor=GREY))
    d.add(String(cx, 125, "every arrow is a Redis read or write — no process calls another directly",
                 textAnchor="middle", fontName="Helvetica-Oblique", fontSize=7.5, fillColor=GREY))
    return d


def hypothesis_counts():
    files = [("phase2/analysis_test.json", "verdict"), ("phase3/analysis_test.json", "overall_pass_all_seeds"),
             ("phase5/analysis_test_v2.json", "overall_pass_all_seeds"),
             ("phase6/analysis_test_v3.json", "overall_pass_all_seeds")]
    n_pass = n_all = 0
    for f, k in files:
        p = RES / f
        if p.exists():
            v = json.loads(p.read_text()).get(k, {})
            n_pass += sum(bool(x) for x in v.values())
            n_all += len(v)
    return n_pass, n_all


def n_satellites():
    lines = [l for l in (ROOT / "mission_control" / "data" / "satellites.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    return len(lines) // 3


N_SAT = n_satellites()
HP, HA = hypothesis_counts()
HYP_TEXT = (f"{HP} of {HA} preregistered hypotheses passed" if HA else
            "the hypothesis count is shown on the Evidence page")

S = []

# ── COVER ─────────────────────────────────────────────────────────────────────
S += [Spacer(1, 50),
      P("OrbitalNet OS", ParagraphStyle("t", parent=h1, fontSize=30, leading=36, alignment=TA_CENTER)),
      P("The complete demo &amp; understanding guide",
        ParagraphStyle("t2", parent=body, fontSize=14, leading=18, alignment=TA_CENTER, textColor=GREY)),
      Spacer(1, 24),
      P("Read this once end-to-end and you will be able to: run the demo, explain every file, answer the usual "
        "examiner questions, and recover if something breaks.", ParagraphStyle("c0", parent=body, alignment=TA_CENTER)),
      Spacer(1, 30),
      table([["#", "Section", "Read it when"],
             ["1", "The project in 60 seconds", "First — memorise the pitch"],
             ["2", "Key ideas in plain English", "To understand the jargon"],
             ["3", "Architecture: how the pieces fit", "To draw it on the whiteboard"],
             ["4", "File-by-file guide", "When asked &lsquo;what does this file do?&rsquo;"],
             ["5", "Life of one mission (step by step)", "To explain the core algorithm"],
             ["6", "The research side (Discovery)", "To explain the scientific contribution"],
             ["7", "Demo script: click-by-click", "Right before the demo"],
             ["8", "Troubleshooting", "When something breaks"],
             ["9", "Honest limitations", "So nothing catches you off guard"],
             ["10", "Examiner Q&amp;A", "To rehearse"],
             ["11", "One-page cheat sheet", "Print and keep next to the laptop"]],
            [10 * mm, 80 * mm, 80 * mm]),
      PageBreak()]

# ── 1. PITCH ──────────────────────────────────────────────────────────────────
S += [P("1. The project in 60 seconds", h1),
      P("<b>The problem.</b> Today most satellites are told what to do by a ground station, one command at a time. That "
        "is slow, it is a single point of failure, and when something unexpected happens in the sky the system can only "
        "label it as one of the things it already knows."),
      P("<b>Our idea.</b> Let the satellites organise themselves. OrbitalNet OS takes about "
        f"<b>{N_SAT:,} real satellites</b> (real orbit data), moves them with real orbital physics, and when a mission "
        "comes in (&lsquo;watch this cyclone&rsquo;) the satellites <b>bid for the job in an auction</b>. The best ones "
        "form a team (an <b>enclave</b>). As they fly out of view, the team hands the job over to new satellites "
        "automatically. If satellites fail, the swarm heals itself."),
      P("<b>The research part.</b> When a strange flash of light (a <b>transient</b>) appears in the sky, the system "
        "decides which satellite should look at it and when, to learn the most. Crucially, it keeps an extra option, "
        "<b>h0 = &lsquo;none of the known explanations&rsquo;</b>, so it can say <i>&lsquo;this is something new&rsquo;</i> "
        "instead of forcing a wrong label. This was tested on real astronomical data with hypotheses written down "
        f"<i>before</i> testing; {HYP_TEXT}."),
      say("OrbitalNet OS is a self-organising satellite constellation. It uses real orbit data, the satellites "
          "auction tasks among themselves instead of waiting for ground control, they hand off missions as they "
          "move and recover from failures, and on the research side the planner can recognise when an event in the "
          "sky matches none of the physics it knows."),
      P("Two layers to keep in your head", h2),
      table([["Layer", "Question it answers", "Where you see it"],
             ["Operations", "<i>Which satellites should do this Earth-observation job right now?</i>",
              "Orbital View, Mission Dispatch, Auction Internals"],
             ["Discovery (research)", "<i>What is this new event in the sky, and is it something unknown?</i>",
              "Event Lab, Evidence, Experiment Archive, Anomaly Watch"]],
            [35 * mm, 75 * mm, 60 * mm]),
      PageBreak()]

# ── 2. CONCEPTS ───────────────────────────────────────────────────────────────
S += [P("2. Key ideas in plain English", h1),
      table([["Term", "Simple explanation", "Where in the code"],
             ["TLE (Two-Line Element)", "A standard 2-line text format published by NORAD/CelesTrak describing a "
              "satellite's orbit. satellites.txt holds name + 2 lines for each satellite.", "satellites.txt"],
             ["SGP4", "The standard mathematical model that takes a TLE and a time and tells you where the satellite is. "
              "We use the official <font face='Courier'>sgp4</font> Python library.", "physics_engine.py"],
             ["ECI -> lat/lon", "SGP4 gives x,y,z in space (Earth-Centred Inertial). We rotate by Earth's spin (GMST) to "
              "get latitude/longitude on the map.", "eci_to_latlon()"],
             ["Telemetry", "Health data: battery (SoC), temperature margin, memory, etc. Here it is <b>simulated</b> by a "
              "mock hardware layer (HAL).", "hal_simulator.py"],
             ["Payload type", "What sensor the satellite carries: EO (camera), SAR (radar), SIGINT (signals), MW "
              "(weather), RELAY (comms).", "classify_satellite()"],
             ["Redis / Memurai", "An in-memory key-value database. Memurai is Redis for Windows. Every program reads and "
              "writes shared keys here instead of talking to each other directly.", "config.py"],
             ["Contract Net Protocol (CNP)", "A classic multi-agent protocol: a manager announces a task, agents bid, "
              "the best bids win the contract. Our satellites are the agents.", "consensus_engine.py"],
             ["Gatekeeper", "A yes/no filter before scoring: is the satellite free, does it have the right sensor, is it "
              "close enough? If not, it cannot bid.", "consensus_engine.py, scoring_engine.py"],
             ["Enclave", "The winning team of satellites working on one mission.", "MISSIONS_LEDGER"],
             ["Rolling enclave / hand-off", "Satellites move ~7.5 km/s, so they leave the target. Leavers are released "
              "and the auction re-opens to recruit replacements.", "consensus_engine.py"],
             ["Plane leader", "Satellites are grouped by orbital plane; the best-scoring one in each group is marked "
              "PLANE_LEAD.", "elect_plane_leaders()"],
             ["Chaos engineering", "Deliberately killing satellites to prove the system recovers.", "TRIGGER_CHAOS"],
             ["WebSocket", "A live, always-open connection between server and browser so the globe updates twice a "
              "second without reloading.", "streamer.py, index.html"],
             ["Three.js / WebGL", "JavaScript library for 3D graphics in the browser — draws the globe.", "index.html"],
             ["Streamlit", "Python library that turns a script into a web app. Our whole console is Streamlit.",
              "app.py, pages/, views/"],
             ["Transient", "A sky event that brightens and fades in days: kilonova, supernova, flare, GRB afterglow, "
              "tidal disruption event (TDE).", "research/transients/"],
             ["Light curve", "Brightness of the event over time. Its shape is the fingerprint of what it is.",
              "Event Lab chart"],
             ["Bayesian belief", "A probability for each possible explanation, updated after every measurement.",
              "research/inference/"],
             ["h0 (null hypothesis)", "&lsquo;None of my known models explains this.&rsquo; Modelled with a flexible "
              "Gaussian Process. If P(h0) gets high, the event is probably new.", "research/inference/openworld.py"],
             ["EIG (Expected Information Gain)", "How much a measurement is expected to reduce uncertainty. The planner "
              "picks the (time, satellite) with highest EIG.", "research/planners/"],
             ["Open-world vs closed-world", "Closed-world must pick one of the known classes. Open-world can also say "
              "&lsquo;unknown&rsquo; (h0).", "Strategy P vs B3"],
             ["Preregistration", "Writing hypotheses and pass/fail rules down <i>before</i> running the final test, so "
              "you can't cheat by moving goalposts.", "research/PREREGISTRATION*.md"],
             ["AUROC", "A 0–1 score of how well P(h0) separates unknown events from known ones (0.5 = guessing, 1 = "
              "perfect).", "Evidence page"]],
            [36 * mm, 98 * mm, 36 * mm]),
      PageBreak()]

# ── 3. ARCHITECTURE ───────────────────────────────────────────────────────────
S += [P("3. Architecture: how the pieces fit", h1),
      diagram(),
      P("Figure 1: Four independent programs share data through Redis.", ParagraphStyle("cap", parent=small,
                                                                                         alignment=TA_CENTER)),
      P("The one big design idea: Redis is the message bus", h2),
      P("The four programs never import or call each other. They only read and write <b>Redis keys</b>. That gives "
        "<b>loose coupling</b>: if the consensus engine crashes, the globe keeps moving; restart it and it carries on. "
        "This is the same idea used in real microservice systems."),
      table([["Redis key", "Written by", "Read by", "Holds"],
             ["STARLINK-&lt;id&gt; (one per satellite)", "physics engine (every 1 s), consensus engine (roles)",
              "consensus, streamer, console", "JSON: position, lat/lon, payload, telemetry, score, role"],
             ["MISSIONS_LEDGER (hash)", "Mission Dispatch page, consensus engine", "consensus, streamer, console",
              "Every mission: target, sensor, nodes needed, status (OPEN_AUCTION / EXECUTING), enclave"],
             ["AUCTION_LOGS (hash)", "consensus engine", "Auction Internals page",
              "Full bid table for each auction: distance, battery, score, WON/LOST"],
             ["TRIGGER_CHAOS", "Mission Dispatch (&lsquo;Simulate Node Jamming&rsquo;)", "consensus engine",
              "&lsquo;1&rsquo; = kill half of each enclave once"],
             ["CURRENT_MISSION", "Mission Dispatch", "streamer -> globe", "Target to lock the camera/lasers on"],
             ["TIME_MULTIPLIER / CHRONOS_MULTIPLIER", "Dispatch slider / (see Section 9)", "physics engine",
              "Simulation speed"]],
            [40 * mm, 42 * mm, 36 * mm, 52 * mm]),
      P("Start-up order (what DEMO.bat does)", h2),
      bullets(["<b>DEMO.bat</b> just runs <font face='Courier'>python demo.py</font>.",
               "demo.py checks Memurai is answering on 127.0.0.1:6379 (tries <font face='Courier'>net start Memurai</font> "
               "if not), warns if ports 8501/8765 are busy.",
               "Starts physics_engine.py, waits 2 s so satellites exist in Redis.",
               "Starts streamer.py (WebSocket on port 8765).",
               "Starts consensus_engine.py.",
               "Starts Streamlit app.py on port 8501 and opens your browser.",
               "Watches all four; Ctrl+C (or closing the window) shuts them all down cleanly."], numbered=True),
      tip("<font face='Courier'>boot_os.py</font> is the older launcher that does the same thing. "
          "Use <b>DEMO.bat</b> for the demo. <font face='Courier'>lambda_function.py</font>, "
          "<font face='Courier'>cloud_dashboard.py</font> and <font face='Courier'>TECHNICAL_SPEC.md</font> are the "
          "<b>old AWS version</b> (Lambda + SNS + DynamoDB) that was replaced by the local Redis design.",
          "GOOD TO KNOW"),
      PageBreak()]

# ── 4. FILES ──────────────────────────────────────────────────────────────────
S += [P("4. File-by-file guide", h1),
      P("Operations layer (the live system)", h2),
      table([["File", "What it does", "How it works (one breath)"],
             ["DEMO.bat / demo.py", "One-click launcher", "Checks Redis, starts the 4 processes in order, opens the "
              "browser, cleans up on Ctrl+C."],
             ["satellites.txt", f"Input data: {N_SAT:,} real satellites (Starlink)", "Name line + TLE line 1 + TLE line 2, "
              "repeated."],
             ["physics_engine.py", "The &lsquo;universe&rsquo;", "Loads every TLE into an sgp4 Satrec. Every second: "
              "advance sim clock, sgp4() -> x,y,z, convert to lat/lon, get telemetry from HAL, compute a health score, "
              "write all satellites to Redis in one pipeline."],
             ["hal_simulator.py", "Fake hardware sensors", "MockHAL per satellite: battery drains in the southern "
              "hemisphere (eclipse proxy) and charges in the north; memory fills and empties; groups values as "
              "P0_Gatekeepers, P1_Mission, P2/P3_Efficiency, P4_Maintenance."],
             ["scoring_engine.py", "Health/capability score maths", "Gatekeeper (battery &lt;15%, overheating, wheel "
              "saturation, uncalibrated, collision risk, already busy -> score 0), else weighted sum of telemetry, then "
              "risk decay C x e<super>-0.5R</super>. Has a self-test: <font face='Courier'>python scoring_engine.py</font>."],
             ["consensus_engine.py", "The brain: elections and auctions", "Every 5 s: read all satellites, elect plane "
              "leaders, then for each mission run the auction (OPEN_AUCTION) or maintain the enclave (EXECUTING). Full "
              "detail in Section 5."],
             ["scenario_engine.py", "Ready-made missions", "4 scripted scenarios (Sankalp piracy SAR, Amogha border "
              "SIGINT, Cyclone Bay of Bengal MW, Mumbai grid-down EO) and the chaos trigger."],
             ["streamer.py", "Live data pipe to the globe", "Async WebSocket server; every 0.5 s sends all satellites + "
              "missions as one JSON message to each connected browser."],
             ["index.html", "3D globe", "Three.js scene; connects to ws://localhost:8765, plots each satellite coloured "
              "by payload, green for active enclave, white for lead, lines to the target."],
             ["config.py", "Shared settings", "Constants + get_redis_client() so everybody connects the same way."],
             ["app.py", "The console shell", "Sets theme, shows Redis status in sidebar, defines the grouped navigation "
              "(Command / Operations / Discovery)."],
             ["ui/theme.py", "Look &amp; feel", "Carbon/red design system: hero banners, KPI tiles, labels."],
             ["views/overview.py", "Home screen", "Live counts from Redis every 4 s: satellites, executing missions, open "
              "auctions, logs, sim speed."],
             ["pages/1_visualization.py", "Orbital View page", "Reads index.html fresh each load (cache-bust comment) and "
              "embeds it."],
             ["pages/2_ground_station.py", "Mission Dispatch page", "Forms that write missions into MISSIONS_LEDGER, the "
              "scenario broadcaster, chaos button, mission list, purge."],
             ["pages/3_under_the_hood.py", "Auction Internals page", "4 tabs: Live Bidding Arena, Auction Ledger, Node Deep "
              "Scan, Fleet Statistics — all read from Redis."]],
            [36 * mm, 38 * mm, 96 * mm]),
      P("Discovery layer (research — never touches Redis)", h2),
      table([["Folder / file", "What it does"],
             ["research/orbitsim/", "Research copy of orbit maths: TLE loading, propagation, line-of-sight visibility, "
              "contact schedules."],
             ["research/transients/", "Light-curve models for each event class and the instrument noise model."],
             ["research/inference/", "Bayesian belief over known classes (bayes.py) and the Gaussian-Process h0 model "
              "(openworld.py)."],
             ["research/planners/", "The strategies: B0 fixed cadence, B1 nearest-capable (CNP-like), B2 classifier "
              "entropy, B3 closed-world EIG, P open-world EIG (ours), plus lookahead variants."],
             ["research/experiments/", "One script per phase; each takes --seed and --n-events and writes "
              "JSON/CSV to research/results/."],
             ["research/results/", "The only source of numbers. Pages and papers read from here; nothing hand-typed."],
             ["research/anomaly/", "Satellite anomaly track: maneuver detector (jumps in orbital elements) and "
              "fragmentation detector (bursts of new debris in the catalog), on real Space-Track data."],
             ["research/app/", "Event Lab logic, Evidence page, Experiment Archive viewer, Anomaly Watch page."],
             ["research/tests/", "pytest test suite: <font face='Courier'>pytest research/</font>."],
             ["research/PREREGISTRATION*.md", "Hypotheses and pass rules, committed before test seeds were run."]],
            [45 * mm, 125 * mm]),
      PageBreak()]

# ── 5. MISSION LIFE ───────────────────────────────────────────────────────────
S += [P("5. Life of one mission (step by step)", h1),
      P("Example: you dispatch <b>&lsquo;Cyclone Precognition&rsquo;</b> — 5 MW (weather) satellites needed over the "
        "Bay of Bengal (12.5&deg;N, 87.5&deg;E), radius 1200 km."),
      bullets([
          "<b>Request.</b> The Dispatch page writes a JSON entry into the Redis hash MISSIONS_LEDGER with status "
          "<b>OPEN_AUCTION</b>.",
          "<b>Snapshot.</b> Within 5 s the consensus engine reads every STARLINK-* key (all satellite states, freshly "
          "written by the physics engine).",
          "<b>Plane leaders.</b> Satellites are grouped by orbital plane (RAAN) and the highest current_score in each "
          "group becomes PLANE_LEAD.",
          "<b>Gatekeeper.</b> A satellite may bid only if: not already locked to a mission, carries the required "
          "sensor (MW), and its ground distance to the target (haversine formula) is &lt;= radius + 1000 km "
          "(1000 km margin because LEO satellites can tilt their sensor).",
          "<b>Bid score.</b> proximity = (max_distance &minus; distance) / max_distance, a 0–1 number; "
          "score = w<sub>prox</sub> &times; proximity + w<sub>battery</sub> &times; battery. Defaults 0.7 / 0.3, "
          "or the weights chosen on the Dispatch page.",
          "<b>Award.</b> Sort bids high to low. If at least N bidders exist, the top N win: they get role "
          "MISSION_ACTIVE and are locked; the mission becomes <b>EXECUTING</b> with the enclave list. If fewer than N "
          "are in range, it stays PENDING and retries every 5 s as satellites move in.",
          "<b>Forensics.</b> The full bid table (every bidder, distance, battery, score, WON/LOST) is saved to "
          "AUCTION_LOGS — this is what the Auction Ledger tab shows.",
          "<b>Rolling enclave.</b> Every 5 s each member is re-checked. Out of range -> unlocked, role back to MEMBER "
          "(&lsquo;[HANDOFF]&rsquo; in the console).",
          "<b>Chaos.</b> If TRIGGER_CHAOS is set, half of each enclave is killed at random (&lsquo;[CHAOS] EMP "
          "struck&rsquo;), then the trigger is cleared.",
          "<b>Self-healing.</b> If the enclave drops below N, the mission goes back to OPEN_AUCTION and the auction "
          "recruits fresh satellites — no human involved.",
          "<b>Display.</b> The streamer pushes all of this to the globe twice per second; satellites turn green and "
          "lines snap to the target."], numbered=True),
      say("Nobody assigns satellites by hand. The mission is just posted to a shared ledger. Satellites that "
          "physically can do it — right sensor, close enough, not busy — bid, and the score balances closeness against "
          "battery. The best N form an enclave. Because they're moving at seven and a half kilometres per second, the "
          "team constantly loses members, and the same auction automatically recruits replacements. Every decision "
          "is logged so you can audit why a satellite won."),
      P("Worked example of the score", h2),
      P("Radius 1200 km -> max distance 2200 km. Satellite A is 440 km away with 90% battery; satellite B is 220 km "
        "away with 40% battery. With weights 0.7 / 0.3:"),
      table([["", "Proximity", "Score"],
             ["A", "(2200 &minus; 440)/2200 = 0.80", "0.7&times;0.80 + 0.3&times;0.90 = <b>0.83</b>"],
             ["B", "(2200 &minus; 220)/2200 = 0.90", "0.7&times;0.90 + 0.3&times;0.40 = <b>0.75</b>"]],
            [20 * mm, 70 * mm, 80 * mm]),
      P("A wins even though B is closer, because B's battery is low. Raise the proximity weight and B would win — that "
        "is exactly what the weight sliders on Mission Dispatch demonstrate.", small),
      PageBreak()]

# ── 6. RESEARCH ───────────────────────────────────────────────────────────────
S += [P("6. The research side (Discovery)", h1),
      P("<b>The question:</b> a short-lived event appears in the sky. We have a small budget of measurements (e.g. 5) "
        "and each satellite can only see the event when it has line of sight. Which satellite should measure, and when, "
        "to identify the event fastest — <i>and</i> to notice if it's something we have no model for?"),
      P("How the open-world planner (strategy P) works", h2),
      bullets([
          "<b>Hypotheses:</b> K known classes (e.g. kilonova, shock cooling, GRB afterglow, stellar flare) <b>plus h0</b>.",
          "<b>Belief:</b> each known class is a light-curve template; h0 is a Gaussian Process, i.e. &lsquo;some smooth "
          "curve, shape unknown&rsquo;. After each measurement, Bayes' rule updates the probability of every option.",
          "<b>Choosing the next measurement:</b> for every feasible (time, satellite) pair — satellite must actually see "
          "the target, time must be in the future — compute expected information gain, and pick the best.",
          "<b>Mode switch:</b> if P(h0) &gt; 0.9 twice in a row, stop trying to classify and switch to &lsquo;keep "
          "watching it&rsquo; so the anomaly is preserved for follow-up.",
          "<b>Confidence rule:</b> only claim a class at &gt;= 95% probability; otherwise say &lsquo;not sure&rsquo;."]),
      P("Baselines it is compared against", h2),
      table([["Code", "Strategy", "Idea"],
             ["B0", "Fixed cadence", "Measure at regular times, no thinking"],
             ["B1", "Nearest capable (CNP-style)", "Whichever satellite is available/closest — like the ops layer"],
             ["B2", "Classifier entropy", "Measure when the classifier is most confused"],
             ["B3", "Closed-world EIG", "Same as ours but <b>without h0</b> — the key comparison"],
             ["P", "Open-world EIG (ours)", "EIG over known classes + h0"]],
            [15 * mm, 50 * mm, 105 * mm]),
      P("Scientific discipline (say this — examiners love it)", h2),
      bullets(["All strategies get <b>identical</b> events, orbits, budgets and noise for a given seed.",
               "Settings tuned on <b>validation seeds only</b>; hypotheses written in PREREGISTRATION files and committed "
               "<b>before</b> the test seeds were run.",
               "Every number comes from files in research/results/ generated by scripts — <b>nothing typed by hand</b>. "
               "Failed hypotheses are shown as failures.",
               "Phase 3 onwards uses <b>real ZTF Bright Transient Survey</b> light curves replayed against the <b>real "
               "Starlink fleet</b> with historical TLEs; some real classes (TDE, SLSN, SN Ibn) are hidden from the "
               "planner to act as genuine unknowns."]),
      P("Phases", h2),
      table([["Phase", "What was done"],
             ["1", "Existence proof: can an open-world planner recognise a class it was never told about?"],
             ["2", "Simulated transients, real orbits, 20 satellites; P vs B0–B3"],
             ["3", "Real ZTF transients, real fleet, withheld real classes as unknowns"],
             ["4–5", "Two colour bands (g + r); preregistration v2"],
             ["6", "Frozen final configuration (v3), re-tested"],
             ["C", "Conformal open-set calibration and lookahead planner"],
             ["Anomaly", "Maneuver + fragmentation detection on real Space-Track data (work in progress)"]],
            [22 * mm, 148 * mm]),
      P(f"<b>Result headline:</b> {HYP_TEXT} (counted live from research/results/ when this PDF was built). Open the "
        "<b>Evidence</b> page during the demo to show the exact PASS/FAIL matrix and AUROC values instead of quoting "
        "numbers from memory."),
      say("The difference between our planner and a normal one is one extra hypothesis: 'none of the above'. A normal "
          "planner is forced to call an unknown event a kilonova or a flare. Ours can say 'this matches nothing I know', "
          "and then switches to keeping it observed. We tested that honestly — hypotheses frozen before the test, real "
          "telescope data, and we show the failures too."),
      PageBreak()]

# ── 7. DEMO SCRIPT ────────────────────────────────────────────────────────────
S += [P("7. Demo script: click-by-click (8–10 minutes)", h1),
      P("Before the demo (do this 15 minutes early)", h2),
      bullets([
          "Memurai running: Windows key -> <font face='Courier'>services.msc</font> -> Memurai -> Start. "
          "(DEMO.bat also tries this.)",
          "Dependencies installed once: <font face='Courier'>pip install -r requirements.txt websockets plotly</font>",
          "Close any old demo window (ports 8501 / 8765 must be free).",
          "Double-click <b>DEMO.bat</b>. Wait for &lsquo;All systems online&rsquo; and the browser at "
          "http://localhost:8501.",
          "Do one test mission and press &lsquo;CANCEL ALL&rsquo;/&lsquo;Purge All Missions&rsquo; so you start clean "
          "but everything is warmed up.",
          "Keep the black console window visible on a second screen if possible — the [OK] / [HANDOFF] / [CHAOS] "
          "messages are great live proof."]),
      P("The run", h2),
      table([["Step", "Click", "Show", "Say"],
             ["1 (30 s)", "Overview", "Green &lsquo;All systems nominal&rsquo;, assets in orbit count",
              "Four independent programs talking only through Redis. These are real satellites propagated live with SGP4."],
             ["2 (1 min)", "Operations -> Orbital View", "Spin/zoom the globe; legend colours",
              "Each dot is a real satellite at its real position. Colour = sensor type. Updates twice a second over a "
              "WebSocket."],
             ["3 (2 min)", "Mission Dispatch -> pick a scenario (e.g. Cyclone) -> BROADCAST TACTICAL RFP",
              "Mission appears as OPEN_AUCTION, then EXECUTING within ~5 s",
              "I only posted the job. The satellites bid; nobody chose them."],
             ["4 (1 min)", "Back to Orbital View", "Green satellites + lines to target",
              "That's the enclave. Watch over time: members leave and are replaced — rolling hand-off."],
             ["5 (2 min)", "Auction Internals -> Auction Ledger, then Live Bidding Arena, Node Deep Scan",
              "Bid table: distance, battery, score, WON/LOST; one satellite's full telemetry",
              "Every decision is auditable. Here is why this satellite won and that one lost."],
             ["6 (1 min)", "Mission Dispatch -> Simulate Node Jamming",
              "Console shows [CHAOS], then [ALERT] re-opening auction; enclave refills",
              "I just killed half the team. The swarm detects it and re-auctions on its own — self-healing."],
             ["7 (2 min)", "Discovery -> Event Lab -> &lsquo;Kilonova&rsquo; -> Launch; then &lsquo;Mystery "
              "signal&rsquo; -> Launch", "Belief bars; known event identified, mystery ends in h0",
              "Same satellites, now doing science. For the mystery signal the system says 'none of my models' instead "
              "of guessing."],
             ["8 (1 min)", "Evidence", "PASS/FAIL matrix", "Preregistered, held-out, generated from result files, "
              "failures shown honestly."],
             ["(optional)", "Anomaly Watch", "Maneuver/fragmentation plots", "Extension on real Space-Track data; "
              "clearly marked work in progress."]],
            [16 * mm, 42 * mm, 50 * mm, 62 * mm]),
      tip("If you are short on time, do steps 1, 3, 4, 6, 7. Steps 3 + 6 (auction then self-healing) are the "
          "strongest proof of the core idea.", "IF SHORT ON TIME"),
      tip("Use the <b>pre-made scenarios</b> or a large radius (800–1500 km) and 2–3 nodes. A tiny radius with 5 nodes "
          "may sit in PENDING because not enough satellites of that sensor are overhead — that's correct behaviour, "
          "but it looks like nothing is happening. If it happens, say so: &lsquo;the gatekeeper is correctly refusing — "
          "not enough capable satellites in range yet.&rsquo;", "AVOID AN EMPTY AUCTION"),
      PageBreak()]

# ── 8. TROUBLESHOOTING ────────────────────────────────────────────────────────
S += [P("8. Troubleshooting", h1),
      table([["Symptom", "Cause", "Fix"],
             ["&lsquo;Memurai (Redis) is not running&rsquo;", "Redis service stopped",
              "services.msc -> Memurai -> Start, then run DEMO.bat again."],
             ["&lsquo;Port 8501/8765 already in use&rsquo;", "An old demo is still running",
              "Close the old window; or Task Manager -> end python.exe processes; rerun."],
             ["Sidebar says bus offline / Overview red", "Redis down or physics engine crashed",
              "Check the console for errors; restart DEMO.bat."],
             ["Globe is black / no satellites", "streamer.py not running or browser blocked the WebSocket",
              "Check console for &lsquo;Booting WebSocket Bridge&rsquo;; refresh the Orbital View page."],
             ["ModuleNotFoundError: websockets / plotly", "Not in requirements.txt",
              "<font face='Courier'>pip install websockets plotly</font>"],
             ["ModuleNotFoundError: sgp4 / redis / streamlit", "Dependencies not installed",
              "<font face='Courier'>pip install -r requirements.txt</font>"],
             ["Mission stuck at OPEN_AUCTION", "Not enough satellites with that sensor in range",
              "Increase radius, reduce nodes, or wait — satellites move into range."],
             ["Auction Internals tab looks empty", "No missions yet", "Dispatch a mission first; switch on Auto-refresh."],
             ["Weird characters (Ã°Å¸...) on a page", "File re-saved with wrong encoding", "Re-save as UTF-8 (see CLAUDE.md)."],
             ["Event Lab slow on first click", "Loads TLEs and computes visibility", "Wait a few seconds; it's normal."]],
            [45 * mm, 50 * mm, 75 * mm]),
      P("Useful commands", h2),
      table([["Command", "Purpose"],
             ["DEMO.bat  (or python demo.py)", "Run the whole demo"],
             ["python scoring_engine.py", "Run the scoring self-test (assert-based)"],
             ["pytest research/", "Run the research test suite"],
             ["python -m research.experiments.&lt;script&gt; --seed N --n-events M", "Re-run an experiment"]],
            [85 * mm, 85 * mm]),
      PageBreak()]

# ── 9. LIMITATIONS ────────────────────────────────────────────────────────────
S += [P("9. Honest limitations (know these before the examiner does)", h1),
      P("These were found by reading the current code. Saying them yourself, calmly, sounds far better than being "
        "caught out.", small),
      table([["Limitation", "What to say"],
             ["<b>Telemetry is simulated.</b> Battery, temperature, etc. come from MockHAL with random values; "
              "eclipse is approximated by &lsquo;southern hemisphere&rsquo;.",
              "Orbits are real; health data is a stand-in for real spacecraft telemetry, which isn't public."],
             ["<b>Sensor types are assigned.</b> The dataset is all Starlink (comms satellites), so EO/SAR/SIGINT/MW "
              "roles are given by a deterministic hash of the name.",
              "We needed a mixed fleet to demonstrate sensor-aware auctions; the classifier also supports real names "
              "(Sentinel, Landsat, NOAA...)."],
             ["<b>Speed slider vs physics.</b> The Dispatch slider writes TIME_MULTIPLIER, but physics_engine.py reads "
              "CHRONOS_MULTIPLIER, so in the current code the slider does not actually change orbit speed.",
              "Avoid demonstrating the slider, or fix it first (one-line key rename)."],
             ["<b>Plane grouping.</b> The mock RAAN value is constant, so all satellites fall into one &lsquo;plane&rsquo; "
              "and one leader is elected.", "Leader election logic is in place; feeding real RAAN from the TLE is the "
              "next step."],
             ["<b>Centralised simulation of a decentralised idea.</b> The auction runs inside one process, not on each "
              "satellite.", "It simulates the protocol; the Redis decoupling is how it would be split onto separate "
              "nodes."],
             ["<b>Distance is ground distance</b> (haversine), not true line-of-sight with elevation angle (the "
              "research layer does use real visibility geometry).", "A simplification for real-time speed with "
              "~10,000 satellites."],
             ["<b>Anomaly track is work in progress</b>; thresholds not frozen, held-out window not run.",
              "It's clearly labelled that way on the page."]],
            [90 * mm, 80 * mm]),
      PageBreak()]

# ── 10. Q&A ───────────────────────────────────────────────────────────────────
QA = [
    ("Why Redis and not direct function calls?",
     "Loose coupling and fault tolerance. Each process can crash and restart independently, and they could run on "
     "different machines. Redis is in-memory, so it's fast enough for ~10,000 satellites per second."),
    ("Why did you move away from AWS?",
     "The earlier version used Lambda, SNS and DynamoDB. It had cost, latency and couldn't stream thousands of "
     "satellites in real time. The local Redis design is free, fast and runs offline."),
    ("What is SGP4 and why use it?",
     "The standard model NORAD uses with TLE data. It accounts for Earth's oblateness and atmospheric drag, so "
     "positions match reality — using anything else with TLEs would be wrong."),
    ("How is the winner chosen?",
     "Gatekeeper first (free, right sensor, in range), then score = w1 x proximity + w2 x battery, both normalised to "
     "0–1 so the weights are meaningful. Top N win."),
    ("Why normalise proximity?",
     "Earlier, raw distance could reach about 18 while battery maxed at 1, so the weights had no effect. Dividing by "
     "the maximum view distance puts both on the same 0–1 scale."),
    ("What happens if a satellite fails mid-mission?",
     "The enclave is re-checked every 5 s; if it drops below the required size, the mission goes back to auction and "
     "new satellites are recruited automatically. The jamming button demonstrates this."),
    ("What is the Contract Net Protocol?",
     "A 1980 multi-agent protocol (Smith): announce task, receive bids, award contract. It's a natural fit because "
     "satellites have different capabilities and positions."),
    ("What is h0 and why does it matter?",
     "The 'none of the above' hypothesis, modelled with a Gaussian Process. Without it, every unknown event gets "
     "forced into a known class, often with high confidence — a confident wrong answer."),
    ("What is expected information gain?",
     "How much a measurement is expected to reduce uncertainty about which hypothesis is true. We pick the satellite "
     "and time with the highest value."),
    ("How do we know the results aren't cherry-picked?",
     "Hypotheses were preregistered and committed before running test seeds, tuning only used validation seeds, all "
     "strategies saw identical inputs, and every number is generated from result files. Failures are reported."),
    ("Is the data real?",
     "Orbits: real TLEs. Research: real ZTF light curves, real Starlink fleet, real Space-Track history for anomalies. "
     "Satellite health telemetry in the ops demo is simulated."),
    ("What would you do next?",
     "Real RAAN-based planes, true elevation-angle visibility in the ops layer, running agents on separate nodes, "
     "freezing and testing the anomaly detectors, and connecting the Discovery planner to the live dispatch."),
    ("Does it scale?",
     f"The physics engine propagates all {N_SAT:,} satellites every second and writes them in one Redis pipeline; the "
     "globe renders them all in WebGL."),
]
S += [P("10. Examiner Q&amp;A", h1)]
for q, a in QA:
    S += [KeepTogether([P(f"<b>Q. {q}</b>", ParagraphStyle("q", parent=body, textColor=RED, spaceAfter=1)),
                        P(f"A. {a}")])]
S += [PageBreak()]

# ── 11. CHEAT SHEET ───────────────────────────────────────────────────────────
S += [P("11. One-page cheat sheet", h1),
      table([["Pitch", "Self-organising satellite constellation: real orbits, satellites auction tasks (CNP), "
                       "rolling hand-offs and self-healing; open-world planner can say &lsquo;unknown&rsquo; (h0)."],
             ["Run", "Memurai on -> double-click DEMO.bat -> http://localhost:8501 -> Ctrl+C to stop"],
             ["4 processes", "physics_engine (SGP4, 1 Hz) · streamer (WebSocket :8765, 2 Hz) · consensus_engine "
                             "(auctions, every 5 s) · Streamlit app (:8501)"],
             ["Glue", "Redis keys only: STARLINK-&lt;id&gt;, MISSIONS_LEDGER, AUCTION_LOGS, TRIGGER_CHAOS, "
                      "CURRENT_MISSION"],
             ["Auction", "Gatekeeper (free + right sensor + within radius+1000 km) -> score = 0.7·prox + 0.3·battery "
                         "-> top N = enclave -> EXECUTING"],
             ["Maintenance", "Every 5 s: drop out-of-range members, chaos kills half, below N -> re-auction"],
             ["Health score", "Gatekeepers -> weighted sum -> &times; e<super>-0.5&middot;risk</super> "
                              "(scoring_engine.py)"],
             ["Sensors", "EO camera · SAR radar · SIGINT signals · MW weather · RELAY comms"],
             ["Globe colours", "Purple SAR · Blue EO · Yellow SIGINT · Orange MW · Grey RELAY · Green ACTIVE · White LEAD"],
             ["Research", "Strategy P = EIG over known classes + h0 (Gaussian Process). Baselines B0 cadence, B1 "
                          "nearest, B2 entropy, B3 closed-world EIG."],
             ["Rigor", "Preregistered · validation vs test seeds · identical inputs · numbers only from research/results/"],
             ["Result", HYP_TEXT + " — show the Evidence page."],
             ["Demo order", "Overview -> Orbital View -> Dispatch scenario -> globe -> Auction Ledger -> Jamming -> Event "
                            "Lab (Kilonova, Mystery) -> Evidence"],
             ["Don't", "Don't demo the speed slider (see Section 9). Don't use tiny radius + 5 nodes."]],
            [30 * mm, 140 * mm], head=False)]


def footer(c, doc):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawString(20 * mm, 10 * mm, "OrbitalNet OS — Demo & Understanding Guide")
    c.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
    c.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm,
                        bottomMargin=18 * mm, title="OrbitalNet OS — Demo & Understanding Guide")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print(f"Wrote {OUT}  (satellites={N_SAT}, hypotheses={HP}/{HA})")
