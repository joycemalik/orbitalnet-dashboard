"""Builds materials/OrbitalNet_Deck.pptx (+ .pdf via PowerPoint) — 13-slide project presentation.

Illustrations: materials/deck/figs.tex (TikZ, compiled here). Metrics: research/papers/main/generated/numbers.tex
(generated from research/results/) and satellites.txt. No result number is typed by hand.
Run: python materials/deck/build_deck.py
"""
import re
import shutil
import subprocess
from pathlib import Path

import pymupdf
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "materials" / "deck"
BUILD = DECK / "build"
ASSETS = DECK / "assets"
NUMS = ROOT / "research" / "papers" / "main" / "generated" / "numbers.tex"
OUT = ROOT / "materials" / "OrbitalNet_Deck.pptx"

C = {k: RGBColor.from_string(v) for k, v in dict(
    navy="0B2545", space="050914", ink="14161B", grey="5B6270", light="F3F6FA", white="FFFFFF",
    sky="0EA5E9", cy="22D3EE", amb="F59E0B", grn="16A34A", rd="DC2626", vio="7C3AED").items()}
FONT = "Segoe UI"
SW, SH = Inches(13.333), Inches(7.5)


# ── data + figures ──────────────────────────────────────────────────────────
def numbers():
    d = {}
    for k, v in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", NUMS.read_text(encoding="utf-8")):
        d[k] = v.replace("\\%", "%").replace("--", "–").replace("\\,", " ")
    return d


