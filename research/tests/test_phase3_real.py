"""Phase 3 tests. They use only repo-tracked inputs (satellites.txt) and
synthetic RealEvent objects, never the gitignored raw downloads, so they run
on a fresh clone."""

import datetime
from pathlib import Path

import numpy as np
import pytest

from research.data.fetch_bts import FLEET_COVERAGE_START_MJD, _evenly_spaced
from research.experiments import phase3_real_replay as p3
from research.inference.openworld import AmplitudeMarginalGP, SimpleGP
from research.orbitsim.contacts import build_contact_schedule_historical
from research.orbitsim.geometry import radec_to_unit_eci
from research.orbitsim.tle import load_3le_latest, load_tle_subset
from research.transients.real_events import (
    RealEvent,
    build_class_templates,
    mag_to_flux,
    sexagesimal_to_deg,
    template_flux_fn_resolver,
)
from research.transients.noise import ZEROPOINT_MAG

REPO_ROOT = Path(__file__).resolve().parents[2]


def _event(oid, cls, t0_mjd, peak=10.0, tau=15.0):
    t = np.linspace(0.0, 70.0, 30)
    flux = peak * np.exp(-0.5 * ((t - 12.0) / 5.0) ** 2) * (t < 12) + peak * np.exp(-(t - 12.0) / tau) * (t >= 12)
    return RealEvent(oid, cls, cls, 150.0, 20.0, t0_mjd, t, flux, np.full_like(t, 0.05 * peak))


def test_zero_point_matches_noise_model():
    assert mag_to_flux(ZEROPOINT_MAG) == pytest.approx(1.0)
    assert mag_to_flux(ZEROPOINT_MAG - 2.5) == pytest.approx(10.0)


def test_sexagesimal_parsing_handles_negative_zero_degree_dec():
    ra, dec = sexagesimal_to_deg("12:00:00.0", "-00:30:00.0")
    assert ra == pytest.approx(180.0)
    assert dec == pytest.approx(-0.5)


def test_truth_curve_passes_near_real_points():
    ev = _event("x", "sn_ia", 59000.0)
    assert np.max(np.abs(ev.truth_flux(ev.t_days) - ev.flux)) < 0.1 * ev.flux.max()


def test_templates_are_peak_normalized_and_class_specific():
    events = [_event(f"a{i}", "sn_ia", 58500.0 + i, tau=8.0) for i in range(3)]
    events += [_event(f"b{i}", "sn_ii", 58500.0 + i, tau=60.0) for i in range(3)]
    events += [_event(f"c{i}", "sn_ibc", 58500.0 + i, tau=20.0) for i in range(3)]
    tpl = build_class_templates(events)
    for shape in tpl.values():
        assert shape.max() == pytest.approx(1.0)
    f = template_flux_fn_resolver(tpl)
    assert f("sn_ia")(40.0, 1.0) < f("sn_ibc")(40.0, 1.0) < f("sn_ii")(40.0, 1.0)


def test_split_has_no_temporal_leakage():
    events = [_event(f"e{i}", "sn_ia", FLEET_COVERAGE_START_MJD - 100 + 10 * i) for i in range(40)]
    s = p3.split_events(events)
    assert all(e.t0_mjd < FLEET_COVERAGE_START_MJD for e in s["template"])
    assert max(e.t0_mjd for e in s["validation"]) <= min(e.t0_mjd for e in s["test"])
    assert len(s["template"]) + len(s["validation"]) + len(s["test"]) == len(events)


def test_evenly_spaced_is_deterministic_and_spans_range():
    items = [{"peakt": float(i)} for i in range(100)]
    out = _evenly_spaced(items, 5)
    assert [r["peakt"] for r in out] == [0.0, 25.0, 50.0, 74.0, 99.0]
    assert _evenly_spaced(items, 5) == out


def test_radec_unit_vector():
    assert radec_to_unit_eci(0.0, 90.0) == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)
    assert radec_to_unit_eci(90.0, 0.0) == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)


