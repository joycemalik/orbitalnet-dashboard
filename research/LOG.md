# research/ LOG

Running log of what was built, what passed, what surprised us, and decisions
made on ambiguous points. Append-only, one section per phase.

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
