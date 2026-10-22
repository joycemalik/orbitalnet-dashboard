"""Exports result numbers for the static venue pages (docs/venues/).

Reads research/results/*/summary.json ONLY and writes
docs/venues/results.js, which sets `window.RESULTS`. The venue pages fill
every <span data-r="..."> from that object, so no result number is ever
typed into the HTML by hand. Re-run after any experiment:

  python -m research.figures.export_site_results

Pure json/pathlib — no live-stack imports.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "research" / "results"
OUT_PATH = REPO_ROOT / "docs" / "venues" / "results.js"


def _read_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def phase1() -> dict | None:
    s = _read_json(RESULTS_DIR / "phase1" / "summary.json")
    if s is None:
        return None
    cfg = s["config"]
    out = {
        "seed": cfg["seed"],
        "n_events": cfg["n_events"],
        "tag": cfg.get("tag"),
        "git_commit": s["git_commit"][:12],
        "config_hash": s["config_hash"],
    }
    for name, st in s["strategies"].items():
        out[name] = {
            "cw_modeled": st["confident_wrong_rate_modeled"],
            "cw_withheld": st["confident_wrong_rate_withheld"],
            "acc_withheld": st["accuracy_withheld"],
        }
    return out


def phase2() -> dict | None:
    # Phase 2 writes per-scenario summaries; none exist until it is run.
    found = sorted((RESULTS_DIR / "phase2").glob("**/summary.json")) if (RESULTS_DIR / "phase2").exists() else []
    return {"n_summaries": len(found)} if found else None


def phase3() -> dict | None:
    runs = sorted((RESULTS_DIR / "phase3").glob("*/summary.json")) if (RESULTS_DIR / "phase3").exists() else []
    if not runs:
        return None
    out = {
        "n_runs": len(runs),
        "n_scored_total": sum((_read_json(p) or {}).get("n_scored", 0) or 0 for p in runs),
    }
    # Preregistered test outcome (research/PREREGISTRATION.md), if it exists.
    for key, fname in (("test", "analysis_test.json"), ("phase4_test", "analysis_phase4_test.json")):
        a = _read_json(RESULTS_DIR / "phase3" / fname)
        if a is None:
            continue
        r0 = a["runs"][0]
        out[key] = {
            "overall_pass": a["overall_pass_all_seeds"],
            "n_seeds": len(a["runs"]), "n_events": r0["n_events"],
            "n_withheld": r0["n_withheld"], "n_modeled": r0["n_modeled"],
            "seeds": [{
                "H1": r["H1_P_vs_B3_confident_wrong_withheld"], "H2": r["H2_auroc_p_h0"],
                "H3": r["H3_P_vs_B3_confident_wrong_modeled"],
                "cw_withheld": r["reported"]["confident_wrong_withheld"],
                "cw_modeled": r["reported"]["confident_wrong_modeled"],
                "acc_modeled": r["reported"]["accuracy_modeled"],
                "h0_false_alarm": r["reported"]["P_h0_false_alarm_modeled"],
            } for r in a["runs"]],
        }
    return out


def phase5() -> dict | None:
    """Preregistration v2 (colour + model discrepancy) test outcome + validation table."""
    out = {}
    cmp_ = _read_json(RESULTS_DIR / "phase5" / "compare_validation_all.json")
    if cmp_ is not None:
        out["validation"] = {Path(k).name.replace("validation_seed1_", "").replace(".", "p"): {
            "P": v["P_open_world_eig"], "B3": v["B3_closed_world_eig"]} for k, v in cmp_["arms"].items()}
    a = _read_json(RESULTS_DIR / "phase5" / "analysis_test_v2.json")
    if a is not None:
        keys = {"H1": "H1_P_vs_B3_confident_wrong_withheld", "H2": "H2_auroc_p_h0",
                "H3": "H3_P_vs_B3_confident_wrong_modeled", "H4": "H4_auroc_vs_r5", "H5": "H5_acc_modeled_P_vs_B3"}
        r0 = a["runs"][0]
        out["test"] = {
            "overall_pass": a["overall_pass_all_seeds"], "n_events": r0["n_events"],
            "n_withheld": r0["n_withheld"], "n_modeled": r0["n_modeled"],
            "seeds": [{**{h: r[k] for h, k in keys.items()},
                       "auroc_vs_r10": r["reported_auroc_vs_r10"],
                       "cw_withheld": r["reported"]["confident_wrong_withheld"],
                       "acc_modeled": r["reported"]["accuracy_modeled"],
                       "acc_withheld": r["reported"]["accuracy_withheld"],
                       "h0_false_alarm": r["reported"]["P_h0_false_alarm_modeled"]} for r in a["runs"]],
        }
    return out or None


def rnaas() -> dict | None:
    # Written by research/figures/rnaas_note.py from phase1_full raw trajectories.
    s = _read_json(RESULTS_DIR / "rnaas_note" / "numbers.json")
    if s is None:
        return None
    out = {"n_events": s["n_events_total"], "n_seeds": len(s["configs"]),
           "seeds": [c["seed"] for c in s["configs"]], "paired": s["paired_flag_P_vs_B3h0"]}
    for row, st in s["pooled"].items():
        out[row] = {k: st[k] for k in ("n_modeled", "n_withheld", "acc_modeled", "cw_modeled",
                                       "cw_withheld", "flag_withheld", "auroc_h0")}
    return out


def _verdict_text(ok: bool) -> str:
    return "pass" if ok else "FAIL"


def phase2c() -> dict | None:
    # Causal simulation, preregistered (PREREGISTRATION_PHASE2.md); S1 decides.
    a = _read_json(RESULTS_DIR / "phase2" / "analysis_test.json")
    if a is None:
        return None
    s1 = next(r for r in a["runs"] if r["scenario"] == "S1_nominal")
    rep = s1["reported"]
    return {
        "n_events_total": sum(r["n_events"] for r in a["runs"]), "n_events_s1": s1["n_events"],
        "verdict": {h: _verdict_text(v) for h, v in a["verdict"].items()},
        "n_pass": sum(a["verdict"].values()), "n_hyp": len(a["verdict"]),
        "median_tti_days": {"P": s1["H1"]["median_P_days"],
                            **{b: e["median_days"] for b, e in s1["H1"]["per_baseline"].items()}},
        "H2": {k: s1["H2"][k] for k in ("estimate", "ci95", "mean_delta_fast", "mean_delta_slow")},
        "H3": {"tpr_P": s1["H3"]["P_tpr_at_fpr"], "tpr_B3_entropy": s1["H3"]["comparators"]["B3_entropy"]["tpr_at_fpr"],
               "auroc_P": s1["H3"]["P_auroc"], "auroc_B3_entropy": s1["H3"]["comparators"]["B3_entropy"]["auroc"]},
        "cw_withheld": {k: v["confident_wrong_withheld"] for k, v in rep.items()},
        "flag_withheld": {k: v["accuracy_withheld"] for k, v in rep.items() if k.startswith("P_")},
    }


def phase6() -> dict | None:
    # Causal real replay, preregistered (PREREGISTRATION_V3.md), third look at the test events.
    a = _read_json(RESULTS_DIR / "phase6" / "analysis_test_v3.json")
    if a is None:
        return None
    keys = {"H1": "H1_P_vs_B3_confident_wrong_withheld", "H2": "H2_auroc_p_h0",
            "H3": "H3_P_vs_B3_confident_wrong_modeled", "H4": "H4_auroc_vs_r5", "H5": "H5_acc_modeled_P_vs_B3"}
    ov = a["overall_pass_all_seeds"]
    r0 = a["runs"][0]
    return {
        "n_events": r0["n_events"], "n_withheld": r0["n_withheld"], "n_modeled": r0["n_modeled"],
        "n_runs": len(a["runs"]), "verdict": {h: _verdict_text(v) for h, v in ov.items()},
        "n_pass": sum(ov.values()), "n_hyp": len(ov),
        "seeds": [{h: {"estimate": r[k]["estimate"], "ci95": r[k]["ci95"]} for h, k in keys.items()}
                  | {"cw_withheld": r["reported"]["confident_wrong_withheld"],
                     "acc_modeled": r["reported"]["accuracy_modeled"],
                     "flag_withheld_P": r["reported"]["accuracy_withheld"]["P_open_world_eig"],
                     "h0_false_alarm": r["reported"]["P_h0_false_alarm_modeled"]} for r in a["runs"]],
    }


def status(p2c: dict | None, p6: dict | None) -> dict:
    """Counts for the homepage status panel, so it can never again claim
    'PENDING' once result files exist."""
    real = p6["n_events"] * p6["n_runs"] if p6 else 0
    passed = (p2c["n_pass"] if p2c else 0) + (p6["n_pass"] if p6 else 0)
    total = (p2c["n_hyp"] if p2c else 0) + (p6["n_hyp"] if p6 else 0)
    return {"sim_events": p2c["n_events_total"] if p2c else 0, "real_events": real,
            "hypotheses_passed": f"{passed} of {total} pass" if total else "PENDING"}


def main() -> None:
    p2c, p6 = phase2c(), phase6()
    data = {"phase1": phase1(), "phase2": phase2(), "phase3": phase3(), "phase5": phase5(), "rnaas": rnaas(),
            "phase2c": p2c, "phase6": p6, "status": status(p2c, p6)}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        "// GENERATED by research/figures/export_site_results.py from research/results/.\n"
        "// Do not edit by hand.\n"
        "window.RESULTS = " + json.dumps(data, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
