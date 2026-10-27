"""Phase 3 (anomaly track): detector recall on sourced known events and
false-alarm rate on objects that cannot maneuver, over a threshold grid.

- Recall: research/anomaly/known_events.csv rows in the chosen window; an event
  counts as detected if a detection of a compatible kind starts within
  --tol-days of its date on the same object.
- False alarms: tier D (Envisat, dead rocket bodies) and the sourced
  no-propulsion objects in known_inert.csv (Hubble, Swift) cannot thrust, so every
  maneuver/plane-change detection on them is false. Reported per object-year.
  (A few tier D objects might still be active stages early in life; the first
  --settle-days after launch are excluded, as are the last --final-decay-days
  before the catalog decay date, where accelerating drag dominates the fits.)
- Detections within a day of a Kp >= --kp-storm day are tagged storm=True.
  Storm-time lowerings are drag (the atlas track's subject), so the maneuver
  false-alarm rate is reported excluding them; the storm-lowering count is
  reported separately, never dropped silently.

Precision on maneuverable objects is NOT computed: no complete public list of
e.g. ISS reboosts exists in the sources used, so unlisted detections there are
unknown, not false.

Run: python -m research.experiments.anomaly_validation --start 2021-01-01 --end 2024-01-01
"""

from __future__ import annotations

import argparse
import glob
import itertools
import json
from pathlib import Path

import pandas as pd

from research.anomaly.detectors import detect_geo_drift_changes, detect_plane_changes, detect_steps
from research.anomaly.elements import build_series
from research.anomaly.fetch_reference import ANOMALY_RAW
from research.anomaly.spaceweather import daily_max_kp, storm_days, tag_storm
from research.anomaly.targets import RESULTS_DIR, load_satcat

KNOWN = Path(__file__).resolve().parents[1] / "anomaly" / "known_events.csv"
INERT = Path(__file__).resolve().parents[1] / "anomaly" / "known_inert.csv"  # sourced: no propulsion
COMPATIBLE = {"maneuver_raise": {"maneuver_raise"}, "maneuver_lower": {"maneuver_lower"},
              "geo_drift_change": {"geo_drift_change"}}


def load_tier(tier: str, start: str, end: str) -> pd.DataFrame:
    df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(ANOMALY_RAW / "gp" / tier / "*.parquet")))])
    s = build_series(df)
    return s[(s.EPOCH >= pd.Timestamp(start, tz="UTC")) & (s.EPOCH < pd.Timestamp(end, tz="UTC"))]


def run_detectors(obj: pd.DataFrame, z: float, min_km: float, min_deg: float = 0.05) -> list:
    ev = detect_steps(obj, z=z, min_step=min_km) + detect_plane_changes(obj, z=z, min_step=min_deg)
    return ev + detect_geo_drift_changes(obj, z=z)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--end", default="2024-01-01")
    ap.add_argument("--tol-days", type=float, default=2.0)
    ap.add_argument("--settle-days", type=float, default=30.0)
    ap.add_argument("--final-decay-days", type=float, default=180.0)
    ap.add_argument("--kp-storm", type=float, default=6.0)
    args = ap.parse_args()
    if pd.Timestamp(args.end) > pd.Timestamp("2024-07-01"):
        raise SystemExit("validation must not touch the held-out window (>= 2024-07-01)")

    known = pd.read_csv(KNOWN, parse_dates=["date"])
    known = known[(known.window == "validation") & (known.date >= args.start) & (known.date < args.end)]
    pos = pd.concat([load_tier(t, args.start, args.end) for t in ("A_stations", "B_geo_inspectors")])
    pos = pos[pos.NORAD_CAT_ID.isin(known.norad)]
    inert = pd.read_csv(INERT).norad
    sci = load_tier("E_science", args.start, args.end)
    neg = pd.concat([load_tier("D_derelicts", args.start, args.end), sci[sci.NORAD_CAT_ID.isin(inert)]])
    cat = load_satcat().set_index("NORAD_CAT_ID")
    ids = neg.NORAD_CAT_ID.astype(str)
    launch = pd.to_datetime(ids.map(cat.LAUNCH_DATE), utc=True)
    decay = pd.to_datetime(ids.map(cat.DECAY_DATE), utc=True)
    neg = neg[(neg.EPOCH > launch + pd.Timedelta(days=args.settle_days))
              & ~(neg.EPOCH > decay - pd.Timedelta(days=args.final_decay_days))]
    storms = storm_days(daily_max_kp(), args.kp_storm)
    neg_years = sum((g.EPOCH.max() - g.EPOCH.min()).days / 365.25 for _, g in neg.groupby("NORAD_CAT_ID"))

    rows = []
    for z, min_km, min_deg in itertools.product([8.0, 15.0], [0.1, 0.2, 0.3, 0.5], [0.02, 0.05, 0.1]):
        dets = {n: run_detectors(g, z, min_km, min_deg) for n, g in pos.groupby("NORAD_CAT_ID")}
        hits = []
        for k in known.itertuples():
            ok = any(e.kind in COMPATIBLE[k.kind] and
                     abs((e.epoch_start.tz_convert(None) - k.date).total_seconds()) <= args.tol_days * 86400
                     for e in dets.get(k.norad, []))
            hits.append({"norad": k.norad, "date": k.date.date().isoformat(), "kind": k.kind, "detected": ok})
        neg_ev = [e for _, g in neg.groupby("NORAD_CAT_ID")
                  for e in tag_storm(run_detectors(g, z, min_km, min_deg), storms) if e.kind != "geo_drift_change"]
        storm_lowers = sum(e.storm and e.kind == "maneuver_lower" for e in neg_ev)
        fa = len(neg_ev) - storm_lowers
        fa_by_kind = {k: sum(e.kind == k and not (e.storm and k == "maneuver_lower") for e in neg_ev)
                      for k in ("maneuver_raise", "maneuver_lower", "plane_change")}
        rows.append({"z": z, "min_km": min_km, "min_deg": min_deg, "recall": sum(h["detected"] for h in hits) / len(hits),
                     "false_alarms": fa, "false_alarms_by_kind": fa_by_kind, "storm_lowerings": storm_lowers,
                     "false_alarms_per_object_year": fa / neg_years, "events": hits})
        print(f"z={z:5.1f} min_km={min_km:4.1f} min_deg={min_deg:4.2f} recall={rows[-1]['recall']:.2f} "
              f"FA/obj-yr={rows[-1]['false_alarms_per_object_year']:.3f} {fa_by_kind} storm_lowers={storm_lowers}", flush=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = {"args": vars(args), "n_known": len(known), "n_negative_objects": int(neg.NORAD_CAT_ID.nunique()),
           "negative_object_years": neg_years, "grid": rows}
    (RESULTS_DIR / "validation_grid.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
