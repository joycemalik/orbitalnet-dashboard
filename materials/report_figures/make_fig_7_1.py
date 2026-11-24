"""Fig 7.1: satellites and enclaves after the four missions were awarded.

Reads the live fleet state from Redis (run boot_os.py first, then dispatch the
four ScenarioManager missions). Only OPS-* missions (the four scenarios) are drawn.
Run:  python materials/report_figures/make_fig_7_1.py
"""
import json
from pathlib import Path
import redis
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "fig_7_1_satellites_and_enclaves.png"
r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)

keys = list(r.scan_iter("STARLINK-*"))
vals = r.mget(keys)
sats = {}
for v in vals:
    if not v:
        continue
    d = json.loads(v)
    if d.get("lat") is not None:
        sats[d["id"]] = (d["lon"], d["lat"])

missions = [json.loads(v) for k, v in r.hgetall("MISSIONS_LEDGER").items() if k.startswith("OPS-")]
missions.sort(key=lambda m: m["id"])

fig, ax = plt.subplots(figsize=(11, 5.6))
xs, ys = zip(*sats.values())
ax.scatter(xs, ys, s=0.6, c="#9ca3af", alpha=0.5, linewidths=0, label=f"Propagated satellites (n = {len(sats):,})")
colors = ["#dc2626", "#2563eb", "#16a34a", "#9333ea"]
for m, c in zip(missions, colors):
    pts = [sats[s] for s in m.get("enclave", []) if s in sats]
    if pts:
        ex, ey = zip(*pts)
        ax.scatter(ex, ey, s=40, c=c, edgecolors="black", linewidths=0.5, zorder=3,
                   label=f"{m['name'].split('(')[0].strip().title()}: {len(pts)}/{m['required_nodes']} nodes, {m['status']}")
    ax.scatter(m["target_lon"], m["target_lat"], marker="*", s=260, c=c, edgecolors="black", linewidths=0.8, zorder=4)
ax.set_xlim(-180, 180); ax.set_ylim(-90, 90)
ax.set_xlabel("Longitude (deg)"); ax.set_ylabel("Latitude (deg)")
ax.grid(alpha=0.25)
ax.legend(loc="lower left", fontsize=7.5, markerscale=1.0, framealpha=0.92)
ax.set_title("Live fleet state from Redis; stars mark mission targets", fontsize=10)
fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
print("wrote", OUT.name, "| satellites:", len(sats), "| missions:", [(m["id"], m["status"], len(m.get("enclave", []))) for m in missions])
