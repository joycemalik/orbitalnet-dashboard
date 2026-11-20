"""Builds docs/OrbitalNet_Handout.pdf — a one-page illustrated project handout.
Result counts are read from research/results/ at build time (never typed by hand)."""
import json
import math
from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "OrbitalNet_Handout.pdf"
RES = ROOT / "research" / "results"
RED, INK, GREY, LIGHT = (colors.HexColor(c) for c in ("#B00500", "#1A1A1A", "#666666", "#F3F3F3"))
BLUE, GREEN, AMBER, PURPLE = (colors.HexColor(c) for c in ("#2F6DB5", "#2E8B57", "#D98E04", "#7A3FB0"))
W, H = A4
M = 14 * mm


def counts():
    n_sat = len([l for l in (ROOT / "satellites.txt").read_text(encoding="utf-8").splitlines() if l.strip()]) // 3
    hp = ha = 0
    for f, k in [("phase2/analysis_test.json", "verdict"), ("phase3/analysis_test.json", "overall_pass_all_seeds"),
                 ("phase5/analysis_test_v2.json", "overall_pass_all_seeds"),
                 ("phase6/analysis_test_v3.json", "overall_pass_all_seeds")]:
        p = RES / f
        if p.exists():
            v = json.loads(p.read_text()).get(k, {})
            hp += sum(bool(x) for x in v.values()); ha += len(v)
    return n_sat, hp, ha


def wrap(c, text, x, y, width, font="Helvetica", size=8.6, leading=11, color=INK):
    c.setFont(font, size); c.setFillColor(color)
    for para in text.split("\n"):
        line = ""
        for w in para.split():
            t = (line + " " + w).strip()
            if c.stringWidth(t, font, size) > width:
                c.drawString(x, y, line); y -= leading; line = w
            else:
                line = t
        c.drawString(x, y, line); y -= leading
    return y


def heading(c, x, y, num, text):
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 8); c.drawString(x, y, num)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 10.5); c.drawString(x + 16, y, text)
    c.setStrokeColor(RED); c.setLineWidth(0.8); c.line(x, y - 3, x + 22, y - 3)
    return y - 15


def box(c, x, y, w, h, title, sub, hot=False, edge=RED):
    c.setFillColor(RED if hot else LIGHT); c.setStrokeColor(edge); c.setLineWidth(0.9)
    c.roundRect(x, y, w, h, 4, fill=1, stroke=1)
    c.setFillColor(colors.white if hot else INK); c.setFont("Helvetica-Bold", 8.2)
    c.drawCentredString(x + w / 2, y + h / 2 + 1.5, title)
    c.setFillColor(colors.white if hot else GREY); c.setFont("Helvetica", 6.6)
    c.drawCentredString(x + w / 2, y + h / 2 - 7.5, sub)


def arrow(c, x1, y1, x2, y2):
    c.setStrokeColor(INK); c.setFillColor(INK); c.setLineWidth(0.9); c.line(x1, y1, x2, y2)
    a = math.atan2(y2 - y1, x2 - x1); L = 4.5
    p = c.beginPath(); p.moveTo(x2, y2)
    p.lineTo(x2 - L * math.cos(a - 0.4), y2 - L * math.sin(a - 0.4))
    p.lineTo(x2 - L * math.cos(a + 0.4), y2 - L * math.sin(a + 0.4)); p.close()
    c.drawPath(p, fill=1, stroke=0)


