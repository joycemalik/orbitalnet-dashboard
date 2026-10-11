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


def main() -> None:
    data = {"phase1": phase1(), "phase2": phase2(), "phase3": phase3(), "phase5": phase5(), "rnaas": rnaas()}
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
