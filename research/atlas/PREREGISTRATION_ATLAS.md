# Preregistration: Storm Drag Atlas, May 2024 event

Committed before any catalogue data for this study was downloaded.
Only the public GFZ Kp/ap/F10.7 file (already on disk) had been read, to define the
storm onset and the quiet baseline by rule.

## Data
- Space-Track `gp_history`, one query per UTC day 2024-04-20 .. 2024-06-10,
  filter MEAN_MOTION > 11.25 (perigee-ish < ~1000 km) and ECCENTRICITY < 0.02.
- Object types from the CelesTrak SATCAT already on disk.
- Kp/ap/F10.7 from GFZ Potsdam.

## Definitions (fixed now)
- SMA a = (mu / n^2)^(1/3), n from MEAN_MOTION; altitude = a - 6378.137 km.
- Decay rate of an object = (a2 - a1)/(t2 - t1) between consecutive element sets with
  0.2 d <= t2 - t1 <= 2 d; assigned to the interval midpoint, binned to 12 h.
- Primary sample: SATCAT type DEBRIS or ROCKET BODY only (no station-keeping).
  Secondary sample: PAYLOAD (reported separately, never merged into primary).
- Shells: 50 km bins from 300 to 650 km, by the object's median altitude in the baseline.
- Quiet baseline (by rule): days 2024-04-27 .. 2024-05-08 with daily max Kp <= 4.
  Per-object baseline rate b_i = median of its rates on baseline days; objects with
  b_i > -20 m/day (not drag-dominated / noise) or fewer than 6 baseline rates are dropped.
- Density ratio of an object in a bin: r_i = rate_i / b_i. Shell ratio R_s(t) = median over
  objects of r_i; require >= 30 objects in a shell-bin or the cell is left empty.
- Storm onset t0: first 3-hour Kp >= 7 in the GFZ file within 2024-05-09 .. 2024-05-12.

## Hypotheses (primary sample)
- HA1 (timing): for every shell 350-550 km that has data, R_s(t) peaks within
  [t0, t0 + 72 h].
- HA2 (altitude dependence): peak R_s rises with altitude across shells 350-600 km
  (Spearman rho > 0 over shells with data).
- HA3 (detectability): in >= 80 % of shells 350-550 km the peak R_s exceeds
  mean + 5 sd of that shell's baseline-day R_s.
- HA4 (primary vs secondary): the payload sample's peak R_s is NOT larger than the
  debris/rocket-body sample's in the same shell (payloads thrust; a larger value would
  indicate contamination, not physics). Reported as a check only.

## Procedure
Run `python -m research.atlas.density_ratio` once on all fetched data. No threshold above is
tuned. If a hypothesis fails it is reported as failed in `research/results/atlas/`.

## Limitations stated up front
Mean-element SMA noise (tens of metres); 12 h time resolution; F10.7 and other drivers are
not regressed out; Dst from Kyoto WDC is not used (Kp only).
