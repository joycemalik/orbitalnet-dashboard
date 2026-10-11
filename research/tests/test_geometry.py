import numpy as np
import pytest

from research.orbitsim.geometry import earth_angular_radius_deg, visibility_margin_deg


def test_target_away_from_earth_is_visible():
    """Satellite at +x, looking further away from Earth (+x direction):
    Earth is behind the satellite, so the target must be visible."""
    r_sat = np.array([7000.0, 0.0, 0.0])
    target_dir = np.array([1.0, 0.0, 0.0])
    margin = visibility_margin_deg(r_sat, target_dir)
    expected = 180.0 - earth_angular_radius_deg(7000.0)
    assert margin == pytest.approx(expected, abs=1e-6)
    assert margin >= 0


def test_target_toward_earth_is_occluded():
    """Same satellite, looking straight back toward Earth's center (-x):
    Earth must block that direction exactly (angle 0 < Earth's angular radius)."""
    r_sat = np.array([7000.0, 0.0, 0.0])
    target_dir = np.array([-1.0, 0.0, 0.0])
    margin = visibility_margin_deg(r_sat, target_dir)
    expected = 0.0 - earth_angular_radius_deg(7000.0)
    assert margin == pytest.approx(expected, abs=1e-6)
    assert margin < 0


def test_higher_altitude_sees_a_smaller_earth_disk():
    assert earth_angular_radius_deg(42000.0) < earth_angular_radius_deg(7000.0)


def test_perpendicular_direction_is_visible_for_leo():
    """Looking perpendicular to the nadir vector from a ~600km-altitude LEO
    orbit: Earth's angular radius there (~65 deg) is well under 90 deg, so
    this must be visible."""
    r_sat = np.array([0.0, 7000.0, 0.0])
    target_dir = np.array([1.0, 0.0, 0.0])
    margin = visibility_margin_deg(r_sat, target_dir)
    assert margin > 0


def test_sun_direction_at_equinox_and_solstice():
    from research.orbitsim.geometry import sun_unit_vector_eci
    from research.orbitsim.tle import datetime_to_jd_fr
    import datetime
    jd, fr = datetime_to_jd_fr(datetime.datetime(2024, 3, 20, 3, 6))   # March equinox
    assert sun_unit_vector_eci(jd + fr) == pytest.approx([1.0, 0.0, 0.0], abs=0.01)
    jd, fr = datetime_to_jd_fr(datetime.datetime(2024, 6, 20, 20, 51))  # June solstice: dec = +23.44
    v = sun_unit_vector_eci(jd + fr)
    assert np.degrees(np.arcsin(v[2])) == pytest.approx(23.44, abs=0.05)
