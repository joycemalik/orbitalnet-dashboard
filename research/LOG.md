# research/ LOG

Running log of what was built, what passed, what surprised us, and decisions
made on ambiguous points. Append-only, one section per phase.

## Phase 2c — validation tuning outcome and preregistration (2026-10-22)

Grid (S1, validation seed 1, 500 events): results/phase2/selection_validation.json.
P mean log score by config (best first): g0.1/l1.2 -0.210, g0.1/l0.3 -0.245,
g0.01/l1.2 -0.284, g0.01/l0.3 -0.291, g0.001/l1.2 -0.640, ... g0.1/l5 -1.234.
Rule -> **gamma 0.1, lengthscale 1.2 d** (edge of grid; stated as limitation).
Larger gamma -> P uses more of its budget (obs 3.3 at 1e-4 -> 4.2 at 0.1)
and recovers more amplitude information on fast classes.

Dry run, chosen config (results/phase2/analysis_validation_chosen.json):
S1 H1 FAIL (P median 0.956 d = B2's; vs B3 9.65 d), H2 pass +0.321
[0.165, 0.479], H3 pass dTPR +0.72 (AUROC 0.993 vs B3 entropy 0.662).
S2: H1 fail, H2/H3 pass. S3 (model error): H2 -0.077 [-0.179, 0.023], H3
pass (AUROC 0.870 vs 0.709). H1 criterion kept as written. Frozen in
PREREGISTRATION_PHASE2.md.

## Phase 6 — PREREGISTERED V3 TEST RESULT: causal real replay (2026-10-22)

Run exactly as frozen in PREREGISTRATION_V3.md (commit 9c9a024). THIRD look
at the two-band test events (declared). 364 events (276 SNe, 88 real
unmodeled), seeds 1-3. Analysis: results/phase6/analysis_test_v3.json.

| | seed 1 | seed 2 | seed 3 | verdict |
|---|---|---|---|---|
| H1 P - B3 confident-wrong, unmodeled | -0.489 [-0.602, -0.364] | -0.420 [-0.545, -0.295] | -0.364 [-0.477, -0.250] | **PASS** |
| H2 AUROC of P(h0) | 0.811 [0.758, 0.859] | 0.812 [0.756, 0.862] | 0.788 [0.733, 0.840] | **PASS** |
| H3 P - B3 confident-wrong, SNe (< +0.05) | -0.047 [-0.087, -0.007] | -0.036 [-0.080, 0.004] | -0.033 [-0.072, 0.011] | **PASS** |
| H4 AUROC gain vs single band | +0.187 [0.133, 0.244] | +0.175 [0.116, 0.235] | +0.241 [0.183, 0.301] | **PASS** |
| H5 P - B3 SN accuracy (> -0.05) | +0.011 [-0.051, 0.072] | +0.025 [-0.040, 0.091] | -0.014 [-0.076, 0.047] | **FAIL** |

Reported (seed 1/2/3): confident-wrong on unmodeled B3 0.56/0.52/0.50,
B1 0.46/0.40/0.44, B2 0.16/0.11/0.21, P 0.07/0.10/0.14. P flags
42%/47%/39% of unmodeled events (v2 retrospective: 66/73/64%); false
"unknown" on SNe 8%/8%/8% (v2: 24%). SN accuracy P 0.59/0.63/0.60 vs
B3 0.58/0.60/0.62 (point estimates now equal or better; H5 fails only
because the lower CI bound is -0.051 and -0.076 on seeds 1 and 3).

What this means:
- With a time arrow, the open-world planner's cost on ordinary SNe largely
  disappears: H3 now passes (failed in Phase 3 and v2), false "unknown"
  drops from ~24% to ~8%, and P's SN accuracy matches B3's. H5 still fails
  formally: the CIs are too wide to rule out a 5-point loss.
- The price moved to the unknowns: P flags fewer of them (~43% vs ~68%
  retrospectively), because causally the planners use only ~2-3 of 5
  measurements (greedy jumps late). Closed-world planners are also less
  often confidently wrong causally (B3 ~0.53 vs ~0.79) for the same reason:
  fewer measurements, less confidence.
- AUROC of P(h0) is essentially unchanged (0.79-0.81 vs 0.77-0.80).

## Causality bug found; Phase 2c (causal simulation) and Phase 6 (causal real replay) — protocol (2026-10-22)

### The bug
No phase enforced a time arrow. Every planner chose any unused (epoch,
satellite) cell, so it could measure at day 0.01 after measuring at day 0.96.
Measured on 40 Phase 2 events (seed 7): B1 40/40, B2 38/40, B3 39/40,
P 38/40 sequences went backwards in time; only B0 (earliest-first) was
forward. Phases 1 and 3-5 used the same loop.

What it means for existing results: strategies were compared fairly (all
had the same freedom), but the comparison is RETROSPECTIVE EPOCH SELECTION
(choose 5 of 16 epochs, adaptively, in any order), not sequential follow-up.
Decision (user, 2026-10-22): keep Phase 1 / 3-5 numbers, relabel them as
retrospective epoch selection everywhere they appear, and re-run causally
as new, separately labelled experiments. They are not replaced.

### Fix
Strictly forward (user's choice): after a measurement at epoch i, epochs
<= i are closed for that strategy (one measurement per epoch). Phase 2:
always on. Real replay: `--causal` (off reproduces Phases 3-5 exactly;
tested). Tests: research/tests/test_causal.py.

### Phase 2c: what changed besides causality (manuscript H1-H3 now testable)
- H1 metric was wrong: `time_to_identification` fired when ANY class passed
  0.95 and counted steps. Now: time (days) of the first measurement at which
  the posterior on the TRUE class >= 0.95; censored (inf) if never.
- Ablations added (manuscript "Ablations"): P_no_decay (gamma = 0) and
  P_no_adequacy (beta = 0, h0 kept in belief and mode switch).
- H2 metric: information recovered about ln(amplitude) under the true class,
  0.5 ln(1 + Var_prior(ln A) * sum_i SNR_i^2) on the noise-free true signal
  (amplitude is the only physical parameter in these models). The grid
  entropy version is also recorded but saturates at ln(15) — not primary.
- H3 comparator: entropy of the closed-world posterior ("classifier-entropy
  threshold"), recorded for every strategy.
- Runner takes --split/--seed/--n-events, runs events in parallel (same
  per-event SeedSequence, so results do not depend on worker count), test
  seeds (>= 1000) locked until PREREGISTRATION_PHASE2.md exists (it used to
  check Phase 3's file).
- The old non-causal Phase 2 was never run at scale; nothing is superseded.

### Phase 2c validation tuning protocol (written BEFORE any run is seen)
Smoke run (seed 99, 60 events, scratch dir, default gamma 0.01) showed the
decay term dominates the utility at gamma = 0.01 (SNR^2 up to ~2500 vs
I_class <= ln 4), so gamma must be calibrated, as the manuscript asks.
- Split: validation, S1_nominal, seed 1, 500 events.
- Grid: gamma in {1e-4, 1e-3, 1e-2, 1e-1} x h0 GP lengthscale in
  {0.3, 1.2, 5} d. beta fixed at 1 (manuscript default; not tuned).
  gamma = 0 is not in the grid: it is the H2 ablation, not a configuration.
- Rule: maximize P's mean log score over ALL validation events (proper
  scoring rule; covers modeled and withheld truth, favours no single
  hypothesis). Ties within 0.02 -> smaller gamma, then lengthscale 1.2.
- Then at the chosen config: S2_crowding (seed 2) and S3_model_error
  (seed 3), 500 validation events each, and a dry run of the analysis.
  Then PREREGISTRATION_PHASE2.md, then test (seeds 1000/2000/3000, 1000 events).

### Phase 6 (causal real replay) validation protocol (written BEFORE any run)
Same two-band event set, validation split, seed 1, all with --causal:
gr@5 x kappa {0, 0.5, 1} (l = 5 d), plus r@5 (Phase 3 config) as the H4
control. Rule as before: max P AUROC; ties within 0.01 -> lower P
confident-wrong on modeled. Then PREREGISTRATION_V3.md with the V2
hypotheses H1-H5 unchanged, and a DECLARED THIRD LOOK at the test events
(seeds 1-3; chosen config, r@5 and r@10 controls, all causal).

## Phases 4+5 — PREREGISTERED V2 TEST RESULT (2026-10-12)

Run exactly as frozen in PREREGISTRATION_V2.md (commit b5374da, recorded in
all 9 test config.json files). SECOND look at the test events (declared).
364 two-band test events (276 SNe, 88 real unmodeled), seeds 1-3.
Analysis: results/phase5/analysis_test_v2.json.

| | seed 1 | seed 2 | seed 3 | verdict |
|---|---|---|---|---|
| H1 P - B3 confident-wrong, unmodeled | -0.602 [-0.716, -0.489] | -0.670 [-0.773, -0.557] | -0.602 [-0.727, -0.477] | **PASS** |
| H2 AUROC of P(h0) | 0.798 [0.747, 0.846] | 0.802 [0.746, 0.853] | 0.771 [0.714, 0.824] | **PASS** |
| H3 P - B3 confident-wrong, SNe (< +0.05) | +0.004 [-0.058, 0.065] | +0.036 [-0.025, 0.098] | +0.058 [-0.007, 0.123] | **FAIL** |
| H4 AUROC gain vs single-band Phase 3 config | +0.193 [0.143, 0.244] | +0.214 [0.161, 0.270] | +0.146 [0.098, 0.196] | **PASS** |
| H5 P - B3 SN accuracy (> -0.05) | -0.080 [-0.141, -0.018] | -0.062 [-0.127, 0.004] | -0.076 [-0.141, -0.011] | **FAIL** |

Reported (seed 1/2/3): AUROC gain vs r@10 (same flux count) +0.181/+0.194/+0.169,
all CIs > 0. P flags 66%/73%/64% of real unmodeled events; false "unknown"
on SNe 24%/25%/24% (Phase 3 test: ~40%). Confident-wrong on unmodeled:
B3 0.795/0.795/0.784, B1 (CNP auction) 0.477/0.489/0.489, P 0.193/0.125/0.182.
SN accuracy: P 0.54/0.53/0.54, B3 0.62/0.59/0.62; single-band P was 0.33-0.37.

What this means:
- Confirmed on held-out real data: colour + model discrepancy turn P(h0)
  from a weak signal (AUROC ~0.60) into a usable one (~0.79), and the gain
  is colour, not data volume.
- Robust across both test looks: closed-world planners are confidently
  wrong on ~3/4-4/5 of genuinely unmodeled real transients; P cuts that
  ~4-6x while flagging ~2/3 of them.
- FAILED (H3, H5): P still pays for this on ordinary SNe — ~6-8 points lower
  accuracy than B3, and we cannot rule out more confident errors. The
  validation numbers (P accuracy = B3's) were optimistic; the test set says
  the trade-off is reduced, not eliminated.
- Validation -> test drift: AUROC 0.85 -> 0.79, false-alarm 0.16 -> 0.24.
  Expected regression to the mean after picking the best of 11 configs.

## Phase 5 — model discrepancy: templates carry real population scatter (2026-10-12)

Motivation (from the Phase 3 test): P calls ~40% of ordinary SNe "unknown".
Each modeled class predicts its median template EXACTLY (+ instrument
noise), so any real SN that deviates from the median is heavily penalized
while the flexible h0 GP is not — h0 wins by default. Standard remedy in
template fitting: a model-discrepancy term. Hypothesis: adding each class's
real scatter lowers false "unknown" calls without losing the unknowns.

### Design (written BEFORE any Phase 5 run was seen)
- Scatter s_c(t): 1.4826*MAD across TEMPLATE-split (pre-2020) events'
  normalized curves around the class median, per band, same normalization
  as the templates. Values ~0.1-0.4 of peak (checked, not tuned).
- Likelihood: y ~ N(A T_c(t), sigma_inst^2 + (kappa * A * s_c(t))^2).
  Belief update only — planners still score candidates with instrument
  noise (documented simplification). Discrepancy is treated as independent
  between measurements (in reality an event deviates coherently; this
  under-penalizes repeated deviations — stated limitation).
- kappa = 0 reproduces Phase 3/4 bit-identically (tested).
- Validation grid (seed 1, two-band event set, GP lengthscale 5 d):
  bands {r, gr} x kappa {0.5, 1, 2}. kappa=0 arms are the Phase 4 runs.

### Phases 4+5 validation outcome (seed 1, 362 common events, 81 unmodeled)
Source: results/phase5/compare_validation_all.json. P = open-world planner.

| arm | P AUROC | P acc SNe | P false "unknown" | P flags unknowns | P cw unknown | B3 cw unknown | B3 acc SNe |
|---|---|---|---|---|---|---|---|
| r@5 (Phase 3 config) | 0.614 | 0.406 | 0.295 | 0.519 | 0.222 | 0.691 | 0.470 |
| r@10 | 0.607 | 0.335 | 0.402 | 0.605 | 0.198 | 0.741 | 0.480 |
| gr@5, l=5 | 0.733 | 0.463 | 0.384 | 0.741 | 0.111 | 0.852 | 0.587 |
| gr@5, l=10 | 0.724 | 0.438 | 0.423 | 0.765 | 0.086 | 0.852 | 0.587 |
| gr@5, l=20 | 0.721 | 0.402 | 0.459 | 0.840 | 0.037 | 0.852 | 0.587 |
| r@5, kappa 0.5 | 0.680 | 0.541 | 0.117 | 0.383 | 0.198 | 0.506 | 0.491 |
| r@5, kappa 1 | 0.680 | 0.548 | 0.075 | 0.309 | 0.062 | 0.321 | 0.488 |
| r@5, kappa 2 | 0.594 | 0.488 | 0.132 | 0.198 | 0.012 | 0.185 | 0.459 |
| **gr@5, kappa 0.5** | **0.846** | **0.594** | **0.164** | 0.691 | 0.198 | 0.753 | 0.584 |
| gr@5, kappa 1 | 0.822 | 0.644 | 0.082 | 0.506 | 0.173 | 0.617 | 0.552 |
| gr@5, kappa 2 | 0.663 | 0.491 | 0.146 | 0.296 | 0.185 | 0.457 | 0.427 |

Reading:
- Colour is the lever, not data volume: r@10 (same number of fluxes as gr@5)
  does not raise AUROC (0.607 vs 0.614); gr@5 does (+0.12).
- Colour alone makes everyone more confident — including confidently wrong
  (B3 on unknowns 0.69 -> 0.85; P on SNe 0.30 -> 0.44).
- The discrepancy term fixes P's over-confidence: false "unknown" 0.30 ->
  0.16, SN accuracy 0.41 -> 0.59 (matching B3), AUROC 0.61 -> 0.85.
- Too much discrepancy (kappa 2) makes modeled classes absorb everything
  (same failure mode as the stretch idea).
- Robustness of the Phase 3 config (results/phase3_robustness):
  P's AUROC 0.57-0.64 and its large confident-wrong advantage on unknowns
  hold for budget 3/8 and 4/16 satellites. A 45 deg Sun-exclusion cone
  changed visibility for only 17/439 events (ZTF finds transients at night,
  i.e. away from the Sun — a selection effect, not a bug; verified per event).

Rule -> **gr@5, kappa 0.5, l = 5 d**. Dry-run of the v2 analysis on validation
(results/phase5/analysis_validation_chosen.json): H1-H5 all pass; H5 only
barely (lower CI -0.050 vs margin -0.05). Frozen in PREREGISTRATION_V2.md.

### Revised plan for the second test look (fixed now)
Instead of one test run per phase, Phases 4 and 5 share ONE second look:
pick the single best config on validation among {gr@5 x lengthscale} and
{r, gr} x kappa (rule: max P AUROC; ties within 0.01 -> lower P
confident-wrong on modeled), freeze it in PREREGISTRATION_V2.md with the
same H1-H3 + the r@5/r@10 controls, run the test split once.

## Phase 3 — PREREGISTERED TEST RESULT (2026-10-12)

Run exactly as frozen in PREREGISTRATION.md (commit 6ba1d6d, recorded in
every test config.json): test split, 439 real events (347 SNe, 92 real
unmodeled: TDE/SLSN/Ibn), noise seeds 1-3. Analysis:
`results/phase3/analysis_test.json` (stratified paired bootstrap, 10k).

| | seed 1 | seed 2 | seed 3 | verdict |
|---|---|---|---|---|
| H1: P - B3 confident-wrong, unmodeled | -0.543 [-0.652, -0.435] | -0.685 [-0.783, -0.587] | -0.576 [-0.685, -0.457] | **PASS** |
| H2: AUROC of P(h0) | 0.625 [0.560, 0.687] | 0.643 [0.580, 0.704] | 0.641 [0.578, 0.701] | **PASS** |
| H3: P - B3 confident-wrong, SNe (< +0.05) | +0.043 [-0.017, 0.104] | +0.046 [-0.014, 0.107] | +0.000 [-0.061, 0.061] | **FAIL** |

Reported (seed 1 / 2 / 3):
- Confident-wrong on real unmodeled events: B3 0.717/0.772/0.750,
  B1 (live-stack CNP auction) 0.391/0.467/0.402, **P 0.174/0.087/0.174**.
  P - B1: -0.217/-0.380/-0.228, all CIs below 0.
- P identifies unmodeled events as h0: 0.554/0.630/0.587 (baselines: 0 by construction).
- Cost: P calls 41%/41%/36% of ordinary SNe "unknown" (validation: 29% —
  worse on test). SN accuracy P 0.31-0.35 vs B3 0.50-0.52 (chance 0.33).

What this means:
- The headline survives a sealed test: on real data, closed-world planners
  are confidently wrong about ~3/4 of genuinely unmodeled transients; the
  open-world planner cuts that ~4-9x and flags ~60% of them as unknown.
- H3 failed: we cannot claim P is no worse on ordinary SNe; the CI allows
  up to ~10 points more confident errors. Combined with a ~40% false
  "unknown" rate and SN accuracy at chance, P on single-band data buys
  safety on unknowns by giving up classification of knowns. That is the
  honest trade-off, and the reason for Phase 4 (colour).
- Caveat on the metric: B0 (fixed cadence) is almost never confident, so
  its confident-wrong rate is ~2% — low confident-wrong alone is not
  success; P's case rests on H1 *together with* actually flagging h0.

## Phase 4 — colour: two-band (g+r) replay (2026-10-12)

Motivation: Phase 3 validation showed P can barely rank real unmodeled
events above ordinary SNe (AUROC ~0.59) from 5 single-band points, and SN
Ia vs Ibc are confused — exactly the cases astronomers separate with
colour. Hypothesis: giving every pointing a simultaneous g and r flux
(a dual-band imager) lets the open-world planner separate the classes.

### Design (written BEFORE any Phase 4 run was seen)
- Event set: Phase 3 events that ALSO have >= 8 g-band detections
  (1,121 usable; split 394 template / 363 validation / 364 test). Both arms
  below use this same event set, so the comparison is paired.
- g templates: each template-split event's g truth curve divided by its
  r-band PEAK, median per class — keeps the class colour evolution.
- Each pointing returns r and g at once (same instrument noise per band);
  the g value enters belief/GP at t + 1e4 d (zero cross-band GP covariance,
  shared amplitude). Planners still score candidates on r-band predictions
  only — colour enters through the measurements, not the choice.
- g-band noise is drawn after r noise, so the r values are bit-identical
  between arms (tested).
- Arms: r@5 (Phase 3 config on this event set), gr@5 (same pointings,
  colour added), r@10 (same NUMBER of fluxes as gr@5 — controls for "it's
  just more data").

### Validation tuning protocol (fixed now)
Validation split, seed 1. gr@5 with h0 GP lengthscale in {5, 10, 20} d;
r@5 and r@10 at the frozen Phase 3 lengthscale (5 d). Selection rule for
the gr config: same as Phase 3 (max P AUROC; ties within 0.01 -> lower P
confident-wrong on modeled). Then PREREGISTRATION_PHASE4.md, then test.

### Declared test-set reuse
The Phase 4 test events are a subset of the Phase 3 test events. Phase 4
was designed while the Phase 3 test run was still in progress (before its
numbers were seen), but Phase 3 test results WILL be seen before Phase 4's
test run, so Phase 4 is a second look at those events. Its config was chosen on validation only, and
this reuse must be stated wherever Phase 4 test numbers are reported.

## Phase 3 — real-data counterfactual replay: infrastructure (2026-10-11)

Status: pipeline built and tested; NO results yet. Raw data download is
incomplete (see "Open items"), so nothing has been run at scale.

### What it is
Real ZTF Bright Transient Survey events (spectroscopic class = truth, real
r-band light curve, real RA/Dec, real date) replayed against the Phase 2
Starlink fleet propagated from Space-Track TLEs archived at the time. Only
the planners' measurements are simulated (GP mean through the real points +
limiting-magnitude instrument noise). Same 5 strategies as Phase 2, unchanged.

### Decisions
- **Hypothesis set**: modeled = SN Ia / SN II / SN Ibc; withheld (real h0) =
  TDE, SLSN-I/II, SN Ibn. User chose "both studies": this SN study is the
  main one; a small case study on the manuscript classes is still to do.
- **Class models are empirical templates** (median peak-normalized curve)
  built ONLY from events first detected before 2020-01-01, i.e. before the
  fleet existed. Default chosen by me when the user said "start the next
  phase" without picking between this and sncosmo; flagged in chat.
- **Split**: template = pre-2020; post-2020 events halved by date into
  validation (older) and test (newer). Test is locked in code until
  PREREGISTRATION.md exists.
- **Selection bug fixed**: first selection took the EARLIEST 300 events per
  class, so almost all supernovae predated the fleet. Now per modeled class:
  up to 300 pre-2020 + 300 post-2020, evenly spaced in time; all withheld.
- **No truth extrapolation**: candidate times after an event's last real
  detection are infeasible for every strategy.
- **No stale orbits**: a cell is infeasible if the nearest archived TLE
  containing that satellite is > 7 days from the observation time.
- **h0 GP**: signal amplitude marginalized over the same amplitude grid as the
  modeled classes (real fluxes span ~3 dex; a fixed var_f would make h0
  evidence track brightness instead of shape). Lengthscale 10 d, fixed,
  tunable on validation only.
- Candidate times 0.5-60 d (16 log-spaced), budget 5, 8 satellites,
  limiting mags 19/20/21: same structure as Phase 2, timescale widened for SNe.
- Sun exclusion still NOT modeled (now possible since dates are real; future work).

### Validation tuning protocol (written BEFORE any tuning run was seen)
First validation run (seed 1, no stretch, GP lengthscale 10 d; committed
180660f): P's AUROC(P(h0): withheld vs modeled) = 0.582, and P decided h0 on
33% of modeled SNe. Diagnosis: a single fixed median template per class is
too rigid for real SN diversity, so the flexible h0 GP wins by default.

Change: optional per-event template stretch s (f = A * template(t/s)),
log-uniform over 7 values in [0.5, 2.0]; marginalized like amplitude.
B2/P decay terms now use posterior-mean flux (identical to before for
amplitude-only models; verified max diff 3.6e-15 on Phase 2 beliefs).

Grid (validation split, seed 1 only):
  stretch in {off, [0.5, 2.0]} x GP lengthscale in {5, 10, 20} days.
Selection rule, fixed now: pick the config with the highest P AUROC; ties
(within 0.01) broken by lower P confident-wrong rate on MODELED events.
The chosen config is then frozen in PREREGISTRATION.md before the test
split is run once. All configs' results are kept, not just the winner.

### Validation tuning outcome (seed 1, 439 events each)
| config | P AUROC | P cw modeled | P cw withheld | P h0 on modeled | B3 cw withheld |
|---|---|---|---|---|---|
| no stretch, l=5  | 0.593 | 0.281 | 0.195 | 0.287 | 0.759 |
| no stretch, l=10 | 0.582 | 0.295 | 0.115 | 0.332 | 0.759 |
| no stretch, l=20 | 0.593 | 0.310 | 0.103 | 0.369 | 0.759 |
| stretch, l=5     | 0.562 | 0.256 | 0.092 | 0.281 | 0.414 |
| stretch, l=10    | 0.552 | 0.267 | 0.069 | 0.330 | 0.414 |
| stretch, l=20    | 0.570 | 0.273 | 0.023 | 0.369 | 0.414 |
(numbers copied from results/phase3/validation_seed1*/summary.json)

Pre-declared rule -> tie at 0.593 (l=5, l=20), broken by lower P
confident-wrong on modeled -> **no stretch, GP lengthscale 5 d**.

What this says, honestly: the stretch hypothesis was WRONG — it did not
raise AUROC; it made the modeled classes flexible enough to absorb many
withheld events (B3 confident-wrong on withheld fell 0.76 -> 0.41), which
also blurs the h0 signal. P's ability to *rank* unmodeled above modeled
events is weak in every config (AUROC 0.55-0.59). The robust effect is
the confident-wrong reduction on real unmodeled events, which comes with
a ~29% h0 false-alarm rate on ordinary SNe. Likely ceiling: 5 single-band
points cannot separate SN subtypes or many TDE/SLSN shapes; colour
(multi-band) is the obvious next lever, and is NOT tried before the test run.

### Losses (reported by the loader, never silent)
- ~35% of downloaded objects have < 8 r-band detections and are dropped.
- 30 TLE weeks Feb-Aug 2021 came back EMPTY although the fleet was in orbit
  (likely Space-Track throttling). Events there currently get no contact.

### Open items
1. Re-run `fetch_bts` (~1,100 new light curves for the post-2020 pool).
2. Re-run `fetch_tles` for new event weeks, after deleting the empty 2021 files.
3. Validation run, then PREREGISTRATION.md, then test run.
4. Viewer replay tab; manuscript-class case study.

## Phase 2 — single-planner experiment with real orbits (2026-10-01)

### Two passes: own design, then realigned to the manuscript
Phase 2 was built twice. The first pass (documented in the earlier parts of
this entry's git history) used toy exponential/plateau/oscillating classes,
a plain-EIG utility with no decay/adequacy weighting, and 5 scenarios
varying fleet size — all explicitly labeled "this project's own design"
because no manuscript existed yet. Mid-session the user supplied
`Hypothesis-Discriminating Observation Campaigns for Distributed
Space Observatories.pdf`. Its Part IV defines H1-H4, the utility function
(eq. 3-4), the exact class list, and the scenario list precisely — all
different from the first pass. The first pass's validation results
(null control passed on all 5 of the old scenarios) were discarded rather
than used for a preregistration, since preregistering against a superseded
design would have been pointless. Phase 2 was then rebuilt to match the
manuscript. This section documents the SECOND (current) build.

### Built
- `transients/models.py`: replaced the toy P2 classes with the manuscript's
  4 modeled (kilonova, shock-cooling/Type IIb early phase, GRB afterglow
  broken power-law, M-dwarf flare) + 3 withheld (FBOT/AT2018cow-like, TDE,
  synthetic "nonsense") classes, as physically-motivated analytic
  approximations — NOT the published templates (sncosmo etc.) the
  manuscript asks for, since this branch has no network access beyond
  `requirements-research.txt`. Documented inline and here; replacing these
  with real forward models is the single highest-value follow-up.
  Also added `modeled_flux_fn_p2_perturbed(cls, factor)` (time-dilates a
  class's shape by `factor`) for the model-error scenario.
- `inference/mutual_information.py`: added `expected_information_gain_batch`
  (Phase 1 already had the scalar version); this was already done before
  the manuscript arrived but is load-bearing for Phase 2's utility.
- `planners/phase2.py`: rewrote the baselines to match the manuscript's
  definitions — B0 is now a deterministic fixed-cadence dispatcher (was
  random), B2 is now a "classifier-entropy" disagreement heuristic over
  point-estimate amplitudes with no Bayesian marginal-likelihood machinery
  (was best-SNR greedy). B1 (CNP reimplementation) and B3 (closed-world EIG,
  renamed internally to share a `_class_only_eig_batch` helper with P)
  needed no change. P now computes `U = I_class + beta*I_Z + gamma*D`:
  - `I_class`: exact, via `_class_only_eig_batch` (closed-world only, same
    computation B3 uses).
  - `I_Z` (adequacy term): exact, by reusing the already-built open-world
    cell/weight machinery with a 2-group split (all modeled cells vs. the
    single h0 cell) instead of the old per-class+h0 grouping — this is
    actually simpler than what was there before.
  - `D` (decay term): **approximated**, not exact. The manuscript's
    `I_k(Y_a)` is a per-class mutual-information quantity that would need
    one more EIG quadrature per class per candidate per step — at ~1000
    events x 3 scenarios this was not affordable on top of I_class and I_Z.
    Used a Fisher-information-style SNR² proxy instead:
    `D ≈ Σ_k b_t(h_k) · [SNR_k(t)² − SNR_k(t')²]₊` where t' is the next
    time the same satellite is visible (or SNR treated as 0 if there is no
    later opportunity, i.e. maximal urgency). SNR² is the right order
    for Fisher information of an amplitude-like parameter under Gaussian
    noise, so this is a defensible proxy, not an arbitrary one, but it is
    not what eq. 4 literally specifies. Tested in
    `tests/test_phase2_utility.py` (zero when nothing is lost by waiting,
    positive when the class is fading).
  - `cost(a)`: fixed at 1 (uniform). The manuscript's exposure/slew cost
    model is not implemented.
  - beta=1.0, gamma=0.01 are fixed defaults chosen so I_class/I_Z (nats,
    O(0-1.4) for K=4) and D (SNR² units, empirically larger) land on a
    comparable scale — picked for scale-matching before seeing results, not
    tuned against outcomes. The manuscript's own statistics section says to
    tune beta/gamma on a validation split; that calibration step is not yet
    automated here (see "What we distrust" below).
  - Mode switch (manuscript 5.5): implemented as a fallback at the
    experiment-script level (`phase2_single_planner.run_one_event`), not
    inside the planner — once P(h0) exceeds `MODE_SWITCH_TAU=0.9` for two
    consecutive steps, remaining steps for that event use
    `fixed_cadence_planner` instead of P's own EIG utility, approximating
    "maximize coverage" with "take whatever's next." A `time_coverage_fraction`
    metric (fraction of the full candidate-time range spanned by chosen
    measurements) stands in for the manuscript's wavelength-coverage
    preservation metric, since no wavelength bands are modeled.
- `experiments/scenarios.py`: replaced the fleet-size-based S1-S5 with
  Nominal / Crowding / Model-error (3 scenarios); Communication sweep and
  Node loss are reserved for Phase 4 (see PLAN.md section 6 for why).
  Crowding randomly masks a fraction of (time, satellite) cells once per
  event, shared across strategies. Model error swaps the BELIEF's
  (not the true event's) flux resolver for the time-dilated perturbed one.
- `experiments/phase2_single_planner.py`: widened `CANDIDATE_TIMES_DAYS`
  from [0.2, 10] days (12 points) to [0.01, 20] days (16 points) — the
  manuscript's classes span minutes (flare) to weeks (TDE), which the old
  grid could not represent. `CONFIDENT_THRESHOLD` raised to 0.95 (manuscript
  H1). Added the mode-switch/preservation logic described above.

### Tests passed
`pytest research/` — 33/33 passed, including:
- `test_phase2_planners.py`: updated for the renamed B0/B2 (fixed-cadence
  picks the deterministic earliest-time/lowest-satellite cell;
  classifier-entropy matches its own documented disagreement formula
  independently recomputed in the test).
- `test_phase2_utility.py` (new): the perturbed-model resolver equals the
  true model evaluated at `t/factor`; `_next_visible_index` finds the
  correct next-visible slot per satellite; the decay-term proxy is exactly
  zero when waiting loses nothing and strictly positive when the class is
  fading.

### What we distrust about this result
- The decay term is a proxy, not eq. 4's literal quantity (see above) — H2
  (irreversibility) should be read as testing "does SOME decay-aware term
  help fast classes more," not as a direct test of the manuscript's exact
  formulation.
- beta/gamma are fixed, not calibrated on a validation split as the
  manuscript's statistics section asks — a real calibration pass (sweep a
  small grid on validation seeds, pick by some criterion, freeze before
  test seeds) should happen before any of this is reported as more than a
  qualitative existence check.
- The forward models are this project's own analytic approximations of the
  named classes' qualitative shapes (timescale family, single/double-peaked,
  power-law vs. exponential), not the published templates the manuscript
  calls for. Good enough to test the PLANNER logic; not good enough to
  claim astrophysical realism.
- `cost(a)=1` for every action means the utility's division by cost is a
  no-op right now; the manuscript's resource-cost model (exposure, slew) is
  unimplemented.
- Crowding and model-error are this project's own operationalizations of
  the manuscript's scenario names (cell-masking; time-dilated belief), not
  validated against any other source — documented as such in scenarios.py.

## Phase 1 — Existence proof (2026-10-01)

### Built
- `transients/models.py`: two modeled classes ("fast" tau=1.0d, "slow" tau=4.0d,
  pure exponential decay) + one withheld class ("bump": Gaussian rise + exp
  decay), amplitude drawn log-uniform per event.
- `transients/noise.py`: fixed-sigma (SIGMA0=1.0) additive Gaussian noise,
  pre-drawn per candidate time so every strategy sees identical noise at a
  given time for a given event (paired comparison).
- `inference/bayes.py`: exact discrete joint posterior over (class, amplitude
  grid of 25 log-spaced points), closed-form Bayesian update, class-marginal
  posterior, per-class evidence (marginalized over amplitude).
- `inference/mutual_information.py`: expected information gain via exact 1D
  trapezoidal quadrature over the observation y (no Monte Carlo).
- `inference/openworld.py`: fixed-hyperparameter RBF-kernel GP
  (lengthscale=1.2d, var_f=100) as the h0 model; top-level Bayes-factor
  posterior over {fast, slow, h0}.
- `planners/`: `random` (B0-style), `B3_closed_world_eig` (ignores h0),
  `P_open_world_eig` (includes h0 and the GP predictive in its EIG search).
- `experiments/phase1_existence_proof.py`: runs all three strategies on
  IDENTICAL events/noise per seed, writes config/summary/worked_example JSON
  (committed) and events_raw.jsonl (gitignored), updates progress.json live.
- `app/viewer.py` + `app/data.py` + `app/plotting.py`: read-only Streamlit
  viewer, 6 tabs (one per phase), provenance line (seed/git hash/config hash)
  on every result page, DEMO warning on tag="demo" runs.
- `launch.py` + `launch_research.bat`: dependency check, background
  experiment subprocess, viewer on port 8502 (never 8501), browser open,
  clean shutdown on Ctrl+C.

### Tests passed
`pytest research/` — 9/9 passed:
- Bayesian update vs. independently-computed (`scipy.stats.norm`) closed-form
  posterior, single update and sequential updates.
- Posterior concentration sanity check under near-zero noise.
- EIG == 0 for indistinguishable predictives (known answer).
- EIG -> ln(2) in the noiseless, well-separated, uniform-binary-prior limit
  (known answer).
- EIG strictly between 0 and ln(2) for partial separation (sanity bound).
- GP log marginal likelihood vs. independently-computed (`scipy.stats.norm`)
  closed form for a single observation (known answer).
- GP behaves as its prior with zero observations.

### Quick demo result (seed=0, n_events=100, tag=demo)
| strategy | confident-wrong (modeled truth) | confident-wrong (withheld truth) | accuracy (withheld, h0 credited) |
|---|---|---|---|
| random | 0.000 | 0.879 | 0.000 |
| B3_closed_world_eig | 0.000 | 1.000 | 0.000 |
| P_open_world_eig | 0.000 | 0.121 | 0.788 |

B3 is confidently wrong on every single withheld-class event (it has no way to
say "neither"); P drops that to 12% and correctly attributes 79% of withheld
events to h0. Neither strategy is ever confidently wrong when the truth is
actually a modeled class. This is the qualitative result the research goal
predicts, from real code on a real (if small) sample — not asserted a priori.

### Surprises
- **Performance bug found during the quick-demo run**: the initial
  `expected_information_gain` implementation looped in Python over all 2001
  quadrature points, calling a Python-level `group_entropy` (itself another
  Python loop) at each one. 5 events took 3m42s. Root cause: no vectorization
  across the quadrature axis. Fixed by vectorizing both the quadrature loop
  and the per-group logsumexp (loop only over the tiny number of groups, 2-3,
  never over the 2001 y-points or the event/strategy loops). After the fix:
  5 events in 5.2s, 100 events in 159.5s (quick demo), pytest suite 8.2s -> 0.48s.
  This would have made Phase 2+ (1000+ events, more candidates, orbits)
  completely infeasible if left unfixed — worth flagging because it was a
  silent correctness-preserving-but-unusably-slow bug, exactly the kind of
  thing that would otherwise surface much later as "Phase 2 is taking days."

### Decisions made on ambiguous points
- **Streamlit import in `research/app/`**: the branch rule in CLAUDE.md says
  new work in `research/` "must NOT import redis, streamlit, websockets, or
  any live-stack module." The user's own follow-up instruction explicitly
  asked for `research/app/` to be "a Streamlit app... still headless at the
  core," and only restated the redis/websockets ban for it. Read this as: the
  core research packages (transients/, inference/, planners/, experiments/)
  stay streamlit-free and fully unit-testable; `research/app/` is a narrow,
  explicitly-requested exception that only reads result files and never
  computes. Flagged to the user rather than silently assumed.
- **`launch_research.bat` lives at the repo root**, outside `research/`,
  because a "one-click launcher" only works there, and the user asked for it
  by that exact name. Also flagged as a narrow exception to "work only inside
  research/".
- **Phase 1 noise model**: fixed-sigma additive Gaussian (not yet the
  limiting-magnitude model — that's explicitly a Phase 2 item per the
  original brief). Chosen so the Bayesian update and MI estimator have exact
  Gaussian likelihoods, which is what makes the known-answer tests possible.
- **GP hyperparameters are fixed, not optimized** (lengthscale=1.2d,
  var_f=100): a notebook-sized existence proof doesn't need marginal-
  likelihood hyperparameter optimization, and fixing them keeps Phase 1 fully
  deterministic given a seed. Revisit in Phase 2+ if GP evidence turns out to
  be sensitive to this choice.
- **Confident-wrong threshold = 0.9**, **n_obs_budget = 5**, **amplitude grid
  = 25 log-spaced points**, **20 log-spaced candidate times from 0.2 to 10
  days**: reasonable round-number choices for a notebook-sized demo, not
  tuned against the outcome (chosen before the first run, unchanged after
  seeing results).

### What we distrust about this result
- n=100 is a demo sample; the confident-wrong-rate numbers above have real
  sampling noise (e.g. 0.879 vs 0.788 are not precise to three decimals at
  this n). Phase 2's acceptance criterion (1000 events) is what the paired
  comparison should actually be judged on.
- The GP's fixed hyperparameters were chosen by eye, not fit or
  cross-validated. If Phase 2's instrument noise model makes light curves
  noisier or shorter in duration, these may need revisiting — and if they
  do, that revisit must happen on validation seeds only, per the branch
  preregistration rule, not on whatever seed produces a nicer plot.
- "Confident-wrong" is a threshold-based summary (0.9) of what is really a
  continuous miscalibration story; Phase 2's AUROC-of-P(h0) metric is a more
  complete picture and should be treated as the primary evidence over this
  single-threshold number.
