"""Builds docs/OrbitalNet_Handout.pdf — one-page illustrated project brief.
Counts are read from satellites.txt and research/results/ at build time; nothing is hand-typed."""
import json
import math
import random
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "OrbitalNet_Handout.pdf"
RES = ROOT / "research" / "results"
hx = colors.HexColor
RED, INK, GREY, LIGHT, SPACE = hx("#C8102E"), hx("#15171C"), hx("#5C6370"), hx("#F2F3F5"), hx("#070B14")
BLUE, CYAN, GREEN, AMBER, PURPLE = hx("#2F6DB5"), hx("#38BDF8"), hx("#22A06B"), hx("#E3A008"), hx("#8B5CF6")
W, H = A4
M = 13 * mm

TEAM = "Joyce Malik  ·  Anup H  ·  Moghitha B  ·  Swathi Satish"
GUIDES = "Guided by  Smitha Shekar B  &  Harish G"
DEPT = "Department of Computer Science and Engineering, Dr. Ambedkar Institute of Technology, Bengaluru"


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


def wrap(c, text, x, y, width, font="Helvetica", size=8.2, leading=10.6, color=INK):
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


def heading(c, x, y, num, text, width):
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 7.5); c.drawString(x, y + 0.5, num)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 10); c.drawString(x + 14, y, text.upper())
    c.setStrokeColor(hx("#D5D8DE")); c.setLineWidth(0.5)
    c.line(x + 18 + c.stringWidth(text.upper(), "Helvetica-Bold", 10), y + 3, x + width, y + 3)
    return y - 13


def arrow(c, x1, y1, x2, y2, col=INK, lw=0.9):
    c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(lw); c.line(x1, y1, x2, y2)
    a = math.atan2(y2 - y1, x2 - x1); L = 4.2
    p = c.beginPath(); p.moveTo(x2, y2)
    p.lineTo(x2 - L * math.cos(a - 0.4), y2 - L * math.sin(a - 0.4))
    p.lineTo(x2 - L * math.cos(a + 0.4), y2 - L * math.sin(a + 0.4)); p.close()
    c.drawPath(p, fill=1, stroke=0)


def glow(c, x, y, r, col, steps=6):
    for i in range(steps, 0, -1):
        c.setFillColor(col, alpha=0.06 + 0.02 * (steps - i)); c.circle(x, y, r * (1 + i * 0.55), fill=1, stroke=0)
    c.setFillColor(col, alpha=1); c.circle(x, y, r, fill=1, stroke=0)


