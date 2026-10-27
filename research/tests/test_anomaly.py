import numpy as np
import pandas as pd
import pytest

from research.anomaly.detectors import (detect_geo_drift_changes, detect_plane_changes,
                                        detect_sk_stopped, detect_steps)
from research.anomaly.elements import R_EARTH, build_series, geo_drift_deg_day, sma_km


def test_sma_iss_and_geo():
    # ISS ~15.5 rev/day -> ~420 km altitude; GEO is 42164 km by definition.
    assert sma_km(15.5) - R_EARTH == pytest.approx(418, abs=5)
    assert sma_km(1.00273790935) == pytest.approx(42164.2, abs=0.5)
    assert geo_drift_deg_day(1.00273790935) == pytest.approx(0.0, abs=1e-9)


def synthetic(n=200, cadence_h=8.0, decay_km_day=0.05, noise_km=0.03, seed=0,
              burns=(), incl_steps=(), base_alt=550.0, norad=99999):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * cadence_h / 24.0
    sma = R_EARTH + base_alt - decay_km_day * t
    for day, dv in burns:
        sma = sma + dv * (t >= day)
    sma = sma + rng.normal(0, noise_km, n)
    inc = 53.0 + rng.normal(0, 0.0005, n)
    for day, di in incl_steps:
        inc = inc + di * (t >= day)
    mm = np.sqrt(398600.4418 / sma ** 3) * 86400 / (2 * np.pi)
    gp = pd.DataFrame({"NORAD_CAT_ID": norad,
                       "EPOCH": pd.Timestamp("2022-01-01", tz="UTC") + pd.to_timedelta(t, "D"),
                       "MEAN_MOTION": mm, "ECCENTRICITY": 1e-4, "INCLINATION": inc,
                       "RA_OF_ASC_NODE": 0.0, "BSTAR": 1e-4})
    return build_series(gp)


def test_build_series_drops_corrupt_and_duplicates():
    s = synthetic(n=20)
    gp = pd.concat([s.iloc[:, :7], s.iloc[:1, :7]])
    gp.loc[gp.index[3], "MEAN_MOTION"] = 40.0
    out = build_series(gp)
    assert len(out) == 19 and out.attrs["dropped"] == 1


def test_no_false_alarms_on_pure_drag():
    for seed in range(5):
        assert detect_steps(synthetic(seed=seed)) == []


def test_recovers_injected_raise_and_lower():
    s = synthetic(burns=[(20.0, 2.0), (45.0, -3.0)])
    ev = detect_steps(s)
    assert [e.kind for e in ev] == ["maneuver_raise", "maneuver_lower"]
    assert ev[0].magnitude == pytest.approx(2.0, abs=0.2)
    assert abs((ev[0].epoch_start - pd.Timestamp("2022-01-21", tz="UTC")).days) <= 1


def test_plane_change():
    ev = detect_plane_changes(synthetic(incl_steps=[(30.0, 0.05)]))
    assert len(ev) == 1 and ev[0].magnitude == pytest.approx(0.05, abs=0.005)


def test_sk_stopped_signature():
    burns = [(d, 1.0) for d in (5, 10, 15, 20)]
    s = synthetic(n=400, burns=burns, decay_km_day=0.1)  # 133 days, last burn at day 20
    ev = detect_sk_stopped(s, detect_steps(s))
    assert len(ev) == 1 and ev[0].kind == "sk_stopped" and ev[0].magnitude > 5


def test_geo_drift_change():
    n = 120
    t = np.arange(n) * 1.0
    drift = np.where(t >= 60, 0.5, 0.0)  # starts drifting 0.5 deg/day west at day 60
    mm = 1.00273790935 + drift / 360.0 + np.random.default_rng(1).normal(0, 1e-6, n)
    gp = pd.DataFrame({"NORAD_CAT_ID": 1, "EPOCH": pd.Timestamp("2022-01-01", tz="UTC") + pd.to_timedelta(t, "D"),
                       "MEAN_MOTION": mm, "ECCENTRICITY": 1e-4, "INCLINATION": 0.1,
                       "RA_OF_ASC_NODE": 0.0, "BSTAR": 0.0})
    ev = detect_geo_drift_changes(build_series(gp))
    assert len(ev) == 1 and ev[0].magnitude == pytest.approx(0.5, abs=0.02)


def test_single_bad_element_set_is_not_a_maneuver():
    s = synthetic(burns=[(40.0, 2.0)])
    s.loc[60, "SMA_KM"] += 5.0  # one corrupt TLE: jumps out and straight back
    ev = detect_steps(s)
    assert [e.kind for e in ev] == ["maneuver_raise"]
    assert ev[0].magnitude == pytest.approx(2.0, abs=0.2)


def test_step_across_tracking_gap_is_not_a_maneuver():
    s = synthetic(n=200, decay_km_day=0.3)
    s = s.drop(s.index[90:120])  # 10-day gap; 3 km of drag accumulates across it
    assert detect_steps(s, min_step=0.5) == []


def test_burn_spread_over_two_sets_counts_by_total():
    s = synthetic(noise_km=0.005, burns=[(40.0, 0.25), (40.34, 0.3)])  # fit lag: 0.55 km over two consecutive sets
    ev = detect_steps(s, min_step=0.5)
    assert len(ev) == 1 and ev[0].magnitude == pytest.approx(0.55, abs=0.1)


def test_burn_inside_publication_gap_is_kept():
    s = synthetic(n=200, burns=[(32.0, 1.5)])
    s = s.drop(s.index[93:103])  # ~3.7-day publication gap around the burn
    ev = detect_steps(s, min_step=0.5)
    assert len(ev) == 1 and ev[0].kind == "maneuver_raise"


def test_daily_kp_and_storm_tagging():
    from research.anomaly.spaceweather import daily_max_kp, storm_days, tag_storm
    from research.anomaly.detectors import Event
    kp = daily_max_kp()
    # Gannon storm, 10-11 May 2024, reached Kp 9-.
    assert kp[pd.Timestamp("2024-05-10", tz="UTC")] >= 8.6
    storms = storm_days(kp)
    ts = pd.Timestamp("2024-05-11 06:00", tz="UTC")
    calm = pd.Timestamp("2024-05-20 06:00", tz="UTC")
    tagged = tag_storm([Event(1, "maneuver_lower", ts, ts, -1.0, 10.0),
                        Event(1, "maneuver_lower", calm, calm, -1.0, 10.0)], storms)
    assert [e.storm for e in tagged] == [True, False]


def test_fragmentation_burst_from_catalog_order():
    from research.anomaly.fragmentation import bursts, catalog_dates
    rows = [("SAT A", "2000-001A", 100, "PAY", "2000-01-01")]
    rows += [(f"FILLER {i}", f"2022-{i:03d}A", 200 + i, "PAY", "2022-05-01") for i in range(3)]
    rows += [("SAT A DEB", f"2000-001{c}", 300 + i, "DEB", "2000-01-01") for i, c in enumerate("BCDEFG")]
    sc = pd.DataFrame(rows, columns=["OBJECT_NAME", "OBJECT_ID", "NORAD_CAT_ID", "OBJECT_TYPE", "LAUNCH_DATE"])
    sc["NORAD_CAT_ID"] = sc.NORAD_CAT_ID.astype(str)
    sc["DECAY_DATE"] = None
    b = bursts(catalog_dates(sc), "2021-01-01", "2024-01-01")
    assert len(b) == 1 and b.pieces[0] == 6 and b.first_cataloged[0] == "2022-05-01"
