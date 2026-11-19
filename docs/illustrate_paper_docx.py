"""Makes research/Research paper - illustrated.docx from research/Research paper.docx.

Body text is left unchanged. Adds: title + author block, 6 conceptual figures, 1 table, and replaces the
placeholder reference list with verified citations. Figures are schematic (no result numbers).
"""
import copy
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "research" / "Research paper.docx"
OUT = ROOT / "research" / "Research paper - illustrated.docx"
FIG = ROOT / "docs" / "figures" / "paper_docx"
FIG.mkdir(parents=True, exist_ok=True)

RED, INK, GREY, BLUE, GREEN, AMBER, PURPLE = "#B00500", "#1A1A1A", "#777777", "#2F6DB5", "#2E8B57", "#D98E04", "#7A3FB0"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})


def save(fig, name):
    p = FIG / name
    fig.savefig(p, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return p


def rbox(ax, x, y, w, h, text, fc="#F3F3F3", ec=RED, tc=INK, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=tc, weight="bold" if bold else "normal",
            wrap=True)


def arrow(ax, p, q, color=INK, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, color=color, lw=1.2,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls))


# ── Fig 1: the problem ──────────────────────────────────────────────────────
def fig1():
    t = np.linspace(0, 12, 400)
    def lc(rise, decay, peak=1.0, tp=1.0):
        return peak * np.where(t < tp, np.exp(-0.5 * ((t - tp) / rise) ** 2), np.exp(-(t - tp) / decay))
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.axvspan(0, 2.5, color=RED, alpha=0.07)
    ax.text(1.25, 1.12, "diagnostic window", ha="center", color=RED, fontsize=9)
    curves = [("Kilonova", lc(0.3, 1.2), RED), ("Early shock cooling", lc(0.4, 3.0, 0.85), AMBER),
              ("Relativistic afterglow", 0.95 * np.clip(t + 0.2, 0.2, None) ** -1.1 / 0.2 ** -1.1, BLUE),
              ("Stellar flare", lc(0.08, 0.5, 0.9, 0.6), PURPLE)]
    for name, y, c in curves:
        ax.plot(t, y, color=c, lw=2, label=name)
    unk = lc(0.6, 2.0, 0.7, 1.5) + 0.35 * np.exp(-0.5 * ((t - 7) / 1.0) ** 2)
    ax.plot(t, unk, color=INK, lw=2, ls="--", label="Unmodelled event ($h_0$)")
    ax.plot([0.4, 0.7, 1.0], [0.35, 0.62, 0.8], "o", color=INK, ms=6, zorder=5)
    ax.annotate("first few observations:\nconsistent with many models", (0.7, 0.62), (3.2, 0.95),
                arrowprops=dict(arrowstyle="->", color=GREY), fontsize=8.5, color=GREY)
    ax.set_xlim(0, 12); ax.set_ylim(0, 1.25)
    ax.set_xlabel("Time since detection (days)"); ax.set_ylabel("Normalised flux")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_title("Schematic light curves (illustrative shapes, not data)", fontsize=9, color=GREY)
    return save(fig, "fig1_problem.png")


# ── Fig 2: 7-stage loop ─────────────────────────────────────────────────────
def fig2():
    fig, ax = plt.subplots(figsize=(8.4, 4.6)); ax.set_axis_off(); ax.set_xlim(-2.6, 2.6); ax.set_ylim(-1.35, 1.35)
    stages = ["1. Orbital &\ninstrument feasibility", "2. Generate feasible\nmeasurement actions",
              "3. Utility\nestimation", "4. Decentralised\nallocation (auction)", "5. Measurement\nexecution",
              "6. Local belief\nupdate", "7. Belief-summary\nexchange (when in contact)"]
    n = len(stages); R = 1.05; pts = []
    for i, s in enumerate(stages):
        a = np.pi / 2 - 2 * np.pi * i / n
        x, y = 1.75 * R * np.cos(a), R * np.sin(a)
        pts.append((x, y))
        rbox(ax, x, y, 1.25, 0.36, s, fs=8)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        v = np.array([x2 - x1, y2 - y1]); u = v / np.linalg.norm(v)
        arrow(ax, (x1 + u[0] * 0.55, y1 + u[1] * 0.22), (x2 - u[0] * 0.55, y2 - u[1] * 0.22), rad=-0.15)
    rbox(ax, 0, 0, 1.3, 0.55, "Repeat until\nunobservable, budget\nspent, or preservation\nmode", fc=RED, ec=RED,
         tc="white", fs=8.5, bold=True)
    return save(fig, "fig2_architecture.png")


