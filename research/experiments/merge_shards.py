"""Merge Phase 4 shard files (possibly from different laptops) into one
result file. Refuses if the shards disagree on code version, library
versions or run settings, or if any episode is missing or duplicated.

Usage:
  python -m research.experiments.merge_shards research/results/phase4/<run_name>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research.util import atomic_write_json

MUST_MATCH = ("git_commit", "python", "numpy", "split", "seed", "n_episodes", "scenario", "reserves", "n_shards",
              "n_events_per_episode", "ranges_km", "sat_budget", "beta", "gamma", "gp_lengthscale")


def merge(run_dir: Path) -> dict:
    shards = sorted(run_dir.glob("shard_*of*.json"))
    if not shards:
        raise SystemExit(f"no shard files in {run_dir}")
    loaded = [json.loads(p.read_text()) for p in shards]
    ref = loaded[0]["meta"]
    for p, d in zip(shards, loaded):
        for key in MUST_MATCH:
            if d["meta"][key] != ref[key]:
                raise SystemExit(f"{p.name}: meta[{key!r}]={d['meta'][key]!r} differs from {ref[key]!r}")
    got = sorted(d["meta"]["shard"] for d in loaded)
    if got != list(range(ref["n_shards"])):
        raise SystemExit(f"shards present {got}, expected 0..{ref['n_shards'] - 1}")
    episodes = [ep for d in loaded for ep in d["episodes"]]
    idx = sorted(ep["episode_index"] for ep in episodes)
    if idx != list(range(ref["n_episodes"])):
        raise SystemExit("episode indices missing or duplicated after merge")
    episodes.sort(key=lambda ep: ep["episode_index"])
    meta = {k: ref[k] for k in MUST_MATCH}
    meta["merged_from"] = [p.name for p in shards]
    meta["seconds_per_shard"] = [d["meta"]["seconds"] for d in loaded]
    return {"meta": meta, "episodes": episodes}


def main() -> None:
    run_dir = Path(sys.argv[1])
    out = merge(run_dir)
    path = run_dir / "merged.json"
    atomic_write_json(str(path), out)
    print(f"wrote {path} ({len(out['episodes'])} episodes)")


if __name__ == "__main__":
    main()
