"""Screenshots of the running OrbitalNet OS (start boot_os.py first).
Run: python materials/report_figures/take_screenshots.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "screenshots"
BASE = "http://localhost:8501"
# (file name, sidebar link text or None for the landing page, wait ms)
SHOTS = [
    ("fig_7_4_overview_console.png", None, 8000),
    ("fig_7_5_orbital_view_globe.png", "Orbital View", 25000),
    ("fig_7_6_mission_dispatch.png", "Mission Dispatch", 10000),
    ("fig_7_7_auction_internals.png", "Auction Internals", 10000),
    ("fig_7_8_event_lab.png", "Event Lab", 15000),
    ("fig_7_9_evidence.png", "Evidence", 12000),
    ("fig_7_10_anomaly_watch.png", "Anomaly Watch", 12000),
]
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True,
                          args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
    for name, path, wait in SHOTS:
        pg.goto(BASE, wait_until="networkidle")
        pg.wait_for_timeout(4000)
        if path:
            pg.locator("[data-testid=stSidebar]").get_by_text(path, exact=True).first.click()
        pg.wait_for_timeout(wait)
        pg.screenshot(path=str(OUT / name), full_page=False)
        print("wrote", name)
    b.close()
