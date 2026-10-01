# research/ LOG

Running log of what was built, what passed, what surprised us, and decisions
made on ambiguous points. Append-only, one section per phase.

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