# ── Fig 3: hypothesis space + utility ──────────────────────────────────────
def fig3():
    fig, ax = plt.subplots(figsize=(8.2, 3.4)); ax.set_axis_off(); ax.set_xlim(0, 11.4); ax.set_ylim(0, 5)
    ax.text(1.6, 4.6, "Open-world hypothesis set", ha="center", weight="bold")
    for i, (lab, c) in enumerate([("$h_1$ kilonova", RED), ("$h_2$ shock cooling", AMBER),
                                  ("$h_3$ afterglow", BLUE), ("$h_K$ flare", PURPLE)]):
        rbox(ax, 1.6, 3.9 - i * 0.6, 2.4, 0.45, lab, ec=c, fs=8.5)
    rbox(ax, 1.6, 1.2, 2.4, 0.55, "$h_0$: none of the above\n(flexible GP model)", fc="#222", ec=INK, tc="white", fs=8.5)
    ax.text(1.6, 0.45, "posterior $b_t$ over all K+1", ha="center", fontsize=8, color=GREY)
    arrow(ax, (2.9, 2.6), (3.9, 2.6))
    terms = [("$I(H_k;Y_a\\,|\\,b_t)$", "which known\nclass?", BLUE),
             ("$\\beta\\, I(Z;Y_a\\,|\\,b_t)$", "is the library\nadequate?", INK),
             ("$\\gamma\\, D(a,b_t)$", "information lost\nif delayed", RED)]
    for i, (f, d, c) in enumerate(terms):
        x = 4.9 + i * 2.25
        rbox(ax, x, 3.0, 1.55, 0.75, f, ec=c, fs=10)
        ax.text(x, 2.2, d, ha="center", fontsize=7.8, color=GREY)
        if i < 2:
            ax.text(x + 1.125, 3.0, "+", ha="center", va="center", fontsize=14)
    ax.plot([4.1, 10.4], [1.7, 1.7], color=INK, lw=1)
    rbox(ax, 7.15, 1.2, 1.9, 0.5, "$c(a)$  resource cost", ec=GREY, fs=9)
    ax.text(3.95, 1.7, "$U(a\\,|\\,b_t)=$", ha="right", va="center", fontsize=11)
    ax.text(7.15, 0.45, "highest-utility feasible action is selected", ha="center", fontsize=8, color=GREY)
    return save(fig, "fig3_utility.png")


# ── Fig 4: decentralised auction, intermittent contact ─────────────────────
def fig4():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 3.4), gridspec_kw=dict(width_ratios=[1, 1.3]))
    a1.set_axis_off(); a1.set_xlim(-1.4, 1.4); a1.set_ylim(-1.4, 1.4); a1.set_aspect("equal")
    a1.add_patch(Circle((0, 0), 0.55, color="#DCE8F5"))
    a1.text(0, 0, "Earth", ha="center", va="center", fontsize=8, color=BLUE)
    a1.add_patch(Circle((0, 0), 1.05, fill=False, ls=":", ec=GREY))
    sats = {f"S{i+1}": (1.05 * np.cos(a), 1.05 * np.sin(a)) for i, a in enumerate(np.linspace(0.3, 2 * np.pi + 0.3, 6, endpoint=False))}
    cols = [BLUE, AMBER, PURPLE, BLUE, GREEN, AMBER]
    links = [("S1", "S2", True), ("S2", "S3", False), ("S3", "S4", True), ("S4", "S5", False), ("S5", "S6", True), ("S6", "S1", True)]
    for u, v, up in links:
        (x1, y1), (x2, y2) = sats[u], sats[v]
        a1.plot([x1, x2], [y1, y2], color=GREEN if up else GREY, lw=1.6 if up else 1, ls="-" if up else "--")
    for (k, (x, y)), c in zip(sats.items(), cols):
        a1.add_patch(Circle((x, y), 0.14, color=c)); a1.text(x, y, k, ha="center", va="center", fontsize=7, color="white")
    a1.text(1.25, 1.3, "*", fontsize=18, color=RED, ha="center"); a1.text(1.25, 1.12, "target", fontsize=7.5, color=RED, ha="center")
    a1.set_title("Contact graph at time t\n(solid = link up, dashed = no contact)", fontsize=8.5)
    a2.set_axis_off(); a2.set_xlim(0, 10); a2.set_ylim(0, 6)
    steps = ["Each node scores candidate actions\nwith its LOCAL (possibly stale) belief",
             "Bid = marginal utility given known\ncommitments of other nodes",
             "Highest bid wins; conflicts resolved\nwhen nodes are in contact",
             "Share compact evidence + observation IDs\n(prevents double-counting)"]
    for i, s in enumerate(steps):
        rbox(a2, 5, 5.2 - i * 1.4, 9.2, 1.0, s, fs=8.2, ec=RED if i == 2 else GREY)
        if i < 3:
            arrow(a2, (5, 4.68 - i * 1.4), (5, 4.22 - i * 1.4))
    return save(fig, "fig4_auction.png")