def main():
    n_sat, hp, ha = counts()
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("OrbitalNet OS — Project Handout")

    # ── header band ──
    c.setFillColor(INK); c.rect(0, H - 34 * mm, W, 34 * mm, fill=1, stroke=0)
    c.setFillColor(RED); c.rect(0, H - 34 * mm, 5 * mm, 34 * mm, fill=1, stroke=0)
    # orbit motif
    cx, cy = W - 32 * mm, H - 17 * mm
    c.setStrokeColor(colors.HexColor("#555555")); c.setLineWidth(0.6)
    for r in (9, 14, 19):
        c.ellipse(cx - r * mm, cy - r * 0.45 * mm, cx + r * mm, cy + r * 0.45 * mm, stroke=1, fill=0)
    c.setFillColor(colors.HexColor("#2F6DB5")); c.circle(cx, cy, 5 * mm, fill=1, stroke=0)
    for ang, r, col in [(20, 9, GREEN), (150, 14, AMBER), (250, 19, RED), (320, 14, colors.white)]:
        a = math.radians(ang)
        c.setFillColor(col); c.circle(cx + r * mm * math.cos(a), cy + r * 0.45 * mm * math.sin(a), 1.3 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 22); c.drawString(M + 2 * mm, H - 15 * mm, "OrbitalNet OS")
    c.setFont("Helvetica", 10.5)
    c.drawString(M + 2 * mm, H - 21.5 * mm, "A self-organising satellite constellation that can say “this is something new”")
    c.setFillColor(colors.HexColor("#BBBBBB")); c.setFont("Helvetica", 7.8)
    c.drawString(M + 2 * mm, H - 28 * mm, "Joyce Malik · Anup H · Moghitha B · Swathi Satish  —  Dept. of CSE, "
                 "Dr. Ambedkar Institute of Technology, Bengaluru")

    # ── KPI strip ──
    y0 = H - 50 * mm
    kpis = [(f"{n_sat:,}", "real satellites (TLE)"), ("SGP4", "orbit physics, 1 Hz"),
            ("4", "independent services"), (f"{hp}/{ha}" if ha else "—", "preregistered hypotheses passed")]
    kw = (W - 2 * M - 3 * 4 * mm) / 4
    for i, (v, l) in enumerate(kpis):
        x = M + i * (kw + 4 * mm)
        c.setFillColor(LIGHT); c.roundRect(x, y0, kw, 13 * mm, 3, fill=1, stroke=0)
        c.setFillColor(RED); c.rect(x, y0, 1.2 * mm, 13 * mm, fill=1, stroke=0)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 14); c.drawString(x + 4 * mm, y0 + 6 * mm, v)
        c.setFillColor(GREY); c.setFont("Helvetica", 7.2); c.drawString(x + 4 * mm, y0 + 2.2 * mm, l)

    colw = (W - 2 * M - 8 * mm) / 2
    L, R = M, M + colw + 8 * mm

    # ── left: problem + idea ──
    y = y0 - 9 * mm
    y = heading(c, L, y, "01", "The problem")
    y = wrap(c, "Satellites today wait for ground control to tell them what to do — slow, a single point of failure, "
                "and blind to anything outside its known categories. When a strange flash appears in the sky, a normal "
                "system forces it into a label it already knows.", L, y, colw)
    y -= 4
    y = heading(c, L, y, "02", "Our idea")
    y = wrap(c, "Let the satellites organise themselves. Missions are posted to a shared ledger; satellites that can "
                "do the job bid for it in an auction, the best form a team (an enclave), hand the job over as they fly "
                "out of view, and recover automatically when members fail. For science, the planner keeps an extra "
                "answer — h0, “none of the known models” — so it can flag genuinely new events.", L, y, colw)

    # ── right: architecture diagram ──
    yr = y0 - 9 * mm
    yr = heading(c, R, yr, "03", "How it fits together")
    bw, bh = 34 * mm, 11 * mm
    top = yr - bh - 1 * mm
    box(c, R, top, bw, bh, "Physics engine", "SGP4 orbits + telemetry")
    box(c, R + colw - bw, top, bw, bh, "Consensus engine", "leaders + CNP auctions")
    rx = R + colw / 2 - 17 * mm
    box(c, rx, top - 15 * mm, 34 * mm, bh, "REDIS BUS", "shared keys only", hot=True)
    box(c, R, top - 31 * mm, bw, bh, "WebSocket streamer", "live feed :8765")
    box(c, R + colw - bw, top - 31 * mm, bw, bh, "Streamlit console", "ops + discovery :8501")
    arrow(c, R + bw / 2, top, rx + 6 * mm, top - 15 * mm + bh)
    arrow(c, R + colw - bw / 2, top, rx + 28 * mm, top - 15 * mm + bh)
    arrow(c, rx + 6 * mm, top - 15 * mm, R + bw / 2, top - 31 * mm + bh)
    arrow(c, rx + 28 * mm, top - 15 * mm, R + colw - bw / 2, top - 31 * mm + bh)
    c.setFillColor(GREY); c.setFont("Helvetica-Oblique", 6.8)
    c.drawCentredString(R + colw / 2, top - 37 * mm,
                        "No service calls another — any one can crash and restart independently.")
    c.drawCentredString(R + colw / 2, top - 40.5 * mm, "Streamer -> 3D WebGL globe (Three.js) showing every satellite live.")

    # ── middle full-width: auction pipeline ──
    y = min(y, top - 46 * mm) - 2 * mm
    y = heading(c, L, y, "04", "Life of a mission — the auction")
    steps = [("Post mission", "target, sensor,\nteam size", BLUE), ("Gatekeeper", "free + right sensor\n+ in range", AMBER),
             ("Bid", "0.7 x proximity\n+ 0.3 x battery", PURPLE), ("Award", "top N form\nan enclave", GREEN),
             ("Roll & heal", "leavers released,\nauction re-opens", RED)]
    sw = (W - 2 * M - 4 * 6 * mm) / 5
    for i, (t, d, col) in enumerate(steps):
        x = M + i * (sw + 6 * mm)
        c.setFillColor(colors.white); c.setStrokeColor(col); c.setLineWidth(1.2)
        c.roundRect(x, y - 15 * mm, sw, 15 * mm, 4, fill=1, stroke=1)
        c.setFillColor(col); c.circle(x + 5 * mm, y - 4 * mm, 2.6 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 7.5); c.drawCentredString(x + 5 * mm, y - 5.1 * mm, str(i + 1))
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 8.6); c.drawString(x + 9 * mm, y - 5 * mm, t)
        c.setFillColor(GREY); c.setFont("Helvetica", 6.9)
        for j, ln in enumerate(d.split("\n")):
            c.drawString(x + 3 * mm, y - 9.5 * mm - j * 8, ln)
        if i < 4:
            arrow(c, x + sw + 0.8 * mm, y - 7.5 * mm, x + sw + 5.2 * mm, y - 7.5 * mm)
    y -= 21 * mm

    # ── research (left) + light-curve sketch (right) ──
    y = heading(c, L, y, "05", "The research: open-world discovery")
    yl = wrap(c, "A transient (kilonova, supernova, flare...) brightens and fades in days. With a small measurement "
                 "budget, the planner picks which satellite observes and when, by expected information gain over the "
                 "known classes plus h0 (a Gaussian-process “anything else” model). If P(h0) stays high, it "
                 "switches from identifying the event to preserving evidence of it.", L, y, colw)
    yl -= 3
    yl = wrap(c, "Tested on real ZTF light curves against the real Starlink fleet, against four baselines (B0 cadence, "
                 "B1 nearest, B2 entropy, B3 closed-world), with hypotheses preregistered before testing. "
                 + (f"Result: {hp} of {ha} hypotheses passed; failures are reported, not hidden." if ha else ""),
              L, yl, colw)

    d = Drawing(colw, 38 * mm)
    gx, gy, gw, gh = 8, 10, colw - 14, 38 * mm - 18
    d.add(Line(gx, gy, gx + gw, gy, strokeColor=GREY, strokeWidth=0.6))
    d.add(Line(gx, gy, gx, gy + gh, strokeColor=GREY, strokeWidth=0.6))
    d.add(Rect(gx, gy, gw * 0.22, gh, fillColor=colors.HexColor("#FBEAEA"), strokeColor=None))
    d.add(String(gx + gw * 0.11, gy + gh - 7, "decision window", textAnchor="middle", fontSize=6, fontName="Helvetica", fillColor=RED))

    def curve(fn, col, dash=None):
        pts = []
        for k in range(61):
            t = k / 60 * 12
            pts.append((gx + t / 12 * gw, gy + min(fn(t), 1.05) * (gh - 10)))
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            ln = Line(x1, y1, x2, y2, strokeColor=col, strokeWidth=1.3)
            if dash:
                ln.strokeDashArray = dash
            d.add(ln)

    def lc(rise, decay, tp=1.0, pk=1.0):
        return lambda t: pk * (math.exp(-0.5 * ((t - tp) / rise) ** 2) if t < tp else math.exp(-(t - tp) / decay))
    curve(lc(0.3, 1.2), RED); curve(lc(0.4, 3.0, 1.0, 0.85), AMBER); curve(lc(0.08, 0.5, 0.6, 0.9), PURPLE)
    curve(lambda t: lc(0.6, 2.0, 1.5, 0.7)(t) + 0.35 * math.exp(-0.5 * ((t - 7) / 1.0) ** 2), INK, dash=[2, 2])
    for i, (lab, col) in enumerate([("kilonova", RED), ("shock cooling", AMBER), ("flare", PURPLE), ("h0: unknown", INK)]):
        d.add(Rect(gx + gw - 62, gy + gh - 8 - i * 8, 6, 2, fillColor=col, strokeColor=None))
        d.add(String(gx + gw - 53, gy + gh - 9.5 - i * 8, lab, fontSize=6, fontName="Helvetica", fillColor=INK))
    d.add(String(gx + gw / 2, 1, "time since detection  (schematic shapes, not data)", textAnchor="middle",
                 fontSize=6, fontName="Helvetica", fillColor=GREY))
    d.drawOn(c, R, y - 38 * mm + 6)
    y = min(yl, y - 38 * mm) - 3 * mm

    # ── bottom: features | tech ──
    y = heading(c, L, y, "06", "What you can see in the demo")
    feats = ["3D globe of every real satellite, coloured by sensor",
             "Mission Dispatch: post a mission, watch the auction",
             "Auction Internals: every bid, score, WON / LOST",
             "Jamming button: kill half a team, watch it self-heal",
             "Event Lab: inject a sky event, see the h0 verdict",
             "Evidence: pass/fail matrix read from result files"]
    yy = y
    for i, f in enumerate(feats):
        x = L if i < 3 else L + colw / 2 + 6 * mm
        if i == 3:
            yy = y
        c.setFillColor(RED); c.circle(x + 1.2 * mm, yy + 2.4, 1.1 * mm, fill=1, stroke=0)
        yy = wrap(c, f, x + 4 * mm, yy, colw / 2 - 2 * mm, size=7.8, leading=9.6) - 1.5
    yR = heading(c, R, y + 15, "07", "Built with")
    tech = [("Python", "sgp4, NumPy, SciPy"), ("Redis / Memurai", "message bus"), ("Streamlit + Plotly", "console"),
            ("Three.js / WebGL", "3D globe"), ("WebSockets", "live stream"), ("pytest", "research tests")]
    for i, (a, b) in enumerate(tech):
        x = R + (i % 3) * (colw / 3); yy2 = yR - (i // 3) * 21
        c.setFillColor(LIGHT); c.roundRect(x, yy2 - 6, colw / 3 - 3, 18, 2, fill=1, stroke=0)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 7); c.drawString(x + 4, yy2 + 3.5, a)
        c.setFillColor(GREY); c.setFont("Helvetica", 6); c.drawString(x + 4, yy2 - 3, b)
    c.setFillColor(GREY); c.setFont("Helvetica", 7)
    c.drawString(R, yR - 44, "Data: CelesTrak / Space-Track TLEs · ZTF Bright Transient Survey · GFZ Kp")


    # ── 08: what is new ──
    y = min(yy, yR - 50) - 6 * mm
    y = heading(c, L, y, "08", "What makes it different")
    cards = [("Decentralised", "No central scheduler: satellites negotiate tasks among themselves and re-form "
                               "teams when members leave or fail.", BLUE),
             ("Open-world", "An explicit “none of the above” hypothesis (h0) means unknown events are flagged, "
                            "not forced into a wrong label.", RED),
             ("Honest science", "Real orbits and real ZTF data; hypotheses fixed before testing; every number "
                                "generated from result files, failures shown.", GREEN)]
    cw3 = (W - 2 * M - 2 * 5 * mm) / 3
    for i, (t, dsc, col) in enumerate(cards):
        x = M + i * (cw3 + 5 * mm)
        c.setFillColor(LIGHT); c.roundRect(x, y - 24 * mm, cw3, 24 * mm, 4, fill=1, stroke=0)
        c.setFillColor(col); c.rect(x, y - 1.6 * mm, cw3, 1.6 * mm, fill=1, stroke=0)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 9.5); c.drawString(x + 3 * mm, y - 7 * mm, t)
        wrap(c, dsc, x + 3 * mm, y - 12 * mm, cw3 - 6 * mm, size=7.8, leading=9.8, color=GREY)

    # ── footer ──
    c.setFillColor(INK); c.rect(0, 0, W, 11 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 8)
    c.drawString(M, 4.2 * mm, "Run it:")
    c.setFont("Helvetica", 8)
    c.drawString(M + 12 * mm, 4.2 * mm, "start Memurai  ->  double-click DEMO.bat  ->  http://localhost:8501")
    c.setFillColor(colors.HexColor("#BBBBBB"))
    c.drawRightString(W - M, 4.2 * mm, "github.com/joycemalik/orbitalnet-dashboard")
    c.showPage(); c.save()
    print("wrote", OUT, "| bottom content y =", round(yy / mm, 1), "mm")


if __name__ == "__main__":
    main()