def test_3le_keeps_latest_and_handles_empty(tmp_path):
    lines = (REPO_ROOT / "satellites.txt").read_text(encoding="utf-8").splitlines()[:3]
    f = tmp_path / "w.tle"
    f.write_text(f"0 {lines[0].strip()}\n{lines[1]}\n{lines[2]}\n", encoding="utf-8")
    assert list(load_3le_latest(str(f))) == [lines[0].strip()]
    empty = tmp_path / "e.tle"
    empty.write_text("", encoding="utf-8")
    assert load_3le_latest(str(empty)) == {}


def _archive_from_repo_tles(n=4):
    fleet = load_tle_subset(str(REPO_ROOT / "satellites.txt"), max_satellites=n)
    sat = next(iter(fleet.values()))
    epoch = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(
        days=sat.jdsatepoch + sat.jdsatepochF - 2451544.5)
    return [(epoch, fleet)], tuple(fleet), epoch


def test_stale_tles_are_never_propagated():
    archive, names, epoch = _archive_from_repo_tles()
    times = np.array([0.0, 30.0])
    sched, age = build_contact_schedule_historical(archive, names, epoch, times,
                                                   radec_to_unit_eci(0.0, 0.0), max_tle_age_days=7.0)
    assert np.all(~sched.visibility[1])  # 30 days from the only TLE: masked, not guessed
    assert np.all(np.isinf(age[1]))
    assert np.all(age[0] < 7.0)


def test_amplitude_marginal_gp_reduces_to_simple_gp_for_single_amplitude():
    t, y, s = np.array([0.0, 5.0, 10.0]), np.array([3.0, 4.0, 2.0]), np.array([0.5, 0.5, 0.5])
    a = AmplitudeMarginalGP(np.array([4.0]), lengthscale=10.0)
    ref = SimpleGP(lengthscale=10.0, var_f=16.0).log_marginal_likelihood(t, y, s)
    assert a.log_marginal_likelihood(t, y, s) == pytest.approx(ref)


def test_all_strategies_see_identical_inputs(monkeypatch):
    """Branch rule: identical events, orbits, budgets and noise per seed."""
    archive, names, epoch = _archive_from_repo_tles(n=8)
    mjd = (epoch - datetime.datetime(1858, 11, 17, tzinfo=datetime.timezone.utc)).total_seconds() / 86400.0
    monkeypatch.setattr(p3, "MAX_TLE_AGE_DAYS", 1e9)  # synthetic archive has one epoch only
    templates = build_class_templates([_event(f"{c}{i}", c, 58000.0, tau=t)
                                       for c, t in (("sn_ia", 8), ("sn_ii", 60), ("sn_ibc", 20)) for i in range(2)])
    ev = _event("z", "sn_ibc", mjd)
    rec = p3.run_one_event(ev, np.random.SeedSequence(7), archive, names, template_flux_fn_resolver(templates))
    assert rec is not None
    cell_values = {}
    for strat in rec["strategies"].values():
        assert strat["n_obs_used"] <= p3.N_OBS_BUDGET
        for h in strat["history"]:
            key = (h["t"], h["sat"])
            assert cell_values.setdefault(key, (h["y"], h["sigma"])) == (h["y"], h["sigma"])
    rec2 = p3.run_one_event(ev, np.random.SeedSequence(7), archive, names, template_flux_fn_resolver(templates))
    assert rec2 == rec


def test_stretch_grid_decodes_amplitude_and_stretch():
    from research.transients.real_events import StretchAmplitudeGrid
    tpl = build_class_templates([_event(f"{c}{i}", c, 58000.0, tau=t)
                                 for c, t in (("sn_ia", 8), ("sn_ii", 60), ("sn_ibc", 20)) for i in range(2)])
    g = StretchAmplitudeGrid(np.array([1.0, 3.0]), np.array([1.0, 2.0]))
    f = g.resolver(tpl)("sn_ia")
    base = template_flux_fn_resolver(tpl)("sn_ia")
    t = np.array([5.0, 20.0, 40.0])
    # param index = amp_idx * n_stretch + stretch_idx
    assert f(t, np.full(3, 0.0)) == pytest.approx(base(t, 1.0))          # A=1, s=1
    assert f(t, np.full(3, 3.0)) == pytest.approx(base(t / 2.0, 3.0))    # A=3, s=2
    # broadcasting used by the planners: (n_t, 1) x (1, n_params)
    assert f(t[:, None], g.params[None, :]).shape == (3, 4)


