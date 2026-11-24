"""Phase E analysis: anytime false-'unknown' and detection rates of the e-process on real events.

An event raises an alarm if log E_t >= log(1/alpha) at ANY measurement step (anytime rule).

Usage:
  python -m research.experiments.phaseE_analysis summary research/results/phaseE/fresh_cal_seed1.json
  python -m research.experiments.phaseE_analysis evaluate      # preregistered HR1/HR2 on the test runs
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from scipy.stats import beta

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RES = REPO_ROOT / "research" / "results" / "phaseE"
ALPHA = 0.1
SEEDS = (1, 2, 3)
STRATS = ("P_open_world_eig", "B3_closed_world_eig", "L_lookahead_0.25")


def cp_upper(k: int, n: int, level: float = 0.95) -> float:
    return 1.0 if k == n else float(beta.ppf(level, k + 1, n - k))


def cp_lower(k: int, n: int, level: float = 0.95) -> float:
    return 0.0 if k == 0 else float(beta.ppf(1 - level, k, n - k + 1))


def alarmed(log_e: list[float], alpha: float = ALPHA) -> bool:
    return any(v >= math.log(1 / alpha) for v in log_e)


def rates(path: Path) -> dict:
    events = json.loads(path.read_text())["events"]
    out = {}
    for s in STRATS:
        for group, sel in (("modelled", lambda e: not e["withheld"]), ("withheld", lambda e: e["withheld"])):
            ev = [e for e in events if sel(e) and s in e["strategies"]]
            k = sum(alarmed(e["strategies"][s]["log_e"]) for e in ev)
            out.setdefault(s, {})[group] = {"k": k, "n": len(ev), "rate": k / len(ev) if ev else None,
                                            "cp_upper95": cp_upper(k, len(ev)) if ev else None,
                                            "cp_lower95": cp_lower(k, len(ev)) if ev else None}
    return out


def evaluate() -> dict:
    res = {"alpha": ALPHA, "HR1": {}, "HR2": {}, "descriptive": {}}
    for seed in SEEDS:
        ft = rates(RES / f"fresh_test_seed{seed}.json")
        te = rates(RES / f"test_seed{seed}.json")
        res["HR1"][seed] = ft["P_open_world_eig"]["modelled"]
        res["HR2"][seed] = te["P_open_world_eig"]["withheld"]
        res["descriptive"][seed] = {"fresh_test": ft, "test": te}
    res["HR1_pass"] = all(v["cp_upper95"] <= ALPHA for v in res["HR1"].values())
    res["HR2_pass"] = all(v["cp_lower95"] > ALPHA for v in res["HR2"].values())
    (RES / "analysis_E.json").write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    if sys.argv[1] == "summary":
        print(json.dumps(rates(Path(sys.argv[2])), indent=1))
    else:
        r = evaluate()
        print("HR1", "PASS" if r["HR1_pass"] else "FAIL", {s: (v["k"], v["n"], round(v["cp_upper95"], 3)) for s, v in r["HR1"].items()})
        print("HR2", "PASS" if r["HR2_pass"] else "FAIL", {s: (v["k"], v["n"], round(v["cp_lower95"], 3)) for s, v in r["HR2"].items()})
