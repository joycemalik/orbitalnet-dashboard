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
G_BAND_FID = 1
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
    # Phase 4 (colour): g-band detections on the SAME time axis (days since the
    # first r detection, so g times can be negative). None when not loaded.
    g_t_days: np.ndarray | None = None
    g_flux: np.ndarray | None = None
    g_flux_err: np.ndarray | None = None

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

    def truth_flux_g(self, t: np.ndarray) -> np.ndarray:
        """Same GP construction as `truth_flux`, through the real g detections.
        The signal scale is the r-band peak so both bands share one prior scale."""
        gp = SimpleGP(lengthscale=TRUTH_GP_LENGTHSCALE, var_f=float(max(np.max(self.flux), np.max(self.g_flux)) ** 2))
        t = np.asarray(t, dtype=float)
        K = gp.kernel(self.g_t_days, self.g_t_days) + np.diag(self.g_flux_err ** 2)
        alpha = np.linalg.solve(K, self.g_flux)
        return gp.kernel(t, self.g_t_days) @ alpha

    @property
    def last_time_with_truth(self) -> float:
        """Latest time both loaded bands still have real data (no extrapolation)."""
        if self.g_t_days is None:
            return float(self.t_days[-1])
        return float(min(self.t_days[-1], self.g_t_days[-1]))


def _band_detections(raw: dict, fid: int) -> list[dict]:
    dets = [d for d in raw.get("detections", [])
            if d.get("fid") == fid and d.get("isdiffpos", 1) in (1, "t")
            and d.get("magpsf") is not None and d.get("sigmapsf") is not None]
    dets.sort(key=lambda d: d["mjd"])
    return dets


def parse_g_band(raw: dict, t0_mjd: float) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    dets = _band_detections(raw, G_BAND_FID)
    if len(dets) < MIN_DETECTIONS:
        return None
    mjd = np.array([d["mjd"] for d in dets])
    flux = mag_to_flux([d["magpsf"] for d in dets])
    return mjd - t0_mjd, flux, flux_err_from_mag_err(flux, [d["sigmapsf"] for d in dets])


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


def load_real_events(raw_dir: Path = RAW_DIR, require_g: bool = False) -> tuple[list[RealEvent], dict[str, int]]:
    """Returns (events, exclusion_counts). Exclusions are reported, never silent.
    `require_g` (Phase 4) also loads g band and drops events with too few g points."""
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
        g = (None, None, None)
        if require_g:
            g = parse_g_band(json.loads(path.read_text()), t0)
            if g is None:
                excluded["too_few_g_detections"] = excluded.get("too_few_g_detections", 0) + 1
                continue
        events.append(RealEvent(obj["oid"], obj["cls"], obj["bts_type"], ra, dec, t0, t, f, e, *g))
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