def _event_gr(oid, cls, t0_mjd, colour=0.6, **kw):
    ev = _event(oid, cls, t0_mjd, **kw)
    import dataclasses
    return dataclasses.replace(ev, g_t_days=ev.t_days.copy(), g_flux=colour * ev.flux, g_flux_err=colour * ev.flux_err)


def test_g_template_keeps_colour_relative_to_r_peak():
    from research.transients.real_events import build_class_templates_g
    events = [_event_gr(f"{c}{i}", c, 58000.0, colour=col, tau=t)
              for c, t, col in (("sn_ia", 8, 0.9), ("sn_ii", 60, 0.5), ("sn_ibc", 20, 0.3)) for i in range(2)]
    tg, tr = build_class_templates_g(events), build_class_templates(events)
    i = int(np.argmax(tr["sn_ii"]))
    assert tg["sn_ii"][i] == pytest.approx(0.5, abs=0.05)
    assert tg["sn_ibc"][i] == pytest.approx(0.3, abs=0.05)


def test_two_band_resolver_routes_by_time_offset():
    from research.transients.real_events import G_TIME_OFFSET_DAYS, build_class_templates_g, two_band_flux_fn_resolver
    events = [_event_gr(f"{c}{i}", c, 58000.0, colour=0.5, tau=t)
              for c, t in (("sn_ia", 8), ("sn_ii", 60), ("sn_ibc", 20)) for i in range(2)]
    tr, tg = build_class_templates(events), build_class_templates_g(events)
    f = two_band_flux_fn_resolver(tr, tg)("sn_ia")
    r = template_flux_fn_resolver(tr)("sn_ia")
    assert f(np.array([12.0]), 2.0) == pytest.approx(r(np.array([12.0]), 2.0))
    assert f(np.array([12.0 + G_TIME_OFFSET_DAYS]), 2.0) == pytest.approx(0.5 * r(np.array([12.0]), 2.0), rel=0.05)
    # the offset gives zero GP covariance between bands
    assert SimpleGP(lengthscale=20.0).kernel(np.array([0.0]), np.array([G_TIME_OFFSET_DAYS]))[0, 0] == 0.0


def test_two_band_arm_sees_same_r_values_as_r_arm(monkeypatch):
    from research.transients.real_events import build_class_templates_g, two_band_flux_fn_resolver
    archive, names, epoch = _archive_from_repo_tles(n=8)
    mjd = (epoch - datetime.datetime(1858, 11, 17, tzinfo=datetime.timezone.utc)).total_seconds() / 86400.0
    monkeypatch.setattr(p3, "MAX_TLE_AGE_DAYS", 1e9)
    tev = [_event_gr(f"{c}{i}", c, 58000.0, tau=t) for c, t in (("sn_ia", 8), ("sn_ii", 60), ("sn_ibc", 20)) for i in range(2)]
    tr, tg = build_class_templates(tev), build_class_templates_g(tev)
    ev = _event_gr("z", "sn_ii", mjd)
    r_rec = p3.run_one_event(ev, np.random.SeedSequence(3), archive, names, template_flux_fn_resolver(tr), bands="r")
    gr_rec = p3.run_one_event(ev, np.random.SeedSequence(3), archive, names, two_band_flux_fn_resolver(tr, tg), bands="gr")
    # B0 is data-independent, so it picks the same cells in both arms: r values must match exactly
    h_r = r_rec["strategies"]["B0_fixed_cadence"]["history"]
    h_gr = gr_rec["strategies"]["B0_fixed_cadence"]["history"]
    assert [(h["t"], h["sat"], h["y"]) for h in h_r] == [(h["t"], h["sat"], h["y"]) for h in h_gr]
