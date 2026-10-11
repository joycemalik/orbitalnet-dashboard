"""Numbers for the RNAAS research note, computed ONLY from Phase 1 raw
trajectories in research/results/phase1_full/seed*/events_raw.jsonl.

Every strategy's per-step history already records BOTH the closed-world
class posterior and the open-world posterior (with h0). That lets this
script separate two effects:

  * having h0 in the belief   -> score B3's / random's own measurements
                                 with the open-world posterior ("+h0 post hoc")
  * planning with h0          -> P, which also chose its measurements using h0

Writes (committed):
  research/results/rnaas_note/numbers.json
  research/results/rnaas_note/numbers.tex   (\\newcommand macros used by the note)
  research/results/rnaas_note/table.tex     (the note's single table)

Usage:
  python -m research.figures.rnaas_note
"""

from __future__ import annotations

import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
IN_DIR = REPO_ROOT / "research" / "results" / "phase1_full"
OUT_DIR = REPO_ROOT / "research" / "results" / "rnaas_note"
THRESHOLD = 0.9  # must equal phase1_existence_proof.CONFIDENT_THRESHOLD; checked against config.json below

# (row label, strategy key in events_raw, which posterior scores it)
ROWS = [
    ("random", "random", "closed"),
    ("random_h0", "random", "open"),
    ("B3", "B3_closed_world_eig", "closed"),
    ("B3_h0", "B3_closed_world_eig", "open"),
    ("P", "P_open_world_eig", "open"),
]
LABELS = {
    "random": "Random times, closed-world posterior",
    "random_h0": "Random times, open-world posterior (post hoc)",
    "B3": "Closed-world EIG, closed-world posterior",
    "B3_h0": "Closed-world EIG, open-world posterior (post hoc)",
    "P": "Open-world EIG, open-world posterior",
}
MODELED = ("fast", "slow")


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def auroc(pos: list[float], neg: list[float]) -> float:
    """P(score_pos > score_neg) + 0.5 P(tie): Mann-Whitney form, no sklearn."""
    if not pos or not neg:
        return float("nan")
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks = [0.0] * len(allv)
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2 + 1
        i = j + 1
    r_pos = sum(r for r, (_, lab) in zip(ranks, allv) if lab == 1)
    n1, n0 = len(pos), len(neg)
    return (r_pos - n1 * (n1 + 1) / 2) / (n1 * n0)


def final_post(strat_rec: dict, which: str) -> dict:
    last = strat_rec["history"][-1]
    return last["class_posterior"] if which == "closed" else last["open_world_posterior"]


def load_events() -> tuple[list[dict], list[dict]]:
    events, configs = [], []
    for d in sorted(IN_DIR.glob("seed*")):
        cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
        if cfg["confident_threshold"] != THRESHOLD:
            raise SystemExit(f"{d}: threshold {cfg['confident_threshold']} != {THRESHOLD}")
        configs.append({"seed": cfg["seed"], "n_events": cfg["n_events"], "tag": cfg["tag"]})
        with open(d / "events_raw.jsonl", encoding="utf-8") as f:
            for line in f:
                ev = json.loads(line)
                ev["_seed"] = cfg["seed"]
                events.append(ev)
    return events, configs


def score(events: list[dict]) -> dict:
    out = {}
    for row, key, which in ROWS:
        m_n = m_conf_wrong = m_correct = 0
        w_n = w_conf_wrong = w_flag = 0
        h0_mod, h0_with = [], []
        for ev in events:
            post = final_post(ev["strategies"][key], which)
            dec = max(post, key=post.get)
            conf = post[dec] >= THRESHOLD
            if ev["true_class"] in MODELED:
                m_n += 1
                ok = dec == ev["true_class"]
                m_correct += ok
                m_conf_wrong += conf and not ok
                if which == "open":
                    h0_mod.append(post["h0"])
            else:
                w_n += 1
                ok = dec == "h0"
                w_flag += ok
                w_conf_wrong += conf and not ok
                if which == "open":
                    h0_with.append(post["h0"])
        out[row] = {
            "label": LABELS[row],
            "n_modeled": m_n, "n_withheld": w_n,
            "acc_modeled": m_correct / m_n, "acc_modeled_ci": wilson(m_correct, m_n),
            "cw_modeled": m_conf_wrong / m_n, "cw_modeled_ci": wilson(m_conf_wrong, m_n),
            "cw_withheld": w_conf_wrong / w_n, "cw_withheld_ci": wilson(w_conf_wrong, w_n),
            "flag_withheld": w_flag / w_n, "flag_withheld_ci": wilson(w_flag, w_n),
            "auroc_h0": auroc(h0_with, h0_mod) if which == "open" else None,
        }
    return out