def n_sats():
    lines = [l for l in (ROOT / "mission_control" / "data" / "satellites.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    return f"{len(lines) // 3:,}"


def build_figs(N):
    BUILD.mkdir(parents=True, exist_ok=True)
    shutil.copy(NUMS, BUILD / "numbers.tex")
    mid = lambda k: (lambda v: sum(v) / len(v))([float(x) for x in re.findall(r"\d*\.?\d+", N[k])])
    v = [r"\newcommand{\NSat}{" + n_sats().replace(",", "{,}") + "}"]
    for k in ["SimAucP", "SimAucBthree", "SimTprP", "SimTprBthree", "SimCwWhP", "SimCwWhBthree",
              "RealCCwWhP", "RealCCwWhBthree"]:
        v.append(rf"\newcommand{{\v{k}}}{{{mid(k) / (100 if '%' in N[k] else 1):.3f}}}")
    (BUILD / "vars.tex").write_text("\n".join(v) + "\n", encoding="utf-8")
    shutil.copy(DECK / "figs.tex", BUILD / "figs.tex")
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "figs.tex"], cwd=BUILD, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    names = ["hero", "cnp", "enclave", "h0", "topology", "results"]
    doc = pymupdf.open(BUILD / "figs.pdf")
    out = {}
    for i, n in enumerate(names):
        p = BUILD / f"fig_{n}.png"
        doc[i].get_pixmap(dpi=110 if n == "hero" else 260).save(p)
        out[n] = p
    return out


# ── helpers ─────────────────────────────────────────────────────────────────
def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None):
    sh = s.shapes.add_shape(shape, x, y, w, h)
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = Pt(1)
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    sh.shadow.inherit = False
    return sh


def text(s, x, y, w, h, runs, size=16, color="ink", bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         spacing=1.1):
    """runs: str | list of paragraphs; a paragraph is str or list of (text, {opts})."""
    tb = s.shapes.add_textbox(x, y, w, h); tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.line_spacing = spacing
        for t, o in ([(para, {})] if isinstance(para, str) else para):
            r = p.add_run(); r.text = t
            f = r.font; f.name = FONT; f.size = Pt(o.get("size", size)); f.bold = o.get("bold", bold)
            f.italic = o.get("italic", False); f.color.rgb = C[o.get("color", color)]
        if isinstance(para, list) and para and "space_after" in para[0][1]:
            p.space_after = Pt(para[0][1]["space_after"])
    return tb


def pic(s, path, x, y, w=None, h=None):
    return s.shapes.add_picture(str(path), x, y, w, h)


def header(s, num, title, kicker, accent="sky"):
    rect(s, 0, 0, SW, SH, C["white"])
    rect(s, 0, 0, SW, Inches(0.09), C[accent])
    text(s, Inches(0.6), Inches(0.32), Inches(1), Inches(0.5), f"{num:02d}", 20, accent, True)
    text(s, Inches(1.25), Inches(0.28), Inches(11), Inches(0.6), title, 28, "navy", True)
    text(s, Inches(1.27), Inches(0.86), Inches(11.5), Inches(0.4), kicker, 13, "grey")
    footer(s, num)


def footer(s, num, dark=False):
    col = "cy" if dark else "grey"
    text(s, Inches(0.6), Inches(7.05), Inches(8), Inches(0.3), "OrbitalNet OS  ·  CSE Programme, SCSE  ·  Dr. AIT", 10, col)
    text(s, Inches(11.7), Inches(7.05), Inches(1.1), Inches(0.3), str(num), 10, col, True, PP_ALIGN.RIGHT)


def card(s, x, y, w, h, accent, title, body, title_size=15, body_size=12, fill="light"):
    rect(s, x, y, w, h, C[fill], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    rect(s, x, y + Inches(0.12), Inches(0.07), h - Inches(0.24), C[accent])
    text(s, x + Inches(0.22), y + Inches(0.12), w - Inches(0.35), Inches(0.45), title, title_size, accent, True)
    text(s, x + Inches(0.22), y + Inches(0.52), w - Inches(0.35), h - Inches(0.6), body, body_size, "ink", spacing=1.15)


def kpi(s, x, y, w, h, value, label, sub, accent):
    rect(s, x, y, w, h, C["navy"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    rect(s, x, y + h - Inches(0.07), w, Inches(0.07), C[accent])
    text(s, x + Inches(0.2), y + Inches(0.05), w - Inches(0.3), Inches(0.6), value, 28, "white", True)
    text(s, x + Inches(0.2), y + Inches(0.62), w - Inches(0.3), Inches(0.3), label, 11, "cy", True)
    text(s, x + Inches(0.2), y + Inches(0.86), w - Inches(0.3), Inches(0.3), sub, 10, "white")


def bullets(s, x, y, w, h, items, accent="sky", size=15):
    paras = []
    for head, body in items:
        paras.append([("▸  ", {"color": accent, "bold": True, "space_after": 9}), (head, {"bold": True, "color": "navy"}),
                      ("  " + body if body else "", {})])
    return text(s, x, y, w, h, paras, size, spacing=1.12)


def fit(path, max_w, max_h):
    from PIL import Image
    iw, ih = Image.open(path).size
    sc = min(max_w / iw, max_h / ih)
    return Emu(int(iw * sc)), Emu(int(ih * sc))


def place(s, path, x, y, max_w, max_h, center=True):
    w, h = fit(path, max_w, max_h)
    if center:
        x += (max_w - w) // 2; y += (max_h - h) // 2
    return pic(s, path, x, y, w, h)


# ── slides ──────────────────────────────────────────────────────────────────
def main():
    N = numbers(); sats = n_sats(); F = build_figs(N)
    prs = Presentation(); prs.slide_width, prs.slide_height = SW, SH
    blank = prs.slide_layouts[6]
    new = lambda: prs.slides.add_slide(blank)

    # 1 cover
    s = new()
    rect(s, 0, 0, SW, SH, C["white"])
    rect(s, Inches(0.3), Inches(0.3), SW - Inches(0.6), SH - Inches(0.6), C["white"], line=C["navy"])
    place(s, ASSETS / "cover_header.png", Inches(0.55), Inches(0.45), Inches(12.2), Inches(1.75))
    rect(s, Inches(0.55), Inches(2.3), Inches(12.23), Inches(0.04), C["navy"])
    text(s, Inches(0.5), Inches(2.45), Inches(12.3), Inches(0.4), "COMPUTER SCIENCE AND ENGINEERING PROGRAMME", 15, "amb", True, PP_ALIGN.CENTER)
    text(s, Inches(0.5), Inches(2.85), Inches(12.3), Inches(0.7),
         ["Project Evaluation and Selection Process", "for the 10th National Techno Exhibition – 2026"], 14, "navy", False, PP_ALIGN.CENTER)
    rect(s, Inches(1.2), Inches(3.65), Inches(10.9), Inches(1.0), C["navy"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
    text(s, Inches(1.3), Inches(3.68), Inches(10.7), Inches(0.95),
         [[("OrbitalNet OS", {"size": 26, "bold": True, "color": "white"})],
          [("Distributed Architecture for Intelligent Satellite Fleet Management", {"size": 15, "color": "cy"})]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)
    team = [("Joyce Malik", "1DA23CS069"), ("Moghitha B", "1DA23CS111"), ("Swathi Sathish", "1DA23CS204"), ("Anup H", "1DA23CS207")]
    text(s, Inches(0.9), Inches(4.95), Inches(5.5), Inches(0.4), "TEAM MEMBERS", 13, "rd", True)
    for i, (n, u) in enumerate(team):
        text(s, Inches(0.9), Inches(5.35 + i * 0.36), Inches(3), Inches(0.36), n, 14, "ink", True)
        text(s, Inches(3.4), Inches(5.35 + i * 0.36), Inches(2.4), Inches(0.36), u, 14, "grey")
    text(s, Inches(6.9), Inches(4.95), Inches(5.6), Inches(0.4), "UNDER THE GUIDANCE OF", 13, "rd", True)
    for i, g in enumerate(["Dr. SMITHA SHEKAR B", "Dr. HARISH G"]):
        text(s, Inches(6.9), Inches(5.35 + i * 0.75), Inches(5.6), Inches(0.75),
             [[(g, {"bold": True, "size": 14})], [("Professor, CSE Programme, SCSE, Dr. AIT, Bengaluru", {"size": 12, "color": "grey"})]], spacing=1.0)

    # 2 hero
    s = new(); pic(s, F["hero"], 0, 0, SW, SH)
    rect(s, Inches(0.7), Inches(1.15), Inches(0.9), Inches(0.08), C["rd"])
    text(s, Inches(0.7), Inches(1.3), Inches(8), Inches(0.4), "MAJOR PROJECT  ·  SCHOOL OF CSE", 13, "white", True)
    text(s, Inches(0.65), Inches(1.75), Inches(9), Inches(1.2), "OrbitalNet OS", 60, "white", True)
    text(s, Inches(0.7), Inches(2.95), Inches(7.5), Inches(1), "Distributed Architecture for Intelligent Satellite Fleet Management", 22, "cy")
    text(s, Inches(0.7), Inches(4.15), Inches(6.8), Inches(1.2),
         "A fleet that negotiates its own missions, heals its own coverage, and knows when it is looking at something new.",
         16, "white", spacing=1.2)
    text(s, Inches(0.7), Inches(5.6), Inches(7), Inches(0.4), "JOYCE MALIK  ·  MOGHITHA B  ·  SWATHI SATHISH  ·  ANUP H", 13, "white", True)
    text(s, Inches(0.7), Inches(5.95), Inches(7), Inches(0.4), "Guides: Dr. SMITHA SHEKAR B  ·  Dr. HARISH G", 12, "cy")

    # 3 abstract + agenda
    s = new(); header(s, 3, "Abstract", "From ground-scripted satellites to a self-organising fleet", "rd")
    text(s, Inches(0.8), Inches(1.55), Inches(7.2), Inches(4.6), [
        [("OrbitalNet OS", {"bold": True, "color": "navy"}),
         (f" is a distributed operating layer for satellite fleets. It propagates {sats} real satellites with SGP4 and lets "
          "each spacecraft negotiate its own tasking through a ", {}), ("Contract-Net auction", {"bold": True}),
         (", sustaining coverage with rolling hand-offs and autonomous recovery.", {"space_after": 14})],
        [("On top sits a scientific decision engine: an ", {}), ("open-world Bayesian planner", {"bold": True}),
         (" that decides which satellite observes a fading transient, and when, while keeping an explicit "
          "“none of the above” hypothesis ", {}), ("h₀", {"bold": True, "color": "rd"}),
         (" so it can recognise genuinely new events.", {})],
    ], 17, spacing=1.3)
    agenda = [("Problem & objectives", "sky"), ("Architecture & stack", "vio"), ("Auction & decision maths", "grn"),
              ("Rolling enclaves", "amb"), ("Discovering the unknown (h₀)", "rd"), ("Live demo", "sky"),
              ("Results", "grn"), ("Applications & future", "vio")]
    rect(s, Inches(8.5), Inches(1.5), Inches(4.3), Inches(5.3), C["light"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    text(s, Inches(8.8), Inches(1.65), Inches(4), Inches(0.4), "AGENDA", 13, "grey", True)
    for i, (a, col) in enumerate(agenda):
        y = Inches(2.15 + i * 0.57)
        rect(s, Inches(8.8), y, Inches(0.42), Inches(0.42), C[col], shape=MSO_SHAPE.OVAL)
        text(s, Inches(8.8), y, Inches(0.42), Inches(0.42), str(i + 1), 13, "white", True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
        text(s, Inches(9.4), y, Inches(3.3), Inches(0.42), a, 15, "navy", True, anchor=MSO_ANCHOR.MIDDLE)

    # 4 problem -> solution
    s = new(); header(s, 4, "The Shift: From Ground Control to Fleet Intelligence", "Three limits of scripted operations, and how OrbitalNet OS answers each", "rd")
    rows = [("Centralised bottleneck", "Every decision waits for a ground pass; operators script each satellite.",
             "Intent-based tasking", "Ground announces a goal; satellites bid and self-assign in one consensus cycle."),
            ("Single point of failure", "One lost link or node interrupts the mission.",
             "Self-healing enclaves", "Rolling hand-offs and re-auctions keep coverage alive automatically."),
            ("Closed-world interpretation", "Classifiers force every event into a known class.",
             "Open-world inference", "An explicit h₀ hypothesis flags events beyond known physics, with a certified false-alarm rate.")]
    for i, (p, pb, so, sb) in enumerate(rows):
        y = Inches(1.6 + i * 1.75)
        card(s, Inches(0.7), y, Inches(5.3), Inches(1.5), "grey", p, pb, 17, 14)
        arr = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(6.2), y + Inches(0.5), Inches(0.9), Inches(0.5))
        arr.fill.solid(); arr.fill.fore_color.rgb = C[["sky", "grn", "rd"][i]]; arr.line.fill.background()
        card(s, Inches(7.3), y, Inches(5.3), Inches(1.5), ["sky", "grn", "rd"][i], so, sb, 17, 14)

    # 5 objectives
    s = new(); header(s, 5, "Objectives", "What the system set out to achieve, and does", "sky")
    objs = [("01", "Autonomous allocation", "Replace manual scripting with goal-based missions that the fleet allocates itself.", "sky"),
            ("02", "Physics-grounded decisions", f"Drive every choice from real orbits: {sats} satellites propagated with SGP4.", "vio"),
            ("03", "Resilience by design", "Survive node loss and link churn through leader election, re-auction and hand-off.", "grn"),
            ("04", "Trustworthy discovery", "Plan observations of fading transients and recognise novel events with calibrated confidence.", "rd")]
    for i, (n, t, b, col) in enumerate(objs):
        x = Inches(0.7 + i * 3.08)
        rect(s, x, Inches(1.7), Inches(2.85), Inches(4.9), C["light"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
        rect(s, x, Inches(1.7), Inches(2.85), Inches(0.1), C[col])
        text(s, x + Inches(0.3), Inches(2.0), Inches(2.4), Inches(1), n, 44, col, True)
        text(s, x + Inches(0.3), Inches(3.1), Inches(2.4), Inches(1), t, 19, "navy", True, spacing=1.05)
        text(s, x + Inches(0.3), Inches(4.15), Inches(2.4), Inches(2.3), b, 14, "ink", spacing=1.25)

    # 6 architecture + stack
    s = new(); header(s, 6, "System Architecture", "Event-sourced microservices that share state only through a Redis bus", "vio")
    place(s, F["topology"], Inches(0.5), Inches(1.4), Inches(7.6), Inches(5.5))
    bullets(s, Inches(8.4), Inches(1.6), Inches(4.5), Inches(3.2), [
        ("Decoupled.", "Services never call each other; each can crash and restart independently."),
        ("Real time.", "Physics at 1 Hz, streamed to a WebGL globe over WebSockets."),
        ("Auditable.", "Every bid and award is written to an auction ledger."),
    ], "vio", 14)
    stack = [("Python", "sky"), ("SGP4", "vio"), ("Redis / Memurai", "rd"), ("asyncio WebSockets", "amb"),
             ("Three.js / WebGL", "navy"), ("Streamlit", "rd"), ("NumPy · SciPy · GP", "grn"), ("pytest", "grey")]
    for i, (t, col) in enumerate(stack):
        x = Inches(8.4 + (i % 2) * 2.25); y = Inches(4.75 + (i // 2) * 0.52)
        rect(s, x, y, Inches(2.1), Inches(0.42), C[col], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3)
        text(s, x, y, Inches(2.1), Inches(0.42), t, 12, "white", True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)

    # 7 CNP + maths
    s = new(); header(s, 7, "How the Fleet Talks: Contract Net Protocol", "One announcement, local filtering, competitive bids, award and hand-off", "grn")
    place(s, F["cnp"], Inches(0.5), Inches(1.45), Inches(7.4), Inches(4.0))
    text(s, Inches(0.6), Inches(5.6), Inches(7.2), Inches(1.3), [
        [("Feasibility gate: ", {"bold": True, "color": "vio"}), ("haversine distance  D ≤ D_max  (target radius + slew envelope)", {})],
        [("Bid: ", {"bold": True, "color": "vio"}), ("U = w_prox · (D_max − D)/D_max  +  w_batt · SoC", {})],
        [("Award: ", {"bold": True, "color": "grn"}), ("top-N bids form the enclave; plane leaders run the auction", {})],
    ], 14, spacing=1.35)
    card(s, Inches(8.3), Inches(1.55), Inches(4.5), Inches(2.45), "vio", "Capability score",
         "Hard gatekeepers (battery, thermal, wheels, calibration, conjunction) admit safe nodes; the weighted score is discounted by risk:  C · e^(−λR).", 17, 13)
    card(s, Inches(8.3), Inches(4.2), Inches(4.5), Inches(2.6), "grn", "Why it scales",
         "Each satellite evaluates only itself; the ground sends one message instead of thousands of scripts. Decisions are local, fast and logged.", 17, 13)

    # 8 rolling enclaves
    s = new(); header(s, 8, "Rolling Enclaves & Self-Healing", "Coverage that continues as satellites move at about 7.5 km/s", "amb")
    place(s, F["enclave"], Inches(0.5), Inches(1.4), Inches(7.6), Inches(3.6))
    text(s, Inches(0.7), Inches(5.2), Inches(7.3), Inches(1.6),
         "As the active node recedes its bid U falls; the approaching node's U overtakes it and the enclave hands off over an "
         "inter-satellite link. Each cycle re-validates members and re-opens the auction for any gap.", 15, spacing=1.3)
    card(s, Inches(8.4), Inches(1.55), Inches(4.4), Inches(1.6), "rd", "Chaos injection",
         "Disable part of an enclave live; the auction recruits replacements on its own.", 17, 13)
    card(s, Inches(8.4), Inches(3.35), Inches(4.4), Inches(1.6), "sky", "Leader election",
         "Each orbital plane elects its most capable node, so the fleet divides work without a master.", 17, 13)
    card(s, Inches(8.4), Inches(5.15), Inches(4.4), Inches(1.65), "grn", "Fault isolation",
         "Services share state only via Redis, so a crash in one never stops the others.", 17, 13)

    # 9 h0
    s = new(); header(s, 9, "Seeing the Unknown: hypothesis h₀", "Open-world Bayesian planning for fading astronomical transients", "rd")
    place(s, F["h0"], Inches(0.5), Inches(1.5), Inches(7.6), Inches(4.3))
    text(s, Inches(0.7), Inches(6.0), Inches(7.4), Inches(0.8),
         "Schematic: data that a known model misfits are explained by h₀, and the posterior shifts to h₀.", 12, "grey")
    bullets(s, Inches(8.4), Inches(1.6), Inches(4.5), Inches(5.2), [
        ("Open hypothesis space.", "Known physics (kilonova, shock-cooling, GRB, flare) plus h₀, a Gaussian process for any smooth light curve."),
        ("Occam's razor, built in.", "Bayesian evidence rewards a model that fits; h₀ rises only when none do. No training data."),
        ("Planning under fading.", "Pick the satellite and moment that maximise expected information gain before the source fades."),
        ("Certified.", "Split-conformal calibration bounds the false-alarm rate of every “unknown” verdict."),
    ], "rd", 14)

    # 10 demo
    s = new(); header(s, 10, "Live Demonstration", "What the audience sees, screen by screen", "sky")
    place(s, ASSETS / "demo_dashboard.png", Inches(0.6), Inches(1.5), Inches(6.6), Inches(3.2))
    text(s, Inches(0.6), Inches(4.75), Inches(6.6), Inches(0.35), "Mission console: live bids and orbital tracking", 11, "grey", align=PP_ALIGN.CENTER)
    tiles = [("Orbital view", f"WebGL globe of all {sats} satellites with enclave links", "sky"),
             ("Mission dispatch", "Broadcast cyclone, maritime or disaster missions", "grn"),
             ("Auction forensics", "Every bidder's distance, battery, score and outcome", "vio"),
             ("Chaos & self-heal", "Knock out nodes, watch replacements win", "rd"),
             ("Event Lab", "Inject a transient; the fleet plans it and returns a verdict", "amb"),
             ("Evidence board", "Preregistered hypothesis matrix, read live", "navy")]
    for i, (t, b, col) in enumerate(tiles):
        x = Inches(7.5 + (i % 2) * 2.7); y = Inches(1.5 + (i // 2) * 1.75)
        card(s, x, y, Inches(2.55), Inches(1.6), col, t, b, 15, 12)
    text(s, Inches(0.6), Inches(5.3), Inches(6.6), Inches(1.4), [
        [("Run it: ", {"bold": True, "color": "sky"}), ("python boot_os.py", {"bold": True})],
        [("Boots physics → streamer → consensus → console, all coordinating through Redis.", {"color": "grey"})]], 14, spacing=1.3)

    # 11 results
    s = new(); header(s, 11, "Results", "Preregistered hypotheses, identical inputs for every strategy, held-out test seeds", "grn")
    ks = [(N["SimAucP"], "NOVELTY AUROC", f"vs {N['SimAucBthree']} closed-world", "grn"),
          (N["SimTprP"], "NOVEL EVENTS FLAGGED", f"vs {N['SimTprBthree']} baseline, 5% FA", "amb"),
          (N["RealNEvents"], "REAL ZTF TRANSIENTS", f"AUROC {N['RealCAuc']}", "vio"),
          (N["ConfFa"], "CERTIFIED FALSE ALARMS", f"bound {N['ConfAlphaPct']}", "rd")]
    for i, (v, l, sub, col) in enumerate(ks):
        kpi(s, Inches(0.7), Inches(1.5 + i * 1.33), Inches(3.4), Inches(1.2), v, l, sub, col)
    place(s, F["results"], Inches(4.4), Inches(1.45), Inches(8.5), Inches(4.75))
    text(s, Inches(4.5), Inches(6.25), Inches(8.3), Inches(0.6),
         "Higher is better for the first two groups; lower is better for confident errors. Every figure is generated from result files.",
         12, "grey", align=PP_ALIGN.CENTER)

    # 12 applications + innovation
    s = new(); header(s, 12, "Applications & Innovation", "Where it applies, and what is new", "vio")
    apps = [("Mega-constellations", "One operator supervises thousands of satellites through onboard autonomy.", "sky"),
            ("Resilient operations", "Peer-to-peer tasking keeps missions running through link loss.", "grn"),
            ("Disaster response", "Tip-and-cue: cyclone, flood and maritime events tasked in one consensus cycle.", "amb"),
            ("Time-domain astronomy", "Rapid follow-up of transients, with novelty flagged reliably.", "rd")]
    for i, (t, b, col) in enumerate(apps):
        x = Inches(0.7 + (i % 2) * 3.15); y = Inches(1.55 + (i // 2) * 2.05)
        card(s, x, y, Inches(3.0), Inches(1.85), col, t, b, 15, 13)
    rect(s, Inches(7.2), Inches(1.55), Inches(5.6), Inches(3.95), C["navy"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    text(s, Inches(7.5), Inches(1.7), Inches(5.1), Inches(0.5), "WHAT IS NEW", 13, "cy", True)
    bl = ["Real-orbit physics + market-based tasking in one system", "Self-healing coverage via rolling enclaves",
          "Explicit h₀ for open-world inference, without training data", "Deadline-aware planning under fading signals",
          "Certified false-alarm guarantee"]
    text(s, Inches(7.5), Inches(2.15), Inches(5.1), Inches(3.3),
         [[("✓  ", {"color": "grn", "bold": True, "space_after": 8}), (b, {"color": "white"})] for b in bl], 14, spacing=1.15)
    card(s, Inches(0.7), Inches(5.7), Inches(12.1), Inches(1.15), "vio", "Research output",
         f"Manuscripts prepared for the Journal of Astrophysics and Astronomy and Research Notes of the AAS; {N['RealNEvents']} real ZTF "
         "events evaluated; code and results open-sourced under the MIT licence.", 15, 13)

    # 13 future + thank you
    s = new()
    pic(s, F["hero"], 0, 0, SW, SH)
    rect(s, 0, 0, Inches(7.6), SH, C["space"]).fill.transparency = 0
    text(s, Inches(0.7), Inches(0.6), Inches(6.5), Inches(0.7), "Future Enhancements", 28, "white", True)
    road = [("Hardware-in-the-loop", "Run the agent on ESP32 / CubeSat flight computers.", "cy"),
            ("Industry-grade validation", "Cross-check against STK / GMAT simulations.", "amb"),
            ("Richer scoring engine", "Scale to 50+ parameters: power, thermal, latency, risk.", "grn"),
            ("Cross-fleet cooperation", "Tasking across operators and constellations.", "vio")]
    for i, (t, b, col) in enumerate(road):
        y = Inches(1.55 + i * 1.05)
        rect(s, Inches(0.75), y + Inches(0.08), Inches(0.3), Inches(0.3), C[col], shape=MSO_SHAPE.OVAL)
        if i < 3:
            rect(s, Inches(0.88), y + Inches(0.42), Inches(0.04), Inches(0.68), C["grey"])
        text(s, Inches(1.3), y, Inches(5.8), Inches(0.4), t, 17, col, True)
        text(s, Inches(1.3), y + Inches(0.4), Inches(5.8), Inches(0.5), b, 13, "white")
    text(s, Inches(0.7), Inches(5.95), Inches(6.5), Inches(0.8), "Thank You  ·  Questions?", 30, "white", True)
    text(s, Inches(0.7), Inches(6.65), Inches(6.5), Inches(0.4), "github.com/joycemalik/orbitalnet-dashboard", 13, "cy", True)

    prs.save(OUT)
    print("wrote", OUT, len(prs.slides), "slides")
    export_pdf()


def export_pdf():
    try:
        import comtypes.client
        pp = comtypes.client.CreateObject("PowerPoint.Application")
        deck = pp.Presentations.Open(str(OUT), WithWindow=False)
        deck.SaveAs(str(OUT.with_suffix(".pdf")), 32)
        deck.Close(); pp.Quit()
        print("wrote", OUT.with_suffix(".pdf"))
    except Exception as e:  # PowerPoint unavailable
        print("PDF export skipped:", e)


if __name__ == "__main__":
    main()
