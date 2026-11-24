"""Overview — the first screen: is the system alive, and where do I go."""

import json

import streamlit as st

from ui.theme import GREEN, ROSSO, AMBER, BLUE, card, hero, kpis, label


@st.cache_data(ttl=3, show_spinner=False)
def snapshot():
    try:
        from config import get_redis_client
        r = get_redis_client()
        r.ping()
        missions = [json.loads(v) for v in r.hgetall("MISSIONS_LEDGER").values()]
        sats = sum(1 for _ in r.scan_iter("STARLINK-*", count=2000))
        return {"online": True, "sats": sats,
                "executing": sum(m.get("status") == "EXECUTING" for m in missions),
                "auction": sum(m.get("status") == "OPEN_AUCTION" for m in missions),
                "logs": r.hlen("AUCTION_LOGS"),
                "speed": str(r.get("TIME_MULTIPLIER") or "1")}
    except Exception:
        return {"online": False, "sats": 0, "executing": 0, "auction": 0, "logs": 0, "speed": "—"}


s = snapshot()
hero("OrbitalNet OS · Mission Console", "Autonomous satellite swarm",
     "Real orbits, propagated live. Satellites bid for every task, form teams on their own, "
     "and decide which observation teaches them the most — including when something matches no known physics.",
     status="All systems nominal" if s["online"] else "Redis bus offline", ok=s["online"])

label("01", "Live telemetry")


@st.fragment(run_every="4s")
def telemetry():
    s = snapshot()
    kpis([("Assets in orbit", f"{s['sats']:,}", "", "SGP4-propagated from real TLEs", GREEN),
          ("Missions executing", s["executing"], "", "enclaves formed", ROSSO),
          ("Open auctions", s["auction"], "", "contract-net bidding", AMBER),
          ("Auctions logged", s["logs"], "", "full forensic trail", BLUE),
          ("Time warp", s["speed"], "×", "chronos multiplier", None)])



telemetry()

label("02", "Where to go")
c1, c2, c3 = st.columns(3)
with c1:
    card("OPERATIONS", "Watch the swarm work",
         "3D globe of every asset. Dispatch a mission and see satellites bid, win and lock onto the target.")
    st.page_link("pages/1_visualization.py", label="Open Orbital View", icon=":material/public:")
    st.page_link("pages/2_ground_station.py", label="Dispatch a mission", icon=":material/satellite_alt:")
with c2:
    card("DISCOVERY", "Inject a space event",
         "Invent a transient anywhere in the sky. The fleet plans observations and tests it against "
         "known physics and the null hypothesis h0.")
    st.page_link("research/app/pages/1_🔭_Event_Lab.py", label="Open Event Lab", icon=":material/science:")
with c3:
    card("EVIDENCE", "What the research shows",
         "Preregistered hypotheses on real ZTF transients and the real Starlink fleet — passes and failures.")
    st.page_link("research/app/pages/2_📊_Scorecard.py", label="Open Evidence", icon=":material/fact_check:")
    st.page_link("research/app/pages/3_🛰️_Anomaly_Tracker.py", label="Anomaly Watch", icon=":material/radar:")

label("03", "How it works")
a, b, c, d = st.columns(4)
with a: card("PHYSICS", "Orbits", "SGP4 propagates real two-line elements every tick.")
with b: card("BUS", "Redis", "Every engine talks only through Redis — any part can crash and restart.")
with c: card("CONSENSUS", "Contract-net auction", "Plane leaders run auctions; the best-scored team forms an enclave.")
with d: card("PLANNER", "Open-world inference", "Chooses the measurement with the most information, keeps h0 alive.")