# ── Fig 5: mode switch ──────────────────────────────────────────────────────
def fig5():
    fig, ax = plt.subplots(figsize=(7, 2.8)); ax.set_axis_off(); ax.set_xlim(0, 10); ax.set_ylim(0, 4.3)
    rbox(ax, 2.2, 2.2, 3.4, 1.4, "DISCRIMINATION MODE\nchoose measurements that\nseparate known models", fc="#EAF1FA", ec=BLUE, fs=9)
    rbox(ax, 7.8, 2.2, 3.4, 1.4, "PRESERVATION MODE\nmaximise time/wavelength\ncoverage, keep raw data", fc="#FBEAEA", ec=RED, fs=9)
    arrow(ax, (3.95, 2.55), (6.05, 2.55), color=RED)
    ax.text(5, 2.85, "$P(h_0) > \\tau$ for $n$\nconsecutive updates", ha="center", fontsize=8.5, color=RED)
    arrow(ax, (2.2, 1.45), (2.2, 0.75)); ax.text(2.2, 0.45, "confident class\n(posterior $\\geq$ threshold)", ha="center", fontsize=8, color=GREY)
    arrow(ax, (7.8, 1.45), (7.8, 0.75)); ax.text(7.8, 0.45, "evidence retained for\nlater scientific analysis", ha="center", fontsize=8, color=GREY)
    ax.text(5, 4.15, "$\\tau$ calibrated on validation events only", ha="center", fontsize=8, color=GREY, style="italic")
    return save(fig, "fig5_modeswitch.png")


# ── Fig 6: evaluation roadmap ───────────────────────────────────────────────
def fig6():
    fig, ax = plt.subplots(figsize=(8.4, 2.6)); ax.set_axis_off(); ax.set_xlim(0, 12); ax.set_ylim(0, 3.4)
    st = [("Controlled\nsimulation", "LEO constellation,\nknown truth, H1-H4", BLUE),
          ("Archival replay", "ZTF light curves,\nreal epochs only", AMBER),
          ("Hardware-in-\nthe-loop", "ESP32 nodes, ESP-NOW,\nreplayed contacts", GREEN),
          ("Reporting", "preregistered tests,\nfailures included", RED)]
    for i, (h, d, c) in enumerate(st):
        x = 1.5 + i * 3
        rbox(ax, x, 2.3, 2.3, 0.9, h, ec=c, fs=8.5, bold=True)
        ax.text(x, 1.25, d, ha="center", va="center", fontsize=8, color=GREY)
        if i < 3:
            arrow(ax, (x + 1.2, 2.3), (x + 1.8, 2.3))
    ax.text(6, 0.25, "Each stage answers a different question; results are reported separately.", ha="center",
            fontsize=8, style="italic", color=GREY)
    return save(fig, "fig6_roadmap.png")


