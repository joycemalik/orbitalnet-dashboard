# Preregistration R1: independent replication on the October 2024 storm

Committed before any October 2024 catalogue data was downloaded. Only the GFZ Kp file
already on disk was read, to fix the baseline and onset by the same rules as the May study.

## What the May 2024 study found (for context, results in research/results/atlas/)
HA1-HA3 passed; HA4 (payloads not larger than debris) FAILED. A post-hoc, exploratory look at
the May data (not a preregistered test) showed that the excess comes from station-keeping
constellation satellites (names containing STARLINK or ONEWEB): their quiet-time decay is
partly cancelled by thrust, so their baseline rate is small and the storm "ratio" is inflated
(thrust-masking explanation). Other payloads were close to the debris/rocket-body response,
but not identical (at 400 km they exceeded it).

## Event
Storm of 2024-10-10/11 (Kp ~8.7). Data: Space-Track gp_history, one query per UTC day
2024-09-28 .. 2024-11-05, same filters as May (MEAN_MOTION > 11.25, ECCENTRICITY < 0.02).

## Fixed definitions (identical to PREREGISTRATION_ATLAS.md except the dates)
- Baseline window 2024-09-28 .. 2024-10-05, keeping days with daily max Kp <= 4.
  The window ends before the 6-8 Oct disturbance on purpose; this is set from the Kp file alone.
- Onset t0: first 3-hour Kp >= 7 in 2024-10-09 .. 2024-10-13.
- Samples: primary = DEB + R/B; secondary = PAY, split by SATCAT name into
  "constellation" (contains STARLINK or ONEWEB) and "other".
- All other definitions (rates, 12 h bins, 50 km shells, >= 30 objects per cell, baseline filters)
  unchanged.

## Hypotheses
- R-HA1, R-HA2, R-HA3: same statements as HA1, HA2, HA3 (timing within 72 h of t0 for
  350-550 km shells, peak ratio rising with altitude over 350-600 km, peak > baseline mean +
  5 sd in >= 80 % of 350-550 km shells).
- R-HA4: repeated as a check, same statement as HA4. Reported whatever the outcome.
- R-HX1 (thrust masking): constellation payload peak R exceeds primary peak R in >= 3 shells.
- R-HX2: other-payload peak R lies within [0.8, 1.25] x primary peak R in every shell with
  data. NOTE: this tolerance was chosen after seeing the May data, so R-HX2 tests a fitted
  statement and is weaker evidence than R-HX1.

## Procedure
One run: `python -m research.atlas.density_ratio --event oct2024`. No thresholds tuned.
Failures are reported as failures.
