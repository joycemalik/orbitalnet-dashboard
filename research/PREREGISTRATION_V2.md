# Preregistration v2 — colour + model discrepancy (Phases 4+5), second test look

Fixed BEFORE any v2 test run. Validation history: research/LOG.md Phases 4-5;
selection: `research/results/phase5/compare_validation_all.json`, chosen by the
rule declared in LOG.md before those runs (max P AUROC; ties within 0.01 ->
lower P confident-wrong on modeled).

## Declared reuse of the test split
The test events are the two-band-eligible subset (>= 8 g and >= 8 r points)
of the Phase 3 test split, whose Phase 3 results (PREREGISTRATION.md) have
been seen. This is therefore a SECOND look at those events. The v2 config
was chosen on the validation split only. Report this wherever v2 numbers appear.

## Frozen configuration
- Code: the commit that adds this file.
- Event set: `load_real_events(require_g=True)`, test split = newer half of
  post-2020-01-01 events (`split_events`), all of it.
- Primary arm (P and all baselines): two bands (g+r per pointing), budget 5,
  h0 GP lengthscale 5 d, model discrepancy kappa = 0.5, no stretch, no Sun
  exclusion, 8 satellites, max TLE age 7 d, confidence 0.95.
- Control arms on the same events: r@5 (= Phase 3 config) and r@10.
- Noise seeds 1, 2, 3.

Commands (per seed S):
```
python -m research.experiments.phase3_real_replay --split test --seed S --n-events 100000 --results-dir research/results/phase5 --gp-lengthscale 5 --bands gr --discrepancy-scale 0.5 --tag final_gr5_k0.5
python -m research.experiments.phase3_real_replay --split test --seed S --n-events 100000 --results-dir research/results/phase5 --gp-lengthscale 5 --require-g --tag final_r5
python -m research.experiments.phase3_real_replay --split test --seed S --n-events 100000 --results-dir research/results/phase5 --gp-lengthscale 5 --require-g --budget 10 --tag final_r10
```
Analysis: `research/experiments/phase5_analysis.py` (committed with this file).

## Hypotheses (pass only if passing on all three seeds; 95% stratified
## paired bootstrap over events, 10,000 resamples)
- **H1** P - B3 confident-wrong rate on unmodeled events: CI < 0.
- **H2** AUROC of P(h0), unmodeled vs modeled: CI > 0.5.
- **H3** P - B3 confident-wrong rate on modeled events: upper CI < +0.05.
- **H4** AUROC(primary) - AUROC(r@5 arm): CI > 0 (colour + discrepancy improve
  on the Phase 3 configuration, same events, same r-band values).
- **H5** P - B3 accuracy on modeled events: lower CI > -0.05 (P classifies
  ordinary SNe no worse than the closed-world planner).
- Reported only: AUROC difference vs r@10; all Phase 3 reported metrics.

## Commitments
All results reported, including failures. No further test runs of variants.
Limitations as in PREREGISTRATION.md, plus: dual-band simultaneous imaging is
assumed; planners score candidates on r-band predictions and instrument
noise only; discrepancy treated as independent across measurements.