def paired_flag(events: list[dict]) -> dict:
    """Withheld events only: P vs B3_h0 on 'flagged as h0' (discordant pairs)."""
    p_only = b_only = 0
    for ev in events:
        if ev["true_class"] in MODELED:
            continue
        def flagged(key):
            post = final_post(ev["strategies"][key], "open")
            return max(post, key=post.get) == "h0"
        a, b = flagged("P_open_world_eig"), flagged("B3_closed_world_eig")
        p_only += a and not b
        b_only += b and not a
    n = p_only + b_only
    # exact two-sided binomial (McNemar) p-value
    k = min(p_only, b_only)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    return {"P_only": p_only, "B3h0_only": b_only, "mcnemar_exact_p": p}


def pct(x: float) -> str:
    return f"{100 * x:.1f}"


def main() -> None:
    events, configs = load_events()
    if not events:
        raise SystemExit(f"no events under {IN_DIR}")
    pooled = score(events)
    per_seed = {c["seed"]: score([e for e in events if e["_seed"] == c["seed"]]) for c in configs}
    paired = paired_flag(events)
    data = {"configs": configs, "n_events_total": len(events), "pooled": pooled,
            "per_seed": per_seed, "paired_flag_P_vs_B3h0": paired}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "numbers.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def mac(name, val):
        return f"\\newcommand{{\\{name}}}{{{val}}}"
    lines = ["% GENERATED by research/figures/rnaas_note.py. Do not edit.",
             mac("NEvents", len(events)), mac("NSeeds", len(configs)),
             mac("NModeled", pooled["P"]["n_modeled"]), mac("NWithheld", pooled["P"]["n_withheld"])]
    for row in pooled:
        tag = row.replace("_h0", "H").replace("random", "Rnd").replace("B3", "B")  # TeX macro names cannot contain digits
        s = pooled[row]
        lines += [mac(f"{tag}CwWith", pct(s["cw_withheld"])), mac(f"{tag}FlagWith", pct(s["flag_withheld"])),
                  mac(f"{tag}CwMod", pct(s["cw_modeled"])), mac(f"{tag}AccMod", pct(s["acc_modeled"]))]
        if s["auroc_h0"] is not None:
            lines.append(mac(f"{tag}Auroc", f"{s['auroc_h0']:.3f}"))
    lines += [mac("PairPOnly", paired["P_only"]), mac("PairBOnly", paired["B3h0_only"]),
              mac("PairP", f"{paired['mcnemar_exact_p']:.2g}")]
    (OUT_DIR / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def cell(s, k):
        lo, hi = s[k + "_ci"]
        return f"{pct(s[k])} [{pct(lo)}, {pct(hi)}]"
    t = ["% GENERATED by research/figures/rnaas_note.py. Do not edit.",
         "\\begin{tabular}{lcccc}", "\\hline",
         "Strategy & Acc.\\ (modeled) & Conf.\\ wrong (withheld) & Flagged $h_0$ (withheld) & AUROC $P(h_0)$\\\\",
         "\\hline"]
    for row in pooled:
        s = pooled[row]
        au = f"{s['auroc_h0']:.3f}" if s["auroc_h0"] is not None else "--"
        t.append(f"{s['label']} & {cell(s, 'acc_modeled')} & {cell(s, 'cw_withheld')} & {cell(s, 'flag_withheld')} & {au}\\\\")
    t += ["\\hline", "\\end{tabular}"]
    (OUT_DIR / "table.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    for row, s in pooled.items():
        print(f"{row:10s} accM={pct(s['acc_modeled']):>5} cwM={pct(s['cw_modeled']):>5} "
              f"cwW={pct(s['cw_withheld']):>5} flagW={pct(s['flag_withheld']):>5} auroc={s['auroc_h0']}")
    print("paired:", paired, "| n =", len(events))


if __name__ == "__main__":
    main()