# ── hero illustration ─────────────────────────────────────────────────────────
def hero(c, top):
    hh = 78 * mm
    y0 = top - hh
    c.saveState()
    cp = c.beginPath(); cp.rect(0, y0, W, hh); c.clipPath(cp, stroke=0, fill=0)
    c.setFillColor(SPACE); c.rect(0, y0, W, hh, fill=1, stroke=0)
    rnd = random.Random(7)
    for _ in range(420):
        x, y = rnd.uniform(0, W), rnd.uniform(y0, top)
        c.setFillColor(colors.white, alpha=rnd.uniform(0.15, 0.85)); c.circle(x, y, rnd.choice([0.25, 0.35, 0.5, 0.8]), fill=1, stroke=0)
    # Earth limb
    ex, er = W * 0.62, 260 * mm
    ey = y0 - er + 20 * mm
    for i in range(14, 0, -1):
        c.setFillColor(CYAN, alpha=0.012 * (15 - i)); c.circle(ex, ey, er + i * 2.2 * mm, fill=1, stroke=0)
    c.setFillColor(hx("#0E2A4F"), alpha=1); c.circle(ex, ey, er, fill=1, stroke=0)
    c.setFillColor(hx("#143A6B")); c.circle(ex - 20 * mm, ey - 6 * mm, er - 6 * mm, fill=1, stroke=0)
    # orbits (ellipses around Earth centre, clipped to hero by drawing order)
    sats = []
    for k, (rr, tilt, col) in enumerate([(er + 12 * mm, 0.0, CYAN), (er + 24 * mm, 0.0, AMBER), (er + 37 * mm, 0.0, PURPLE)]):
        c.setStrokeColor(col, alpha=0.6); c.setLineWidth(0.8); c.setDash(1.5, 2.5)
        p = c.beginPath()
        for t in range(0, 181):
            a = math.radians(60 + t * 0.33)
            x = ex + rr * math.cos(a); y = ey + rr * math.sin(a) - tilt * (x - ex) * 0.2
            (p.moveTo if t == 0 else p.lineTo)(x, y)
        c.drawPath(p, stroke=1, fill=0); c.setDash()
        for j, ang in enumerate([70, 76, 82, 88, 94, 100, 106, 112]):
            a = math.radians(ang + k * 2.5)
            x = ex + rr * math.cos(a); y = ey + rr * math.sin(a) - tilt * (x - ex) * 0.2
            if y0 + 4 < y < top - 6:
                sats.append((x, y, col))
    # enclave: links from selected satellites to a ground target
    tx, ty = W * 0.66, y0 + 17 * mm
    team = sorted(sats, key=lambda s: math.hypot(s[0] - tx, s[1] - ty))[:4]
    for (x, y, _) in team:
        c.setStrokeColor(GREEN, alpha=0.85); c.setLineWidth(1.0); c.line(x, y, tx, ty)
    # inter-satellite links
    for (x1, y1, _), (x2, y2, _) in zip(team, team[1:]):
        c.setStrokeColor(colors.white, alpha=0.5); c.setLineWidth(0.5); c.setDash(1, 2); c.line(x1, y1, x2, y2); c.setDash()
    for (x, y, col) in sats:
        glow(c, x, y, 1.7, GREEN if (x, y, col) in team else col, steps=4)
    glow(c, tx, ty, 1.6, RED, steps=7)
    c.setFillColor(colors.white, alpha=0.9); c.setFont("Helvetica", 6)
    c.drawString(tx + 4, ty - 2, "TASKED TARGET · ENCLAVE LOCKED")
    # transient in the sky
    sx, sy = W * 0.88, top - 18 * mm
    for i in range(10, 0, -1):
        c.setFillColor(hx("#FDE68A"), alpha=0.03 * (11 - i)); c.circle(sx, sy, i * 1.9 * mm, fill=1, stroke=0)
    c.setStrokeColor(colors.white, alpha=0.9); c.setLineWidth(0.6)
    c.line(sx - 9 * mm, sy, sx + 9 * mm, sy); c.line(sx, sy - 9 * mm, sx, sy + 9 * mm)
    glow(c, sx, sy, 1.8, colors.white, steps=3)
    c.setFillColor(hx("#FDE68A"), alpha=1); c.setFont("Helvetica-Bold", 6.2)
    c.drawRightString(sx - 4 * mm, sy - 11 * mm, "NEW TRANSIENT  ·  P(h0) RISING")
    # observation rays from two satellites to the transient
    for (x, y, _) in sorted(sats, key=lambda s: -s[1])[:2]:
        c.setStrokeColor(hx("#FDE68A"), alpha=0.55); c.setLineWidth(0.6); c.setDash(2, 2); c.line(x, y, sx, sy); c.setDash()
    c.restoreState()
    # title block
    c.setFillColor(RED, alpha=1); c.rect(M, top - 13 * mm, 9 * mm, 1.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white, alpha=0.75); c.setFont("Helvetica-Bold", 6.8)
    c.drawString(M + 11 * mm, top - 13.3 * mm, "MAJOR PROJECT  ·  AUTONOMOUS SPACE SYSTEMS  ·  BAYESIAN DECISION THEORY")
    c.setFillColor(colors.white, alpha=1); c.setFont("Helvetica-Bold", 30)
    c.drawString(M, top - 27 * mm, "OrbitalNet OS")
    c.setFont("Helvetica", 11.5); c.setFillColor(hx("#E5E7EB"))
    c.drawString(M, top - 34 * mm, "Self-organising satellite constellations that")
    c.drawString(M, top - 39.5 * mm, "plan observations — and recognise the unknown.")
    c.setFont("Helvetica-Bold", 8.4); c.setFillColor(colors.white)
    c.drawString(M, top - 50 * mm, TEAM)
    c.setFont("Helvetica", 7.6); c.setFillColor(hx("#FCA5A5"))
    c.drawString(M, top - 55 * mm, GUIDES)
    c.setFillColor(hx("#9CA3AF")); c.setFont("Helvetica", 6.8)
    c.drawString(M, top - 60 * mm, DEPT)
    return y0


