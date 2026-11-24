# Preregistration - Phase 4: decentralised fleet follow-up (H4, HE1, HE2)

Committed before any test seed (>= 4000) is run. Code: research/planners/decentralised.py,
research/orbitsim/isl.py, research/inference/evalues.py, research/experiments/phase4_decentralised.py,
research/experiments/phase4_analysis.py, at the commit that adds this file.

## Fixed configuration
- Episodes of 4 concurrent transients (Phase 2 classes, modeled and withheld drawn uniformly),
  8 real-TLE satellites, 16 epochs 0.01-20 d, budget 3 measurements per satellite, 1 per epoch.
- ISL: separation <= R and line of sight clear of Earth + 80 km; 2-min store-and-forward.
  R in {1000, 2000, 3000, 5000} km. Strategies O (ideal links), G (none), A_R (auction per
  connected component), K_R (knowledge sharing only).
- P utility frozen from PREREGISTRATION_PHASE2.md (beta 1, gamma 0.1, GP length scale 1.2 d).
- Reserve prices chosen on validation (seed 41, 100 episodes) by the rule declared in LOG.md
  before validation: O = 1, G = 3, A = 10, K = 10 (results/phase4_fleet/reserves.json).
  A and K were chosen at the upper edge of the grid; reported as a limitation, grid not extended.
- alpha = 0.1 for every e-value statement.

## Test runs
python -m research.experiments.phase4_decentralised --split test --seed 4000 --n-episodes 250 --scenario nominal --reserves-json research/results/phase4_fleet/reserves.json
python -m research.experiments.phase4_decentralised --split test --seed 4100 --n-episodes 250 --scenario model_error --reserves-json research/results/phase4_fleet/reserves.json
Only the nominal run (1000 events) decides pass/fail; the model-error run is reported.

## Statistics
Differences are paired (same episodes) with 95% percentile intervals from 10^4 bootstrap
resamples of whole episodes (events in an episode share geometry and allocation). Rates with
a ceiling use one-sided 95% Clopper-Pearson upper bounds. "Accuracy" = correct open-world
decision on modeled events.

## Hypotheses (predictions from validation)
- H4.1 Value of communication: accuracy(O) - accuracy(G) > 0 (CI lower bound > 0).
- H4.2 Realistic crosslinks help: accuracy(A_5000) - accuracy(G) > 0 (CI lower bound > 0).
- H4.3 Realistic crosslinks fall short of ideal: accuracy(O) - accuracy(A_5000) > 0 (CI lower bound > 0).
- H4.4 Plan coordination adds nothing beyond shared knowledge: accuracy(A_5000) - accuracy(K_5000)
  lies within +-0.05 (whole CI inside [-0.05, 0.05]).
- HE1 Anytime-valid unknown detection: for every strategy, the ground e-process false-"unknown"
  rate on modeled events (sup over epochs of E >= 1/alpha) has CP upper bound <= alpha.
- HE2 Valid fusion across spacecraft: for A_5000, the per-(event, spacecraft) false-alarm rate of
  the mean of last-known e-values has CP upper bound <= alpha.

## Reported without pass/fail (declared now)
Per strategy: accuracy, confident-wrong on unknowns, Bayesian flag rate, AUROC of P(h0), log score,
measurements and duplicates per event, records moved, staleness; e-process detection rate on
unknowns vs Bayesian flag rate; product-fusion false-alarm rate (validation showed no inflation,
so no prediction is made); accuracy as a function of R for A and K; all of the above for the
model-error run.
