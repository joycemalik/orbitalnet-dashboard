# Preregistration v3 — causal real-data replay (Phase 6), third test look

Fixed BEFORE any v3 (causal) test run. Validation history: research/LOG.md
"Causality bug found; Phase 2c ... Phase 6" section; selection:
`research/results/phase6/compare_validation.json`, by the rule declared in
LOG.md before those runs (max P AUROC; ties within 0.01 -> lower P
confident-wrong on modeled). Chosen: gr@5, kappa 0.5, l = 5 d (P AUROC 0.851
vs 0.825 at kappa 1, 0.750 at kappa 0).

## Why this exists
Phases 3-5 did not enforce a time arrow (planners could measure earlier
epochs after later ones). Those results stand as RETROSPECTIVE EPOCH
SELECTION and are not replaced. v3 is the same comparison with every
measurement strictly later than the previous one (`--causal`).

## Declared reuse of the test split
Same test events as v2 (two-band-eligible subset of the Phase 3 test split).
Phase 3 and v2 test results have been seen. This is a THIRD look at those
events, stated wherever v3 numbers appear. Config chosen on validation only.

## Frozen configuration
- Code: the commit that adds this file.
- Identical to PREREGISTRATION_V2.md except `--causal` on every arm.
- Noise seeds 1, 2, 3.

Commands (per seed S):
```
python -m research.experiments.phase3_real_replay --split test --seed S --n-events 100000 --results-dir research/results/phase6 --gp-lengthscale 5 --bands gr --discrepancy-scale 0.5 --causal --tag final_gr5_k0.5
python -m research.experiments.phase3_real_replay --split test --seed S --n-events 100000 --results-dir research/results/phase6 --gp-lengthscale 5 --require-g --causal --tag final_r5
python -m research.experiments.phase3_real_replay --split test --seed S --n-events 100000 --results-dir research/results/phase6 --gp-lengthscale 5 --require-g --budget 10 --causal --tag final_r10
```
Analysis: `research/experiments/phase5_analysis.py`, unchanged, pointed at
the phase6 directories, output `research/results/phase6/analysis_test_v3.json`.

## Hypotheses — identical to v2 (pass only if passing on all three seeds;
## 95% stratified paired bootstrap over events, 10,000 resamples)
- **H1** P - B3 confident-wrong rate on unmodeled events: CI < 0.
- **H2** AUROC of P(h0), unmodeled vs modeled: CI > 0.5.
- **H3** P - B3 confident-wrong rate on modeled events: upper CI < +0.05.
- **H4** AUROC(primary) - AUROC(r@5 arm): CI > 0.
- **H5** P - B3 accuracy on modeled events: lower CI > -0.05.
- Reported only: AUROC difference vs r@10; causal vs retrospective (v2)
  differences per metric on the same events and seeds.

## Observed on validation before freezing (description only, no change to H1-H5)
Dry run (`results/phase6/analysis_validation_chosen.json`): H1-H5 all pass.
Causally, the adaptive planners use only part of the budget (mean
measurements, validation seed 1, r@5: B1 3.1, B2 2.0, B3 2.6, P 2.2; B0 5):
one-step greedy utilities jump to a late epoch and forfeit the earlier
ones. Consequently the r@10 control is not binding for adaptive planners
(P's AUROC is the same as at r@5); it stays reported-only.

## Commitments
All results reported, including failures. No further test runs of variants.
Limitations as in PREREGISTRATION_V2.md.
