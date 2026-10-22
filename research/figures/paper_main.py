"""Numbers, tables and figures for the main paper (research/papers/main/),
generated ONLY from research/results/. Nothing here is typed in by hand.

Inputs:
  results/phase2/analysis_test.json            Phase 2c (causal simulation), preregistered
  results/phase2/selection_validation.json     Phase 2c validation selection
  results/phase6/analysis_test_v3.json         causal real replay, preregistered (third look)
  results/phase5/analysis_test_v2.json         retrospective real replay (v2), for comparison
  results/phase6/test_seed{S}_final_*/events.jsonl, results/phase5/... (ROC, budget use)
  research/LOG.md is NOT read; the causality-bug rate is recomputed here.

Outputs (research/papers/main/generated/): numbers.tex, figures/*.pdf

Usage:
  python -m research.figures.paper_main
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from research.experiments.metrics import auroc
from research.experiments.phase2_analysis import roc_curve

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "research" / "results"
OUT = REPO / "research" / "papers" / "main" / "generated"
FIG = OUT / "figures"

# Reference categorical palette, fixed order (dataviz skill, light mode).
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
STRAT = {  # key -> (label, colour)
    "P_open_world_eig": ("P (open world)", C[0]),
    "B3_closed_world_eig": ("B3 closed-world EIG", C[1]),
    "B2_classifier_entropy": ("B2 classifier entropy", C[2]),
    "B1_cnp_reimplementation": ("B1 CNP auction", C[3]),
    "B0_fixed_cadence": ("B0 fixed cadence", C[4]),
    "P_no_decay": (r"P, $\gamma=0$ (no decay)", C[5]),
    "P_no_adequacy": (r"P, $\beta=0$ (no adequacy)", C[6]),
}
ROMAN = {"H1": "One", "H2": "Two", "H3": "Three", "H4": "Four", "H5": "Five"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "lines.linewidth": 1.6, "savefig.bbox": "tight", "pdf.fonttype": 42,
})


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def events(d: Path) -> list[dict]:
    return [json.loads(l) for l in open(d / "events.jsonl", encoding="utf-8")]


def num(x) -> float:
    return float("inf") if x == "inf" else float(x)


class Macros:
    def __init__(self):
        self.lines = []

    def add(self, name: str, value: str):
        assert name.isalpha(), name
        self.lines.append(f"\\newcommand{{\\{name}}}{{{value}}}")

    def pct(self, name, x, digits=0):
        self.add(name, f"{100 * x:.{digits}f}\\%")

    def f(self, name, x, digits=2):
        self.add(name, f"{x:.{digits}f}")

    def ci(self, name, lohi, digits=2, scale=1.0):
        self.add(name, f"[{scale * lohi[0]:.{digits}f}, {scale * lohi[1]:.{digits}f}]")


def span(lo: float, hi: float, fmt: str) -> str:
    a, b = fmt.format(lo), fmt.format(hi)
    return a if a == b else f"{a}--{b}"


def pct_span(lo: float, hi: float) -> str:
    return span(100 * lo, 100 * hi, "{:.0f}") + "\\%"


def word(i: int) -> str:
    return ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven"][i]


# --------------------------------------------------------------------- simulation
def sim(m: Macros):
    a = jload(RES / "phase2" / "analysis_test.json")
    sel = jload(RES / "phase2" / "selection_validation.json")["chosen"]
    m.add("SimGamma", f"{sel['gamma']:g}")
    m.add("SimLengthscale", f"{sel['gp_lengthscale']:g}")
    runs = {r["scenario"]: r for r in a["runs"]}
    s1 = runs["S1_nominal"]
    m.add("SimNEvents", str(s1["n_events"]))
    m.add("SimNModeled", str(s1["H1"]["n_modeled"]))
    m.add("SimNWithheld", str(s1["H3"]["n_withheld"]))
    for h in ("H1", "H2", "H3"):
        m.add(f"SimH{ROMAN[h]}Verdict", r"\textbf{pass}" if a["verdict"][h] else r"\textbf{fail}")

    # H1
    h1 = s1["H1"]
    m.add("SimTtiP", fmt_days(num(h1["median_P_days"])))
    m.pct("SimIdP", h1["fraction_identified_P"])
    for b, key in (("B0_fixed_cadence", "Bzero"), ("B1_cnp_reimplementation", "Bone"),
                   ("B2_classifier_entropy", "Btwo"), ("B3_closed_world_eig", "Bthree")):
        e = h1["per_baseline"][b]
        m.add(f"SimTti{key}", fmt_days(num(e["median_days"])))
        m.pct(f"SimId{key}", e["fraction_identified"])
        m.add(f"SimHolm{key}", fmt_p(e["holm_p"]))
        m.f(f"SimRbc{key}", e["rank_biserial"])
        m.pct(f"SimFaster{key}", e["p_faster"])
        m.pct(f"SimSlower{key}", e["p_slower"])
    obs = h1["mean_obs_used_modeled"]
    m.f("SimObsP", obs["P_open_world_eig"], 1)
    m.f("SimObsBthree", obs["B3_closed_world_eig"], 1)

    # H2
    h2 = s1["H2"]
    m.f("SimHtwoFast", h2["mean_delta_fast"], 3)
    m.f("SimHtwoSlow", h2["mean_delta_slow"], 3)
    m.f("SimHtwoEst", h2["estimate"], 3)
    m.ci("SimHtwoCI", h2["ci95"], 3)
    m.ci("SimHtwoFastCI", h2["ci_delta_fast"], 3)
    m.ci("SimHtwoSlowCI", h2["ci_delta_slow"], 3)

    # H3
    h3 = s1["H3"]
    b3 = h3["comparators"]["B3_entropy"]
    m.pct("SimTprP", h3["P_tpr_at_fpr"])
    m.pct("SimTprBthree", b3["tpr_at_fpr"])
    m.f("SimHthreeEst", 100 * h3["estimate"], 0)
    m.ci("SimHthreeCI", h3["ci95"], 0, 100)
    m.f("SimAucP", h3["P_auroc"], 3)
    m.f("SimAucBthree", b3["auroc"], 3)
    m.f("SimAucBtwo", h3["comparators"]["B2_entropy"]["auroc"], 3)
    m.f("SimAucPown", h3["comparators"]["P_own_measurements_entropy"]["auroc"], 3)
    m.pct("SimTprPown", h3["comparators"]["P_own_measurements_entropy"]["tpr_at_fpr"])

    # per-scenario table
    rows = []
    for sc, label in (("S1_nominal", "Nominal"), ("S2_crowding", "Crowding"), ("S3_model_error", "Model error")):
        r = runs[sc]
        rep = r["reported"]
        for key in STRAT:
            e = rep[key]
            tti = num(r["tti_days"][key][len(r["tti_days"][key]) // 2]) if key in r["tti_days"] else None
            rows.append((label, key, e, tti, r))
    table_sim(rows)
    rep = s1["reported"]
    m.pct("SimCwWhBthree", rep["B3_closed_world_eig"]["confident_wrong_withheld"])
    m.pct("SimCwWhP", rep["P_open_world_eig"]["confident_wrong_withheld"])
    m.pct("SimAccModP", rep["P_open_world_eig"]["accuracy_modeled"])
    m.pct("SimAccModBthree", rep["B3_closed_world_eig"]["accuracy_modeled"])
    m.pct("SimFaP", rep["P_open_world_eig"]["h0_false_alarm_modeled"])
    s3 = runs["S3_model_error"]["reported"]["P_open_world_eig"]
    m.pct("SimFaPModelError", s3["h0_false_alarm_modeled"])
    m.pct("SimAccModPModelError", s3["accuracy_modeled"])
    m.f("SimAucPModelError", runs["S3_model_error"]["H3"]["P_auroc"], 3)
    m.f("SimAucBthreeModelError", runs["S3_model_error"]["H3"]["comparators"]["B3_entropy"]["auroc"], 3)
    m.f("SimAucPCrowding", runs["S2_crowding"]["H3"]["P_auroc"], 3)
    for sc, nm in (("S2_crowding", "Crowding"), ("S3_model_error", "ModelError")):
        for h in ("H1", "H2", "H3"):
            m.add(f"SimH{ROMAN[h]}{nm}", "pass" if runs[sc][h]["pass"] else "fail")

    fig_tti(s1)
    fig_h2(s1)
    fig_roc_sim(s1)


def fmt_days(d: float) -> str:
    if not np.isfinite(d):
        return r"$>$\,budget"
    return f"{d * 24:.1f}\\,h" if d < 1 else f"{d:.2f}\\,d"


def fmt_p(p: float) -> str:
    return "$<10^{-4}$" if p < 1e-4 else f"{p:.2g}"


def table_sim(rows):
    out = [r"\begin{tabular}{llrrrrr}", r"\toprule",
           r"Scenario & Strategy & Acc.\ mod. & CW unmod. & CW mod. & $\bar n_{\rm obs}$ & log score \\", r"\midrule"]
    last = None
    for label, key, e, _, _ in rows:
        sc = label if label != last else ""
        if label != last and last is not None:
            out.append(r"\midrule")
        last = label
        out.append(f"{sc} & {STRAT[key][0]} & {100 * e['accuracy_modeled']:.0f} & "
                   f"{100 * e['confident_wrong_withheld']:.0f} & {100 * e['confident_wrong_modeled']:.0f} & "
                   f"{e['mean_obs_used']:.1f} & {e['mean_log_score']:.2f} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    (OUT / "table_sim.tex").write_text("\n".join(out) + "\n", encoding="utf-8")


def fig_tti(s1):
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    for key in ("P_open_world_eig", "B3_closed_world_eig", "B2_classifier_entropy",
                "B1_cnp_reimplementation", "B0_fixed_cadence", "P_no_decay"):
        t = np.array([num(x) for x in s1["tti_days"][key]])
        n = len(t)
        fin = np.sort(t[np.isfinite(t)])
        xs = np.r_[fin, 30.0]
        ys = np.r_[np.arange(1, len(fin) + 1) / n, len(fin) / n]
        ax.step(xs, ys, where="post", color=STRAT[key][1], label=STRAT[key][0],
                lw=2.2 if key == "P_open_world_eig" else 1.4)
    ax.set_xscale("log")
    ax.set_xlim(0.008, 30)
    ax.set_ylim(0, 1)
    ax.set_xlabel("time since alert (days)")
    ax.set_ylabel("fraction of modeled events\nidentified ($\\geq$0.95 on true class)")
    ax.legend(fontsize=6, loc="upper left")
    fig.savefig(FIG / "fig1_tti.pdf")
    plt.close(fig)


def fig_h2(s1):
    pc = s1["H2"]["per_class"]
    order = ["flare", "kilonova", "shock_cooling", "grb_afterglow"]
    names = {"flare": "flare", "kilonova": "kilonova", "shock_cooling": "shock cooling", "grb_afterglow": "GRB afterglow"}
    fig, ax = plt.subplots(figsize=(3.4, 1.9))
    vals = [pc[c]["mean_delta"] for c in order]
    cols = [C[0] if c != "grb_afterglow" else C[1] for c in order]
    ax.barh(range(len(order)), vals, color=cols, height=0.55)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_yticks(range(len(order)), [f"{names[c]} (n={pc[c]['n']})" for c in order])
    ax.invert_yaxis()
    ax.set_xlabel("information gained from the decay term\n(nats on ln amplitude, P minus P without decay)")
    ax.grid(axis="y", visible=False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=C[0], label="fast classes"), Patch(color=C[1], label="slow class")], fontsize=6)
    fig.savefig(FIG / "fig2_decay.pdf")
    plt.close(fig)


def fig_roc_sim(s1):
    roc = s1["H3"]["roc"]
    fig, ax = plt.subplots(figsize=(3.2, 2.6))
    spec = [("P_p_h0", "P: $P(h_0)$", C[0], "-"), ("B3_entropy", "B3: posterior entropy", C[1], "-"),
            ("B2_entropy", "B2: posterior entropy", C[2], "-"),
            ("P_own_measurements_entropy", "P's data, closed-world entropy", C[6], "--")]
    for k, lab, col, ls in spec:
        ax.plot(roc[k]["fpr"], roc[k]["tpr"], color=col, ls=ls, label=lab, lw=2.2 if k == "P_p_h0" else 1.4)
    ax.axvline(0.05, color=MUTED, lw=0.8, ls=":")
    ax.plot([0, 1], [0, 1], color=GRID, lw=0.8)
    ax.set_xlabel("false-alarm rate on modeled events")
    ax.set_ylabel("detection rate on withheld events")
    ax.legend(fontsize=6, loc="lower right")
    fig.savefig(FIG / "fig3_roc_sim.pdf")
    plt.close(fig)


# --------------------------------------------------------------------- real data
H_KEYS = {"H1": "H1_P_vs_B3_confident_wrong_withheld", "H2": "H2_auroc_p_h0",
          "H3": "H3_P_vs_B3_confident_wrong_modeled", "H4": "H4_auroc_vs_r5", "H5": "H5_acc_modeled_P_vs_B3"}


def real(m: Macros):
    v3 = jload(RES / "phase6" / "analysis_test_v3.json")
    v2 = jload(RES / "phase5" / "analysis_test_v2.json")
    for tag, a in (("C", v3), ("R", v2)):
        for h in H_KEYS:
            m.add(f"Real{tag}H{ROMAN[h]}Verdict", r"\textbf{pass}" if a["overall_pass_all_seeds"][h] else r"\textbf{fail}")
    m.add("RealNEvents", str(v3["runs"][0]["n_events"]))
    m.add("RealNWithheld", str(v3["runs"][0]["n_withheld"]))
    m.add("RealNModeled", str(v3["runs"][0]["n_modeled"]))

    def rng(a, f):
        vals = [f(r) for r in a["runs"]]
        return min(vals), max(vals)

    for tag, a in (("C", v3), ("R", v2)):
        lo, hi = rng(a, lambda r: r["H2_auroc_p_h0"]["estimate"])
        m.add(f"Real{tag}Auc", span(lo, hi, "{:.2f}"))
        for strat, nm in (("B3_closed_world_eig", "Bthree"), ("P_open_world_eig", "P"), ("B1_cnp_reimplementation", "Bone")):
            lo, hi = rng(a, lambda r: r["reported"]["confident_wrong_withheld"][strat])
            m.add(f"Real{tag}CwWh{nm}", pct_span(lo, hi))
            lo, hi = rng(a, lambda r: r["reported"]["accuracy_modeled"][strat])
            m.add(f"Real{tag}AccMod{nm}", pct_span(lo, hi))
        lo, hi = rng(a, lambda r: r["reported"]["accuracy_withheld"]["P_open_world_eig"])
        m.add(f"Real{tag}FlagP", pct_span(lo, hi))
        lo, hi = rng(a, lambda r: r["reported"]["P_h0_false_alarm_modeled"])
        m.add(f"Real{tag}FaP", pct_span(lo, hi))
    table_real(v3, v2)

    # budget actually used, causal vs retrospective (test, all seeds)
    use = {}
    for tag, base in (("C", "phase6/test_seed{S}_final_gr5_k0.5"), ("R", "phase5/test_seed{S}_final_gr5_k0.5")):
        for strat, nm in (("P_open_world_eig", "P"), ("B3_closed_world_eig", "Bthree"), ("B0_fixed_cadence", "Bzero")):
            vals = [s["strategies"][strat]["n_obs_used"] for S in (1, 2, 3) for s in events(RES / base.format(S=S))]
            use[(tag, nm)] = float(np.mean(vals))
            m.f(f"Real{tag}Obs{nm}", use[(tag, nm)], 1)
    fig_roc_real()


def table_real(v3, v2):
    out = [r"\begin{tabular}{lll@{\hspace{4pt}}l}", r"\toprule",
           r"& Seed & Causal (v3) & Retrospective (v2) \\", r"\midrule"]
    labels = {"H1": r"H1 $\Delta$CW unmod.", "H2": r"H2 AUROC $P(h_0)$", "H3": r"H3 $\Delta$CW mod.",
              "H4": r"H4 $\Delta$AUROC colour", "H5": r"H5 $\Delta$acc.\ mod."}
    for h, key in H_KEYS.items():
        for i, (r3, r2) in enumerate(zip(v3["runs"], v2["runs"])):
            def cell(r):
                e = r[key]
                return f"{e['estimate']:+.2f} [{e['ci95'][0]:+.2f}, {e['ci95'][1]:+.2f}]{'' if e['pass'] else r'$^\times$'}"
            out.append(f"{labels[h] if i == 0 else ''} & {r3['seed']} & {cell(r3)} & {cell(r2)} \\\\")
        out.append(r"\addlinespace")
    out += [r"\bottomrule", r"\end{tabular}"]
    (OUT / "table_real.tex").write_text("\n".join(out) + "\n", encoding="utf-8")


def fig_roc_real():
    fig, ax = plt.subplots(figsize=(3.2, 2.6))
    spec = [("phase6/test_seed1_final_gr5_k0.5", "causal, colour + discrepancy", C[0], "-"),
            ("phase6/test_seed1_final_r5", "causal, single band", C[1], "-"),
            ("phase5/test_seed1_final_gr5_k0.5", "retrospective, colour + discrepancy", C[0], "--")]
    for d, lab, col, ls in spec:
        ev = events(RES / d)
        pos = np.array([e["strategies"]["P_open_world_eig"]["p_h0_final"] for e in ev if e["withheld"]])
        neg = np.array([e["strategies"]["P_open_world_eig"]["p_h0_final"] for e in ev if not e["withheld"]])
        fpr, tpr = roc_curve(pos, neg)
        ax.plot(fpr, tpr, color=col, ls=ls, label=f"{lab} ({auroc(pos, neg):.2f})", lw=2.0 if ls == "-" else 1.2)
    ax.plot([0, 1], [0, 1], color=GRID, lw=0.8)
    ax.set_xlabel("false-alarm rate on ordinary SNe")
    ax.set_ylabel("detection rate on real unmodeled")
    ax.legend(fontsize=5.5, loc="lower right", title="P's $P(h_0)$, test seed 1 (AUROC)", title_fontsize=6)
    fig.savefig(FIG / "fig4_roc_real.pdf")
    plt.close(fig)


# --------------------------------------------------------------------- causality bug
def causality_bug_rate(m: Macros):
    """Fraction of adaptive-planner sequences that went backwards in time in
    the retrospective (v2) test runs -- recomputed from their histories."""
    back = tot = 0
    for S in (1, 2, 3):
        for e in events(RES / f"phase5/test_seed{S}_final_gr5_k0.5"):
            for k in ("B1_cnp_reimplementation", "B2_classifier_entropy", "B3_closed_world_eig", "P_open_world_eig"):
                ts = [h["t"] for h in e["strategies"][k]["history"]]
                if len(ts) >= 2:
                    tot += 1
                    back += any(b < a for a, b in zip(ts, ts[1:]))
    m.pct("CausalBugPct", back / tot)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    m = Macros()
    causality_bug_rate(m)
    sim(m)
    real(m)
    (OUT / "numbers.tex").write_text("% GENERATED by research/figures/paper_main.py -- do not edit\n"
                                     + "\n".join(m.lines) + "\n", encoding="utf-8")
    print(f"wrote {len(m.lines)} macros, tables and figures to {OUT}")


if __name__ == "__main__":
    main()
