"""Phase 3: real transients from the ZTF Bright Transient Survey (see
research/data/fetch_bts.py for provenance and class mapping).

Each event is the object's real ZTF r-band (fid=2) detections, converted from
magnitude to linear flux with the SAME zero point as the instrument noise
model (transients.noise.ZEROPOINT_MAG), so "flux 1.0" means the same thing
for the real light curve and for the simulated instrument noise floor.
Time is measured in days from the first r-band detection, matching the
"time since alert" axis the planners already use.

Ground truth at arbitrary times is the GP posterior mean through the real
points (`truth_flux`); only the planner's *measurements* of that truth are
simulated. Nothing here is fit to the class labels.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from research.data.fetch_bts import MODELED_CLASSES, RAW_DIR, WITHHELD_CLASSES
from research.inference.openworld import SimpleGP
from research.transients.noise import ZEROPOINT_MAG

R_BAND_FID = 2
MIN_DETECTIONS = 8  # fewer points cannot pin down a light-curve shape
TRUTH_GP_LENGTHSCALE = 8.0  # days; SN-scale evolution (vs 1.2 d for the fast synthetic classes)


def mag_to_flux(mag: np.ndarray) -> np.ndarray:
    return 10 ** (-0.4 * (np.asarray(mag, dtype=float) - ZEROPOINT_MAG))


def flux_err_from_mag_err(flux: np.ndarray, mag_err: np.ndarray) -> np.ndarray:
    return np.abs(flux) * np.log(10) / 2.5 * np.asarray(mag_err, dtype=float)


def sexagesimal_to_deg(ra: str, dec: str) -> tuple[float, float]:
    h, m, s = (float(x) for x in ra.split(":"))
    sign = -1.0 if dec.strip().startswith("-") else 1.0
    d, dm, ds = (abs(float(x)) for x in dec.split(":"))
    return 15.0 * (h + m / 60 + s / 3600), sign * (d + dm / 60 + ds / 3600)


@dataclass(frozen=True)
class RealEvent:
    oid: str
    true_class: str
    bts_type: str
    ra_deg: float
    dec_deg: float
    t0_mjd: float
    t_days: np.ndarray
    flux: np.ndarray
    flux_err: np.ndarray

    @property
    def is_withheld(self) -> bool:
        return self.true_class in WITHHELD_CLASSES

    def truth_flux(self, t: np.ndarray) -> np.ndarray:
        """GP posterior mean through the real detections (zero outside data support
        decays back toward the zero prior mean, i.e. 'faded below detection')."""
        gp = SimpleGP(lengthscale=TRUTH_GP_LENGTHSCALE, var_f=float(np.max(self.flux) ** 2))
        t = np.asarray(t, dtype=float)
        K = gp.kernel(self.t_days, self.t_days) + np.diag(self.flux_err ** 2)
        alpha = np.linalg.solve(K, self.flux)
        return gp.kernel(t, self.t_days) @ alpha


def parse_lightcurve(raw: dict) -> tuple[float, np.ndarray, np.ndarray, np.ndarray] | None:
    dets = [d for d in raw.get("detections", [])
            if d.get("fid") == R_BAND_FID and d.get("isdiffpos", 1) in (1, "t")
            and d.get("magpsf") is not None and d.get("sigmapsf") is not None]
    if len(dets) < MIN_DETECTIONS:
        return None
    dets.sort(key=lambda d: d["mjd"])
    mjd = np.array([d["mjd"] for d in dets])
    flux = mag_to_flux([d["magpsf"] for d in dets])
    err = flux_err_from_mag_err(flux, [d["sigmapsf"] for d in dets])
    return float(mjd[0]), mjd - mjd[0], flux, err


def load_real_events(raw_dir: Path = RAW_DIR) -> tuple[list[RealEvent], dict[str, int]]:
    """Returns (events, exclusion_counts). Exclusions are reported, never silent."""
    selection = json.loads((raw_dir / "selection.json").read_text())
    events: list[RealEvent] = []
    excluded = {"missing_download": 0, "too_few_r_detections": 0}
    for obj in selection["objects"]:
        path = raw_dir / "lightcurves" / f"{obj['oid']}.json"
        if not path.exists():
            excluded["missing_download"] += 1
            continue
        parsed = parse_lightcurve(json.loads(path.read_text()))
        if parsed is None:
            excluded["too_few_r_detections"] += 1
            continue
        t0, t, f, e = parsed
        ra, dec = sexagesimal_to_deg(obj["ra"], obj["dec"])
        events.append(RealEvent(obj["oid"], obj["cls"], obj["bts_type"], ra, dec, t0, t, f, e))
    events.sort(key=lambda ev: (ev.t0_mjd, ev.oid))
    return events, excluded


TEMPLATE_GRID_DAYS = np.linspace(0.0, 90.0, 181)


def build_class_templates(events: list[RealEvent]) -> dict[str, np.ndarray]:
    """Empirical per-class light-curve shape: the median over `events` (the
    TEMPLATE split only -- never validation/test events) of each event's
    peak-normalized truth curve on TEMPLATE_GRID_DAYS. Each event contributes
    only inside its own observed span; grid points no event covers are filled
    by holding the last covered value (documented; affects late times only)."""
    templates: dict[str, np.ndarray] = {}
    for cls in MODELED_CLASSES:
        curves = []
        for ev in events:
            if ev.true_class != cls:
                continue
            f = ev.truth_flux(TEMPLATE_GRID_DAYS)
            f = f / np.max(f)
            f[TEMPLATE_GRID_DAYS > ev.t_days[-1]] = np.nan
            curves.append(f)
        if not curves:
            raise ValueError(f"no template-split events for class {cls!r}")
        with warnings.catch_warnings():  # all-NaN columns (past every event's span) are expected
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(np.array(curves), axis=0)
        covered = ~np.isnan(med)
        last = np.flatnonzero(covered)[-1]
        med[last + 1:] = med[last]
        templates[cls] = np.clip(med / np.max(med), 0.0, None)
    return templates


def template_flux_fn_resolver(templates: dict[str, np.ndarray]):
    """Same contract as transients.models.modeled_flux_fn_p2: cls -> f(t, A)."""
    def resolver(cls: str):
        shape = templates[cls]
        return lambda t, amplitude: amplitude * np.interp(t, TEMPLATE_GRID_DAYS, shape)
    return resolver


class StretchAmplitudeGrid:
    """Nuisance grid for template classes: every (amplitude A, stretch s)
    pair, f(t) = A * template(t / s). s > 1 is a slower-evolving event, the
    standard SN light-curve "stretch". ClosedWorldBelief's nuisance axis
    holds one float per cell; here that float is the pair's index, decoded
    by the resolver, so every planner/EIG routine works unchanged. The prior
    stays uniform over the grid = log-uniform in both A and s."""

    def __init__(self, amplitudes: np.ndarray, stretches: np.ndarray):
        self.amplitudes = np.asarray(amplitudes, dtype=float)
        self.stretches = np.asarray(stretches, dtype=float)
        n = len(self.amplitudes) * len(self.stretches)
        self.params = np.arange(n, dtype=float)
        self.amp_of = np.repeat(self.amplitudes, len(self.stretches))
        self.stretch_of = np.tile(self.stretches, len(self.amplitudes))

    def resolver(self, templates: dict[str, np.ndarray]):
        def resolve(cls: str):
            shape = templates[cls]

            def f(t, param):
                t, param = np.broadcast_arrays(np.asarray(t, dtype=float), np.asarray(param, dtype=float))
                idx = np.rint(param).astype(int)
                vals = np.interp((t / self.stretch_of[idx]).ravel(), TEMPLATE_GRID_DAYS, shape)
                return self.amp_of[idx] * vals.reshape(t.shape)
            return f
        return resolve


__all__ = ["StretchAmplitudeGrid", "RealEvent", "load_real_events", "build_class_templates", "template_flux_fn_resolver",
           "MODELED_CLASSES", "WITHHELD_CLASSES"]
