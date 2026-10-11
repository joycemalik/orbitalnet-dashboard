# Phase 3 preregistration — real-data counterfactual replay

Committing this file unlocks the test split (`phase3_real_replay.py --split test`).
Everything below is fixed BEFORE any test-split event is run. Validation
history that led here: research/LOG.md, Phase 3 section; results in
`research/results/phase3/validation_seed1*`.

## Frozen configuration
- Code: the commit that adds this file. No code changes before the test run.
- Data: `research/data/raw/manifest.json` (sha256 of every downloaded file).
- Test split: post-2020-01-01 usable events, newer half by first-detection
  date (`split_events`), all of it (`--n-events 100000`).
- Templates: built from pre-2020 events only, no stretch.
- h0 model: amplitude-marginalized GP, lengthscale **5 days**.
- Unchanged from validation: 16 candidate times 0.5-60 d, budget 5,
  8 satellites, limiting mags 19/20/21, max TLE age 7 d, confidence 0.95,
  strategies B0, B1, B2, B3, P exactly as in `planners/phase2.py`.
- Noise seeds: **1, 2, 3** (three full runs; events identical across seeds,
  only instrument assignment and noise differ).

Command, per seed:
`python -m research.experiments.phase3_real_replay --split test --seed S --n-events 100000 --gp-lengthscale 5 --tag final`

## Hypotheses and pass criteria
Uncertainty: 95% percentile bootstrap over EVENTS (10,000 resamples, paired
across strategies), computed per seed; a hypothesis passes only if it passes
on all three seeds. Analysis script: `research/experiments/phase3_analysis.py`,
committed before the test run.

- **H1 (primary).** On withheld (real unmodeled) events, P's confident-wrong
  rate is lower than B3's: CI of (P - B3) entirely below 0.
- **H2.** P(h0) ranks withheld above modeled events better than chance:
  CI of AUROC entirely above 0.5.
- **H3 (cost, non-inferiority).** On modeled events, P's confident-wrong rate
  is not more than 0.05 above B3's: upper CI bound of (P - B3) < 0.05.
- **Reported, no pass/fail:** accuracy (modeled, withheld), h0 false-alarm
  rate on modeled events, mean log score, the same comparisons vs B1 (the
  live-stack CNP auction), per-class confusion matrices, exclusion counts.

## Commitments
- All results are reported, including failed hypotheses.
- No re-runs with other settings on the test split. Any later change is a
  new, separately labelled experiment and cannot replace these numbers.
- Known limitations stated in the paper: measurements resampled from real
  curves (not new photons); single band; assumed instrument noise; geometric
  contact only (no Sun exclusion, no link budget); empirical templates.
