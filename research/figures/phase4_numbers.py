"""Generate Phase 4 LaTeX macros, table and figure from results/phase4_fleet
analysis files. Nothing is typed by hand.

Usage: python -m research.figures.phase4_numbers
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results" / "phase4_fleet"
OUT = ROOT / "papers" / "main" / "generated"


def pct(x: float) -> str:
    return f"{100 * x:.0f}\\%"


def pts(x: float) -> str:
    return f"{100 * x:+.1f}"


def verdict(passed: bool) -> str:
    return "\\textbf{pass}" if passed else "\\textbf{fail}"


def ci_pts(ci) -> str:
    return f"[{100 * ci[0]:+.1f}, {100 * ci[1]:+.1f}]"


def main() -> None:
    nom = json.loads((RES / "analysis_test_nominal.json").read_text())
    me = json.loads((RES / "analysis_test_model_error.json").read_text())
    ex = json.loads((RES / "analysis_exploratory_equal_reserve3.json").read_text())
    res = json.loads((RES / "reserves.json").read_text())
    H, S = nom["hypotheses"], nom["summary"]
    m = {}
    m["FleetNEpisodes"] = str(nom["meta"]["n_episodes"])
    m["FleetNEvents"] = str(nom["meta"]["n_episodes"] * nom["meta"]["n_events_per_episode"])
    m["FleetNModeled"] = str(S["O"]["n_modeled"])
    m["FleetNUnknown"] = str(S["O"]["n_unknown"])
    for f, v in res["reserves"].items():
        m[f"FleetReserve{f}"] = f"{v:g}"
    for hid, key in (("H4.1", "HFourOne"), ("H4.2", "HFourTwo"), ("H4.3", "HFourThree"), ("H4.4", "HFourFour")):
        m[f"Fleet{key}Verdict"] = verdict(H[hid]["pass"])
        m[f"Fleet{key}Est"] = pts(H[hid]["estimate"])
        m[f"Fleet{key}CI"] = ci_pts(H[hid]["ci95"])
    for hid, key in (("HE1", "HEOne"), ("HE2", "HETwo")):
        m[f"Fleet{key}Verdict"] = verdict(H[hid]["pass"])
    he1 = H["HE1"]["per_strategy"]
    m["FleetHEOneMaxK"] = str(max(v["k"] for v in he1.values()))
    m["FleetHEOneN"] = str(next(iter(he1.values()))["n"])
    m["FleetHEOneMaxUpper"] = f"{max(v['cp_upper95'] for v in he1.values()):.3f}"
    m["FleetHETwoK"], m["FleetHETwoN"] = str(H["HE2"]["k"]), str(H["HE2"]["n"])
    for s, key in (("O", "O"), ("G", "G"), ("A_5000", "A"), ("K_5000", "K"), ("A_1000", "AOne")):
        v = S[s]
        m[f"FleetAcc{key}"] = pct(v["acc_modeled"])
        m[f"FleetObs{key}"] = f"{v['mean_obs_per_event']:.1f}"
        m[f"FleetLs{key}"] = f"{v['mean_log_score']:.2f}"
        m[f"FleetAuc{key}"] = f"{v['auroc_p_h0']:.2f}"
        m[f"FleetCwU{key}"] = pct(v["cw_unknown"])
        m[f"FleetFlag{key}"] = pct(v["flag_unknown"])
        m[f"FleetEDet{key}"] = pct(v["e_ground_detect_unknown"])
        m[f"FleetStale{key}"] = pct(v["mean_stale_fraction"])
        m[f"FleetDup{key}"] = f"{v['duplicates_per_event']:.1f}"
    lu = {}
    for ep in json.loads((RES / "test_nominal_seed4000_n250_reservesjson" / "shard_0of1.json").read_text())["episodes"]:
        for r, f in ep["link_up_fraction"].items():
            lu.setdefault(r, []).append(f)
    m["FleetLinkUpOne"] = pct(sum(lu["1000"]) / len(lu["1000"]))
    m["FleetLinkUpFive"] = pct(sum(lu["5000"]) / len(lu["5000"]))
    meh = me["hypotheses"]["HE1"]["per_strategy"]
    m["FleetMEFalseUnknownO"] = pct(meh["O"]["false_unknown"])
    m["FleetMEFalseUnknownG"] = pct(meh["G"]["false_unknown"])
    for k, key in (("A_5000-G", "AminusG"), ("O-G", "OminusG"), ("O-A_5000", "OminusA"), ("A_5000-K_5000", "AminusK")):
        m[f"FleetEx{key}Est"] = pts(ex[k]["estimate"])
        m[f"FleetEx{key}CI"] = ci_pts(ex[k]["ci95"])
    m["FleetExAccO"] = pct(ex["summary"]["O"]["acc_modeled"])
    b = json.loads((RES / "analysis_h4b.json").read_text())
    for k, key in (("B1", "BOne"), ("B2", "BTwo"), ("B3", "BThree"), ("B4", "BFour")):
        m[f"Fleet{key}Verdict"] = verdict(b["hypotheses"][k]["pass"])
        m[f"Fleet{key}Est"] = pts(b["hypotheses"][k]["estimate"])
        m[f"Fleet{key}CI"] = ci_pts(b["hypotheses"][k]["ci95"])
        m[f"Fleet{key}Mag"] = f"{abs(b['hypotheses'][k]['estimate']) * 100:.1f}"
    m["FleetHFourOneMag"] = f"{abs(H['H4.1']['estimate']) * 100:.1f}"
    h5 = b["hypotheses"]["B5"]
    m["FleetBFiveVerdict"] = verdict(h5["pass"])
    m["FleetBFiveEst"] = f"{h5['estimate']:+.2f}"
    m["FleetBFiveCI"] = f"[{h5['ci95'][0]:+.2f}, {h5['ci95'][1]:+.2f}]"
    m["FleetBDenseAGEst"] = pts(b["hypotheses"]["reported_dense_A5000_minus_G"]["estimate"])
    m["FleetBDenseAGCI"] = ci_pts(b["hypotheses"]["reported_dense_A5000_minus_G"]["ci95"])
    m["FleetBNEvents"] = str(4 * len(json.loads((RES / "b_sparse_equal3" / "shard_0of1.json").read_text())["episodes"]))
    m["FleetDenseLinkUpOne"] = pct(b["link_up"]["dense"]["1000"])
    m["FleetDenseLinkUpFive"] = pct(b["link_up"]["dense"]["5000"])
    m["FleetBAccOSparse"] = pct(b["summary"]["sparse_equal3"]["O"]["acc_modeled"])
    m["FleetBAccODense"] = pct(b["summary"]["dense_equal3"]["O"]["acc_modeled"])

    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["% GENERATED by research/figures/phase4_numbers.py -- do not edit"]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in m.items()]
    (OUT / "numbers_phase4.tex").write_text("\n".join(lines) + "\n")

    rows = [("O", "Ideal links (oracle)"), ("A_5000", "Auction, ISL $\\leq$5000\\,km"),
            ("K_5000", "Knowledge only, ISL $\\leq$5000\\,km"), ("A_1000", "Auction, ISL $\\leq$1000\\,km"),
            ("G", "No links")]
    t = ["\\begin{tabular}{lrrrrrrr}", "\\toprule",
         "Strategy & Acc.\\ mod. & CW unk. & Flag unk. & AUROC & log score & $\\bar n_{\\rm obs}$ & Stale \\\\",
         "\\midrule"]
    for s, label in rows:
        v = S[s]
        t.append(f"{label} & {100*v['acc_modeled']:.0f} & {100*v['cw_unknown']:.0f} & {100*v['flag_unknown']:.0f} & "
                 f"{v['auroc_p_h0']:.2f} & {v['mean_log_score']:.2f} & {v['mean_obs_per_event']:.1f} & "
                 f"{100*v['mean_stale_fraction']:.0f} \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    (OUT / "table_fleet.tex").write_text("\n".join(t) + "\n")

    ranges = [1000, 2000, 3000, 5000]
    fig, ax = plt.subplots(figsize=(3.4, 2.4), dpi=200)
    for src, style, lab in ((S, "-", "selected reserves (preregistered)"),
                            (ex["summary"], "--", "equal reserve (exploratory)")):
        ax.plot(ranges, [100 * src[f"A_{r}"]["acc_modeled"] for r in ranges], style, marker="o", color="#2b6cb0",
                lw=1.4, ms=3, label=f"A, {lab}")
        ax.axhline(100 * src["O"]["acc_modeled"], ls=style, color="#2f855a", lw=1)
        ax.axhline(100 * src["G"]["acc_modeled"], ls=style, color="#9b2c2c", lw=1)
    ax.text(5150, 100 * S["O"]["acc_modeled"], "O", va="center", fontsize=7, color="#2f855a")
    ax.text(5150, 100 * S["G"]["acc_modeled"], "G", va="center", fontsize=7, color="#9b2c2c")
    ax.set_xlabel("ISL range R (km)", fontsize=7)
    ax.set_ylabel("Accuracy on modeled events (%)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=5, frameon=False, loc="lower right")
    fig.tight_layout()
    (OUT / "figures").mkdir(exist_ok=True)
    fig.savefig(OUT / "figures" / "fig5_fleet.pdf")
    fig.savefig(OUT / "figures" / "fig5_fleet.png")
    print(f"wrote {len(m)} macros, table_fleet.tex, fig5_fleet.pdf")


if __name__ == "__main__":
    main()
