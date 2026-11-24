# Preregistration E: the anytime-valid e-process on real ZTF events

Committed and pushed before any `test` or `fresh_test` run of `research/experiments/phaseE_real_evalues.py`.
The script refuses those splits until this file exists.

## What is tested
The universal-inference e-process from Phase 4 (log E_t = log p_GP(D_t) - max over class and amplitude
grid of log L), raised as "unknown" if E_t >= 1/alpha at ANY step, alpha = 0.1. The planner, the
measurements and the noise draws are the Phase C ones, replayed draw for draw (verified: 4104/4104
measurement sequences identical on fresh_cal seeds 1-3). Nothing is tuned; there is no free parameter.

## Validation evidence used to write this file (results/phaseE/)
- fresh_cal (456 SNe, seeds 1-3): P's anytime false-"unknown" rate 3.9%, 4.4%, 5.0%.
- validation split, seed 1: P false-"unknown" 2/281; detected 25/81 withheld (30.9%).

## Hypotheses (strategy P = P_open_world_eig; seeds 1, 2, 3)
- **HR1** (validity on sealed real data): on `fresh_test` (sealed supernovae, all modelled classes),
  P's anytime false-"unknown" rate has a one-sided 95% Clopper-Pearson upper bound <= 0.10 on every seed.
- **HR2** (power on real unknowns): on the `test` split, the fraction of withheld events
  (TDE, SLSN, SN Ibn) that P flags at any step has a one-sided 95% Clopper-Pearson lower bound > 0.10
  on every seed.

Reported, not tested: the same rates for B3 (closed-world EIG) and L (lookahead), and a side-by-side
with the Phase C conformal rule and P(h0) on the same events.

## Declared caveats
- The grid maximum over amplitude is <= the true supremum, so E is slightly larger than the exact
  universal-inference statistic (anti-conservative). Not corrected.
- Real light curves are not exactly any template, so the null is only approximately true; HR1 tests
  whether the guarantee survives that in practice.
- The `test` and `fresh_test` events were already used in Phase C (and `test` in Phase 3). This is a
  new statistic on the same draws, not new data.

## Analysis
`python -m research.experiments.phaseE_analysis evaluate` writes `results/phaseE/analysis_E.json`.
