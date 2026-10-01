# research/ — Open-World Sequential Measurement Planning: PLAN

Status: **draft, awaiting approval**. No code has been written yet.

## 0. Research goal (restated)

Choose, at each step, which spacecraft makes which measurement next, to discriminate
among K modeled physical explanations of a fading transient plus an explicit
"unmodeled" hypothesis h0, where measurement value decays at a hypothesis-dependent
rate, across a constellation with intermittent inter-satellite links.

## 1. How the existing CNP auction maps to baseline B1

The live-stack auction lives entirely in `consensus_engine.py::elect_plane_leaders()`,
re-run every 5s tick over everything in `MISSIONS_LEDGER`. Its logic, stripped of
Redis bookkeeping, is:

1. **P0 gatekeeper** (hard filter): a satellite is eligible iff `is_task_locked == 0`
   AND `payload_type == required_sensor` AND `haversine(sat, target) <= zone_radius + 1000`.
2. **Score**: `auction_score = w_proximity * normalize(distance) + w_battery * soc`
   — a weighted sum of exactly two normalized terms, no sequential/information-theoretic
   reasoning anywhere.
3. **Dispatch**: sort eligible bidders by score, take the top `required_nodes` as a
   single-shot greedy team (no iteration — one auction tick picks the whole team).
4. **Rolling enclave**: each later tick re-checks the *same* gatekeeper (now "is this
   member still in range") and drops/reopens on failure.

This is a one-shot, feasibility-gated, highest-static-score dispatcher — it never asks
"which measurement teaches me the most." That is exactly the shape of **B1**: a
reimplementation of CNP nearest-capable dispatch, specialized to our setting as:

- Gatekeeper → **visibility/feasibility** test (can this spacecraft observe the
  transient's sky position right now, given its orbit and a minimum elevation/occlusion
  constraint) replacing the hardware+haversine gatekeeper.
- Score → a resource/proximity score (e.g. favor the spacecraft with the best
  geometry/SNR and freest schedule) replacing proximity+battery, computed the same way
  (weighted sum, no information term).
- Dispatch → at each decision epoch, argmax over currently-feasible spacecraft; no
  belief, no expected information gain, no hypothesis tracking. This preserves the
  "dispatch on static score, ignore what you'd learn" character of the original CNP
  logic, which is the point of having it as a baseline.

The rolling-enclave handoff (drop out-of-range, reopen) is *not* reused verbatim for
B1 (B1 picks one spacecraft per measurement, not a persistent team), but the same
mechanic reappears legitimately in Phase 4 as the model for intermittent
inter-satellite contact windows.

## 2. Reuse vs. headless rewrite

### Can reuse (structure/approach, not the running code as-is)

- **SGP4 propagation**: `physics_engine.py::load_satellites()` (TLE parsing via
  `Satrec.twoline2rv`) and the `sat.sgp4(jd, fr)` call pattern. We reuse the *approach*
  and a trimmed subset of `satellites.txt`, but call it synchronously inside a seeded
  simulation function — not the `while True: time.sleep(1)` loop that writes to Redis.
- **`eci_to_latlon`**: useful as-is for ground-track geometry if any ground-station
  visibility is needed, but it is not a visibility/line-of-sight test — see below.
- **Gatekeeper → weighted-score shape** from `scoring_engine.py` (`evaluate_gatekeepers`
  → `calculate_base_capability` → `apply_risk_decay`): this three-stage pattern (hard
  filter, weighted linear score, decay term) is a good scaffold for the baselines'
  resource/adequacy terms and for the hypothesis-dependent value-decay term in the
  planner. The actual numbers (thresholds like `reaction_wheel_rpm >= 0.95`,
  `conjunction_prob`) are demo flavor and are **not** reused — they have no bearing on
  photometric measurement quality.
- **Auction forensics logging shape** (`AUCTION_LOGS` entries in `consensus_engine.py`):
  the idea of logging every bidder, not just the winner, per decision — reused as the
  schema for `research/results/*.json` so experiments are auditable, but written to
  files per the branch rules instead of a Redis hash.

### Must be rewritten headless (no equivalent exists, or existing code is non-physical)

- **Visibility / contact graph**: the only "visibility" check in the live stack is
  ground-target surface distance via haversine with a flat `+1000 km` slew margin — it
  ignores orbital altitude, slant range, elevation angle, and Earth occlusion entirely.
  For both ground-to-transient visibility (Phase 2) and inter-satellite link contact
  windows (Phase 4) we need a real line-of-sight/elevation/Earth-occlusion test. This
  does not exist in the repo and must be written new in `orbitsim/geometry.py`.
- **Sensor/payload model**: `classify_satellite()` assigns sensor type by MD5 hash of
  the satellite's name purely to make the Starlink-only demo dataset look varied. It
  carries no physical information and must not leak (even by copy-paste) into the
  noise model. Phase 2's instrument noise model is derived from limiting magnitudes,
  built fresh.
- **State/control flow**: every live-stack engine is an infinite loop with Redis as
  the only interface (side effects, not return values) — this is untestable and
  non-reproducible by construction. All research code is plain functions over explicit
  arguments/returns so it can be unit tested and driven by `--seed`.
- **Bayesian hypothesis update, mutual-information/EIG estimator, GP auxiliary model
  for h0, decentralized belief merge**: no existing equivalent anywhere in the
  repo — entirely new (`inference/`, `decentral/`).

## 3. Module layout

```
research/
  PLAN.md                       (this file)
  PREREGISTRATION.md            (added later, gates test-seed access — Phase 2+)
  requirements-research.txt     (new deps go here only; requirements.txt untouched)
  orbitsim/
    tle.py                      # headless TLE load + SGP4 propagate (reuses physics_engine.py's approach)
    geometry.py                 # ECI/ECEF transforms, elevation, Earth-occlusion line-of-sight
    contacts.py                 # builds per-seed visibility/contact schedules (ground+ISL)
  transients/
    models.py                   # K parametric light-curve classes + withheld-class generator
    noise.py                    # instrument noise from limiting magnitude
  inference/
    bayes.py                    # closed-world posterior update over K hypotheses
    mutual_information.py       # EIG / MI estimator
    openworld.py                # GP auxiliary model + h0 posterior / adequacy term
  planners/
    baselines.py                # B0 (random/round-robin), B1 (CNP reimpl.), B2, B3
    eig_planner.py               # P: closed-world expected-information-gain planner
    openworld_planner.py          # P + h0 adequacy/decay term
  decentral/                    # Phase 4 only
    belief_merge.py
    marginal_auction.py
  experiments/
    phase1_existence_proof.py
    phase2_single_planner.py
    phase3_ablations.py
    phase4_decentralized.py
    phase5_real_data_check.py
  results/                      # JSON/CSV outputs only, nothing hand-edited
  figures/                      # regenerated only from results/*.json
  tests/
    test_bayes_update.py
    test_mutual_information.py
    test_belief_merge_equivalence.py   # Phase 4 exactness proof
    ...
```

All packages under `research/` are pure numpy/scipy — no `redis`, `streamlit`,
`websockets`, or other live-stack import, per the branch rules in `CLAUDE.md`. Each
experiment script takes `--seed` and `--n-events` and writes only to `research/results/`.

## 4. Risks

- **Superficial B1 mapping**: the live auction's "visibility" is a flat-Earth haversine
  hack. If `orbitsim/geometry.py`'s real occlusion/elevation test and the reused
  haversine-style gatekeeper disagree in spirit, B1 risks being a strawman rather than
  a faithful reimplementation of "what the CNP logic actually does." Mitigate by
  reviewing B1 against the mapping in §1 before Phase 2 is scored.
- **Accidental live-stack coupling**: pulling logic from `physics_engine.py` /
  `scoring_engine.py` by copy-paste risks dragging in a `redis`/`hal_simulator` import
  transitively. Enforced by a lint/test step (e.g. `grep` or an import-time check in
  `tests/`) that fails if anything under `research/` imports a banned module.
- **MI/EIG estimator correctness**: expected-information-gain and GP marginal-likelihood
  estimators are easy to get subtly wrong (Monte Carlo variance, numerical stability).
  Phase 1's acceptance criterion (a known-answer test case) is the main defense; the
  toy case must be chosen so the true MI is analytically computable, not just plausible.
- **Belief-merge exactness (Phase 4)**: "merging via measurement IDs reproduces the
  centralized posterior exactly" only holds if measurements are not double-counted and
  log-odds combine additively under conditional independence. Any planner path that
  lets a spacecraft see a duplicate or correlated measurement ID breaks this silently;
  the Phase 4 test must include a duplicate-ID case, not just the happy path.
- **Scope/sequencing**: six phases is a lot of surface area. Phase 6 (firmware/testbed)
  is explicitly design-only until Phases 1-4 pass — this plan does not create any
  firmware code or hardware-facing scaffolding now.
- **Seed discipline**: validation vs. test seeds must stay separated before
  `PREREGISTRATION.md` is committed. Risk is an experiment script using an un-flagged
  seed range during Phase 2/3 tuning; mitigate by making the seed-role split an
  explicit, checked argument rather than a convention to remember.

## 5. Open questions before Phase 1 starts

- Confirm the exact set of strategies expected in Phase 1 output (closed-world EIG
  planner + GP/h0 planner only, per the prompt) vs. Phase 2's fuller strategy list
  (B0, B1, B2, B3, P) — Phase 1 does not need B1 since there are no orbits yet.
- Confirm `results/` and `figures/` are committed (so reviewers can see without
  rerunning) or gitignored (regenerate-only) — affects repo hygiene but not the code.

Nothing above requires a decision to start Phase 1; flagging for awareness.

## 6. Phase 2 realignment to the manuscript (2026-10-01)

Phase 2 was originally built (classes, utility, scenarios, baselines) as
this project's own design, documented above as such, because no manuscript
existed in the repo yet. The user then supplied
`Hypothesis-Discriminating Observation Campaigns for Distributed
Space Observatories.pdf` ("the manuscript"), which specifies these choices
precisely. Phase 2 was rebuilt to match it. See research/LOG.md's Phase 2
entry for the full list of what changed and the simplifications made where
exact fidelity was not tractable at this compute budget (decay term,
exposure/slew cost, wavelength bands).

**Scenario split across phases**: the manuscript lists five scenarios
(Nominal, Communication sweep, Node loss, Crowding, Model error) without
assigning them to a phase. Communication sweep and Node loss are about
multi-spacecraft belief staleness, which does not exist until Phase 4
(decentralization). Phase 2 (a single centralized planner) runs Nominal,
Crowding, and Model error; Phase 4 runs Communication sweep and Node loss
alongside its own contact-fraction sweep, which subsumes them.
