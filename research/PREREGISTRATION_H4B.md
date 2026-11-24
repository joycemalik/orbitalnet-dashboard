# Preregistration - Phase 4b: replication, spending policy, and fleet geometry

Committed and pushed before test seed 4200 is run. Code as at this commit; fleet rule in
research/orbitsim/fleets.py (dense = 8 satellites of the most populated 5-deg RAAN bin of the
operational 53-deg shell, closest to its median RAAN). Everything else as PREREGISTRATION_H4.md.

## What motivated it (validation and exploratory looks, declared)
- Phase 4 exploratory equal-reserve run on test seed 4000 (an extra look): A_5000 - G = +2.4 points,
  CI including 0; O at reserve 1 vs 3: 0.868 vs 0.814.
- Dense-fleet validation (seed 41, 100 episodes, reserve 3): links up 9-38% of pair-time (sparse
  1-12%), yet accuracy lower for every strategy (O 0.74 vs 0.82); measurements concentrate on fewer
  distinct epochs (O 1.79 vs 2.11 per event).

## Test runs (seed 4200, 500 episodes = 2000 events, nominal; same seed => identical events
## across runs, so all comparisons are paired by episode)
R1  python -m research.experiments.phase4_decentralised --split test --seed 4200 --n-episodes 500 --reserves-json research/results/phase4_fleet/reserves_exploratory_equal3.json --tag b_sparse_equal3
R2  python -m research.experiments.phase4_decentralised --split test --seed 4200 --n-episodes 500 --reserves-json research/results/phase4_fleet/reserves_exploratory_equal3.json --fleet dense --tag b_dense_equal3
R3  python -m research.experiments.phase4_decentralised --split test --seed 4200 --n-episodes 500 --reserves-json research/results/phase4_fleet/reserves.json --tag b_sparse_selected

## Hypotheses (accuracy on modeled events; 95% episode-bootstrap CI, 10^4 resamples)
- B1 Replication: in R1, accuracy(A_5000) - accuracy(G) > 0 (CI lower bound > 0).
- B2 Replication: in R1, accuracy(A_5000) - accuracy(K_5000) within +-0.05.
- B3 Spending policy: accuracy(O in R3, reserve 1) - accuracy(O in R1, reserve 3) > 0.
- B4 Geometry beats links: accuracy(O in R1, sparse) - accuracy(O in R2, dense) > 0.
- B5 Mechanism: distinct epochs per event, O in R1 minus O in R2 > 0.
Reported without pass/fail: every strategy in all three runs; A_5000 - G in the dense fleet; link-up
fractions; duplicates.
