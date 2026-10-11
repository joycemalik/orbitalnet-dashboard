"""Generates markdown tables from research/results/*.json ONLY. Never
computes a new result number — every value here is read verbatim from a
summary.json written by an experiment script.

These tables are this project's own reporting format (see
research/PLAN.md and research/LOG.md Phase 2 entry on why "Tables 2-5 of
the manuscript" is not something this repo can target: no manuscript
exists here). Numbered "Table 1", "Table 2", ... in the order this project
produces them, not against any external document.

Usage:
  python -m research.figures.make_tables > research/results/TABLES.md
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "research" / "results"


def _read_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, (int,)):
        return str(x)
    return f"{x:.{nd}f}"


def table_phase1_existence_proof() -> str:
    summary = _read_json(RESULTS_DIR / "phase1" / "summary.json")
    if summary is None:
        return "## Table 1 - Phase 1 existence proof\n\nNot run yet.\n"

    cfg = summary["config"]
    lines = [
        "## Table 1 - Phase 1 existence proof",
        "",
        f"seed={cfg['seed']} | n_events={cfg['n_events']} | tag={cfg.get('tag')} | "
        f"git_commit={summary['git_commit'][:12]} | config_hash={summary['config_hash']}",
        "",
        "| strategy | confident-wrong (modeled) | confident-wrong (withheld) | accuracy (withheld, h0 credited) |",
        "|---|---|---|---|",
    ]
    for name, stats in summary["strategies"].items():
        lines.append(
            f"| {name} | {_fmt(stats['confident_wrong_rate_modeled'])} | "
            f"{_fmt(stats['confident_wrong_rate_withheld'])} | {_fmt(stats['accuracy_withheld'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def table_phase2_strategy_comparison() -> str:
    phase2_dir = RESULTS_DIR / "phase2"
    if not phase2_dir.is_dir():
        return "## Table 2 - Phase 2 strategy comparison\n\nNot run yet.\n"

    scenario_dirs = sorted(
        p.parent.name for p in phase2_dir.glob("*/summary.json")
    )
    if not scenario_dirs:
        return "## Table 2 - Phase 2 strategy comparison\n\nNot run yet.\n"

    lines = ["## Table 2 - Phase 2 strategy comparison (all scenarios, test seeds)", ""]
    for scenario in scenario_dirs:
        result = _read_json(phase2_dir / scenario / "summary.json")
        lines.append(f"### {scenario}")
        lines.append("")
        lines.append(
            f"seed={result['seed']} | git_commit={result['git_commit'][:12]} | "
            f"config_hash={result['config_hash']} | n_events={result['config']['test_n_events']}"
        )
        lines.append("")
        lines.append(
            "| strategy | accuracy (modeled) | accuracy (withheld) | mean log score | "
            "mean time-to-ID | never identified | AUROC P(h0) |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for name, stats in result["summary"]["strategies"].items():
            lines.append(
                f"| {name} | {_fmt(stats['accuracy_modeled'])} | {_fmt(stats['accuracy_withheld'])} | "
                f"{_fmt(stats['mean_log_score'])} | {_fmt(stats['mean_time_to_identification'])} | "
                f"{_fmt(stats['fraction_never_identified'])} | "
                f"{_fmt(stats.get('auroc_p_h0_withheld_vs_modeled'))} |"
            )
        lines.append("")
        nc, hc, ngc = result["null_control"], result["h0_calibration"], result["negative_control"]
        lines.append(
            f"Validity: null control {'PASSED' if nc['passed'] else 'FAILED'} "
            f"(diff={_fmt(nc['mean_diff'], 4)}); h0 threshold={_fmt(hc['calibrated_threshold'], 4)} "
            f"(target FPR={hc['target_fpr']}); observed test FPR={_fmt(ngc['observed_fpr'], 4)}"
        )
        lines.append("")

    return "\n".join(lines)


def table_phase3_ablations() -> str:
    path = RESULTS_DIR / "phase3" / "summary.json"
    summary = _read_json(path)
    if summary is None:
        return "## Table 3 - Phase 3 ablations\n\nNot run yet.\n"
    lines = ["## Table 3 - Phase 3 ablations", "", f"git_commit={summary['git_commit'][:12]}", ""]
    lines.append("| ablation | confident-wrong (withheld) | accuracy (withheld) | mean log score |")
    lines.append("|---|---|---|---|")
    for name, stats in summary["ablations"].items():
        lines.append(
            f"| {name} | {_fmt(stats['confident_wrong_rate_withheld'])} | "
            f"{_fmt(stats['accuracy_withheld'])} | {_fmt(stats['mean_log_score'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def table_phase4_decentralization() -> str:
    path = RESULTS_DIR / "phase4" / "summary.json"
    summary = _read_json(path)
    if summary is None:
        return "## Table 4 - Phase 4 decentralization\n\nNot run yet.\n"
    lines = ["## Table 4 - Phase 4 decentralization", "", f"git_commit={summary['git_commit'][:12]}", ""]
    lines.append("belief-merge exactness: " + ("PASSED" if summary.get("merge_exactness_passed") else "NOT RUN / FAILED"))
    lines.append("")
    lines.append("| contact fraction | accuracy (modeled) | accuracy (withheld) |")
    lines.append("|---|---|---|")
    for row in summary.get("contact_fraction_sweep", []):
        lines.append(f"| {_fmt(row['contact_fraction'])} | {_fmt(row['accuracy_modeled'])} | {_fmt(row['accuracy_withheld'])} |")
    lines.append("")
    return "\n".join(lines)


def table_phase5_real_data() -> str:
    path = RESULTS_DIR / "phase5" / "summary.json"
    summary = _read_json(path)
    if summary is None:
        return "## Table 5 - Phase 5 real-data h0 check\n\nNot run yet.\n"
    lines = ["## Table 5 - Phase 5 real-data h0 check", ""]
    if summary.get("status") == "NO REAL DATA YET":
        lines.append("**NO REAL DATA YET** - results below are from a clearly-labeled synthetic stand-in only.")
        lines.append("")
    lines.append(f"git_commit={summary['git_commit'][:12]}")
    lines.append("")
    lines.append(json.dumps(summary.get("results", {}), indent=2))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    sections = [
        table_phase1_existence_proof(),
        table_phase2_strategy_comparison(),
        table_phase3_ablations(),
        table_phase4_decentralization(),
        table_phase5_real_data(),
    ]
    print("\n".join(sections))


if __name__ == "__main__":
    main()