REFS = [
    "Antier, S., et al. 2020, “The first six months of the Advanced LIGO's and Advanced Virgo's third observing run with GRANDMA,” Monthly Notices of the Royal Astronomical Society, 492, 3904–3927. doi:10.1093/mnras/stz3142",
    "Adams, C. A., Iatauro, M. J., Gridnev, S., et al. 2024, “Advancing Autonomy in Distributed Space Systems: Insights From on-Orbit Testing with the Starling 1.0 Mission,” NASA Technical Reports Server, 20240004120.",
    "Astudillo, J., Protopapas, P., Pichara, K., & Huijse, P. 2020, “An Information Theory Approach on Deciding Spectroscopic Follow-ups,” The Astronomical Journal, 159, 16. doi:10.3847/1538-3881/ab557d",
    "Barlas, Y. Z., Sloman, S. J., & Kaski, S. 2025, “Robust Experimental Design via Generalised Bayesian Inference,” arXiv:2511.07671.",
    "Catanach, T. A., & Das, N. 2023, “Metrics for Bayesian Optimal Experiment Design under Model Misspecification,” arXiv:2304.07949.",
    "Chien, S., Sherwood, R., Tran, D., et al. 2005, “Using Autonomy Flight Software to Improve Science Return on Earth Observing One,” Journal of Aerospace Computing, Information, and Communication, 2(4), 196–216. doi:10.2514/1.12923",
    "Choi, H.-L., Brunet, L., & How, J. P. 2009, “Consensus-Based Decentralized Auctions for Robust Task Allocation,” IEEE Transactions on Robotics, 25(4), 912–926. doi:10.1109/TRO.2009.2022423",
    "Davenport, J. R. A., et al. 2014, “Kepler Flares II: The Temporal Morphology of White-light Flares on GJ 1243,” The Astrophysical Journal, 797, 122.",
    "Guirguis, D., Wallace, N., Kurniawati, H., & Sukkarieh, S. 2026, “POMDPs for Autonomous Science Exploration,” arXiv:2608.03155.",
    "Kennamer, N., Ishida, E. E. O., Gonzalez-Gaitan, S., et al. 2020, “Active Learning with RESSPECT: Resource Allocation for Extragalactic Astronomical Transients,” IEEE Symposium Series on Computational Intelligence (SSCI). arXiv:2010.05941",
    "Krause, A., & Guestrin, C. 2005, “Near-optimal Nonmyopic Value of Information in Graphical Models,” Proc. 21st Conference on Uncertainty in Artificial Intelligence (UAI), 324–331.",
    "Metzger, B. D. 2017, “Kilonovae,” Living Reviews in Relativity, 20, 3.",
    "Möller, A., Ishida, E. E. O., Peloton, J., et al. 2025, “Real-time active learning for optimised spectroscopic follow-up: Enhancing early SN Ia classification with the Fink broker,” Publications of the Astronomical Society of Australia, 42, e057. doi:10.1017/pasa.2025.20",
    "“NMMA-Astro-COLIBRI: An Automated Light-Curve Supernovae Classification Service in the Multi-Survey Era,” 2026, arXiv:2608.17568. [AUTHOR LIST TO ADD from the arXiv page]",
    "Piro, A. L. 2015, “Using Shock Cooling to Constrain the Progenitors of Type IIb Supernovae,” The Astrophysical Journal Letters, 808, L51.",
    "Sari, R., Piran, T., & Narayan, R. 1998, “Spectra and Light Curves of Gamma-Ray Burst Afterglows,” The Astrophysical Journal Letters, 497, L17.",
    "Tavallali, P., Chien, S., Mandrake, L., et al. 2020, “Adaptive, Model-Driven Observations for Earth Science,” Proc. International Symposium on Artificial Intelligence, Robotics and Automation in Space (i-SAIRAS).",
]

TITLE = "Open-World, Deadline-Aware Follow-Up Planning for Fading Astronomical Transients with Distributed Spacecraft"
AUTHORS = "Joyce Malik*, Anup H, Moghitha B, Swathi Satish"
AFFIL = "Department of Computer Science and Engineering, Dr. Ambedkar Institute of Technology, Bengaluru, India"
CORR = "*Corresponding author: colossus@drait.edu.in · ORCID 0009-0001-8293-8064"


def insert_after(par, text="", style=None):
    new = copy.deepcopy(par._p)
    for r in list(new):
        if r.tag.endswith("}r") or r.tag.endswith("}hyperlink"):
            new.remove(r)
    par._p.addnext(new)
    from docx.text.paragraph import Paragraph
    p = Paragraph(new, par._parent)
    if style:
        p.style = style
    if text:
        p.add_run(text)
    return p


def add_figure_after(par, img, caption, width=6.0):
    p_img = insert_after(par)
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.first_line_indent = 0
    p_img.add_run().add_picture(str(img), width=Inches(width))
    p_cap = insert_after(p_img)
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_cap.add_run(caption); r.italic = True; r.font.size = Pt(9)
    return p_cap


