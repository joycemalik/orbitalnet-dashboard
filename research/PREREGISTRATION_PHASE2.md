# Preregistration — Phase 2c: causal simulation, manuscript H1-H3

Committing this file unlocks test seeds (>= 1000) in
`research/experiments/phase2_single_planner.py`. Everything below is fixed
BEFORE any test seed is run. Validation history: research/LOG.md
("Causality bug found; Phase 2c ..." section) and
`research/results/phase2/selection_validation.json`.

## Frozen configuration
- Code: the commit that adds this file. No code changes before the test runs.
- Causal (strictly forward) measurements; budget 5; 16 log-spaced epochs
  0.01-20 d; 8 satellites; limiting magnitudes 19/20/21; amplitude grid 15;
  confidence 0.95; mode switch tau 0.9 (two consecutive steps).
- Chosen on validation by the pre-declared rule (max P mean log score):
  **gamma = 0.1, h0 GP lengthscale = 1.2 d**, beta = 1. gamma = 0.1 is the
  largest value in the grid (the optimum may lie beyond it; stated as a
  limitation, not re-tuned).
- Strategies: B0, B1, B2, B3, P, and ablations P_no_decay (gamma = 0),
  P_no_adequacy (beta = 0).
- Scenarios and test seeds, 1000 events each:
  S1_nominal seed 1000 (PRIMARY), S2_crowding seed 2000, S3_model_error seed 3000.

Commands:
```
python -m research.experiments.phase2_single_planner --split test --seed 1000 --n-events 1000 --scenario S1_nominal --gamma 0.1 --gp-lengthscale 1.2 --tag final
python -m research.experiments.phase2_single_planner --split test --seed 2000 --n-events 1000 --scenario S2_crowding --gamma 0.1 --gp-lengthscale 1.2 --tag final
python -m research.experiments.phase2_single_planner --split test --seed 3000 --n-events 1000 --scenario S3_model_error --gamma 0.1 --gp-lengthscale 1.2 --tag final
python -m research.experiments.phase2_analysis --runs research/results/phase2/test_S1_nominal_seed1000_final research/results/phase2/test_S2_crowding_seed2000_final research/results/phase2/test_S3_model_error_seed3000_final --out research/results/phase2/analysis_test.json --seed 0
```
(Results do not depend on --workers: each event has its own SeedSequence.)

## Hypotheses and pass criteria (decided on S1_nominal only)
Analysis script: `research/experiments/phase2_analysis.py` (committed with this file).
- **H1 (discrimination).** On modeled events, P's time to posterior >= 0.95
  on the TRUE class is shorter than each of B0, B1, B2, B3: one-sided paired
  Wilcoxon signed-rank (never-identified ranked last), Holm-adjusted over the
  four, every adjusted p < 0.05 AND median(P) < median(B). Same budget for
  all ("no more measurements" holds by construction; mean measurements used
  are reported).
- **H2 (irreversibility).** d = amplitude information (nats, Fisher form on
  the true signal) of P minus P_no_decay, per modeled event. Pass iff the
  95% stratified bootstrap CI of mean(d | fast: kilonova, shock cooling,
  flare) - mean(d | slow: GRB afterglow) is entirely above 0.
- **H3 (open world).** Detection rate on withheld events at 5% false-alarm
  rate on modeled events (read off each ROC) of P's P(h0), minus that of the
  closed-world posterior entropy of B3. Pass iff the 95% paired stratified
  bootstrap CI is entirely above 0.
- **Reported, no pass/fail:** the same three tests on S2 and S3; AUROC
  differences; comparators B2 entropy and the closed-world entropy on P's own
  measurements; accuracy, confident-wrong, log score, budget used for every
  strategy; P_no_adequacy vs P on all metrics; h0 false alarms under model
  error (S3).

## Observed on validation before freezing (description only)
Dry run on validation (`results/phase2/analysis_validation_chosen.json`,
500 events per scenario): S1 H1 FAIL (P median 0.956 d equals B2's; times
lie on a 16-epoch grid, so tied medians are possible; criterion kept as
written, not loosened), H2 pass (+0.321 [0.165, 0.479]), H3 pass
(dTPR +0.72; AUROC P 0.993 vs B3 entropy 0.662). Under model error (S3)
H2 does not hold (-0.077 [-0.179, 0.023]).

## Commitments
All results reported, including failures. No re-runs with other settings
on test seeds. Limitations to state: analytic light-curve shapes (not
published templates); amplitude is the only physical parameter; decay term
is an SNR^2 proxy; cost(a) = 1 (no slew/exposure model); single band;
geometric visibility only; centralized planner (no H4).
