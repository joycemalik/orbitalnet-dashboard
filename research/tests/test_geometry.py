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