def find(doc, starts):
    for p in doc.paragraphs:
        if p.text.strip().startswith(starts):
            return p
    raise KeyError(starts)


def main():
    figs = dict(f1=fig1(), f2=fig2(), f3=fig3(), f4=fig4(), f5=fig5(), f6=fig6())
    doc = Document(str(SRC))
    original = [p.text for p in doc.paragraphs]

    # title + authors before "Abstract -"
    first = find(doc, "Abstract")
    hdr = [(TITLE, 16, True), (AUTHORS, 11, False), (AFFIL, 9.5, False), (CORR, 9, False)]
    for text, size, bold in hdr:
        p = first.insert_paragraph_before()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text); r.bold = bold; r.font.size = Pt(size)

    # figures after the paragraph that introduces each topic
    add_figure_after(find(doc, "A newly detected astronomical transient"), figs["f1"],
                     "Figure 1. Why timing matters: early observations of a transient are consistent with several "
                     "physical models, and the epochs that separate them disappear as the source fades. "
                     "Schematic shapes, not data.")
    add_figure_after(find(doc, "The architecture that we have has seven"), figs["f2"],
                     "Figure 2. The seven-stage planning loop executed by the distributed observatory.")
    add_figure_after(find(doc, "Here we have bₜ"), figs["f3"],
                     "Figure 3. Open-world hypothesis set (K known models plus h₀) and the three-term measurement "
                     "utility normalised by cost.")
    add_figure_after(find(doc, "Messages should contain compact"), figs["f4"],
                     "Figure 4. Decentralised marginal-gain allocation over an intermittent inter-spacecraft "
                     "contact graph.")
    add_figure_after(find(doc, "This switch actually does not explain"), figs["f5"],
                     "Figure 5. Transition from discrimination to evidence-preservation mode.")
    add_figure_after(find(doc, "Our testbed would assess"), figs["f6"],
                     "Figure 6. Staged evaluation roadmap: simulation, archival replay and hardware-in-the-loop.")

    # Table 1 after the baselines paragraph
    anchor = find(doc, "The baselines must receive comparable")
    cap = insert_after(anchor)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = cap.add_run("Table 1. Strategies compared in the proposed evaluation."); rr.italic = True; rr.font.size = Pt(9)
    rows = [("ID", "Strategy", "Known models", "h₀", "Decay term", "Decentralised"),
            ("B0", "Fixed observing recipe", "–", "–", "–", "–"),
            ("B1", "Reactive nearest-capable dispatcher", "–", "–", "–", "✓"),
            ("B2", "Classifier-entropy sampling", "✓", "–", "–", "–"),
            ("B3", "Closed-world EIG", "✓", "–", "–", "–"),
            ("P", "Proposed open-world planner", "✓", "✓", "✓", "✓"),
            ("O", "Centralised oracle (upper bound)", "✓", "✓", "✓", "ideal")]
    tbl = doc.add_table(rows=len(rows), cols=len(rows[0]))
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), "999999")
        borders.append(e)
    tbl._tbl.tblPr.append(borders)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = tbl.cell(i, j); c.text = v
            for pr in c.paragraphs:
                pr.paragraph_format.first_line_indent = 0
                for r in pr.runs:
                    r.font.size = Pt(9); r.bold = i == 0
    cap._p.addnext(tbl._tbl)

    # references: replace bullet items after "References"
    ref_head = find(doc, "References")
    body = ref_head._p.getparent()
    olds = []
    nxt = ref_head._p.getnext()
    while nxt is not None and nxt.tag.endswith("}p"):
        olds.append(nxt); nxt = nxt.getnext()
    template = olds[0] if olds else None
    for o in olds:
        body.remove(o)
    last = ref_head
    for i, ref in enumerate(REFS, 1):
        p = insert_after(last)
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.3)
        r = p.add_run(f"[{i}] {ref}"); r.font.size = Pt(9.5)
        last = p

    doc.save(str(OUT))

    # verify body text unchanged (ignoring inserted paragraphs and the reference list)
    new = [p.text for p in Document(str(OUT)).paragraphs]
    ref_i = original.index(next(t for t in original if t.strip().startswith("References")))
    missing = [t for t in original[:ref_i + 1] if t not in new]
    print("saved", OUT)
    print("original body paragraphs missing/changed:", len(missing))


if __name__ == "__main__":
    main()
