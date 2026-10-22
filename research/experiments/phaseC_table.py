"""Print Markdown tables from a phaseC_analysis JSON (no numbers typed by hand).

  python -m research.experiments.phaseC_table FILE [--alpha 0.1]
"""

from __future__ import annotations

import argparse
import json


def _r(x, key="rate"):
    v = x.get(key) if isinstance(x, dict) else x
    return "-" if v is None else f"{v:.3f}"


def table(res: dict, alpha: str) -> str:
    names = list(res["raw"].keys())
    rows = ["| strategy | obs | AUROC s | raw acc known | raw cw known | raw cw unk | C acc known | C flag known "
            "(Ia/II/Ibc) | C cw known | C flag unk | C cw unk | C-B3 acc known [CI] |",
            "|---" * 12 + "|"]
    for n in names:
        raw, c = res["raw"][n], res["conformal"][alpha][n]
        pc = c["flag_rate_per_class"]
        d = res["vs_B3_raw"][alpha][n]["correct_known"]
        rows.append(
            f"| {n} | {raw['mean_obs_used']:.2f} | {_r(res['auroc_score'].get(n))} | {_r(raw['accuracy_known'])} | "
            f"{_r(raw['confident_wrong_known'])} | {_r(raw.get('confident_wrong_unknown', {}))} | "
            f"{_r(c['accuracy_known'])} | {_r(c['flag_rate_known'])} ({_r(pc['sn_ia'])}/{_r(pc['sn_ii'])}/"
            f"{_r(pc['sn_ibc'])}) | {_r(c['confident_wrong_known'])} | {_r(c.get('flag_rate_unknown', {}))} | "
            f"{_r(c.get('confident_wrong_unknown', {}))} | {d['mean']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}] |")
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--alpha", default="0.1")
    args = ap.parse_args()
    res = json.load(open(args.file, encoding="utf-8"))
    key = f"alpha_{float(args.alpha):g}"
    blocks = ({k: v for k, v in res.items() if k.startswith("fold")} if res["mode"] == "crossfit" else res["evals"])
    for k, v in blocks.items():
        print(f"\n### {k} (n={v['n_eval']}, unknown={v['n_eval_unknown']}, alpha={args.alpha})\n")
        print(table(v, key))


if __name__ == "__main__":
    main()
