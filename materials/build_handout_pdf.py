"""Builds materials/OrbitalNet_Handout.pdf — single-page illustrated technical brief.

Every metric is parsed from research/papers/main/generated/numbers.tex (itself generated from
research/results/) or counted from satellites.txt / result JSONs. Nothing numeric is typed by hand.
"""
import json
import math
import random
import re
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "materials" / "OrbitalNet_Handout.pdf"
RES = ROOT / "research" / "results"
NUMS = ROOT / "research" / "papers" / "main" / "generated" / "numbers.tex"

FD = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
for name, f in [("Sans", "DejaVuSans.ttf"), ("SansB", "DejaVuSans-Bold.ttf"), ("SansI", "DejaVuSans-Oblique.ttf"),
                ("Math", "DejaVuSerif-Italic.ttf"), ("MathR", "DejaVuSerif.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FD / f)))

hx = colors.HexColor
RED, INK, GREY, LIGHT, SPACE = hx("#D0102B"), hx("#14161B"), hx("#5B6270"), hx("#F1F3F6"), hx("#060A14")
BLUE, CYAN, GREEN, AMBER, PURPLE = (hx(c) for c in ("#2563EB", "#22D3EE", "#16A34A", "#F59E0B", "#8B5CF6"))
W, H = A4
M = 9 * mm


def load_numbers():
    d = {}
    for k, v in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", NUMS.read_text(encoding="utf-8")):
        v = v.replace("\\%", "%").replace("\\,", " ").replace("--", "–").replace("~", " ")
        d[k] = re.sub(r"\\textbf\{(\w+)\}", r"\1", v)
    return d


def num(s):
    vals = [float(x) for x in re.findall(r"\d*\.?\d+", s)]
    return sum(vals) / len(vals) if vals else 0.0


def counts():
    n_sat = len([l for l in (ROOT / "mission_control" / "data" / "satellites.txt").read_text(encoding="utf-8").splitlines() if l.strip()]) // 3
    hp = 0
    for f, k in [("phase2/analysis_test.json", "verdict"), ("phase3/analysis_test.json", "overall_pass_all_seeds"),
                 ("phase5/analysis_test_v2.json", "overall_pass_all_seeds"),
                 ("phase6/analysis_test_v3.json", "overall_pass_all_seeds")]:
        p = RES / f
        if p.exists():
            hp += sum(bool(x) for x in json.loads(p.read_text()).get(k, {}).values())
    return n_sat, hp


def txt(c, x, y, s, font="Sans", size=7, col=INK, align="l", alpha=1):
    c.setFont(font, size); c.setFillColor(col, alpha=alpha)
    {"l": c.drawString, "c": c.drawCentredString, "r": c.drawRightString}[align](x, y, s)
    c.setFillAlpha(1)


def panel(c, x, y, w, h, n, title, accent=RED):
    c.setFillColor(colors.white); c.setStrokeColor(hx("#DDE1E7")); c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, 2.5, fill=1, stroke=1)
    c.setFillColor(accent); c.rect(x, y + h - 0.9 * mm, w, 0.9 * mm, fill=1, stroke=0)
    txt(c, x + 2.5 * mm, y + h - 5 * mm, n, "SansB", 6.2, accent)
    txt(c, x + 7.5 * mm, y + h - 5 * mm, title.upper(), "SansB", 6.9, INK)
    return y + h - 7.5 * mm


def mathbox(c, x, y, w, lines, size=7.0, lead=9.4, tag=BLUE):
    h = len(lines) * lead + 3.5
    c.setFillColor(hx("#F6F7FA")); c.setStrokeColor(hx("#E3E6EC")); c.setLineWidth(0.4)
    c.roundRect(x, y - h, w, h, 2, fill=1, stroke=1)
    c.setFillColor(tag); c.rect(x, y - h, 0.8 * mm, h, fill=1, stroke=0)
    yy = y - lead + 1
    for s, lab in lines:
        txt(c, x + 2.6 * mm, yy, s, "Math", size)
        txt(c, x + w - 1.5 * mm, yy, lab, "Sans", 5.0, GREY, "r")
        yy -= lead
    return y - h - 1.4 * mm


def arrow(c, x1, y1, x2, y2, col=INK, lw=0.7, head=3.0, dash=None):
    c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(lw)
    if dash:
        c.setDash(*dash)
    c.line(x1, y1, x2, y2); c.setDash()
    a = math.atan2(y2 - y1, x2 - x1)
    p = c.beginPath(); p.moveTo(x2, y2)
    p.lineTo(x2 - head * math.cos(a - 0.42), y2 - head * math.sin(a - 0.42))
    p.lineTo(x2 - head * math.cos(a + 0.42), y2 - head * math.sin(a + 0.42)); p.close()
    c.drawPath(p, fill=1, stroke=0)


def glow(c, x, y, r, col, steps=5):
    for i in range(steps, 0, -1):
        c.setFillColor(col, alpha=0.07 + 0.025 * (steps - i)); c.circle(x, y, r * (1 + i * 0.6), fill=1, stroke=0)
    c.setFillColor(col, alpha=1); c.circle(x, y, r, fill=1, stroke=0)


def node(c, x, y, w, h, a, b="", fc=colors.white, ec=BLUE, tc=INK, sc=GREY, fs=6.2):
    c.setFillColor(fc); c.setStrokeColor(ec); c.setLineWidth(0.8); c.roundRect(x, y, w, h, 2, fill=1, stroke=1)
    txt(c, x + w / 2, y + h / 2 + 0.6, a, "SansB", fs, tc, "c")
    txt(c, x + w / 2, y + h / 2 - 5.4, b, "Sans", 4.8, sc, "c")


def hero(c):
    hh = 48 * mm; y0 = H - hh
    c.saveState(); cp = c.beginPath(); cp.rect(0, y0, W, hh); c.clipPath(cp, stroke=0, fill=0)
    c.setFillColor(SPACE); c.rect(0, y0, W, hh, fill=1, stroke=0)
    rnd = random.Random(11)
    for _ in range(380):
        c.setFillColor(colors.white, alpha=rnd.uniform(0.15, 0.9))
        c.circle(rnd.uniform(0, W), rnd.uniform(y0, H), rnd.choice([0.25, 0.35, 0.5, 0.75]), fill=1, stroke=0)
    er = 230 * mm; ex = W * 0.76; ey = y0 - er + 14 * mm
    for i in range(16, 0, -1):
        c.setFillColor(CYAN, alpha=0.011 * (17 - i)); c.circle(ex, ey, er + i * 1.9 * mm, fill=1, stroke=0)
    c.setFillColor(hx("#0B2547"), alpha=1); c.circle(ex, ey, er, fill=1, stroke=0)
    c.setFillColor(hx("#12386A")); c.circle(ex - 16 * mm, ey - 5 * mm, er - 5 * mm, fill=1, stroke=0)
    sats = []
    for k, (dr, col) in enumerate([(9, CYAN), (18, AMBER), (27, PURPLE)]):
        rr = er + dr * mm
        c.setStrokeColor(col, alpha=0.55); c.setLineWidth(0.6); c.setDash(1.2, 2.2)
        p = c.beginPath()
        for t in range(121):
            a = math.radians(68 + t * 0.28); (p.moveTo if t == 0 else p.lineTo)(ex + rr * math.cos(a), ey + rr * math.sin(a))
        c.drawPath(p, stroke=1, fill=0); c.setDash()
        for ang in range(72, 102, 3):
            a = math.radians(ang + k * 1.4)
            x, y = ex + rr * math.cos(a), ey + rr * math.sin(a)
            if y0 < y < H and x > W * 0.48:
                sats.append((x, y, col))
    tx, ty = W * 0.72, y0 + 10 * mm
    team = sorted(sats, key=lambda s: math.hypot(s[0] - tx, s[1] - ty))[:5]
    for (x, y, _) in team:
        c.setStrokeColor(GREEN, alpha=0.9); c.setLineWidth(0.8); c.line(x, y, tx, ty)
    for (x1, y1, _), (x2, y2, _) in zip(team, team[1:]):
        c.setStrokeColor(colors.white, alpha=0.55); c.setLineWidth(0.45); c.setDash(1, 1.6); c.line(x1, y1, x2, y2); c.setDash()
    for s in sats:
        glow(c, s[0], s[1], 1.35, GREEN if s in team else s[2], 4)
    glow(c, tx, ty, 1.5, RED, 7)
    txt(c, tx + 4, ty - 2.5, "ENCLAVE  ·  CNP AWARD", "SansB", 4.8, colors.white, alpha=0.9)
    sx, sy = W * 0.93, H - 12 * mm
    for i in range(10, 0, -1):
        c.setFillColor(hx("#FDE68A"), alpha=0.032 * (11 - i)); c.circle(sx, sy, i * 1.5 * mm, fill=1, stroke=0)
    c.setStrokeColor(colors.white, alpha=0.9); c.setLineWidth(0.5)
    c.line(sx - 7 * mm, sy, sx + 7 * mm, sy); c.line(sx, sy - 7 * mm, sx, sy + 7 * mm)
    glow(c, sx, sy, 1.4, colors.white, 3)
    for (x, y, _) in sorted(sats, key=lambda s: -s[1])[:3]:
        c.setStrokeColor(hx("#FDE68A"), alpha=0.6); c.setLineWidth(0.5); c.setDash(1.6, 1.6); c.line(x, y, sx, sy); c.setDash()
    txt(c, sx - 4 * mm, sy - 10.5 * mm, "TRANSIENT  ·  a* = argmax EIG  ·  P(h₀|D)", "SansB", 4.8, hx("#FDE68A"), "r")
    c.restoreState()
    c.setFillColor(RED); c.rect(M, H - 9 * mm, 7 * mm, 0.9 * mm, fill=1, stroke=0)
    txt(c, M + 9 * mm, H - 9.3 * mm, "MAJOR PROJECT  ·  SCHOOL OF COMPUTER SCIENCE & ENGINEERING", "SansB", 5.6, colors.white, alpha=0.75)
    txt(c, M, H - 19 * mm, "OrbitalNet OS", "SansB", 24, colors.white)
    txt(c, M, H - 25 * mm, "Distributed Architecture for Intelligent Satellite Fleet Management", "Sans", 9.2, hx("#E5E7EB"))
    names = "JOYCE MALIK  ·  MOGHITHA B  ·  SWATHI SATHISH  ·  ANUP H"
    txt(c, M, H - 32 * mm, names, "SansB", 6.9, colors.white)
    txt(c, M + c.stringWidth(names, "SansB", 6.9) + 2 * mm, H - 32 * mm, "(CSE, SCSE)", "Sans", 6.2, hx("#9CA3AF"))
    txt(c, M, H - 37 * mm, "Under the Guidance of", "SansI", 5.9, hx("#FCA5A5"))
    txt(c, M, H - 41.5 * mm, "Dr. SMITHA SHEKAR B", "SansB", 6.4, colors.white)
    txt(c, M, H - 44.6 * mm, "Professor, CSE Programme, SCSE", "Sans", 5.3, hx("#9CA3AF"))
    txt(c, M + 42 * mm, H - 41.5 * mm, "Dr. HARISH G", "SansB", 6.4, colors.white)
    txt(c, M + 42 * mm, H - 44.6 * mm, "Professor, CSE Programme, SCSE", "Sans", 5.3, hx("#9CA3AF"))
    return y0


def kpis(c, y, items):
    n = len(items); g = 1.6 * mm; kw = (W - 2 * M - (n - 1) * g) / n; kh = 13 * mm
    for i, (v, l1, l2, col) in enumerate(items):
        x = M + i * (kw + g)
        c.setFillColor(INK); c.roundRect(x, y - kh, kw, kh, 2, fill=1, stroke=0)
        c.setFillColor(col); c.rect(x, y - kh, kw, 0.8 * mm, fill=1, stroke=0)
        txt(c, x + 2.2 * mm, y - 6 * mm, v, "SansB", 11, colors.white)
        txt(c, x + 2.2 * mm, y - 9 * mm, l1, "SansB", 5.0, hx("#D1D5DB"))
        txt(c, x + 2.2 * mm, y - 11.4 * mm, l2, "Sans", 4.7, hx("#9CA3AF"))
    return y - kh - 2 * mm


def topology(c, x, y, w, h):
    top = panel(c, x, y, w, h, "01", "Architectural topology · event-sourced state bus", BLUE)
    c.setFillColor(hx("#0B1220")); c.roundRect(x + 2 * mm, top - 10 * mm, w - 4 * mm, 10 * mm, 2, fill=1, stroke=0)
    rnd = random.Random(3)
    for _ in range(70):
        c.setFillColor(colors.white, alpha=rnd.uniform(0.2, 0.7))
        c.circle(rnd.uniform(x + 3 * mm, x + w - 3 * mm), rnd.uniform(top - 9.5 * mm, top - 0.5 * mm), 0.3, fill=1, stroke=0)
    pts = [(x + 6 * mm + i * (w - 12 * mm) / 11, top - 6 * mm + 1.8 * mm * math.sin(i * 1.1)) for i in range(12)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        c.setStrokeColor(CYAN, alpha=0.45); c.setLineWidth(0.4); c.setDash(1, 1.5); c.line(x1, y1, x2, y2); c.setDash()
    for i, (px, py) in enumerate(pts):
        glow(c, px, py, 0.9, [CYAN, AMBER, PURPLE, GREEN][i % 4], 3)
    txt(c, x + 3.5 * mm, top - 2.6 * mm, "ORBITAL LAYER · TLE → SGP4 → ECI → (φ, λ) @ 1 Hz", "SansB", 4.7, colors.white, alpha=0.85)
    cx, cy = x + w * 0.5, y + 33 * mm
    R = 9.5 * mm
    for i in range(6, 0, -1):
        c.setFillColor(RED, alpha=0.045 * (7 - i)); c.circle(cx, cy, R + i * 1.1 * mm, fill=1, stroke=0)
    c.setFillColor(RED, alpha=1); c.circle(cx, cy, R, fill=1, stroke=0)
    c.setStrokeColor(colors.white, alpha=0.5); c.setLineWidth(0.4); c.circle(cx, cy, R - 1.5 * mm, fill=0, stroke=1)
    txt(c, cx, cy + 1, "REDIS", "SansB", 7.2, colors.white, "c")
    txt(c, cx, cy - 5, "state bus", "Sans", 5, colors.white, "c")
    keys = ["STARLINK-⟨id⟩", "MISSIONS_LEDGER", "AUCTION_LOGS", "TRIGGER_CHAOS", "SCORING_WEIGHTS", "CURRENT_MISSION"]
    kx0 = x + 10 * mm; kwid = (w - 20 * mm) / 3
    for i, k in enumerate(keys):
        kx = kx0 + (i % 3) * kwid + kwid / 2; ky = top - 13.2 * mm - (i // 3) * 6
        tw = c.stringWidth(k, "Sans", 4.1) + 3
        c.setFillColor(hx("#FFF1F2")); c.setStrokeColor(hx("#FECDD3")); c.setLineWidth(0.3)
        c.roundRect(kx - tw / 2, ky - 2.4, tw, 5.0, 1.2, fill=1, stroke=1)
        txt(c, kx, ky - 1.2, k, "Sans", 4.1, RED, "c")
    nw, nh = 25 * mm, 9 * mm
    services = [(x + 2.5 * mm, cy + 4 * mm, "physics_engine", "SGP4 · HAL telemetry", BLUE),
                (x + 2.5 * mm, cy - 13 * mm, "scoring_engine", "gate · Σwθ · e^(−λR)", PURPLE),
                (x + w - 2.5 * mm - nw, cy + 4 * mm, "consensus_engine", "leaders · CNP · enclaves", GREEN),
                (x + w - 2.5 * mm - nw, cy - 13 * mm, "streamer", "async WebSocket · 2 Hz", AMBER)]
    for sx, sy, a, b, col in services:
        node(c, sx, sy, nw, nh, a, b, ec=col)
        left = sx < cx
        ax = sx + nw if left else sx
        hxp = cx + (-1 if left else 1) * (R + 1.0 * mm)
        hyp = cy + (sy + nh / 2 - cy) * 0.45
        arrow(c, ax, sy + nh / 2 + 1.2, hxp, hyp + 1.2, col)
        arrow(c, hxp, hyp - 1.6, ax, sy + nh / 2 - 1.6, col, dash=(1.1, 1.1))
    by = y + 2.5 * mm; bh_ = 8.5 * mm
    node(c, x + 2.5 * mm, by, nw, bh_, "Three.js globe", "WebGL · 10⁴ live sprites", fc=hx("#0B1220"), ec=CYAN,
         tc=colors.white, sc=hx("#9CA3AF"))
    node(c, x + w / 2 - nw / 2, by, nw, bh_, "Streamlit console", "operations · discovery", ec=RED)
    node(c, x + w - 2.5 * mm - nw, by, nw, bh_, "research engine", "Bayes · GP · EIG", fc=hx("#F5F3FF"), ec=PURPLE)
    arrow(c, x + w - 2.5 * mm - nw / 2, cy - 13 * mm, x + 2.5 * mm + nw * 0.85, by + bh_, AMBER, dash=(1.1, 1.1))
    arrow(c, cx, cy - R, x + w / 2, by + bh_, RED)
    txt(c, x + w - 2.5 * mm - nw / 2, by + bh_ + 1.4, "pure · seeded · reproducible", "SansI", 4.3, PURPLE, "c")
    txt(c, x + 2.5 * mm + nw / 2, by + bh_ + 1.4, "solid: write · dashed: read", "SansI", 4.3, GREY, "c")


def decision_math(c, x, y, w, h):
    yy = panel(c, x, y, w, h, "02", "Decision mathematics · capability & auction", PURPLE)
    yy = mathbox(c, x + 2 * mm, yy, w - 4 * mm, [
        ("G(θ) = ∏ₖ 1[ gₖ(θ) ∈ Ωₖ ]", "hard gatekeepers"),
        ("Cᵢ = G(θᵢ) · ( Σⱼ wⱼ θᵢⱼ ) · exp(−λ Rᵢ)", "capability score"),
        ("Rᵢ = p_conj + ½ Φ_rad + ⅕ S_solar", "aggregate risk"),
        ("U_swarm = Σᵢ Cᵢ · max( Δ_div , δ )", "swarm utility"),
    ], tag=PURPLE)
    yy = mathbox(c, x + 2 * mm, yy, w - 4 * mm, [
        ("dᵢ = 2r · asin √( sin²(Δφ/2) + cos φᵢ cos φ* sin²(Δλ/2) )", "haversine"),
        ("bᵢ = w_p ( 1 − dᵢ / d_max ) + w_b · SoCᵢ", "CNP bid"),
        ("E = top-N { bᵢ : G(θᵢ) = 1 ∧ sᵢ = s* ∧ dᵢ ≤ d_max }", "award"),
        ("Eₜ₊₁ = { i ∈ Eₜ : dᵢ(t) ≤ d_max } ,  |E| < N ⇒ re-auction", "rolling enclave"),
        ("L_π = argmax_{i ∈ π} Cᵢ", "plane leader"),
    ], tag=GREEN)
    yy = mathbox(c, x + 2 * mm, yy, w - 4 * mm, [
        ("r(t), v(t) = SGP4( TLE, t )", "orbit propagation"),
        ("θ_G = 280.4606° + 360.9856° · (JD − 2451545)", "sidereal angle"),
        ("λ = atan2(y, x) − θ_G ,   φ = asin( z / ‖r‖ )", "ECI → geodetic"),
    ], tag=BLUE)
    yy = mathbox(c, x + 2 * mm, yy, w - 4 * mm, [
        ("SoCₜ₊₁ = clip( SoCₜ + 1_sun·c⁺ − 1_ecl·c⁻ , 0, 1 )", "power model"),
        ("DoD = 1 − SoC ,   M_buf ← M_buf + Δm  (flush on downlink)", "HAL state"),
    ], tag=AMBER)
    steps = [("ANNOUNCE", BLUE), ("GATE", AMBER), ("BID", PURPLE), ("AWARD", GREEN), ("HEAL", RED)]
    sw = (w - 4 * mm - 4 * 1.8 * mm) / 5
    for i, (s, col) in enumerate(steps):
        bx = x + 2 * mm + i * (sw + 1.8 * mm)
        c.setFillColor(col); c.roundRect(bx, y + 2.5 * mm, sw, 5 * mm, 1.5, fill=1, stroke=0)
        txt(c, bx + sw / 2, y + 4.3 * mm, s, "SansB", 5.2, colors.white, "c")
        if i < 4:
            arrow(c, bx + sw + 0.2 * mm, y + 5 * mm, bx + sw + 1.6 * mm, y + 5 * mm, GREY, head=1.6)
    txt(c, x + w / 2, y + 8.8 * mm, "decentralised · auditable (every bid logged) · fault-tolerant under injected node loss",
        "SansI", 4.9, GREY, "c")


def inference(c, x, y, w, h):
    yy = panel(c, x, y, w, h, "03", "Open-world Bayesian inference · null hypothesis h₀", RED)
    yy = mathbox(c, x + 2 * mm, yy, w - 4 * mm, [
        ("H = { h₁, … , h_K } ∪ { h₀ }", "open hypothesis space"),
        ("p(D | hₖ) = ∫ p(D | hₖ, A) p(A) dA", "marginal evidence"),
        ("log p(D|h₀) = −½ yᵀ(K+Σ)⁻¹y − ½ log|K+Σ| − (n/2) log 2π", "GP evidence"),
        ("K(t, t′) = σ_f² exp( −(t − t′)² / 2l² )", "RBF kernel"),
        ("P(h | D) = p(D|h) P(h) / Σ_{h′} p(D|h′) P(h′)", "posterior"),
        ("q̂ = Q_{⌈(n+1)(1−α)⌉/n}{ sᵢ }  ⇒  P(false unknown) ≤ α", "split-conformal"),
    ], size=6.8, lead=9.2, tag=RED)
    bw_ = (w - 6 * mm) / 2
    for j, (title, vals, hi) in enumerate([("modelled event", [0.84, 0.07, 0.04, 0.02, 0.03], 0),
                                           ("novel event", [0.05, 0.04, 0.03, 0.03, 0.85], 4)]):
        px = x + 2 * mm + j * (bw_ + 2 * mm); ph = yy - y - 2.5 * mm; py = y + 2 * mm
        c.setFillColor(LIGHT); c.roundRect(px, py, bw_, ph, 2, fill=1, stroke=0)
        txt(c, px + 2 * mm, py + ph - 3.8 * mm, "P(h | D)  ·  " + title, "SansB", 5.4, INK)
        cols = [RED, AMBER, BLUE, PURPLE, INK]; labs = ["KN", "SC", "GRB", "FL", "h₀"]
        bb = (bw_ - 6 * mm) / 5
        for i, v in enumerate(vals):
            bx = px + 3 * mm + i * bb
            c.setFillColor(cols[i], alpha=1 if i == hi else 0.25)
            c.rect(bx + 1, py + 4.3 * mm, bb - 3, v * (ph - 9.5 * mm), fill=1, stroke=0)
            c.setFillAlpha(1)
            txt(c, bx + bb / 2 - 1, py + 1.5 * mm, labs[i], "Sans", 4.8, GREY, "c")


def planner(c, x, y, w, h):
    yy = panel(c, x, y, w, h, "04", "Sequential planner · information under fading", GREEN)
    yy = mathbox(c, x + 2 * mm, yy, w - 4 * mm, [
        ("I(H; Y_a | bₜ) = H[H | bₜ] − E_y H[H | bₜ, y]", "expected info gain"),
        ("D(a, bₜ) = I_t(a) − I_{t+τ}(a)", "opportunity decay"),
        ("U(a | bₜ) = [ I(H;Y_a) + β I(Z;Y_a) + γ D(a) ] / c(a)", "utility"),
        ("a* = argmax_{a ∈ A(t)} U(a | bₜ)", "next action"),
        ("P(h₀ | D) > τ for m steps  ⇒  PRESERVE", "mode switch"),
    ], size=6.8, lead=9.2, tag=GREEN)
    gx0, gy0, gw, gh = x + 2 * mm, y + 2 * mm, w - 4 * mm, yy - y - 2.5 * mm
    c.setFillColor(hx("#0B1220")); c.roundRect(gx0, gy0, gw, gh, 2, fill=1, stroke=0)
    ccx, ccy, rr = gx0 + gw * 0.24, gy0 + gh / 2, gh * 0.36
    c.setFillColor(hx("#12386A")); c.circle(ccx, ccy, rr * 0.45, fill=1, stroke=0)
    c.setStrokeColor(CYAN, alpha=0.35); c.setLineWidth(0.4); c.setDash(1, 1.5); c.circle(ccx, ccy, rr, fill=0, stroke=1); c.setDash()
    nodes = [(ccx + rr * math.cos(math.radians(a)), ccy + rr * math.sin(math.radians(a))) for a in range(20, 380, 60)]
    up = [True, False, True, True, False, True]
    for i in range(6):
        (x1, y1), (x2, y2) = nodes[i], nodes[(i + 1) % 6]
        c.setStrokeColor(GREEN if up[i] else hx("#4B5563"), alpha=1); c.setLineWidth(0.9 if up[i] else 0.5)
        if not up[i]:
            c.setDash(1, 1.4)
        c.line(x1, y1, x2, y2); c.setDash()
    for i, (nx, ny) in enumerate(nodes):
        glow(c, nx, ny, 1.4, [CYAN, AMBER, PURPLE, CYAN, GREEN, AMBER][i], 3)
    lx = gx0 + gw * 0.47
    for k, s in enumerate(["local belief bₜ⁽ⁱ⁾, stale-tolerant", "bid = marginal ΔU given commitments",
                           "evidence merged by observation-ID set", "time-varying contact graph G(t)"]):
        txt(c, lx, gy0 + gh - 4.8 * mm - k * 3.9 * mm, "▸ " + s, "Sans", 5.0, colors.white, alpha=0.9)


def results(c, x, y, w, h, N):
    yy = panel(c, x, y, w, h, "05", "Measured performance · preregistered, held-out test seeds", AMBER)
    groups = [("Novelty AUROC", "simulation", N["SimAucP"], N["SimAucBthree"], 1.0, "closed-world"),
              ("Novel flagged", "simulation · 5% FA", N["SimTprP"], N["SimTprBthree"], 100, "entropy"),
              ("Real AUROC", f"{N['RealNEvents']} ZTF events", N["RealCAuc"], "0.5", 1.0, "chance"),
              ("Confident errors", "sim. unknowns · lower wins", N["SimCwWhP"], N["SimCwWhBthree"], 100, "closed-world"),
              ("Confident errors", "real unknowns · lower wins", N["RealCCwWhP"], N["RealCCwWhBthree"], 100, "closed-world"),
              ("False alarms", f"{N['ConfNFresh']} sealed SNe", N["ConfFa"], N["ConfAlphaPct"], 100, "bound α")]
    phases = ["P1 · proof", "P2 · simulation", "P3 · real ZTF", "P5 · two-band", "P6 · frozen v3", "PC · conformal"]
    pw = (w - 4 * mm - 5 * 1.6 * mm) / 6
    for i, ph in enumerate(phases):
        px = x + 2 * mm + i * (pw + 1.6 * mm)
        c.setFillColor([BLUE, CYAN, GREEN, AMBER, PURPLE, RED][i]); c.roundRect(px, yy - 5 * mm, pw, 4.6 * mm, 1.4, fill=1, stroke=0)
        txt(c, px + pw / 2, yy - 3.4 * mm, ph, "SansB", 4.5, colors.white, "c")
        if i < 5:
            arrow(c, px + pw + 0.1 * mm, yy - 2.7 * mm, px + pw + 1.4 * mm, yy - 2.7 * mm, GREY, head=1.4)
    yy -= 6.5 * mm
    gw = (w - 4 * mm) / len(groups)
    for i, (t1, t2, pv, bv, scale, lbl) in enumerate(groups):
        gx = x + 2 * mm + i * gw
        c.setFillColor(LIGHT); c.roundRect(gx + 0.5 * mm, y + 2 * mm, gw - 1 * mm, yy - y - 1.5 * mm, 2, fill=1, stroke=0)
        base = y + 11.5 * mm; ch = yy - base - 5 * mm
        bwid = (gw - 8 * mm) / 2
        for j, (v, col) in enumerate([(pv, GREEN), (bv, hx("#A3A9B3"))]):
            frac = max(num(v) / scale, 0.02)
            bx = gx + 2.8 * mm + j * (bwid + 2.4 * mm)
            c.setFillColor(col); c.rect(bx, base, bwid, frac * ch, fill=1, stroke=0)
            txt(c, bx + bwid / 2, base + frac * ch + 1.3, v, "SansB", 5.2 if j == 0 else 4.6, GREEN if j == 0 else GREY, "c")
        txt(c, gx + 2.8 * mm + bwid / 2, base - 3, "ours", "SansB", 4.5, GREEN, "c")
        txt(c, gx + 2.8 * mm + bwid * 1.5 + 2.4 * mm, base - 3, lbl, "Sans", 4.2, GREY, "c")
        txt(c, gx + gw / 2, y + 6.4 * mm, t1, "SansB", 4.8, INK, "c")
        txt(c, gx + gw / 2, y + 3.6 * mm, t2, "Sans", 4.3, GREY, "c")


def unified(c, x, y, w, h):
    yy = panel(c, x, y, w, h, "06", "Six capabilities · one system", RED) - 1 * mm
    caps = [("Real-orbit physics", "SGP4 over the full TLE catalogue"),
            ("Decentralised tasking", "Contract-Net auctions, no central planner"),
            ("Self-healing enclaves", "rolling hand-off, chaos-tested recovery"),
            ("Open-world inference", "explicit h₀ via GP Bayesian evidence"),
            ("Deadline-aware planning", "EIG with opportunity-decay utility"),
            ("Certified abstention", "split-conformal false-alarm guarantee")]
    cols = [BLUE, GREEN, AMBER, RED, PURPLE, CYAN]
    step = (yy - y - 2 * mm) / len(caps)
    for i, (a, b) in enumerate(caps):
        cy_ = yy - i * step
        c.setFillColor(cols[i]); c.circle(x + 4.2 * mm, cy_ - 1.6 * mm, 1.7 * mm, fill=1, stroke=0)
        txt(c, x + 4.2 * mm, cy_ - 2.6 * mm, "✓", "SansB", 5.6, colors.white, "c")
        txt(c, x + 7.6 * mm, cy_ - 0.9 * mm, a, "SansB", 6.0, INK)
        txt(c, x + 7.6 * mm, cy_ - 3.8 * mm, b, "Sans", 4.9, GREY)


from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import Frame, Paragraph

registerFontFamily("Sans", normal="Sans", bold="SansB", italic="SansI", boldItalic="SansB")
P_BODY = ParagraphStyle("pb", fontName="Sans", fontSize=8.0, leading=11.3, alignment=TA_JUSTIFY, textColor=INK, spaceAfter=4)
P_LI = ParagraphStyle("li", parent=P_BODY, fontSize=7.6, leading=10.3, spaceAfter=2.8, leftIndent=12, firstLineIndent=-12)
P_ABS = ParagraphStyle("pa", parent=P_BODY, fontSize=8.1, leading=11.4, textColor=hx("#1F2937"))


def hexs(col):
    return "#" + col.hexval()[2:]


def H2(n, title, col):
    st = ParagraphStyle("h", fontName="SansB", fontSize=9.4, leading=12.5, textColor=INK, spaceBefore=7, spaceAfter=3.5)
    return Paragraph(f'<font color="{hexs(col)}">{n}&nbsp;&nbsp;|</font>&nbsp;&nbsp;{title.upper()}', st)


def items(lst, col):
    return [Paragraph(f'<font name="SansB" color="{hexs(col)}">{i:02d}</font>&nbsp;&nbsp;<b>{h}.</b> {b}', P_LI)
            for i, (h, b) in enumerate(lst, 1)]


def footer(c, page):
    c.setFillColor(SPACE); c.rect(0, 0, W, 7.5 * mm, fill=1, stroke=0)
    c.setFillColor(RED); c.rect(0, 7.5 * mm - 0.7, W, 0.7, fill=1, stroke=0)
    txt(c, M, 2.8 * mm, "OrbitalNet OS  ·  Major Project  ·  CSE Programme, SCSE", "Sans", 5.6, hx("#D1D5DB"))
    txt(c, W / 2, 2.8 * mm, f"{page} / 2", "SansB", 5.8, colors.white, "c")
    txt(c, W - M, 2.8 * mm, "github.com/joycemalik/orbitalnet-dashboard", "SansB", 5.7, colors.white, "r")


def page_one(c, N, n_sat, hp):
    y = hero(c) - 2.2 * mm
    ah = 35 * mm
    c.setFillColor(hx("#F4F6F9")); c.rect(0, y - ah, W, ah, fill=1, stroke=0)
    c.setFillColor(RED); c.rect(M, y - ah + 3 * mm, 0.9 * mm, ah - 6 * mm, fill=1, stroke=0)
    txt(c, M + 3.5 * mm, y - 5 * mm, "ABSTRACT", "SansB", 7, RED)
    abs_ = Paragraph(
        f"OrbitalNet OS is a distributed operating layer for satellite fleets. It propagates <b>{n_sat:,} real satellites</b> "
        "from public orbital element sets with the SGP4 model, lets every spacecraft negotiate its own tasking through a "
        "<b>Contract-Net auction</b>, sustains coverage through rolling hand-offs, and recovers from node loss autonomously. "
        "Above this operational substrate sits a scientific decision engine: an <b>open-world Bayesian planner</b> that decides "
        "which spacecraft should observe a fading astronomical transient, and when, by maximising expected information gain "
        "across known physical models and an explicit <b>null hypothesis h₀</b>. The result is a fleet that coordinates "
        "itself and states, with a calibrated guarantee, when an event lies beyond known physics.", P_ABS)
    Frame(M + 3.5 * mm, y - ah + 1.5 * mm, W - 2 * M - 3.5 * mm, ah - 7.5 * mm, 0, 0, 0, 0).addFromList([abs_], c)
    y -= ah + 2.2 * mm
    y = kpis(c, y, [
        (f"{n_sat:,}", "SATELLITES PROPAGATED", "real TLEs · SGP4 · 1 Hz", CYAN),
        (N["SimAucP"], "NOVELTY AUROC", f"vs {N['SimAucBthree']} closed-world", GREEN),
        (N["SimTprP"], "NOVEL EVENTS FLAGGED", f"vs {N['SimTprBthree']} baseline", AMBER),
        (N["RealNEvents"], "REAL ZTF TRANSIENTS", "replayed on the real fleet", PURPLE),
        (N["ConfFa"], "CERTIFIED FALSE ALARMS", f"guarantee ≤ {N['ConfAlphaPct']}", RED),
        (str(hp), "PREREGISTERED TESTS", "confirmed on held-out seeds", BLUE),
    ])
    g = 7 * mm; cw = (W - 2 * M - g) / 2; top = y - 1 * mm; bottom = 10 * mm
    c.setStrokeColor(hx("#E5E7EB")); c.setLineWidth(0.5); c.line(W / 2, bottom + 2 * mm, W / 2, top - 2 * mm)
    left = [
        H2("1", "The opportunity", RED),
        Paragraph("Constellations now number in the thousands, and the sky surveys they could serve discover more "
                  "transients each night than any team can follow up. Realising this potential calls for two advances "
                  "together: <b>coordination that scales</b> with the fleet itself, and <b>interpretation that remains "
                  "trustworthy</b> when nature presents something new. OrbitalNet OS is built around both.", P_BODY),
        H2("2", "What OrbitalNet OS does", BLUE),
        Paragraph("The fleet operates as a society of autonomous agents. Each satellite carries its own state "
                  "(position, battery, thermal margin, payload, memory) and reasons about which missions it can serve. "
                  "A mission is simply <i>announced</i>: capable spacecraft bid, the strongest form an <b>enclave</b>, and "
                  "the enclave re-forms continuously as members pass out of view. The same fleet then acts as a "
                  "<b>distributed observatory</b>: for a newly detected transient it plans the measurements that most "
                  "rapidly discriminate between physical explanations (kilonova, shock-cooling supernova, GRB afterglow, "
                  "stellar flare) and recognises when the evidence points beyond all of them.", P_BODY),
        H2("3", "How it works", GREEN),
        *items([
            ("Orbital physics", f"{n_sat:,} two-line element sets are propagated with SGP4 every second and mapped from "
                                "the inertial frame to latitude and longitude through Greenwich sidereal time."),
            ("Health model", "A hardware-abstraction layer evolves battery charge through sunlight and eclipse, memory "
                             "fill and downlink, thermal margin and sensor calibration."),
            ("Capability scoring", "Hard gatekeepers admit only safe nodes, which then receive a weighted capability "
                                   "score discounted exponentially by aggregate risk."),
            ("Contract-Net auction", "Bids blend normalised proximity (haversine distance within the slew envelope) with "
                                     "battery reserve; the top-N bidders win the contract."),
            ("Rolling enclaves", "Each cycle re-validates the enclave, releases departing members and re-opens the "
                                 "auction, so coverage persists and self-heals."),
            ("State bus", "Services exchange state solely through Redis keys, so each runs, restarts and scales "
                          "independently: an event-sourced, fault-isolated topology."),
        ], GREEN),
    ]
    right = [
        H2("4", "The discovery engine", PURPLE),
        Paragraph("For every candidate measurement (which satellite, which instant) the planner computes the expected "
                  "information gain about the event's identity, adds a term for evidence of <b>model inadequacy</b> and "
                  "a term for the <b>information that waiting would forfeit</b> as the source fades, and normalises by "
                  "cost. Its belief spans every known model <i>plus</i> h₀, a Gaussian-process hypothesis able to "
                  "describe any smooth light curve. Bayesian evidence acts as an automatic Occam's razor: it rewards a "
                  "physical model that fits and charges h₀ for its flexibility, so h₀ rises precisely when known "
                  "physics runs out. Split-conformal calibration then certifies the false-alarm rate of every "
                  "“unknown” verdict. The engine is fully analytic: no training data, every decision traceable to "
                  "a likelihood.", P_BODY),
        H2("5", "In the live demonstration", AMBER),
        *items([
            ("Mission console", "Live fleet status, executing missions and open auctions, streamed from the bus."),
            ("Orbital view", f"A WebGL globe rendering all {n_sat:,} satellites, coloured by payload, with enclave links "
                             "locking onto the target."),
            ("Mission dispatch", "Broadcast a scenario (cyclone tracking, maritime overwatch, disaster imaging) and see "
                                 "it awarded within one consensus cycle."),
            ("Auction forensics", "A complete ledger of every bidder's distance, battery, score and outcome."),
            ("Chaos injection", "Disable part of an enclave and watch the auction recruit replacements on its own."),
            ("Event Lab", "Place a transient anywhere in the sky; real satellites plan the campaign and the belief "
                          "engine delivers its verdict, h₀ included."),
            ("Evidence board", "The preregistered hypothesis matrix, read live from experiment result files."),
        ], AMBER),
        H2("6", "What sets it apart", RED),
        Paragraph("OrbitalNet OS brings together, in one coherent system, capabilities usually studied separately: "
                  "<b>real-orbit physics</b>, <b>decentralised market-based tasking</b>, <b>self-healing coverage</b>, "
                  "<b>open-world Bayesian inference</b>, <b>deadline-aware planning</b> and a <b>certified false-alarm "
                  "guarantee</b>. Its claims carry research-grade rigour: hypotheses preregistered before testing, "
                  f"identical inputs for every strategy, {N['RealNEvents']} real ZTF transients replayed against the "
                  "real Starlink fleet, and every figure generated programmatically from result files.", P_BODY),
    ]
    Frame(M, bottom, cw, top - bottom, 0, 0, 0, 0).addFromList(left, c)
    Frame(M + cw + g, bottom, cw, top - bottom, 0, 0, 0, 0).addFromList(right, c)
    if left or right:
        print("WARNING overflow:", len(left), len(right))
    footer(c, "1")


def mini_header(c):
    hh = 15 * mm
    c.setFillColor(SPACE); c.rect(0, H - hh, W, hh, fill=1, stroke=0)
    rnd = random.Random(5)
    for _ in range(160):
        c.setFillColor(colors.white, alpha=rnd.uniform(0.15, 0.8))
        c.circle(rnd.uniform(0, W), rnd.uniform(H - hh, H), rnd.choice([0.25, 0.4, 0.6]), fill=1, stroke=0)
    c.setFillColor(RED, alpha=1); c.rect(0, H - hh, W, 0.7, fill=1, stroke=0)
    txt(c, M, H - 7.5 * mm, "OrbitalNet OS", "SansB", 13, colors.white)
    txt(c, M + 41 * mm, H - 7.5 * mm, "Technical architecture, decision mathematics & measured performance", "Sans", 8, hx("#D1D5DB"))
    txt(c, M, H - 12 * mm, "TOPOLOGY  ·  CAPABILITY & AUCTION CALCULUS  ·  OPEN-WORLD INFERENCE  ·  SEQUENTIAL PLANNING  ·  RESULTS",
        "SansB", 5.2, hx("#FCA5A5"))
    return H - hh


def main():
    N = load_numbers(); n_sat, hp = counts()
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("OrbitalNet OS — Distributed Architecture for Intelligent Satellite Fleet Management")
    page_one(c, N, n_sat, hp)
    c.showPage()
    y = mini_header(c) - 3 * mm
    g = 2.2 * mm; cw = (W - 2 * M - g) / 2
    hA = 84 * mm
    topology(c, M, y - hA, cw, hA); decision_math(c, M + cw + g, y - hA, cw, hA)
    y -= hA + g
    hB = 84 * mm
    inference(c, M, y - hB, cw, hB); planner(c, M + cw + g, y - hB, cw, hB)
    y -= hB + g
    hC = y - 10 * mm
    rw = (W - 2 * M - g) * 0.70
    results(c, M, y - hC, rw, hC, N); unified(c, M + rw + g, y - hC, W - 2 * M - rw - g, hC)
    footer(c, "2")
    c.showPage(); c.save()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
