"""Storm drag atlas: shell-resolved thermospheric density ratio from catalogue decay rates.

Definitions are fixed in PREREGISTRATION_ATLAS.md. Reads the per-day parquet files from
fetch_leo_days.py, the CelesTrak SATCAT and the GFZ Kp file; writes CSV/JSON and a figure to
research/results/atlas/.

Run:  python -m research.atlas.density_ratio
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from research.atlas.common import DAYS_DIR, REF_DIR, RESULTS

MU = 398600.4418  # km^3/s^2
RE = 6378.137     # km
BIN_H = 12
SHELL_EDGES = list(range(300, 651, 50))
BASE_START, BASE_END, KP_QUIET_MAX = "2024-04-27", "2024-05-08", 4.0
MIN_BASE_RATES, MIN_B_M_PER_DAY, MIN_OBJS = 6, -20.0, 30
PRIMARY_TYPES, SECONDARY_TYPES = ("DEB", "R/B"), ("PAY",)


def load_kp(path=None) -> pd.DataFrame:
    path = path or REF_DIR / "gfz_kp_ap_f107.txt"
    rows = []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        f = line.split()
        y, m, d = int(f[0]), int(f[1]), int(f[2])
        for k in range(8):
            rows.append((pd.Timestamp(y, m, d) + pd.Timedelta(hours=3 * k), float(f[7 + k])))
    kp = pd.DataFrame(rows, columns=["t", "kp"])
    return kp[kp.kp >= 0]


def storm_onset(kp: pd.DataFrame, lo="2024-05-09", hi="2024-05-12") -> pd.Timestamp:
    w = kp[(kp.t >= lo) & (kp.t < hi) & (kp.kp >= 7)]
    return w.t.iloc[0]


def quiet_days(kp: pd.DataFrame, start=BASE_START, end=BASE_END) -> list[pd.Timestamp]:
    kp = kp[(kp.t >= start) & (kp.t < pd.Timestamp(end) + pd.Timedelta(days=1))]
    mx = kp.groupby(kp.t.dt.normalize()).kp.max()
    return list(mx[mx <= KP_QUIET_MAX].index)


def sma_km(mean_motion_rev_day: np.ndarray) -> np.ndarray:
    n = np.asarray(mean_motion_rev_day, float) * 2 * np.pi / 86400.0
    return (MU / n**2) ** (1 / 3)


def decay_rates(gp: pd.DataFrame) -> pd.DataFrame:
    """Per-object consecutive-element-set decay rates in m/day, binned to BIN_H hours."""
    gp = gp.drop_duplicates(["NORAD_CAT_ID", "EPOCH"]).copy()
    gp["t"] = pd.to_datetime(gp.EPOCH)
    gp["a"] = sma_km(gp.MEAN_MOTION.values)
    gp = gp.sort_values(["NORAD_CAT_ID", "t"])
    g = gp.groupby("NORAD_CAT_ID")
    dt_d = (gp.t - g.t.shift()).dt.total_seconds() / 86400.0
    da_m = (gp.a - g.a.shift()) * 1000.0
    ok = (dt_d >= 0.2) & (dt_d <= 2.0)
    out = pd.DataFrame({
        "norad": gp.NORAD_CAT_ID, "rate": da_m / dt_d,
        "t": gp.t - pd.to_timedelta(dt_d, unit="D") / 2, "alt": gp.a - RE})[ok]
    out["bin"] = out.t.dt.floor(f"{BIN_H}h")
    return out


def object_baselines(rates: pd.DataFrame, days: list[pd.Timestamp]) -> pd.DataFrame:
    base = rates[rates.bin.dt.normalize().isin(days)]
    g = base.groupby("norad")
    b = pd.DataFrame({"b": g.rate.median(), "n": g.rate.size(), "alt": g.alt.median()})
    return b[(b.n >= MIN_BASE_RATES) & (b.b <= MIN_B_M_PER_DAY)]


def shell_ratio(rates: pd.DataFrame, base: pd.DataFrame, objects: set[int]) -> pd.DataFrame:
    """Median ratio per (shell, time bin); cells with < MIN_OBJS objects are dropped."""
    r = rates[rates.norad.isin(objects)].join(base[["b", "alt"]].rename(columns={"alt": "alt0"}), on="norad", how="inner")
    r["ratio"] = r.rate / r.b
    r["shell"] = pd.cut(r.alt0, SHELL_EDGES, right=False, labels=SHELL_EDGES[:-1]).astype("float")
    r = r.dropna(subset=["shell"])
    per_obj = r.groupby(["shell", "bin", "norad"]).ratio.median().reset_index()
    cell = per_obj.groupby(["shell", "bin"]).ratio.agg(R="median", n="size").reset_index()
    return cell[cell.n >= MIN_OBJS]


def evaluate(cell: pd.DataFrame, cell_sec: pd.DataFrame, t0: pd.Timestamp, days: list[pd.Timestamp]) -> dict:
    out: dict = {"t0": str(t0), "shells": {}}
    base_days = set(days)
    for shell, c in cell.groupby("shell"):
        c = c.sort_values("bin")
        post = c[c.bin >= t0 - pd.Timedelta(hours=BIN_H)]
        if post.empty:
            continue
        pk = post.loc[post.R.idxmax()]
        bd = c[c.bin.dt.normalize().isin(base_days)].R
        sec = cell_sec[cell_sec.shell == shell]
        sec_post = sec[sec.bin >= t0 - pd.Timedelta(hours=BIN_H)]
        out["shells"][int(shell)] = {
            "peak_R": float(pk.R), "peak_time": str(pk.bin), "peak_lag_h": float((pk.bin - t0).total_seconds() / 3600),
            "n_at_peak": int(pk.n), "base_mean": float(bd.mean()) if len(bd) else None,
            "base_sd": float(bd.std()) if len(bd) > 2 else None,
            "secondary_peak_R": float(sec_post.R.max()) if len(sec_post) else None}
    s = out["shells"]
    in_range = {k: v for k, v in s.items() if 350 <= k <= 550}
    out["HA1_timing"] = {"pass": bool(in_range) and all(0 <= v["peak_lag_h"] <= 72 for v in in_range.values()),
                         "shells": {k: v["peak_lag_h"] for k, v in in_range.items()}}
    hi = {k: v["peak_R"] for k, v in s.items() if 350 <= k <= 600}
    rho = spearmanr(list(hi), list(hi.values())).statistic if len(hi) >= 3 else None
    out["HA2_altitude"] = {"pass": bool(rho is not None and rho > 0), "spearman_rho": None if rho is None else float(rho), "n_shells": len(hi)}
    ok = [v["peak_R"] > v["base_mean"] + 5 * v["base_sd"] for v in in_range.values() if v["base_sd"]]
    out["HA3_detectability"] = {"pass": bool(ok) and bool(np.mean(ok) >= 0.8), "fraction": float(np.mean(ok)) if ok else None, "n_shells": len(ok)}
    chk = [v["secondary_peak_R"] <= v["peak_R"] for v in s.values() if v["secondary_peak_R"] is not None]
    out["HA4_payload_not_larger"] = {"pass": bool(chk) and all(chk), "n_shells": len(chk)}
    return out


def plot(cell: pd.DataFrame, kp: pd.DataFrame, t0: pd.Timestamp, path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    piv = cell.pivot(index="shell", columns="bin", values="R").sort_index()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, gridspec_kw={"height_ratios": [1, 3]})
    k = kp[(kp.t >= piv.columns.min()) & (kp.t <= piv.columns.max())]
    a1.step(k.t, k.kp, where="post", color="k")
    a1.axvline(t0, color="r", lw=0.8)
    a1.set_ylabel("Kp")
    im = a2.pcolormesh(piv.columns, piv.index + 25, piv.values, shading="auto", cmap="magma", vmin=0.5, vmax=np.nanmax(piv.values))
    a2.axvline(t0, color="w", lw=0.8)
    a2.set_ylabel("shell centre altitude (km)")
    fig.colorbar(im, ax=[a1, a2], label="median decay-rate ratio ~ rho / rho_quiet")
    fig.savefig(path, dpi=150, bbox_inches="tight")


def main() -> None:
    argparse.ArgumentParser().parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    gp = pd.concat([pd.read_parquet(p) for p in sorted(DAYS_DIR.glob("*.parquet"))], ignore_index=True)
    sat = pd.read_csv(REF_DIR / "celestrak_satcat.csv", usecols=["NORAD_CAT_ID", "OBJECT_TYPE"])
    kp = load_kp()
    t0, days = storm_onset(kp), quiet_days(kp)
    rates = decay_rates(gp)
    base = object_baselines(rates, days)
    typ = sat.set_index("NORAD_CAT_ID").OBJECT_TYPE
    prim = set(typ[typ.isin(PRIMARY_TYPES)].index) & set(base.index)
    sec = set(typ[typ.isin(SECONDARY_TYPES)].index) & set(base.index)
    cell = shell_ratio(rates, base, prim)
    cell_sec = shell_ratio(rates, base, sec)
    cell.to_csv(RESULTS / "shell_ratio_primary.csv", index=False)
    cell_sec.to_csv(RESULTS / "shell_ratio_secondary.csv", index=False)
    res = evaluate(cell, cell_sec, t0, days)
    res.update({"n_element_sets": int(len(gp)), "n_primary_objects": len(prim), "n_secondary_objects": len(sec),
                "n_quiet_days": len(days)})
    (RESULTS / "atlas_summary.json").write_text(json.dumps(res, indent=1))
    plot(cell, kp, t0, RESULTS / "atlas_primary.png")
    print(json.dumps({k: v for k, v in res.items() if k != "shells"}, indent=1))


if __name__ == "__main__":
    main()
