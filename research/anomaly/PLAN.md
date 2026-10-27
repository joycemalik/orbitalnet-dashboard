# Plan: Satellite Anomaly Hunt (discovery mode)

## Context
The user wants to find something new and publishable with real data, in the same citizen-science
spirit as amateurs who find exoplanets. They chose **satellite orbit anomalies**. It ties into
the OrbitalNet project, gets to a first result quickly, and has fewer people competing.
The aim is a list of real events that nobody has reported (unannounced maneuvers, drag
spikes during storms, breakups or fragment releases, satellites that quietly died), each
checked against public catalogs, then written up as a short RNAAS / arXiv note and shared
with the space-tracking community (Jonathan McDowell / GCAT, the r/SpaceTrack / SeeSat
observers, LeoLabs-style SSA folks).

What to expect: the payoff is credit and visibility (citations, a paper, something strong
for a CV or grad application), not money. Big events (major breakups) get caught by the
18th SDS within days, so the novel finds will most likely be **systematic** ones, such as
"N Starlink satellites stopped station-keeping without being announced" or "the storm drag
response measured per altitude shell".

## Where the work lives (all in the user's repo, on its own branch)
- **Step 0:** `git checkout -b research/sat-anomaly` off `research/open-world-planner`.
  Copy this plan into the repo as `research/anomaly/PLAN.md`, log it in `research/LOG.md`,
  and commit. All later work and commits go to that branch, and nothing is merged into
  other branches without asking the user.
- New package `research/anomaly/`. It follows the CLAUDE.md
  research rules: no redis/streamlit imports, every number comes from `research/results/anomaly/`,
  nothing is hand-edited, and each phase ends with passing `pytest research/` and a commit.
- Reuse the Space-Track login, rate limiting and env-var credentials in
  `research/data/fetch_tles.py` (SPACETRACK_USER / SPACETRACK_PASS, at most 30 requests/min and
  300/hour). Reuse `research/orbitsim/` SGP4 helpers wherever they fit.
- Ambiguity to raise at the start of Phase 1: the `--seed/--n-events` experiment rule was written
  for the planner studies. For detectors we'd use `--start/--end/--norad-set` (plus `--seed`
  wherever sampling happens). I'll confirm this with the user before coding.

## Phases
**Target sets (in `research/anomaly/targets.py`, a versioned list of NORAD IDs pulled from SATCAT)**

| Tier | Objects | Why it draws attention |
|---|---|---|
| A: crewed stations | ISS, Tiangong (CSS), visiting vehicles | Undisclosed reboosts and debris-avoidance maneuvers make news fast |
| B: GEO "inspectors" / RPO | Russian Luch/Olymp, Cosmos co-orbital sats (e.g. 2576, 2588), Chinese Shijian-17/21/23/25, TJS series, US GSSAP (where public TLEs exist) | Rendezvous, proximity and drift-relocation events are watched closely by SWF, COMSPOC and the press |
| C: mega-constellations | Starlink, OneWeb, Qianfan (G60), Guowang, Kuiper | Silent failures, mass storm response, upper-stage breakups (the Qianfan Long March 6A, Aug 2024) |
| D: big dead objects / rocket bodies | Envisat, SL-16 / Zenit stages, CZ-5B cores, defunct GEO sats | Fragmentation and uncontrolled reentries |
| E: science flagships | Hubble, Fermi, Swift, TESS, NuSTAR | Orbit decay or anomalies people care about (Swift's decay, Hubble's altitude) |

Note: the US doesn't publish TLEs for classified objects, so we only analyze what the
public catalog holds and say so in the write-up.

**Phase 1: Data (about 1 day)**
- `research/anomaly/fetch_history.py` downloads `gp_history` from Space-Track for every
  tier above, 2021 to 2026. It works in
  chunks by NORAD range and month, caches to `research/data/raw/anomaly/` as parquet, and is
  resumable. It streams to disk so RAM stays under about 4 GB (the machine has 15.7 GB).
- `fetch_spaceweather.py` downloads Kp/ap from GFZ Potsdam, Dst from Kyoto WDC, and F10.7.
- `fetch_reference.py` downloads GCAT satcat and launch lists (planet4589.org) plus Space-Track
  SATCAT and DECAY. These are the "already known" ground truth used to check novelty.

**Phase 2: Element time series and detectors**
- From each TLE, compute semi-major axis, eccentricity, inclination, RAAN drift residual, B*,
  and ndot. Produce one clean time series per satellite, with outlier and duplicate TLEs removed.
- Detectors (simple and explainable before anything fancy):
  1. *Maneuver*: change-point (PELT/CUSUM) on SMA and inclination residuals relative to a
     drag-only model.
  2. *End of station-keeping / silent death*: SMA decaying faster than the shell's median and no
     maneuvers afterwards.
  3. *Storm drag response*: **moved to the separate atlas track** (branch `research/sat-atlas`,
     non-maneuvering debris sample), agreed 2026-10-27 so the two tracks don't publish overlapping results.
  4. *GEO relocation / proximity (tier B)*: changes in longitude-drift rate (start/stop of a
     relocation), and pairwise close approaches computed with SGP4 (pairs within N km for
     M days), which flags possible RPO.
  5. *Station reboost (tier A)*: SMA step-ups compared against published NASA/CMSA reboost
     announcements. The ones nobody announced are the find.
  6. *Fragmentation*: new catalog objects whose elements cluster in (SMA, inc, RAAN) with an
     existing object; trace them back in time to estimate the epoch.

**Phase 3: Validation on known events (this must pass before trusting new finds)**
- The detectors must recover documented events: the Feb 2022 Starlink G4-7 loss, the
  May 2024 Gannon-storm mass maneuvers, and known 2024 breakups (Long March 6A upper stage,
  Intelsat 33e). Also documented ISS debris-avoidance maneuvers, and a documented
  Shijian-21 GEO tow (Jan 2022).
- Thresholds are tuned only on the 2021–2023 validation window. Then commit
  `research/anomaly/PREREGISTRATION_SA.md` (thresholds, novelty criteria) **before** running
  on the held-out 2024-07 → 2026-10 window.

**Phase 4: Discovery run and novelty vetting**
- Run on the held-out window, then subtract everything already listed in GCAT, Space-Track
  decay/notices, or McDowell's Jonathan's Space Report.
- Each surviving candidate gets an auto-generated evidence card (element plots, space-weather
  overlay, TLE source IDs) in `research/results/anomaly/candidates/`.
- I'll hand-review the cards with the user. I won't call anything "new" unless it's absent
  from all the reference sources.

**Phase 5: Report**
- A short paper (RNAAS format, about 1000 words, 1 figure) generated from results files.
- A public candidate table (CSV) plus a page on the existing site.
- Draft outreach posts and an email to McDowell / the SSA community, which the user sends
  personally. I won't post or send anything externally without approval.

## Verification
- `pytest research/` covers element conversion against known values, detectors on synthetic
  injected maneuvers and decays (recall/false-positive rate), and fetchers on cached fixtures.
- Phase 3 recall on the known events is reported from the results files. If it fails, that's
  logged as a result and we pivot (per the "failures are results" memory).
- The final candidate table is regenerated end-to-end from the raw cache with one command:
  `python -m research.anomaly.run_all --start 2024-07-01 --end 2026-10-27`.

## Needs from the user
- Space-Track account credentials set as env vars (same as before).
- Approval before any external post or email.