def evidence_panel(c, x, y, w, h, title, vals, highlight):
    c.setFillColor(LIGHT); c.roundRect(x, y, w, h, 3, fill=1, stroke=0)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 7); c.drawString(x + 4, y + h - 9, title)
    labs = ["KN", "SC", "GRB", "FL", "h0"]
    cols = [RED, AMBER, BLUE, PURPLE, INK]
    bw = (w - 16) / 5
    for i, (v, lab, col) in enumerate(zip(vals, labs, cols)):
        bx = x + 8 + i * bw; bh = v * (h - 26)
        c.setFillColor(col, alpha=1 if i == highlight else 0.28)
        c.rect(bx + 2, y + 11, bw - 6, bh, fill=1, stroke=0)
        c.setFillColor(GREY); c.setFont("Helvetica", 6); c.drawCentredString(bx + bw / 2 - 1, y + 4, lab)


def main():
    n_sat, hp, ha = counts()
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("OrbitalNet OS — Project Brief")
    y = hero(c, H)

    # ── abstract ──
    y -= 7 * mm
    y = wrap(c, "Abstract.  OrbitalNet OS is a decentralised operating layer for satellite constellations. Built on "
                f"{n_sat:,} real orbital element sets propagated with SGP4, it lets spacecraft allocate tasks among "
                "themselves through a Contract-Net auction, maintain coverage with rolling hand-offs, and recover from "
                "node loss without ground intervention. On top of this substrate sits the scientific core: an "
                "open-world Bayesian planner that chooses which spacecraft should observe a fading astronomical "
                "transient, and when, by maximising expected information gain over the known physical models and an "
                "explicit null hypothesis h0 — allowing the system to report that an event lies outside known physics "
                "rather than forcing a confident but wrong label.", M, y, W - 2 * M, size=8.4, leading=11)
    # ── KPI strip ──
    y -= 3 * mm
    kp = [(f"{n_sat:,}", "real satellites, SGP4"), ("K + 1", "hypotheses incl. h0"),
          ("4", "fault-isolated services"), (f"{hp} / {ha}" if ha else "—", "preregistered tests passed")]
    kw = (W - 2 * M - 9 * mm) / 4
    for i, (v, l) in enumerate(kp):
        x = M + i * (kw + 3 * mm)
        c.setFillColor(INK); c.roundRect(x, y - 12 * mm, kw, 12 * mm, 3, fill=1, stroke=0)
        c.setFillColor(RED); c.rect(x, y - 12 * mm, 1.2 * mm, 12 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 13); c.drawString(x + 4 * mm, y - 6.3 * mm, v)
        c.setFillColor(hx("#AEB4BE")); c.setFont("Helvetica", 6.8); c.drawString(x + 4 * mm, y - 10 * mm, l)
    y -= 18 * mm

    cw = (W - 2 * M - 7 * mm) / 2
    L, R = M, M + cw + 7 * mm

    # ── 01 architecture (left) ──
    yl = heading(c, L, y, "01", "Decoupled architecture", cw)
    bw, bh = 30 * mm, 9.5 * mm
    t = yl - bh
    def node(x, yy, a, b, hot=False, col=BLUE):
        c.setFillColor(RED if hot else colors.white); c.setStrokeColor(RED if hot else col); c.setLineWidth(0.9)
        c.roundRect(x, yy, bw, bh, 3, fill=1, stroke=1)
        c.setFillColor(colors.white if hot else INK); c.setFont("Helvetica-Bold", 7.4); c.drawCentredString(x + bw / 2, yy + 5.2 * mm, a)
        c.setFillColor(colors.white if hot else GREY); c.setFont("Helvetica", 5.9); c.drawCentredString(x + bw / 2, yy + 2.0 * mm, b)
    node(L, t, "Orbit propagator", "SGP4 · 1 Hz state vectors")
    node(L + cw - bw, t, "Consensus engine", "leader election · CNP")
    node(L + cw / 2 - bw / 2, t - 13 * mm, "Redis state bus", "publish / subscribe keys", hot=True)
    node(L, t - 26 * mm, "Telemetry stream", "WebSocket → WebGL globe", col=GREEN)
    node(L + cw - bw, t - 26 * mm, "Mission console", "operations · discovery", col=GREEN)
    mx = L + cw / 2
    arrow(c, L + bw / 2, t, mx - 8 * mm, t - 13 * mm + bh); arrow(c, L + cw - bw / 2, t, mx + 8 * mm, t - 13 * mm + bh)
    arrow(c, mx - 8 * mm, t - 13 * mm, L + bw / 2, t - 26 * mm + bh); arrow(c, mx + 8 * mm, t - 13 * mm, L + cw - bw / 2, t - 26 * mm + bh)
    yl = wrap(c, "Services share state only through the bus — no direct calls — so any process can fail and restart "
                 "without halting the constellation.", L, t - 30 * mm, cw, size=7.6, leading=9.6, color=GREY)

    # ── 02 auction (right) ──
    yr = heading(c, R, y, "02", "Decentralised task allocation", cw)
    yr = wrap(c, "Missions are announced to a shared ledger. Each spacecraft passes a hard gatekeeper (free, correct "
                 "payload, within slew range), then bids:", R, yr, cw, size=7.9, leading=10)
    c.setFillColor(LIGHT); c.roundRect(R, yr - 11 * mm, cw, 10 * mm, 3, fill=1, stroke=0)
    c.setFillColor(INK); c.setFont("Times-Italic", 10.5)
    c.drawCentredString(R + cw / 2, yr - 6.4 * mm, "bid  =  w_p · (1 − d / d_max)  +  w_b · battery")
    yr -= 15 * mm
    steps = [("ANNOUNCE", BLUE), ("FILTER", AMBER), ("BID", PURPLE), ("AWARD", GREEN), ("HEAL", RED)]
    sw = (cw - 4 * 2.5 * mm) / 5
    for i, (s, col) in enumerate(steps):
        x = R + i * (sw + 2.5 * mm)
        c.setFillColor(col); c.roundRect(x, yr - 6 * mm, sw, 6 * mm, 2, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 6.3); c.drawCentredString(x + sw / 2, yr - 3.9 * mm, s)
    yr -= 9 * mm
    yr = wrap(c, "The top-N bidders form an enclave. Members leaving view are released and the auction re-opens, "
                 "giving rolling hand-off and self-healing under injected node failures; every bid is logged for audit.",
              R, yr, cw, size=7.6, leading=9.6, color=GREY)

    y = min(yl, yr) - 4 * mm

    # ── 03 h0 (full width) ──
    y = heading(c, L, y, "03", "Open-world inference: how the null hypothesis h0 works", W - 2 * M)
    tw = (W - 2 * M) * 0.56
    yt = wrap(c, "Each known class (kilonova, shock cooling, GRB afterglow, stellar flare) is a physical light-curve "
                 "model. h0 is a Gaussian process — a non-parametric prior over any smooth light curve. All K + 1 "
                 "hypotheses are scored by their Bayesian evidence, the probability of the data averaged over each "
                 "model's parameters:", L, y, tw, size=7.9, leading=10)
    c.setFillColor(LIGHT); c.roundRect(L, yt - 10 * mm, tw, 9.5 * mm, 3, fill=1, stroke=0)
    c.setFillColor(INK); c.setFont("Times-Italic", 10.5)
    c.drawCentredString(L + tw / 2, yt - 4.6 * mm, "P(h | D)  ∝  p(D | h) P(h),        p(D | h0) = N( y ; 0, K + σ²I )")
    c.setFont("Helvetica", 6.4); c.setFillColor(GREY)
    c.drawCentredString(L + tw / 2, yt - 8.3 * mm, "posterior over K known models + h0  ·  GP marginal likelihood with RBF kernel K")
    yt -= 13 * mm
    yt = wrap(c, "No neural network is trained. This is Bayesian model comparison: flexible h0 is automatically "
                 "penalised for its flexibility (Bayesian Occam's razor), so it wins only when every physical model "
                 "fits poorly. The ‘unknown’ decision threshold is then calibrated by split-conformal prediction, "
                 "which certifies the false-alarm rate on known events.", L, yt, tw, size=7.9, leading=10)
    px = L + tw + 5 * mm; pw = (W - M - px - 3 * mm) / 2; ph = 30 * mm
    evidence_panel(c, px, y - ph + 4, pw, ph, "Known event", [0.82, 0.10, 0.04, 0.02, 0.06], 0)
    evidence_panel(c, px + pw + 3 * mm, y - ph + 4, pw, ph, "Unknown event", [0.08, 0.06, 0.05, 0.04, 0.88], 4)
    c.setFillColor(GREY); c.setFont("Helvetica-Oblique", 6.2)
    c.drawString(px, y - ph - 2, "Posterior after measurements (schematic): a known class wins — or h0 does.")
    y = min(yt, y - ph - 4) - 3 * mm

    # ── 04 planner (left) / 05 evaluation (right) ──
    yl = heading(c, L, y, "04", "Planning under fading information", cw)
    c.setFillColor(LIGHT); c.roundRect(L, yl - 10 * mm, cw, 9.5 * mm, 3, fill=1, stroke=0)
    c.setFillColor(INK); c.setFont("Times-Italic", 10)
    c.drawCentredString(L + cw / 2, yl - 5.6 * mm, "U(a) = [ I(H;Y) + β I(Z;Y) + γ D(a) ] / c(a)")
    yl -= 13 * mm
    yl = wrap(c, "Information about the class, about model adequacy, and the value lost if the observation is "
                 "delayed — per unit cost. When P(h0) stays above τ, the planner switches from identification to "
                 "evidence preservation.", L, yl, cw, size=7.6, leading=9.6, color=GREY)

    yr = heading(c, R, y, "05", "Evaluation protocol", cw)
    items = ["Real ZTF Bright Transient Survey light curves, replayed against the real Starlink fleet",
             "Baselines: fixed cadence, nearest-capable dispatch, classifier entropy, closed-world EIG",
             "Hypotheses preregistered; tuning on validation seeds only; identical inputs per seed",
             (f"{hp} of {ha} preregistered hypotheses passed — failures reported, not hidden" if ha else
              "Results generated only from result files")]
    for it in items:
        c.setFillColor(RED); c.rect(R, yr + 1.2, 2.2, 2.2, fill=1, stroke=0)
        yr = wrap(c, it, R + 3.5 * mm, yr, cw - 3.5 * mm, size=7.6, leading=9.4) - 1.5
    y = min(yl, yr) - 2 * mm

    # ── stack strip ──
    c.setFillColor(LIGHT); c.roundRect(M, y - 8 * mm, W - 2 * M, 8 * mm, 3, fill=1, stroke=0)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 6.8); c.drawString(M + 3 * mm, y - 5 * mm, "STACK")
    c.setFont("Helvetica", 6.8); c.setFillColor(GREY)
    c.drawString(M + 15 * mm, y - 5 * mm, "Python · SGP4 · NumPy/SciPy · Gaussian processes · Redis · WebSockets · Three.js · Streamlit")

    # ── footer ──
    c.setFillColor(SPACE); c.rect(0, 0, W, 10 * mm, fill=1, stroke=0)
    c.setFillColor(RED); c.rect(0, 10 * mm - 0.8, W, 0.8, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 7.4)
    c.drawString(M, 3.8 * mm, "LIVE DEMO")
    c.setFont("Helvetica", 7.4); c.setFillColor(hx("#D1D5DB"))
    c.drawString(M + 17 * mm, 3.8 * mm, "Memurai  →  DEMO.bat  →  localhost:8501")
    c.drawRightString(W - M, 3.8 * mm, "github.com/joycemalik/orbitalnet-dashboard")
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 6.8); c.drawRightString(W - M - 3 * mm, y - 5 * mm, "DATA")
    c.setFont("Helvetica", 6.8); c.setFillColor(GREY)
    c.drawRightString(W - M - 3 * mm - 8 * mm, y - 5 * mm, "Space-Track · ZTF · GFZ")
    c.showPage(); c.save()
    print("wrote", OUT, "| lowest content y =", round((y - 8 * mm) / mm, 1), "mm")


if __name__ == "__main__":
    main()