def build_class_templates_g(events: list[RealEvent]) -> dict[str, np.ndarray]:
    """g-band companion to `build_class_templates`: each event's g truth curve
    is divided by the peak of its R-band truth curve (not its own g peak), so
    the template carries the class's g/r colour evolution, not just its shape.
    Normalized so the class's r template peak is 1 (median g/r ratio kept)."""
    templates: dict[str, np.ndarray] = {}
    for cls in MODELED_CLASSES:
        curves = []
        for ev in events:
            if ev.true_class != cls or ev.g_flux is None:
                continue
            r_peak = np.max(ev.truth_flux(TEMPLATE_GRID_DAYS))
            f = ev.truth_flux_g(TEMPLATE_GRID_DAYS) / r_peak
            f[(TEMPLATE_GRID_DAYS > ev.g_t_days[-1]) | (TEMPLATE_GRID_DAYS > ev.t_days[-1])] = np.nan
            curves.append(f)
        if not curves:
            raise ValueError(f"no template-split g-band events for class {cls!r}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(np.array(curves), axis=0)
        covered = ~np.isnan(med)
        last = np.flatnonzero(covered)[-1]
        med[last + 1:] = med[last]
        templates[cls] = np.clip(np.nan_to_num(med), 0.0, None)  # uncovered early grid -> 0
    return templates


# Phase 4 band encoding: a g-band measurement at time t is stored at
# t + G_TIME_OFFSET_DAYS. Every flux function/GP then distinguishes bands by
# time alone, so ClosedWorldBelief, the planners and the GP need no changes;
# with GP lengthscales of days, the 1e4-day offset gives exactly zero r-g
# covariance (bands independent given the shared amplitude).
G_TIME_OFFSET_DAYS = 1.0e4


def two_band_flux_fn_resolver(templates_r: dict[str, np.ndarray], templates_g: dict[str, np.ndarray]):
    def resolve(cls: str):
        r, g = templates_r[cls], templates_g[cls]

        def f(t, amplitude):
            t = np.asarray(t, dtype=float)
            is_g = t >= G_TIME_OFFSET_DAYS / 2
            vals = np.where(is_g, np.interp(t - G_TIME_OFFSET_DAYS, TEMPLATE_GRID_DAYS, g),
                            np.interp(t, TEMPLATE_GRID_DAYS, r))
            return amplitude * vals
        return f
    return resolve


def build_class_scatter(events: list[RealEvent], band: str = "r") -> dict[str, np.ndarray]:
    """Phase 5 model discrepancy: per class and grid time, the robust spread
    (1.4826 * MAD) of the TEMPLATE-split events' normalized curves around the
    class median -- the same normalization as the band's template (r: own
    peak; g: the event's r peak). Units: fraction of amplitude. Times no event
    covers hold the last covered value (early uncovered g times -> 0)."""
    out: dict[str, np.ndarray] = {}
    for cls in MODELED_CLASSES:
        curves = []
        for ev in events:
            if ev.true_class != cls or (band == "g" and ev.g_flux is None):
                continue
            r = ev.truth_flux(TEMPLATE_GRID_DAYS)
            if band == "r":
                f = r / np.max(r)
                f[TEMPLATE_GRID_DAYS > ev.t_days[-1]] = np.nan
            else:
                f = ev.truth_flux_g(TEMPLATE_GRID_DAYS) / np.max(r)
                f[(TEMPLATE_GRID_DAYS > ev.g_t_days[-1]) | (TEMPLATE_GRID_DAYS > ev.t_days[-1])] = np.nan
            curves.append(f)
        arr = np.array(curves)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(arr, axis=0)
            mad = np.nanmedian(np.abs(arr - med), axis=0) * 1.4826
        covered = ~np.isnan(mad)
        last = np.flatnonzero(covered)[-1]
        mad[last + 1:] = mad[last]
        out[cls] = np.nan_to_num(mad)
    return out


def discrepancy_resolver(scatter_r: dict[str, np.ndarray], scale: float,
                         scatter_g: dict[str, np.ndarray] | None = None):
    """cls -> g(t, amplitude) = scale * amplitude * scatter(t); routes g-band
    times (t >= offset/2) to the g scatter, like `two_band_flux_fn_resolver`."""
    def resolve(cls: str):
        r = scatter_r[cls]
        g = scatter_g[cls] if scatter_g is not None else None

        def f(t, amplitude):
            t = np.asarray(t, dtype=float)
            vals = np.interp(t, TEMPLATE_GRID_DAYS, r)
            if g is not None:
                vals = np.where(t >= G_TIME_OFFSET_DAYS / 2, np.interp(t - G_TIME_OFFSET_DAYS, TEMPLATE_GRID_DAYS, g), vals)
            return scale * amplitude * vals
        return f
    return resolve


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


__all__ = ["StretchAmplitudeGrid", "build_class_scatter", "discrepancy_resolver", "build_class_templates_g", "two_band_flux_fn_resolver", "G_TIME_OFFSET_DAYS", "RealEvent", "load_real_events", "build_class_templates", "template_flux_fn_resolver",
           "MODELED_CLASSES", "WITHHELD_CLASSES"]
