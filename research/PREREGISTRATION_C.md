# Preregistration C — conformal open-set layer + lookahead planner L

Fixed BEFORE any fresh_cal / fresh_test / test run of Phase C. Validation
history: research/LOG.md "Phase C" section. Selection of lam:
`research/results/phaseC/lambda_selection_validation.json` (rule declared in
LOG.md before the validation run: max AUROC of s for L; ties within 0.01 ->
higher closed-world accuracy on modeled). Chosen: **lam = 0.25**
(AUROC 0.863, tied with lam = 1 at 0.873; closed-world accuracy 0.687 vs 0.673).
Dry run on validation (2-fold hash split): `results/phaseC/hypotheses_dryrun_validation.json`
-> HC1-HC5 pass, HC6 fails.

## Data
- **fresh_cal / fresh_test**: research/data/fresh_selection.json (modeled-class
  BTS events never used by any earlier phase; role = sha256(oid) parity).
  fresh_test has never been loaded. Two-band eligibility as in Phase 4.
- **test**: the Phase 3 test split, two-band subset. Seen by Phases 3, 4+5 (v2)
  and possibly v3 (another session). This is a DECLARED ADDITIONAL LOOK, used
  only for the claims that need real unknown events (HC4-HC6).

## Frozen configuration
Code: the commit that adds this file. v3 replay config (gr, kappa 0.5,
h0 GP lengthscale 5 d, causal, budget 5). Strategies: B0, B1, B2, B3, P,
L(lam = 0.25), all on identical events, orbits, noise, budgets.
Score s = log p(D|h0) - max_c log p(D|c). Max-rule class-conditional split
conformal threshold, calibrated per strategy on fresh_cal of the SAME noise
seed. alpha = 0.1 primary (0.05 reported). Noise seeds 1, 2, 3.

```
python -m research.experiments.phaseC_replay --events fresh_cal  --seed S --n-events 100000 --lambdas 0.25 --tag final
python -m research.experiments.phaseC_replay --events fresh_test --seed S --n-events 100000 --lambdas 0.25 --tag final
python -m research.experiments.phaseC_replay --events test       --seed S --n-events 100000 --lambdas 0.25 --tag final
python -m research.experiments.phaseC_hypotheses --cal research/results/phaseC/fresh_cal_seedS_final --fresh research/results/phaseC/fresh_test_seedS_final --test research/results/phaseC/test_seedS_final --out research/results/phaseC/hypotheses_seedS.json
```

## Hypotheses (C-L = L + conformal decision; pass only if passing on all three seeds)
- **HC1 validity** (fresh_test): for the pooled known set and for each class,
  the Clopper-Pearson 95% lower bound of the false-"unknown" rate <= alpha.
  (Weak by design — the theorem bounds the expectation over calibration
  draws; point estimates are reported and are the informative number.)
- **HC2 = failed H5, re-tested** (fresh_test): C-L - B3 accuracy on known
  events, paired bootstrap lower 95% > -0.05.
- **HC3 = failed H3, re-tested** (fresh_test): C-L - B3 confident-wrong on
  known events, upper 95% < +0.05.
- **HC4** (test): C-L - B3 confident-wrong on unknown events, upper 95% < 0.
- **HC5** (test): C-L flag rate on unknown events, CP lower 95% > alpha
  (detection beyond a truth-independent flag at rate alpha).
- **HC6** (test): AUROC(s of L) - AUROC(s of P), stratified paired bootstrap
  lower 95% > 0. (Fails in the validation dry run; kept as declared.)

Reported only: alpha = 0.05; every strategy with the conformal layer
(planner-agnostic validity); P's raw false-"unknown" rate on fresh_test and
test (no guarantee) for contrast; HC2/HC3 on test-split known events.

## Commitments
All results reported, including failures. No further test runs of variants.
Exchangeability is exact between fresh_cal and fresh_test (hash split) and
only approximate for the test split (different selection rule); stated.
